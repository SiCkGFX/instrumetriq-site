#!/usr/bin/env python3
"""
Semantic Artifacts Builder
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
from typing import Dict, List, Optional, Set, Tuple, Any


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
    """Build coverage_table.json with real example metrics (verified fields only)."""
    
    def __init__(self):
        # Only track groups that have verified fields in v7 entries
        self.group_stats = {
            "market_microstructure": {"present": 0, "spread_values": []},
            "spot_prices": {"present": 0, "sample_counts": []},
            "activity_and_silence": {"present": 0, "posts_counts": []},
        }
        self.total_entries = 0
    
    def process_entry(self, entry: dict):
        """Process one usable v7 entry (verified fields only)."""
        self.total_entries += 1
        
        # Market microstructure (VERIFIED: spot_raw.spread_bps)
        spot_raw = entry.get("spot_raw", {})
        if spot_raw.get("spread_bps") is not None:
            self.group_stats["market_microstructure"]["present"] += 1
            self.group_stats["market_microstructure"]["spread_values"].append(
                safe_float(spot_raw.get("spread_bps"))
            )
        
        # Spot prices (VERIFIED: spot_prices array >= 700)
        spot_prices = entry.get("spot_prices", [])
        if len(spot_prices) >= 700:
            self.group_stats["spot_prices"]["present"] += 1
            self.group_stats["spot_prices"]["sample_counts"].append(len(spot_prices))
        
        # Activity (VERIFIED: twitter_sentiment_windows.last_cycle.posts_total)
        tsw = entry.get("twitter_sentiment_windows", {})
        last_cycle = tsw.get("last_cycle") or tsw.get("last_2_cycles")
        if last_cycle:
            posts_total = last_cycle.get("posts_total")
            if posts_total is not None:
                self.group_stats["activity_and_silence"]["present"] += 1
                self.group_stats["activity_and_silence"]["posts_counts"].append(posts_total)
    
    def build(self, is_partial_scan: bool = False, scan_limit: int | None = None) -> dict:
        """Build coverage_table.json structure (verified fields only)."""
        feature_groups = []
        
        # Market microstructure (VERIFIED)
        present_rate = (self.group_stats["market_microstructure"]["present"] / self.total_entries * 100) if self.total_entries > 0 else 0
        median_spread = safe_median(self.group_stats["market_microstructure"]["spread_values"])
        feature_groups.append({
            "group": "market_microstructure",
            "present_rate_pct": round(present_rate, 2),
            "example_metric_label": "Median spread (bps)",
            "example_metric_value": round(median_spread, 2) if median_spread else None,
            "example_metric_note": "Bid-ask spread in basis points"
        })
        
        # Spot prices (VERIFIED)
        present_rate = (self.group_stats["spot_prices"]["present"] / self.total_entries * 100) if self.total_entries > 0 else 0
        median_samples = safe_median(self.group_stats["spot_prices"]["sample_counts"])
        feature_groups.append({
            "group": "spot_prices",
            "present_rate_pct": round(present_rate, 2),
            "example_metric_label": "Median sample count",
            "example_metric_value": int(median_samples) if median_samples else None,
            "example_metric_note": "High-resolution price samples per entry"
        })
        
        # Activity and silence (VERIFIED)
        present_rate = (self.group_stats["activity_and_silence"]["present"] / self.total_entries * 100) if self.total_entries > 0 else 0
        median_posts = safe_median(self.group_stats["activity_and_silence"]["posts_counts"])
        feature_groups.append({
            "group": "activity_and_silence",
            "present_rate_pct": round(present_rate, 2),
            "example_metric_label": "Median posts (last_cycle)",
            "example_metric_value": int(median_posts) if median_posts else 0,
            "example_metric_note": "Post count in most recent cycle"
        })
        
        result = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "total_entries": self.total_entries,
            "feature_groups": feature_groups
        }
        
        if is_partial_scan:
            result["partial_scan"] = True
            result["partial_scan_limit"] = scan_limit
            result["note"] = "partial scan - metrics may be unreliable"
        
        return result


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
        
        # Try multiple timestamp fields
        day = None
        # Try snapshot_ts first (ISO string)
        snapshot_ts = entry.get("snapshot_ts")
        if snapshot_ts:
            try:
                dt = datetime.fromisoformat(snapshot_ts.replace('Z', '+00:00'))
                day = dt.date().isoformat()
            except (ValueError, AttributeError):
                pass
        
        # Try meta.added_ts (ISO string)
        if not day:
            meta = entry.get("meta", {})
            added_ts = meta.get("added_ts")
            if added_ts:
                try:
                    dt = datetime.fromisoformat(added_ts.replace('Z', '+00:00'))
                    day = dt.date().isoformat()
                except (ValueError, AttributeError):
                    pass
        
        # Try meta.admitted_at_unix_ms (Unix milliseconds)
        if not day:
            meta = entry.get("meta", {})
            admitted_at = meta.get("admitted_at_unix_ms")
            if admitted_at:
                try:
                    dt = datetime.fromtimestamp(admitted_at / 1000, tz=timezone.utc)
                    day = dt.date().isoformat()
                except (ValueError, OSError):
                    pass
        
        if day:
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
    
    def build(self, is_partial_scan: bool = False, scan_limit: int | None = None) -> dict:
        """Build dataset_summary.json structure (verified fields only)."""
        days_list = sorted(self.days_seen)
        days_running = len(days_list)
        avg_per_day = self.total_entries / days_running if days_running > 0 else 0
        
        # Sentiment buckets NOT AVAILABLE in v7 (no hybrid_mean_score field)
        sentiment_buckets_result = {
            "bucket_definition": "hybrid_mean_score buckets [-1.0, +1.0]",
            "buckets": [],
            "disclaimer": "Descriptive distribution only. No trading signal or correlation claim.",
            "reason_unavailable": "Sentiment scoring not available in v7 entries - dataset is in pre-scoring phase"
        }
        
        # Build activity regimes (VERIFIED: posts_total exists)
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
        
        result = {
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
            "sentiment_buckets": sentiment_buckets_result,
            "activity_regimes": {
                "definition": "Regimes based on posts_total in last_cycle",
                "bins": activity_regimes_data
            }
        }
        
        if is_partial_scan:
            result["partial_scan"] = True
            result["partial_scan_limit"] = scan_limit
        
        return result


class SymbolTableBuilder:
    """Build symbol_table.json with per-symbol activity and market context (verified fields only)."""
    
    def __init__(self):
        self.symbol_data: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "sessions": 0,
            "posts_last_cycle": [],
            "spread_bps": [],
        })
    
    def process_entry(self, entry: dict):
        """Process one usable v7 entry (verified fields only)."""
        symbol = entry.get("symbol")
        if not symbol:
            return
        
        data = self.symbol_data[symbol]
        data["sessions"] += 1
        
        # Activity metrics (VERIFIED)
        tsw = entry.get("twitter_sentiment_windows", {})
        last_cycle = tsw.get("last_cycle")
        if last_cycle:
            posts_total = last_cycle.get("posts_total", 0)
            data["posts_last_cycle"].append(posts_total)
        
        # Market context (VERIFIED)
        spread_bps = entry.get("spot_raw", {}).get("spread_bps")
        if spread_bps is not None:
            data["spread_bps"].append(spread_bps)
    
    def build(self) -> dict:
        """Build symbol_table.json structure (verified fields only)."""
        symbols = []
        
        for symbol, data in self.symbol_data.items():
            # Activity metrics
            median_posts = safe_median(data["posts_last_cycle"])
            p90_posts = safe_percentile(data["posts_last_cycle"], 90)
            
            # Silence rate (% sessions with 0 posts)
            silent_count = sum(1 for p in data["posts_last_cycle"] if p == 0)
            silence_rate = (silent_count / len(data["posts_last_cycle"]) * 100) if data["posts_last_cycle"] else 0
            
            # Market context
            median_spread = safe_median(data["spread_bps"])
            
            symbols.append({
                "symbol": symbol,
                "sessions": data["sessions"],
                "definition": "One session equals one admission-to-expiry monitoring window (~2h)",
                "activity": {
                    "median_posts_last_cycle": int(median_posts) if median_posts is not None else 0,
                    "p90_posts_last_cycle": int(p90_posts) if p90_posts is not None else 0,
                    "silence_rate_pct": round(silence_rate, 1),
                },
                "market_context": {
                    "median_spread_bps": round(median_spread, 2) if median_spread is not None else None,
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


def write_artifacts(output_dir: Path, coverage_builder, summary_builder, symbol_builder, scan_limit=None):
    """Write all three artifacts to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    is_partial_scan = scan_limit is not None
    
    # Coverage table
    coverage_path = output_dir / "coverage_table.json"
    coverage_data = coverage_builder.build(is_partial_scan=is_partial_scan, scan_limit=scan_limit)
    with open(coverage_path, "w", encoding="utf-8") as f:
        json.dump(coverage_data, f, indent=2, ensure_ascii=True)
    print(f"{OK_MARK} Wrote: {coverage_path}")
    
    # Dataset summary
    summary_path = output_dir / "dataset_summary.json"
    summary_data = summary_builder.build(is_partial_scan=is_partial_scan, scan_limit=scan_limit)
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
    
    parser = argparse.ArgumentParser(description="Build semantic artifacts for dataset analysis")
    parser.add_argument("--archive", type=str, help="Archive base path (or use ARCHIVE_BASE_PATH env)")
    parser.add_argument("--output", type=str, help="Output directory (or use OUTPUT_DIR env)")
    parser.add_argument("--scan-limit", type=int, help="Limit entries scanned (for testing)")
    args = parser.parse_args()
    
    # Determine paths
    archive_base = args.archive or os.getenv("ARCHIVE_BASE_PATH")
    output_dir = args.output or os.getenv("OUTPUT_DIR")
    scan_limit_str = args.scan_limit or os.getenv("SEMANTIC_SCAN_LIMIT")
    
    scan_limit = None
    if scan_limit_str:
        try:
            scan_limit = int(scan_limit_str)
        except (ValueError, TypeError):
            print(f"{WARN_MARK} Invalid scan limit: {scan_limit_str}, ignoring")
            scan_limit = None
    
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
    write_artifacts(output_path, coverage_builder, summary_builder, symbol_builder, scan_limit)
    
    print(f"\n{OK_MARK} Semantic artifacts generation complete")
    return 0


if __name__ == "__main__":
    exit(main())
