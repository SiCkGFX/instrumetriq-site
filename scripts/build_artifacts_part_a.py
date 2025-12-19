#!/usr/bin/env python3
"""
Artifact builder for instrumetriq-site (Part A).
Generates coverage, scale, and preview artifacts from CryptoBot v7 archive.

Outputs:
- public/data/artifacts/coverage_v7.json
- public/data/artifacts/scale_v7.json
- public/data/artifacts/preview_row_v7.json
"""

import gzip
import json
import math
import os
import random
import statistics
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
    if not isinstance(spot_prices, list):
        return (False, "spot_prices not a list")
    if len(spot_prices) < 700:
        return (False, f"spot_prices={len(spot_prices)}, need >= 700")
    
    # Check spot_raw required keys
    spot_raw = entry.get("spot_raw", {})
    required_spot_keys = ["mid", "bid", "ask", "spread_bps"]
    missing_keys = [k for k in required_spot_keys if k not in spot_raw]
    if missing_keys:
        return (False, f"spot_raw missing: {missing_keys}")
    
    # Check twitter_sentiment_windows has at least one cycle
    tsw = entry.get("twitter_sentiment_windows", {})
    has_last_cycle = "last_cycle" in tsw and isinstance(tsw["last_cycle"], dict)
    has_last_2_cycles = "last_2_cycles" in tsw and isinstance(tsw["last_2_cycles"], dict)
    
    if not (has_last_cycle or has_last_2_cycles):
        return (False, "twitter_sentiment_windows missing cycles")
    
    return (True, "passed")


def is_valid_number(value) -> bool:
    """Check if value is a valid finite number."""
    if value is None:
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def compute_forward_return_bucket(spot_prices: list) -> str:
    """
    Compute forward 1h return bucket from spot_prices.
    
    Buckets:
    - "very_negative": [-inf, -2%)
    - "negative": [-2%, -0.5%)
    - "neutral": [-0.5%, 0.5%)
    - "positive": [0.5%, 2%)
    - "very_positive": [2%, inf)
    - "unknown": insufficient data
    
    Args:
        spot_prices: List of price sample dicts with 'ts' and 'mid' fields
    
    Returns:
        Bucket label string
    """
    if not isinstance(spot_prices, list) or len(spot_prices) < 2:
        return "unknown"
    
    try:
        # Extract first sample
        first_sample = spot_prices[0]
        if not isinstance(first_sample, dict):
            return "unknown"
        
        first_ts = first_sample.get("ts")
        first_mid = first_sample.get("mid")
        
        if not is_valid_number(first_ts) or not is_valid_number(first_mid):
            return "unknown"
        
        first_ts = float(first_ts)
        first_mid = float(first_mid)
        
        if first_mid <= 0:
            return "unknown"
        
        # Find sample closest to +1h (3600 seconds)
        target_ts = first_ts + 3600
        closest_sample = None
        min_diff = float('inf')
        
        for sample in spot_prices[1:]:
            if not isinstance(sample, dict):
                continue
            
            sample_ts = sample.get("ts")
            if not is_valid_number(sample_ts):
                continue
            
            sample_ts = float(sample_ts)
            diff = abs(sample_ts - target_ts)
            
            if diff < min_diff:
                min_diff = diff
                closest_sample = sample
        
        if closest_sample is None:
            return "unknown"
        
        last_mid = closest_sample.get("mid")
        if not is_valid_number(last_mid):
            return "unknown"
        
        last_mid = float(last_mid)
        if last_mid <= 0:
            return "unknown"
        
        # Compute return
        ret = (last_mid - first_mid) / first_mid
        
        # Bucket
        if ret < -0.02:
            return "very_negative"
        elif ret < -0.005:
            return "negative"
        elif ret < 0.005:
            return "neutral"
        elif ret < 0.02:
            return "positive"
        else:
            return "very_positive"
    
    except (TypeError, ValueError, ZeroDivisionError):
        return "unknown"


