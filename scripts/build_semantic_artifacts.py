#!/usr/bin/env python3
"""
Semantic Artifacts Builder (Phase 4E-1)
Generates clean, well-defined, website-ready data artifacts:
- coverage_table.json (with real example metrics)
- dataset_summary.json (sentiment buckets, volume-based activity regimes)
- symbol_table.json (per-symbol sentiment and market context)
"""

import gzip
import json
import math
import os
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# ASCII-only status marks
OK_MARK = "[OK]"
WARN_MARK = "[WARN]"
ERROR_MARK = "[ERROR]"
INFO_MARK = "[INFO]"


def is_usable_v7_entry(entry: dict) -> Tuple[bool, str]:
    """
    Check if entry passes the usable v7 gate.
    
    Requirements:
    - schema_version == 7
    - spot_prices list with >= 700 samples
    - spot_raw has required keys: mid, bid, ask, spread_bps
    - twitter_sentiment_windows has at least one cycle (last_cycle OR last_2_cycles)
    
    Returns:
        (is_usable, reason) tuple
    """
    # Check schema version
    meta = entry.get("meta", {})
    schema_version = meta.get("schema_version")
    if schema_version != 7:
        return (False, f"schema_version={schema_version}, need 7")
    
    # Check spot_prices count
    spot_prices = entry.get("spot_prices", [])
    if len(spot_prices) < 700:
        return (False, f"spot_prices={len(spot_prices)}, need >=700")
    
    # Check spot_raw
    spot_raw = entry.get("spot_raw", {})
    required_spot_keys = {"mid", "bid", "ask", "spread_bps"}
    if not required_spot_keys.issubset(spot_raw.keys()):
        missing = required_spot_keys - spot_raw.keys()
        return (False, f"spot_raw missing {missing}")
    
    # Check twitter_sentiment_windows has at least one cycle
    tsw = entry.get("twitter_sentiment_windows", {})
    has_last_cycle = tsw.get("last_cycle") is not None
    has_last_2_cycles = tsw.get("last_2_cycles") is not None
    if not (has_last_cycle or has_last_2_cycles):
        return (False, "no twitter_sentiment_windows.last_cycle or last_2_cycles")
    
    return (True, "OK")


def safe_float(value, default=None):
    """Safely convert to float, return default if None or invalid."""
    if value is None:
        return default
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (ValueError, TypeError):
        return default


def safe_median(values: List[float]) -> Optional[float]:
    """Compute median, return None if empty or all None."""
    clean = [v for v in values if v is not None and not math.isnan(v) and not math.isinf(v)]
    if not clean:
        return None
    return statistics.median(clean)


