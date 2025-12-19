#!/usr/bin/env python3
"""
build_artifacts_part_b.py
==========================

Generate BEHAVIORAL artifacts (descriptive only, not predictive):
  1) Sentiment bucket -> forward return distribution (B1)
  2) Activity vs silence regime comparison (B2)

Outputs:
  - public/data/artifacts/sentiment_vs_forward_return_v7.json
  - public/data/artifacts/regimes_activity_vs_silence_v7.json

Usage:
  python scripts/build_artifacts_part_b.py

Testing:
  set ARTIFACT_SCAN_LIMIT=2000
  python scripts/build_artifacts_part_b.py
"""

import gzip
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from statistics import median, quantiles
from typing import Any, Dict, List, Optional


# ============================================================================
# Configuration
# ============================================================================

ARCHIVE_ROOT = Path("D:/Sentiment-Data/CryptoBot/data/archive")
OUTPUT_DIR = Path("public/data/artifacts")

# Sentiment bins: 10 bins from -1 to 1
SENTIMENT_BINS = [
    (-1.0, -0.8),
    (-0.8, -0.6),
    (-0.6, -0.4),
    (-0.4, -0.2),
    (-0.2, 0.0),
    (0.0, 0.2),
    (0.2, 0.4),
    (0.4, 0.6),
    (0.6, 0.8),
    (0.8, 1.0),
]


# ============================================================================
# Usable v7 gate (same as Part A)
# ============================================================================

def is_usable_v7_entry(entry: Dict[str, Any]) -> bool:
    """
    Same gate as build_artifacts_part_a.py and exporter.
    Returns True if entry passes all usability checks.
    """
    # Must be schema v7
    meta = entry.get("meta", {})
    if meta.get("schema_version") != 7:
        return False
    
    # Must have spot_prices list with 700+ samples
    spot_prices = entry.get("spot_prices")
    if not isinstance(spot_prices, list):
        return False
    if len(spot_prices) < 700:
        return False
    
    # Must have spot_raw with required keys
    spot_raw = entry.get("spot_raw", {})
    required_keys = ["mid", "bid", "ask", "spread_bps"]
    if not all(k in spot_raw for k in required_keys):
        return False
    
    # Must have twitter_sentiment_windows with at least one cycle
    tsw = entry.get("twitter_sentiment_windows", {})
    has_last_cycle = "last_cycle" in tsw and isinstance(tsw["last_cycle"], dict)
    has_last_2_cycles = "last_2_cycles" in tsw and isinstance(tsw["last_2_cycles"], dict)
    
    if not (has_last_cycle or has_last_2_cycles):
        return False
    
    return True


# ============================================================================
# Helper: Extract metrics from spot_prices list
# ============================================================================

def parse_timestamp(ts_str: Any) -> Optional[float]:
    """Parse timestamp (numeric or ISO string) to unix seconds."""
    if ts_str is None:
        return None
    
    # If already numeric, return it
    if isinstance(ts_str, (int, float)):
        return float(ts_str)
    
    # If string, try to parse ISO format
    if isinstance(ts_str, str):
        try:
            dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            return dt.timestamp()
        except (ValueError, AttributeError):
            return None
    
    return None