class CoverageTracker:
    """Track feature coverage across v7 entries."""
    
    def __init__(self):
        self.v7_seen = 0
        self.v7_usable = 0
        
        # Feature group trackers
        self.microstructure_present = 0
        self.liquidity_present = 0
        self.order_book_present = 0
        self.time_series_present = 0
        self.sentiment_lexicon_present = 0
        self.sentiment_ai_present = 0
        self.activity_silence_present = 0
        self.engagement_present = 0
        self.author_stats_present = 0
        
        # Example value collectors (bounded)
        self.spread_bps_samples = []
        self.liq_qv_usd_samples = []
        self.sample_count_samples = []
        self.posts_total_samples = []
        self.mean_score_samples = []
        
        self.max_samples = 10000
    
    def add_entry(self, entry: dict, is_usable: bool):
        """Process one v7 entry."""
        self.v7_seen += 1
        if is_usable:
            self.v7_usable += 1
        
        # Market microstructure
        spot_raw = entry.get("spot_raw", {})
        if all(k in spot_raw for k in ["mid", "bid", "ask", "spread_bps"]):
            self.microstructure_present += 1
            
            if len(self.spread_bps_samples) < self.max_samples:
                spread_bps = spot_raw.get("spread_bps")
                if is_valid_number(spread_bps):
                    self.spread_bps_samples.append(float(spread_bps))
        
        # Liquidity
        liq_qv_usd = spot_raw.get("liq_qv_usd")
        derived = entry.get("derived", {})
        liq_global_pct = derived.get("liq_global_pct")
        if is_valid_number(liq_qv_usd) or is_valid_number(liq_global_pct):
            self.liquidity_present += 1
            
            if len(self.liq_qv_usd_samples) < self.max_samples and is_valid_number(liq_qv_usd):
                self.liq_qv_usd_samples.append(float(liq_qv_usd))
        
        # Order book depth
        if any(k.startswith("depth_") for k in spot_raw.keys()) or "obi_5" in spot_raw:
            self.order_book_present += 1
        
        # Time-series prices
        spot_prices = entry.get("spot_prices", [])
        meta = entry.get("meta", {})
        sample_count = meta.get("sample_count")
        if isinstance(spot_prices, list) and len(spot_prices) > 0:
            self.time_series_present += 1
            
            if len(self.sample_count_samples) < self.max_samples and is_valid_number(sample_count):
                self.sample_count_samples.append(int(sample_count))
        
        # Sentiment (lexicon)
        tsw = entry.get("twitter_sentiment_windows", {})
        has_lexicon = False
        for cycle_key in ["last_cycle", "last_2_cycles"]:
            cycle = tsw.get(cycle_key, {})
            lexicon = cycle.get("lexicon_sentiment", {})
            if "score" in lexicon or any(k in lexicon for k in ["posts_pos", "posts_neu", "posts_neg"]):
                has_lexicon = True
                break
        if has_lexicon:
            self.sentiment_lexicon_present += 1
        
        # Sentiment (AI/hybrid)
        has_ai = False
        for cycle_key in ["last_cycle", "last_2_cycles"]:
            cycle = tsw.get(cycle_key, {})
            if "ai_sentiment" in cycle or "hybrid_decision_stats" in cycle:
                has_ai = True
                
                # Collect mean_score sample
                if len(self.mean_score_samples) < self.max_samples:
                    hybrid_stats = cycle.get("hybrid_decision_stats", {})
                    mean_score = hybrid_stats.get("mean_score")
                    if is_valid_number(mean_score):
                        self.mean_score_samples.append(float(mean_score))
                break
        if has_ai:
            self.sentiment_ai_present += 1
        
        # Activity vs silence
        has_activity = False
        for cycle_key in ["last_cycle", "last_2_cycles"]:
            cycle = tsw.get(cycle_key, {})
            activity = cycle.get("sentiment_activity", {})
            if "is_silent" in activity or "recent_posts_count" in activity or "hours_since_latest_tweet" in activity:
                has_activity = True
                
                # Collect posts_total sample
                if len(self.posts_total_samples) < self.max_samples:
                    posts_total = cycle.get("posts_total")
                    if is_valid_number(posts_total):
                        self.posts_total_samples.append(int(posts_total))
                break
        if has_activity:
            self.activity_silence_present += 1
        
        # Engagement
        platform_engagement = entry.get("platform_engagement", {})
        if platform_engagement and any(is_valid_number(v) for v in platform_engagement.values()):
            self.engagement_present += 1
        
        # Author stats
        author_stats = entry.get("author_stats", {})
        if author_stats and any(is_valid_number(v) for v in author_stats.values()):
            self.author_stats_present += 1
    
    def get_coverage_json(self, first_day: str, last_day: str) -> dict:
        """Generate coverage JSON."""
        def compute_rate(count: int, total: int) -> float:
            return count / total if total > 0 else 0.0
        
        def safe_median(samples: list) -> Optional[float]:
            return statistics.median(samples) if samples else None
        
        total = self.v7_seen
        
        return {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "date_range_utc": {
                "first_day": first_day,
                "last_day": last_day
            },
            "counts": {
                "v7_seen": self.v7_seen,
                "v7_usable": self.v7_usable
            },
            "groups": [
                {
                    "id": "microstructure",
                    "label": "Market microstructure",
                    "present_rate": compute_rate(self.microstructure_present, total),
                    "notes": ["Bid, ask, mid, spread_bps, last, range_pct_24h"],
                    "examples": {
                        "median_spread_bps": safe_median(self.spread_bps_samples)
                    }
                },
                {
                    "id": "liquidity",
                    "label": "Liquidity metrics",
                    "present_rate": compute_rate(self.liquidity_present, total),
                    "notes": ["liq_qv_usd, liq_global_pct"],
                    "examples": {
                        "median_liq_qv_usd": safe_median(self.liq_qv_usd_samples)
                    }
                },
                {
                    "id": "order_book",
                    "label": "Order book depth",
                    "present_rate": compute_rate(self.order_book_present, total),
                    "notes": ["depth_* fields, obi_5"],
                    "examples": {}
                },
                {
                    "id": "time_series",
                    "label": "Time-series prices",
                    "present_rate": compute_rate(self.time_series_present, total),
                    "notes": ["spot_prices array"],
                    "examples": {
                        "median_sample_count": safe_median(self.sample_count_samples)
                    }
                },
                {
                    "id": "sentiment_lexicon",
                    "label": "Sentiment (lexicon-based)",
                    "present_rate": compute_rate(self.sentiment_lexicon_present, total),
                    "notes": ["lexicon_sentiment.score, posts_pos/neu/neg"],
                    "examples": {}
                },
                {
                    "id": "sentiment_ai",
                    "label": "Sentiment (AI/hybrid)",
                    "present_rate": compute_rate(self.sentiment_ai_present, total),
                    "notes": ["ai_sentiment, hybrid_decision_stats, decision_sources"],
                    "examples": {
                        "median_mean_score": safe_median(self.mean_score_samples)
                    }
                },
                {
                    "id": "activity_silence",
                    "label": "Activity vs silence detection",
                    "present_rate": compute_rate(self.activity_silence_present, total),
                    "notes": ["is_silent, recent_posts_count, hours_since_latest_tweet"],
                    "examples": {
                        "median_posts_total": safe_median(self.posts_total_samples)
                    }
                },
                {
                    "id": "engagement",
                    "label": "Platform engagement",
                    "present_rate": compute_rate(self.engagement_present, total),
                    "notes": ["platform_engagement totals"],
                    "examples": {}
                },
                {
                    "id": "author_stats",
                    "label": "Author statistics",
                    "present_rate": compute_rate(self.author_stats_present, total),
                    "notes": ["author_stats fields"],
                    "examples": {}
                }
            ]
        }