def safe_percentile(values: List[float], p: float) -> Optional[float]:
    """Compute percentile p (0-100), return None if empty."""
    clean = [v for v in values if v is not None and not math.isnan(v) and not math.isinf(v)]
    if not clean:
        return None
    clean_sorted = sorted(clean)
    k = (len(clean_sorted) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return clean_sorted[int(k)]
    d0 = clean_sorted[int(f)] * (c - k)
    d1 = clean_sorted[int(c)] * (k - f)
    return d0 + d1


class CoverageTableBuilder:
    """Build coverage_table.json with real example metrics."""
    
    def __init__(self):
        self.group_stats = {
            "market_microstructure": {"present": 0, "spread_values": []},
            "liquidity": {"present": 0, "liq_qv_usd_values": []},
            "order_book_depth": {"present": 0, "depth_values": []},
            "spot_prices": {"present": 0, "sample_counts": []},
            "lexicon_sentiment": {"present": 0, "scores": []},
            "ai_sentiment": {"present": 0, "scores": []},
            "activity_and_silence": {"present": 0, "posts_counts": []},
            "platform_engagement": {"present": 0, "engagement_values": []},
            "author_stats": {"present": 0, "author_counts": []},
        }
        self.total_entries = 0
    
    def process_entry(self, entry: dict):
        """Process one usable v7 entry."""
        self.total_entries += 1
        
        # Market microstructure
        spot_raw = entry.get("spot_raw", {})
        if spot_raw.get("spread_bps") is not None:
            self.group_stats["market_microstructure"]["present"] += 1
            self.group_stats["market_microstructure"]["spread_values"].append(
                safe_float(spot_raw.get("spread_bps"))
            )
        
        # Liquidity
        liq = entry.get("liquidity", {})
        if liq.get("liq_qv_usd") is not None:
            self.group_stats["liquidity"]["present"] += 1
            self.group_stats["liquidity"]["liq_qv_usd_values"].append(
                safe_float(liq.get("liq_qv_usd"))
            )
        
        # Order book depth
        if liq.get("depth_snapshot_usd") is not None:
            self.group_stats["order_book_depth"]["present"] += 1
            depth = liq.get("depth_snapshot_usd", {})
            total_depth = safe_float(depth.get("bid", 0), 0) + safe_float(depth.get("ask", 0), 0)
            self.group_stats["order_book_depth"]["depth_values"].append(total_depth)
        
        # Spot prices
        spot_prices = entry.get("spot_prices", [])
        if len(spot_prices) >= 700:
            self.group_stats["spot_prices"]["present"] += 1
            self.group_stats["spot_prices"]["sample_counts"].append(len(spot_prices))
        
        # Sentiment
        tsw = entry.get("twitter_sentiment_windows", {})
        last_cycle = tsw.get("last_cycle") or tsw.get("last_2_cycles")
        if last_cycle:
            lexicon = last_cycle.get("lexicon_sentiment")
            if lexicon and lexicon.get("mean_score") is not None:
                self.group_stats["lexicon_sentiment"]["present"] += 1
                self.group_stats["lexicon_sentiment"]["scores"].append(
                    safe_float(lexicon.get("mean_score"))
                )
            
            ai = last_cycle.get("ai_sentiment")
            if ai and ai.get("mean_score") is not None:
                self.group_stats["ai_sentiment"]["present"] += 1
                self.group_stats["ai_sentiment"]["scores"].append(
                    safe_float(ai.get("mean_score"))
                )
            
            # Activity
            posts_total = last_cycle.get("posts_total", 0)
            if posts_total is not None:
                self.group_stats["activity_and_silence"]["present"] += 1
                self.group_stats["activity_and_silence"]["posts_counts"].append(posts_total)
            
            # Platform engagement (likes, retweets, etc.)
            engagement = last_cycle.get("engagement", {})
            if engagement:
                self.group_stats["platform_engagement"]["present"] += 1
                total_likes = safe_float(engagement.get("total_likes", 0), 0)
                self.group_stats["platform_engagement"]["engagement_values"].append(total_likes)
            
            # Author stats
            authors = last_cycle.get("distinct_authors", 0)
            if authors:
                self.group_stats["author_stats"]["present"] += 1
                self.group_stats["author_stats"]["author_counts"].append(authors)
    
    def build(self) -> dict:
        """Build coverage_table.json structure."""
        feature_groups = []
        
        # Market microstructure
        present_rate = (self.group_stats["market_microstructure"]["present"] / self.total_entries * 100) if self.total_entries > 0 else 0
        median_spread = safe_median(self.group_stats["market_microstructure"]["spread_values"])
        feature_groups.append({
            "group": "market_microstructure",
            "present_rate_pct": round(present_rate, 2),
            "example_metric_label": "Median spread (bps)",
            "example_metric_value": round(median_spread, 2) if median_spread else None,
            "example_metric_note": "Computed across all usable v7 entries"
        })
        
        # Liquidity
        present_rate = (self.group_stats["liquidity"]["present"] / self.total_entries * 100) if self.total_entries > 0 else 0
        median_liq = safe_median(self.group_stats["liquidity"]["liq_qv_usd_values"])
        if present_rate == 0 or median_liq is None:
            feature_groups.append({
                "group": "liquidity",
                "present_rate_pct": round(present_rate, 2),
                "example_metric_label": "N/A",
                "example_metric_value": "Not present in v7 entries",
                "example_metric_note": "Liquidity data not collected for this dataset"
            })
        else:
            feature_groups.append({
                "group": "liquidity",
                "present_rate_pct": round(present_rate, 2),
                "example_metric_label": "Median liq_qv_usd",
                "example_metric_value": round(median_liq),
                "example_metric_note": "Quote volume in USD at admission"
            })
        
        # Order book depth
        present_rate = (self.group_stats["order_book_depth"]["present"] / self.total_entries * 100) if self.total_entries > 0 else 0
        median_depth = safe_median(self.group_stats["order_book_depth"]["depth_values"])
        if present_rate == 0 or median_depth is None:
            feature_groups.append({
                "group": "order_book_depth",
                "present_rate_pct": round(present_rate, 2),
                "example_metric_label": "N/A",
                "example_metric_value": "Not present in v7 entries",
                "example_metric_note": "Order book depth not collected for this dataset"
            })
        else:
            feature_groups.append({
                "group": "order_book_depth",
                "present_rate_pct": round(present_rate, 2),
                "example_metric_label": "Median total depth (USD)",
                "example_metric_value": round(median_depth),
                "example_metric_note": "Bid + ask depth snapshot"
            })
        
        # Spot prices
        present_rate = (self.group_stats["spot_prices"]["present"] / self.total_entries * 100) if self.total_entries > 0 else 0
        median_samples = safe_median(self.group_stats["spot_prices"]["sample_counts"])
        feature_groups.append({
            "group": "spot_prices",
            "present_rate_pct": round(present_rate, 2),
            "example_metric_label": "Median sample count",
            "example_metric_value": int(median_samples) if median_samples else None,
            "example_metric_note": "High-resolution price samples per entry"
        })
        
        # Lexicon sentiment
        present_rate = (self.group_stats["lexicon_sentiment"]["present"] / self.total_entries * 100) if self.total_entries > 0 else 0
        median_score = safe_median(self.group_stats["lexicon_sentiment"]["scores"])
        if present_rate == 0 or median_score is None:
            feature_groups.append({
                "group": "lexicon_sentiment",
                "present_rate_pct": round(present_rate, 2),
                "example_metric_label": "N/A",
                "example_metric_value": "Not present in v7 entries",
                "example_metric_note": "Lexicon sentiment not available for this dataset"
            })
        else:
            feature_groups.append({
                "group": "lexicon_sentiment",
                "present_rate_pct": round(present_rate, 2),
                "example_metric_label": "Median lexicon mean score",
                "example_metric_value": round(median_score, 3),
                "example_metric_note": "Lexicon-based sentiment [-1, +1]"
            })
        
        # AI sentiment
        present_rate = (self.group_stats["ai_sentiment"]["present"] / self.total_entries * 100) if self.total_entries > 0 else 0
        median_score = safe_median(self.group_stats["ai_sentiment"]["scores"])
        if present_rate == 0 or median_score is None:
            feature_groups.append({
                "group": "ai_sentiment",
                "present_rate_pct": round(present_rate, 2),
                "example_metric_label": "N/A",
                "example_metric_value": "Not present in v7 entries",
                "example_metric_note": "AI sentiment not available for this dataset"
            })
        else:
            feature_groups.append({
                "group": "ai_sentiment",
                "present_rate_pct": round(present_rate, 2),
                "example_metric_label": "Median AI mean score",
                "example_metric_value": round(median_score, 3),
                "example_metric_note": "AI-based sentiment [-1, +1]"
            })
        
        # Activity and silence
        present_rate = (self.group_stats["activity_and_silence"]["present"] / self.total_entries * 100) if self.total_entries > 0 else 0
        median_posts = safe_median(self.group_stats["activity_and_silence"]["posts_counts"])
        feature_groups.append({
            "group": "activity_and_silence",
            "present_rate_pct": round(present_rate, 2),
            "example_metric_label": "Median posts (last_cycle)",
            "example_metric_value": int(median_posts) if median_posts else 0,
            "example_metric_note": "Post count in most recent cycle"
        })
        
        # Platform engagement
        present_rate = (self.group_stats["platform_engagement"]["present"] / self.total_entries * 100) if self.total_entries > 0 else 0
        if present_rate == 0:
            feature_groups.append({
                "group": "platform_engagement",
                "present_rate_pct": 0.0,
                "example_metric_label": "N/A",
                "example_metric_value": "Not collected in v7 schema",
                "example_metric_note": "Engagement metrics deprecated in current pipeline"
            })
        else:
            median_likes = safe_median(self.group_stats["platform_engagement"]["engagement_values"])
            feature_groups.append({
                "group": "platform_engagement",
                "present_rate_pct": round(present_rate, 2),
                "example_metric_label": "Median total likes",
                "example_metric_value": int(median_likes) if median_likes else 0,
                "example_metric_note": "Total likes across posts in cycle"
            })
        
        # Author stats
        present_rate = (self.group_stats["author_stats"]["present"] / self.total_entries * 100) if self.total_entries > 0 else 0
        if present_rate == 0:
            feature_groups.append({
                "group": "author_stats",
                "present_rate_pct": 0.0,
                "example_metric_label": "N/A",
                "example_metric_value": "Not collected in v7 schema",
                "example_metric_note": "Author metrics deprecated in current pipeline"
            })
        else:
            median_authors = safe_median(self.group_stats["author_stats"]["author_counts"])
            feature_groups.append({
                "group": "author_stats",
                "present_rate_pct": round(present_rate, 2),
                "example_metric_label": "Median distinct authors",
                "example_metric_value": int(median_authors) if median_authors else 0,
                "example_metric_note": "Unique authors per cycle"
            })
        
        return {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "total_entries": self.total_entries,
            "feature_groups": feature_groups
        }


class DatasetSummaryBuilder:
    """Build dataset_summary.json with sentiment buckets and volume-based activity regimes."""
    
    def __init__(self):
        self.total_entries = 0
        self.distinct_symbols = set()
        self.days_seen = set()
        self.cycles_completed = 0
        
        # Posts scored tracking
        self.posts_scored_total = 0
        self.posts_scored_entries = 0
        
        # Sentiment buckets (10 bins from -1.0 to +1.0)
        self.sentiment_buckets = {i: {"entries": [], "forward_returns": []} for i in range(10)}
        
        # Activity regimes by post volume
        self.activity_bins = {
            "0": {"entries": [], "abs_returns": [], "spread_bps": [], "liq_qv_usd": []},
            "1-2": {"entries": [], "abs_returns": [], "spread_bps": [], "liq_qv_usd": []},
            "3-9": {"entries": [], "abs_returns": [], "spread_bps": [], "liq_qv_usd": []},
            "10-24": {"entries": [], "abs_returns": [], "spread_bps": [], "liq_qv_usd": []},
            "25-49": {"entries": [], "abs_returns": [], "spread_bps": [], "liq_qv_usd": []},
            "50+": {"entries": [], "abs_returns": [], "spread_bps": [], "liq_qv_usd": []},
        }
    
    def process_entry(self, entry: dict):
        """Process one usable v7 entry."""
        self.total_entries += 1
        
        # Track symbols and days
        symbol = entry.get("symbol")
        if symbol:
            self.distinct_symbols.add(symbol)
        
        meta = entry.get("meta", {})
        admitted_at = meta.get("admitted_at_unix_ms")
        if admitted_at:
            day = datetime.fromtimestamp(admitted_at / 1000, tz=timezone.utc).date().isoformat()
            self.days_seen.add(day)
        
        # Posts scored
        tsw = entry.get("twitter_sentiment_windows", {})
        last_cycle = tsw.get("last_cycle")
        last_2_cycles = tsw.get("last_2_cycles")
        
        posts_counted = 0
        if last_cycle and last_cycle.get("posts_total"):
            posts_counted += last_cycle["posts_total"]
            self.posts_scored_entries += 1
        if last_2_cycles and last_2_cycles.get("posts_total"):
            posts_counted += last_2_cycles["posts_total"]
        
        self.posts_scored_total += posts_counted
        
        # Sentiment buckets
        hybrid_mean = entry.get("hybrid_mean_score")
        forward_return = entry.get("forward_return_over_window")
        if hybrid_mean is not None and forward_return is not None:
            # Map to bucket [-1.0, +1.0] -> 10 bins
            bucket_idx = min(9, max(0, int((hybrid_mean + 1.0) / 0.2)))
            self.sentiment_buckets[bucket_idx]["entries"].append(entry)
            self.sentiment_buckets[bucket_idx]["forward_returns"].append(forward_return)
        
        # Activity regimes by post volume
        posts_last_cycle = last_cycle.get("posts_total", 0) if last_cycle else 0
        abs_return = entry.get("abs_return_over_window")
        spread_bps = entry.get("spot_raw", {}).get("spread_bps")
        liq_qv_usd = entry.get("liquidity", {}).get("liq_qv_usd")
        
        bin_key = None
        if posts_last_cycle == 0:
            bin_key = "0"
        elif posts_last_cycle <= 2:
            bin_key = "1-2"
        elif posts_last_cycle <= 9:
            bin_key = "3-9"
        elif posts_last_cycle <= 24:
            bin_key = "10-24"
        elif posts_last_cycle <= 49:
            bin_key = "25-49"
        else:
            bin_key = "50+"
        
        if bin_key:
            self.activity_bins[bin_key]["entries"].append(entry)
            if abs_return is not None:
                self.activity_bins[bin_key]["abs_returns"].append(abs_return)
            if spread_bps is not None:
                self.activity_bins[bin_key]["spread_bps"].append(spread_bps)
            if liq_qv_usd is not None:
                self.activity_bins[bin_key]["liq_qv_usd"].append(liq_qv_usd)
    
    def build(self) -> dict:
        """Build dataset_summary.json structure."""
        days_list = sorted(self.days_seen)
        days_running = len(days_list)
        avg_per_day = self.total_entries / days_running if days_running > 0 else 0
        
        # Build sentiment buckets
        sentiment_buckets_data = []
        for i in range(10):
            bucket_data = self.sentiment_buckets[i]
            n = len(bucket_data["entries"])
            if n == 0:
                continue
            
            returns = bucket_data["forward_returns"]
            median_return = safe_median(returns)
            p25 = safe_percentile(returns, 25)
            p75 = safe_percentile(returns, 75)
            pct_positive = sum(1 for r in returns if r > 0) / len(returns) * 100 if returns else 0
            
            range_min = -1.0 + i * 0.2
            range_max = -1.0 + (i + 1) * 0.2
            
            sentiment_buckets_data.append({
                "range": f"[{range_min:.1f}, {range_max:.1f})",
                "n": n,
                "median_forward_return_bucket": f"{median_return:+.2f}" if median_return is not None else "N/A",
                "iqr_bucket": f"{p25:+.2f} to {p75:+.2f}" if p25 is not None and p75 is not None else "N/A",
                "pct_positive": round(pct_positive, 1)
            })
        
        # Build activity regimes
        activity_regimes_data = []
        for bin_label in ["0", "1-2", "3-9", "10-24", "25-49", "50+"]:
            bin_data = self.activity_bins[bin_label]
            n = len(bin_data["entries"])
            if n == 0:
                continue
            
            # Parse min/max from label
            if bin_label == "0":
                min_posts, max_posts = 0, 0
            elif bin_label == "50+":
                min_posts, max_posts = 50, 999999
            else:
                parts = bin_label.split("-")
                min_posts = int(parts[0])
                max_posts = int(parts[1])
            
            median_abs_return = safe_median(bin_data["abs_returns"])
            p90_abs_return = safe_percentile(bin_data["abs_returns"], 90)
            median_spread = safe_median(bin_data["spread_bps"])
            p90_spread = safe_percentile(bin_data["spread_bps"], 90)
            median_liq = safe_median(bin_data["liq_qv_usd"])
            p90_liq = safe_percentile(bin_data["liq_qv_usd"], 90)
            
            activity_regimes_data.append({
                "label": bin_label,
                "min": min_posts,
                "max": max_posts,
                "n_entries": n,
                "metrics": {
                    "median_abs_return": round(median_abs_return, 2) if median_abs_return is not None else None,
                    "p90_abs_return": round(p90_abs_return, 2) if p90_abs_return is not None else None,
                    "median_spread_bps": round(median_spread, 2) if median_spread is not None else None,
                    "p90_spread_bps": round(p90_spread, 2) if p90_spread is not None else None,
                    "median_liq_qv_usd": round(median_liq) if median_liq is not None else None,
                    "p90_liq_qv_usd": round(p90_liq) if p90_liq is not None else None,
                }
            })
        
        return {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "scale": {
                "days_running": days_running,
                "total_usable_entries": self.total_entries,
                "avg_entries_per_day": round(avg_per_day),
                "distinct_symbols": len(self.distinct_symbols),
                "cycles_completed": self.cycles_completed
            },
            "posts_scored": {
                "total_posts": self.posts_scored_total,
                "from_entries": self.posts_scored_entries,
                "window_definition": "posts counted from twitter_sentiment_windows.last_cycle and last_2_cycles"
            },
            "sentiment_buckets": {
                "bucket_definition": "hybrid_mean_score buckets [-1.0, +1.0]",
                "buckets": sentiment_buckets_data,
                "disclaimer": "Descriptive distribution only. No trading signal or correlation claim."
            },
            "activity_regimes": {
                "definition": "Regimes based on posts_total in last_cycle",
                "bins": activity_regimes_data
            }
        }


class SymbolTableBuilder:
    """Build symbol_table.json with per-symbol sentiment and market context."""
    
    def __init__(self):
        self.symbol_data = defaultdict(lambda: {
            "sessions": 0,
            "first_seen": None,
            "last_seen": None,
            "posts_last_cycle": [],
            "hybrid_scores": [],
            "spread_bps": [],
            "liq_qv_usd": [],
        })
    
    def process_entry(self, entry: dict):
        """Process one usable v7 entry."""
        symbol = entry.get("symbol")
        if not symbol:
            return
        
        data = self.symbol_data[symbol]
        data["sessions"] += 1
        
        # Track first/last seen
        meta = entry.get("meta", {})
        admitted_at = meta.get("admitted_at_unix_ms")
        if admitted_at:
            day = datetime.fromtimestamp(admitted_at / 1000, tz=timezone.utc).date().isoformat()
            if data["first_seen"] is None or day < data["first_seen"]:
                data["first_seen"] = day
            if data["last_seen"] is None or day > data["last_seen"]:
                data["last_seen"] = day
        
        # Sentiment metrics
        tsw = entry.get("twitter_sentiment_windows", {})
        last_cycle = tsw.get("last_cycle")
        if last_cycle:
            posts_total = last_cycle.get("posts_total", 0)
            data["posts_last_cycle"].append(posts_total)
        
        hybrid_score = entry.get("hybrid_mean_score")
        if hybrid_score is not None:
            data["hybrid_scores"].append(hybrid_score)
        
        # Market context
        spread_bps = entry.get("spot_raw", {}).get("spread_bps")
        if spread_bps is not None:
            data["spread_bps"].append(spread_bps)
        
        liq_qv_usd = entry.get("liquidity", {}).get("liq_qv_usd")
        if liq_qv_usd is not None:
            data["liq_qv_usd"].append(liq_qv_usd)
    
    def build(self) -> dict:
        """Build symbol_table.json structure."""
        symbols = []
        
        for symbol, data in self.symbol_data.items():
            # Calculate metrics
            median_posts = safe_median(data["posts_last_cycle"])
            p90_posts = safe_percentile(data["posts_last_cycle"], 90)
            
            # % silent sessions (0 posts)
            silent_count = sum(1 for p in data["posts_last_cycle"] if p == 0)
            pct_silent = (silent_count / len(data["posts_last_cycle"]) * 100) if data["posts_last_cycle"] else 0
            
            median_hybrid = safe_median(data["hybrid_scores"])
            p10_hybrid = safe_percentile(data["hybrid_scores"], 10)
            p90_hybrid = safe_percentile(data["hybrid_scores"], 90)
            
            median_spread = safe_median(data["spread_bps"])
            median_liq = safe_median(data["liq_qv_usd"])
            
            symbols.append({
                "symbol": symbol,
                "sessions": data["sessions"],
                "definition": "One session equals one admission-to-expiry monitoring window (~2h)",
                "first_seen": data["first_seen"],
                "last_seen": data["last_seen"],
                "sentiment": {
                    "median_posts_last_cycle": int(median_posts) if median_posts is not None else 0,
                    "p90_posts_last_cycle": int(p90_posts) if p90_posts is not None else 0,
                    "pct_silent_sessions": round(pct_silent, 1),
                    "median_hybrid_mean_score": round(median_hybrid, 2) if median_hybrid is not None else None,
                    "p10_hybrid_mean_score": round(p10_hybrid, 2) if p10_hybrid is not None else None,
                    "p90_hybrid_mean_score": round(p90_hybrid, 2) if p90_hybrid is not None else None,
                },
                "market_context": {
                    "median_spread_bps": round(median_spread, 2) if median_spread is not None else None,
                    "median_liq_qv_usd": round(median_liq) if median_liq is not None else None,
                }
            })
        
        return {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "total_symbols": len(symbols),
            "symbols": symbols
        }


def scan_archive(archive_path: Path, scan_limit: Optional[int] = None):
    """Scan archive and build all three semantic artifacts."""
    print(f"\n{INFO_MARK} Scanning archive: {archive_path}")
    if scan_limit:
        print(f"{INFO_MARK} Scan limit: {scan_limit}")
    
    coverage_builder = CoverageTableBuilder()
    summary_builder = DatasetSummaryBuilder()
    symbol_builder = SymbolTableBuilder()
    
    processed = 0
    usable = 0
    skipped = 0
    
    # Scan all day directories
    day_dirs = sorted([d for d in archive_path.iterdir() if d.is_dir() and d.name.startswith("20")])
    
    for day_dir in day_dirs:
        for jsonl_gz in day_dir.glob("*.jsonl.gz"):
            with gzip.open(jsonl_gz, "rt", encoding="utf-8") as f:
                for line in f:
                    if scan_limit and processed >= scan_limit:
                        break
                    
                    processed += 1
                    if processed % 1000 == 0:
                        print(f"{INFO_MARK} Processed: {processed}, usable: {usable}")
                    
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        skipped += 1
                        continue
                    
                    is_usable, reason = is_usable_v7_entry(entry)
                    if not is_usable:
                        skipped += 1
                        continue
                    
                    usable += 1
                    coverage_builder.process_entry(entry)
                    summary_builder.process_entry(entry)
                    symbol_builder.process_entry(entry)
                
                if scan_limit and processed >= scan_limit:
                    break
        
        if scan_limit and processed >= scan_limit:
            break
    
    print(f"\n{OK_MARK} Scan complete:")
    print(f"  Processed: {processed}")
    print(f"  Usable v7: {usable}")
    print(f"  Skipped: {skipped}")
    
    return coverage_builder, summary_builder, symbol_builder


def write_artifacts(output_dir: Path, coverage_builder, summary_builder, symbol_builder):
    """Write all three artifacts to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Coverage table
    coverage_path = output_dir / "coverage_table.json"
    coverage_data = coverage_builder.build()
    with open(coverage_path, "w", encoding="utf-8") as f:
        json.dump(coverage_data, f, indent=2, ensure_ascii=True)
    print(f"{OK_MARK} Wrote: {coverage_path}")
    
    # Dataset summary
    summary_path = output_dir / "dataset_summary.json"
    summary_data = summary_builder.build()
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=True)
    print(f"{OK_MARK} Wrote: {summary_path}")
    
    # Symbol table
    symbol_path = output_dir / "symbol_table.json"
    symbol_data = symbol_builder.build()
    with open(symbol_path, "w", encoding="utf-8") as f:
        json.dump(symbol_data, f, indent=2, ensure_ascii=True)
    print(f"{OK_MARK} Wrote: {symbol_path}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Build semantic artifacts (Phase 4E-1)")
    parser.add_argument("--archive", type=str, help="Archive base path (or use ARCHIVE_BASE_PATH env)")
    parser.add_argument("--output", type=str, help="Output directory (or use OUTPUT_DIR env)")
    parser.add_argument("--scan-limit", type=int, help="Limit entries scanned (for testing)")
    args = parser.parse_args()
    
    # Determine paths
    archive_base = args.archive or os.getenv("ARCHIVE_BASE_PATH")
    output_dir = args.output or os.getenv("OUTPUT_DIR")
    scan_limit = args.scan_limit or os.getenv("SEMANTIC_SCAN_LIMIT")
    
    if scan_limit:
        scan_limit = int(scan_limit)
    
    if not archive_base:
        print(f"{ERROR_MARK} ARCHIVE_BASE_PATH not set")
        return 1
    
    if not output_dir:
        print(f"{ERROR_MARK} OUTPUT_DIR not set")
        return 1
    
    archive_path = Path(archive_base)
    output_path = Path(output_dir)
    
    if not archive_path.exists():
        print(f"{ERROR_MARK} Archive not found: {archive_path}")
        return 1
    
    print(f"{OK_MARK} Starting semantic artifact generation")
    print(f"{INFO_MARK} Archive: {archive_path}")
    print(f"{INFO_MARK} Output: {output_path}")
    
    # Scan and build
    coverage_builder, summary_builder, symbol_builder = scan_archive(archive_path, scan_limit)
    
    # Write artifacts
    write_artifacts(output_path, coverage_builder, summary_builder, symbol_builder)
    
    print(f"\n{OK_MARK} Semantic artifacts generation complete")
    return 0


if __name__ == "__main__":
    exit(main())