def get_forward_return_1h(spot_prices: List[Dict[str, Any]]) -> Optional[float]:
    """
    Extract 1h forward return from spot_prices list.
    Finds sample closest to +1h from first sample.
    Returns None if not available.
    """
    if not isinstance(spot_prices, list) or len(spot_prices) < 2:
        return None
    
    try:
        # Get first sample
        first = spot_prices[0]
        if not isinstance(first, dict):
            return None
        
        first_ts = parse_timestamp(first.get("ts"))
        first_mid = first.get("mid")
        
        if first_ts is None or first_mid is None:
            return None
        if first_mid <= 0:
            return None
        
        # Find sample closest to +1h (3600 seconds)
        target_ts = first_ts + 3600
        closest_sample = None
        min_diff = float('inf')
        
        for sample in spot_prices[1:]:
            if not isinstance(sample, dict):
                continue
            
            sample_ts = parse_timestamp(sample.get("ts"))
            if sample_ts is None:
                continue
            
            diff = abs(sample_ts - target_ts)
            if diff < min_diff:
                min_diff = diff
                closest_sample = sample
        
        if closest_sample is None:
            return None
        
        last_mid = closest_sample.get("mid")
        if last_mid is None or last_mid <= 0:
            return None
        
        # Compute return
        return (last_mid - first_mid) / first_mid
    
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def get_abs_return_over_window(spot_prices: List[Dict[str, Any]]) -> Optional[float]:
    """
    Compute absolute return over window from spot_prices list.
    Uses first and last sample mid prices.
    Returns None if not available.
    """
    if not isinstance(spot_prices, list) or len(spot_prices) < 2:
        return None
    
    try:
        first = spot_prices[0]
        last = spot_prices[-1]
        
        if not isinstance(first, dict) or not isinstance(last, dict):
            return None
        
        mid_first = first.get("mid")
        mid_last = last.get("mid")
        
        if mid_first is None or mid_last is None:
            return None
        if mid_first <= 0:
            return None
        
        ret = (mid_last - mid_first) / mid_first
        return abs(ret)
    
    except (TypeError, ValueError, ZeroDivisionError):
        return None


# ============================================================================
# B1: Sentiment Bucket Tracker
# ============================================================================

class SentimentBucketTracker:
    """
    Track forward return distributions bucketed by sentiment score.
    """
    
    def __init__(self):
        # bins: dict from bin_label -> list of forward returns
        self.bins: Dict[str, List[float]] = {}
        for low, high in SENTIMENT_BINS:
            label = f"[{low:.1f}..{high:.1f})"
            self.bins[label] = []
        
        # Coverage tracking
        self.entries_with_mean_score = 0
        self.entries_with_forward_return = 0
        self.total_usable = 0
    
    def ingest(self, entry: Dict[str, Any]) -> None:
        """Process one usable v7 entry."""
        self.total_usable += 1
        
        # Extract mean_score
        tsw = entry.get("twitter_sentiment_windows", {})
        last_cycle = tsw.get("last_cycle", {})
        hybrid_stats = last_cycle.get("hybrid_decision_stats", {})
        mean_score = hybrid_stats.get("mean_score")
        
        if mean_score is None:
            return
        
        self.entries_with_mean_score += 1
        
        # Extract forward return
        spot_prices = entry.get("spot_prices", {})
        fwd_ret = get_forward_return_1h(spot_prices)
        
        if fwd_ret is None:
            return
        
        self.entries_with_forward_return += 1
        
        # Find matching bin
        for low, high in SENTIMENT_BINS:
            if low <= mean_score < high:
                label = f"[{low:.1f}..{high:.1f})"
                self.bins[label].append(fwd_ret)
                break
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        bins_data = []
        
        for low, high in SENTIMENT_BINS:
            label = f"[{low:.1f}..{high:.1f})"
            returns = self.bins[label]
            
            if len(returns) == 0:
                bins_data.append({
                    "bin_label": label,
                    "bin_low": low,
                    "bin_high": high,
                    "sample_count": 0,
                    "median": None,
                    "p25": None,
                    "p75": None,
                    "pct_positive": None,
                })
                continue
            
            returns_sorted = sorted(returns)
            med = median(returns_sorted)
            
            # Compute quartiles
            if len(returns_sorted) >= 4:
                qs = quantiles(returns_sorted, n=4)  # Returns [Q1, Q2, Q3]
                p25 = qs[0]
                p75 = qs[2]
            else:
                p25 = returns_sorted[0]
                p75 = returns_sorted[-1]
            
            pct_pos = sum(1 for r in returns if r > 0) / len(returns)
            
            bins_data.append({
                "bin_label": label,
                "bin_low": low,
                "bin_high": high,
                "sample_count": len(returns),
                "median": round(med, 6),
                "p25": round(p25, 6),
                "p75": round(p75, 6),
                "pct_positive": round(pct_pos, 4),
            })
        
        return {
            "description": "Forward return distributions bucketed by hybrid sentiment mean_score. Descriptive only, not predictive.",
            "data_version": "v7",
            "coverage": {
                "total_usable_entries": self.total_usable,
                "entries_with_mean_score": self.entries_with_mean_score,
                "entries_with_forward_return": self.entries_with_forward_return,
            },
            "bins": bins_data,
        }