class ScaleTracker:
    """Track scale metrics across v7 entries."""
    
    def __init__(self):
        self.v7_seen = 0
        self.v7_usable = 0
        self.first_day = None
        self.last_day = None
        self.symbols = set()
        self.cycle_ids = set()
    
    def add_entry(self, entry: dict, date: str, is_usable: bool):
        """Process one v7 entry."""
        self.v7_seen += 1
        if is_usable:
            self.v7_usable += 1
        
        # Track date range
        if self.first_day is None or date < self.first_day:
            self.first_day = date
        if self.last_day is None or date > self.last_day:
            self.last_day = date
        
        # Track symbols (only for usable entries)
        if is_usable:
            symbol = entry.get("symbol")
            if symbol:
                self.symbols.add(symbol)
        
        # Track cycle IDs
        tsw = entry.get("twitter_sentiment_windows", {})
        for cycle_key in ["last_cycle", "last_2_cycles"]:
            cycle = tsw.get(cycle_key, {})
            bucket_meta = cycle.get("bucket_meta", {})
            cycle_id = bucket_meta.get("cycle_id")
            if cycle_id:
                self.cycle_ids.add(cycle_id)
    
    def get_scale_json(self) -> dict:
        """Generate scale JSON."""
        days_running = 0
        if self.first_day and self.last_day:
            try:
                first = datetime.strptime(self.first_day, "%Y-%m-%d")
                last = datetime.strptime(self.last_day, "%Y-%m-%d")
                days_running = (last - first).days + 1
            except ValueError:
                days_running = 0
        
        avg_usable_per_day = self.v7_usable / days_running if days_running > 0 else 0
        
        return {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "date_range_utc": {
                "first_day": self.first_day or "UNKNOWN",
                "last_day": self.last_day or "UNKNOWN"
            },
            "days_running": days_running,
            "v7_seen_total": self.v7_seen,
            "v7_usable_total": self.v7_usable,
            "avg_usable_per_day": round(avg_usable_per_day, 1),
            "distinct_symbols_total": len(self.symbols),
            "cycles_completed": len(self.cycle_ids)
        }


class PreviewRowCollector:
    """Collect candidate preview rows."""
    
    def __init__(self):
        self.candidates = []
        self.max_candidates = 100
    
    def add_entry(self, entry: dict):
        """Add entry as preview candidate."""
        if len(self.candidates) < self.max_candidates:
            self.candidates.append(entry)
    
    def get_preview_json(self) -> Optional[dict]:
        """Generate preview row JSON (redacted)."""
        if not self.candidates:
            return None
        
        # Pick one at random
        entry = random.choice(self.candidates)
        
        # Extract fields (with redaction)
        symbol = entry.get("symbol", "UNKNOWN")
        
        scores = entry.get("scores", {})
        final_score = scores.get("final")
        
        derived = entry.get("derived", {})
        liq_global_pct = derived.get("liq_global_pct")
        
        spot_raw = entry.get("spot_raw", {})
        spread_bps = spot_raw.get("spread_bps")
        
        tsw = entry.get("twitter_sentiment_windows", {})
        last_cycle = tsw.get("last_cycle", {})
        hybrid_stats = last_cycle.get("hybrid_decision_stats", {})
        mean_score = hybrid_stats.get("mean_score")
        posts_total = last_cycle.get("posts_total")
        activity = last_cycle.get("sentiment_activity", {})
        is_silent = activity.get("is_silent")
        
        # Compute forward return bucket
        spot_prices = entry.get("spot_prices", [])
        next_1h_return_bucket = compute_forward_return_bucket(spot_prices)
        
        return {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "note": "Single redacted example from v7 usable entries. No timestamps, session_id, or exact returns.",
            "row": {
                "symbol": symbol,
                "scores_final": final_score,
                "derived_liq_global_pct": liq_global_pct,
                "spot_raw_spread_bps": spread_bps,
                "twitter_last_cycle_hybrid_mean_score": mean_score,
                "twitter_last_cycle_posts_total": posts_total,
                "twitter_last_cycle_is_silent": is_silent,
                "next_1h_return_bucket": next_1h_return_bucket
            }
        }