# ============================================================================
# B2: Regime Comparison Tracker (Activity vs Silence)
# ============================================================================

class RegimeComparisonTracker:
    """
    Compare activity vs silence regimes on multiple dimensions.
    """
    
    def __init__(self):
        # Two groups: silent and non-silent
        self.silent_returns: List[float] = []
        self.active_returns: List[float] = []
        
        self.silent_liq_qv: List[float] = []
        self.active_liq_qv: List[float] = []
        
        self.silent_spread: List[float] = []
        self.active_spread: List[float] = []
        
        self.silent_liq_global: List[float] = []
        self.active_liq_global: List[float] = []
        
        # Date tracking
        self.dates_seen = set()
        
        # Counts
        self.silent_count = 0
        self.active_count = 0
        self.total_usable = 0
    
    def ingest(self, entry: Dict[str, Any], date_iso: str = None) -> None:
        """Process one usable v7 entry."""
        self.total_usable += 1
        
        # Track date (from folder name)
        if date_iso:
            self.dates_seen.add(date_iso)
        
        # Extract is_silent
        tsw = entry.get("twitter_sentiment_windows", {})
        last_cycle = tsw.get("last_cycle", {})
        sentiment_activity = last_cycle.get("sentiment_activity", {})
        is_silent = sentiment_activity.get("is_silent")
        
        if is_silent is None:
            return
        
        # Extract metrics
        spot_prices = entry.get("spot_prices", {})
        abs_ret = get_abs_return_over_window(spot_prices)
        
        spot_raw = entry.get("spot_raw", {})
        liq_qv = spot_raw.get("liq_qv_usd")
        spread = spot_raw.get("spread_bps")
        
        derived = entry.get("derived", {})
        liq_global = derived.get("liq_global_pct")
        
        # Add to appropriate group
        if is_silent:
            self.silent_count += 1
            if abs_ret is not None:
                self.silent_returns.append(abs_ret)
            if liq_qv is not None:
                self.silent_liq_qv.append(liq_qv)
            if spread is not None:
                self.silent_spread.append(spread)
            if liq_global is not None:
                self.silent_liq_global.append(liq_global)
        else:
            self.active_count += 1
            if abs_ret is not None:
                self.active_returns.append(abs_ret)
            if liq_qv is not None:
                self.active_liq_qv.append(liq_qv)
            if spread is not None:
                self.active_spread.append(spread)
            if liq_global is not None:
                self.active_liq_global.append(liq_global)
    
    def _compute_stats(self, values: List[float]) -> Dict[str, Any]:
        """Compute median and p90 for a list of values."""
        if len(values) == 0:
            return {"count": 0, "median": None, "p90": None}
        
        sorted_vals = sorted(values)
        med = median(sorted_vals)
        
        # p90 using quantiles
        if len(sorted_vals) >= 10:
            qs = quantiles(sorted_vals, n=10)  # Returns 9 values
            p90 = qs[8]  # 9th quantile is p90
        else:
            # Fallback: use index approximation
            idx = int(len(sorted_vals) * 0.9)
            p90 = sorted_vals[min(idx, len(sorted_vals) - 1)]
        
        return {
            "count": len(values),
            "median": round(med, 6),
            "p90": round(p90, 6),
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        dates_list = sorted(self.dates_seen)
        date_range = None
        if len(dates_list) > 0:
            date_range = {
                "first": dates_list[0],
                "last": dates_list[-1],
                "days": len(dates_list),
            }
        
        return {
            "description": "Comparison of silent vs active regimes across multiple dimensions. Descriptive only, not predictive.",
            "data_version": "v7",
            "date_range": date_range,
            "groups": {
                "silent": {
                    "sample_count": self.silent_count,
                    "abs_return_over_window": self._compute_stats(self.silent_returns),
                    "liq_qv_usd": self._compute_stats(self.silent_liq_qv),
                    "spread_bps": self._compute_stats(self.silent_spread),
                    "liq_global_pct": self._compute_stats(self.silent_liq_global),
                },
                "active": {
                    "sample_count": self.active_count,
                    "abs_return_over_window": self._compute_stats(self.active_returns),
                    "liq_qv_usd": self._compute_stats(self.active_liq_qv),
                    "spread_bps": self._compute_stats(self.active_spread),
                    "liq_global_pct": self._compute_stats(self.active_liq_global),
                },
            },
        }


# ============================================================================
# Archive scanning
# ============================================================================

def scan_archive(
    sentiment_tracker: SentimentBucketTracker,
    regime_tracker: RegimeComparisonTracker,
) -> int:
    """
    Stream through archive, filter for usable v7, feed to trackers.
    Returns total entries scanned.
    """
    scan_limit = os.getenv("ARTIFACT_SCAN_LIMIT")
    if scan_limit:
        try:
            scan_limit = int(scan_limit)
            print(f"[SCAN] Limit set to {scan_limit}")
        except ValueError:
            scan_limit = None
    
    if not ARCHIVE_ROOT.exists():
        print(f"[ERROR] Archive root not found: {ARCHIVE_ROOT}")
        sys.exit(1)
    
    day_folders = sorted([d for d in ARCHIVE_ROOT.iterdir() if d.is_dir()])
    
    scanned = 0
    v7_count = 0
    usable_count = 0
    
    for day_folder in day_folders:
        day_str = day_folder.name  # YYYYMMDD
        
        # Parse date
        try:
            date_obj = datetime.strptime(day_str, "%Y%m%d")
            date_iso = date_obj.strftime("%Y-%m-%d")
        except ValueError:
            continue
        
        jsonl_files = sorted(day_folder.glob("*.jsonl.gz"))
        
        for jsonl_path in jsonl_files:
            try:
                with gzip.open(jsonl_path, "rt", encoding="utf-8") as f:
                    for line in f:
                        if scan_limit and scanned >= scan_limit:
                            print(f"[SCAN] Reached scan limit {scan_limit}")
                            return scanned
                        
                        scanned += 1
                        
                        # Parse entry
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        
                        if not isinstance(entry, dict):
                            continue
                        
                        # Count v7
                        meta = entry.get("meta", {})
                        if meta.get("schema_version") == 7:
                            v7_count += 1
                        
                        # Filter usable
                        if not is_usable_v7_entry(entry):
                            continue
                        
                        usable_count += 1
                        
                        # Feed to trackers (with date from folder name)
                        sentiment_tracker.ingest(entry)
                        regime_tracker.ingest(entry, date_iso)
                        
            except Exception as e:
                print(f"[WARN] Could not read {jsonl_path.name}: {e}")
                continue
    
    print(f"[SCAN] Scanned: {scanned}, v7: {v7_count}, usable: {usable_count}")
    return scanned


# ============================================================================
# Write outputs
# ============================================================================

def write_artifacts(
    sentiment_tracker: SentimentBucketTracker,
    regime_tracker: RegimeComparisonTracker,
) -> None:
    """Write JSON artifacts to output directory."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Sentiment buckets
    sentiment_path = OUTPUT_DIR / "sentiment_vs_forward_return_v7.json"
    with open(sentiment_path, "w", encoding="utf-8") as f:
        json.dump(sentiment_tracker.to_dict(), f, indent=2, ensure_ascii=True)
    print(f"[OUT] Wrote {sentiment_path}")
    
    # Regimes
    regime_path = OUTPUT_DIR / "regimes_activity_vs_silence_v7.json"
    with open(regime_path, "w", encoding="utf-8") as f:
        json.dump(regime_tracker.to_dict(), f, indent=2, ensure_ascii=True)
    print(f"[OUT] Wrote {regime_path}")


# ============================================================================
# Main
# ============================================================================

def main():
    print("=" * 60)
    print("Artifact Builder - Part B: Behavior Summaries")
    print("=" * 60)
    
    # Initialize trackers
    sentiment_tracker = SentimentBucketTracker()
    regime_tracker = RegimeComparisonTracker()
    
    # Scan archive
    print(f"[SCAN] Archive: {ARCHIVE_ROOT}")
    scan_archive(sentiment_tracker, regime_tracker)
    
    # Write outputs
    print(f"[OUT] Output dir: {OUTPUT_DIR}")
    write_artifacts(sentiment_tracker, regime_tracker)
    
    print("=" * 60)
    print("[DONE] Artifacts Part B complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