def scan_archive(archive_path: Path, scan_limit: Optional[int] = None):
    """
    Scan CryptoBot archive and generate artifacts.
    
    Args:
        archive_path: Path to CryptoBot archive
        scan_limit: Optional limit on entries to scan
    
    Returns:
        (coverage_tracker, scale_tracker, preview_collector)
    """
    coverage = CoverageTracker()
    scale = ScaleTracker()
    preview = PreviewRowCollector()
    
    entries_scanned = 0
    
    # Find all day folders
    day_folders = sorted([d for d in archive_path.iterdir() 
                         if d.is_dir() and d.name.isdigit() and len(d.name) == 8])
    
    print(f"{INFO_MARK} Scanning {len(day_folders)} day folders...")
    
    for day_folder in day_folders:
        day_str = day_folder.name  # YYYYMMDD
        
        # Parse date
        try:
            date_obj = datetime.strptime(day_str, "%Y%m%d")
            date_iso = date_obj.strftime("%Y-%m-%d")
        except ValueError:
            continue
        
        # Scan all jsonl.gz files in this day
        jsonl_files = list(day_folder.glob("*.jsonl.gz"))
        
        for jsonl_file in jsonl_files:
            try:
                with gzip.open(jsonl_file, 'rt', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        try:
                            entry = json.loads(line)
                            
                            # Safety check
                            if not isinstance(entry, dict):
                                continue
                            
                            # Check if v7
                            meta = entry.get("meta", {})
                            if not isinstance(meta, dict):
                                continue
                            
                            schema_version = meta.get("schema_version")
                            if schema_version != 7:
                                continue
                            
                            # Check if usable
                            is_usable, reason = is_usable_v7_entry(entry)
                            
                            # Track for coverage
                            coverage.add_entry(entry, is_usable)
                            
                            # Track for scale
                            scale.add_entry(entry, date_iso, is_usable)
                            
                            # Collect for preview (only usable)
                            if is_usable:
                                preview.add_entry(entry)
                            
                            entries_scanned += 1
                            
                            # Check scan limit
                            if scan_limit and entries_scanned >= scan_limit:
                                print(f"{INFO_MARK} Reached scan limit ({scan_limit})")
                                return coverage, scale, preview
                        
                        except json.JSONDecodeError:
                            continue
            
            except Exception as e:
                print(f"{WARN_MARK} Could not read {jsonl_file.name}: {e}")
                continue
    
    print(f"{INFO_MARK} Scanned {entries_scanned} v7 entries")
    
    return coverage, scale, preview


def write_artifacts(output_dir: Path, coverage: CoverageTracker, scale: ScaleTracker, preview: PreviewRowCollector):
    """Write artifact JSON files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Coverage
    coverage_json = coverage.get_coverage_json(scale.first_day or "UNKNOWN", scale.last_day or "UNKNOWN")
    coverage_path = output_dir / "coverage_v7.json"
    with open(coverage_path, 'w', encoding='utf-8') as f:
        json.dump(coverage_json, f, indent=2)
    print(f"{OK_MARK} Wrote {coverage_path}")
    
    # Scale
    scale_json = scale.get_scale_json()
    scale_path = output_dir / "scale_v7.json"
    with open(scale_path, 'w', encoding='utf-8') as f:
        json.dump(scale_json, f, indent=2)
    print(f"{OK_MARK} Wrote {scale_path}")
    
    # Preview
    preview_json = preview.get_preview_json()
    if preview_json:
        preview_path = output_dir / "preview_row_v7.json"
        with open(preview_path, 'w', encoding='utf-8') as f:
            json.dump(preview_json, f, indent=2)
        print(f"{OK_MARK} Wrote {preview_path}")
    else:
        print(f"{WARN_MARK} No preview row candidates found")


def main():
    """Main entry point."""
    print(f"{INFO_MARK} Artifact Builder (Part A)")
    print("=" * 60)
    
    # Determine paths
    site_root = Path.cwd()
    cryptobot_archive = site_root.parent / "CryptoBot" / "data" / "archive"
    output_dir = site_root / "public" / "data" / "artifacts"
    
    if not cryptobot_archive.exists():
        print(f"{ERROR_MARK} CryptoBot archive not found: {cryptobot_archive}")
        return 1
    
    print(f"{INFO_MARK} Archive: {cryptobot_archive}")
    print(f"{INFO_MARK} Output: {output_dir}")
    
    # Check for scan limit
    scan_limit = os.environ.get("ARTIFACT_SCAN_LIMIT")
    if scan_limit:
        try:
            scan_limit = int(scan_limit)
            print(f"{INFO_MARK} Using scan limit: {scan_limit}")
        except ValueError:
            scan_limit = None
    
    # Scan archive
    coverage, scale, preview = scan_archive(cryptobot_archive, scan_limit)
    
    # Print summary
    print("")
    print("=" * 60)
    print(f"{INFO_MARK} Summary:")
    print(f"  v7 seen: {coverage.v7_seen}")
    print(f"  v7 usable: {coverage.v7_usable}")
    print(f"  Distinct symbols: {len(scale.symbols)}")
    print(f"  Cycles completed: {len(scale.cycle_ids)}")
    print(f"  Date range: {scale.first_day} to {scale.last_day}")
    print("=" * 60)
    
    # Write artifacts
    write_artifacts(output_dir, coverage, scale, preview)
    
    print(f"\n{OK_MARK} Artifacts generated successfully!")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
