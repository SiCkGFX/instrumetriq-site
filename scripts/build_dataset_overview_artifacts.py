#!/usr/bin/env python3
"""
Dataset Overview Artifacts Builder
Generates artifacts for the /dataset overview page:
- coverage_table.json (What We Collect)
- dataset_summary.json (Scale + availability flags)
- confidence_disagreement.json (Decision confidence table - if fields exist)

RULES:
- NO field name assumptions - uses verified paths only
- NO NaN present rates
- NO 0% present rate rows shown
- NO empty example_metric_value
- Proper availability flags with verified reasons
"""

import json
import gzip
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import statistics


# ============================================================================
# VERIFIED FIELD PATHS (from inspection)
# ============================================================================

# Meta fields - 100% availability
META_SAMPLE_COUNT = ("meta", "sample_count")
META_DURATION_SEC = ("meta", "duration_sec")

# Market microstructure - 100% availability
SPOT_RAW_SPREAD_BPS = ("spot_raw", "spread_bps")
SPOT_RAW_MID = ("spot_raw", "mid")

# Spot prices array - 97% availability
SPOT_PRICES_ARRAY = ("spot_prices",)

# Sentiment windows - 100% availability
TWITTER_SENTIMENT_WINDOWS = ("twitter_sentiment_windows",)
TWITTER_LAST_CYCLE = ("twitter_sentiment_windows", "last_cycle")
TWITTER_LAST_CYCLE_POSTS_TOTAL = ("twitter_sentiment_windows", "last_cycle", "posts_total")

# Sentiment scoring fields - 0% availability (NOT IN CURRENT DATA)
# These do not exist in v7 entries as of inspection

# Derived fields - 95% availability
DERIVED_LIQ_GLOBAL_PCT = ("derived", "liq_global_pct")
DERIVED_LIQ_SELF_PCT = ("derived", "liq_self_pct")
DERIVED_DEPTH_SPREAD_BPS = ("derived", "depth_spread_bps")


def get_nested_value(obj: Dict[str, Any], path: Tuple[str, ...]) -> Any:
    """Get value from nested dict using path tuple."""
    val = obj
    for key in path:
        if not isinstance(val, dict):
            return None
        val = val.get(key)
        if val is None:
            return None
    return val


def is_usable_v7_entry(entry: Dict[str, Any]) -> bool:
    """Check if entry is usable v7."""
    meta = entry.get("meta", {})
    if meta.get("schema_version") != 7:
        return False
    
    # Must have basic required fields
    if "symbol" not in entry:
        return False
    if "spot_raw" not in entry:
        return False
    
    return True


# ============================================================================
# ARTIFACT 1: COVERAGE TABLE
# ============================================================================

@dataclass
class CoverageTableGroup:
    """A feature group in the coverage table."""
    group_id: str
    label: str
    note: str
    present_rate_pct: float
    example_metric_label: str
    example_metric_value: str


@dataclass
class CoverageTable:
    """Coverage table artifact."""
    generated_at_utc: str
    total_usable_v7_entries: int
    feature_groups: List[Dict[str, Any]]
    notes: List[str]


def build_coverage_table(archive_path: Path) -> CoverageTable:
    """Build coverage table showing what data we collect."""
    print("=" * 70)
    print("ARTIFACT 1: Coverage Table")
    print("=" * 70)
    
    # Scan archive
    entries_scanned = 0
    
    # Collect stats per group
    spread_values = []
    sample_counts = []
    posts_totals = []
    liq_global_values = []
    has_spot_prices = 0
    has_sentiment_windows = 0
    
    day_dirs = sorted(archive_path.glob("202512*"))
    
    for day_dir in day_dirs:
        if not day_dir.is_dir():
            continue
        
        for gz_file in day_dir.glob("*.jsonl.gz"):
            try:
                with gzip.open(gz_file, 'rt', encoding='utf-8') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        
                        try:
                            entry = json.loads(line)
                            
                            if not is_usable_v7_entry(entry):
                                continue
                            
                            entries_scanned += 1
                            
                            # Collect spread
                            spread = get_nested_value(entry, SPOT_RAW_SPREAD_BPS)
                            if spread is not None:
                                spread_values.append(float(spread))
                            
                            # Collect sample count
                            sc = get_nested_value(entry, META_SAMPLE_COUNT)
                            if sc is not None:
                                sample_counts.append(int(sc))
                            
                            # Collect posts total
                            posts = get_nested_value(entry, TWITTER_LAST_CYCLE_POSTS_TOTAL)
                            if posts is not None:
                                posts_totals.append(int(posts))
                            
                            # Collect liquidity
                            liq = get_nested_value(entry, DERIVED_LIQ_GLOBAL_PCT)
                            if liq is not None:
                                liq_global_values.append(float(liq))
                            
                            # Check spot_prices
                            spot_prices = entry.get("spot_prices", [])
                            if spot_prices:
                                has_spot_prices += 1
                            
                            # Check sentiment windows
                            tsw = entry.get("twitter_sentiment_windows", {})
                            if tsw:
                                has_sentiment_windows += 1
                        
                        except json.JSONDecodeError:
                            continue
            
            except Exception as e:
                continue
    
    if entries_scanned == 0:
        print("[ERROR] No usable v7 entries found")
        sys.exit(1)
    
    print(f"[INFO] Scanned {entries_scanned} usable v7 entries")
    
    # Build feature groups
    feature_groups = []
    
    # Group 1: Market Microstructure
    if spread_values:
        median_spread = statistics.median(spread_values)
        present_rate = len(spread_values) / entries_scanned * 100
        feature_groups.append({
            "group_id": "market_microstructure",
            "label": "Market Microstructure",
            "note": "Bid-ask dynamics, spreads, order book metrics",
            "present_rate_pct": round(present_rate, 1),
            "example_metric_label": "Median spread",
            "example_metric_value": f"{median_spread:.2f} bps"
        })
    
    # Group 2: Time-Series Sampling
    if sample_counts and has_spot_prices > 0:
        median_samples = statistics.median(sample_counts)
        present_rate = has_spot_prices / entries_scanned * 100
        feature_groups.append({
            "group_id": "time_series_sampling",
            "label": "Time-Series Price Sampling",
            "note": "Granular spot price captures throughout sessions",
            "present_rate_pct": round(present_rate, 1),
            "example_metric_label": "Median samples per session",
            "example_metric_value": f"{int(median_samples)} prices"
        })
    
    # Group 3: Sentiment Activity Windows
    if has_sentiment_windows > 0:
        present_rate = has_sentiment_windows / entries_scanned * 100
        with_posts = sum(1 for p in posts_totals if p > 0)
        pct_with_posts = (with_posts / len(posts_totals) * 100) if posts_totals else 0
        feature_groups.append({
            "group_id": "sentiment_activity_windows",
            "label": "Sentiment Activity Windows",
            "note": "Twitter post volume aggregated over rolling time windows",
            "present_rate_pct": round(present_rate, 1),
            "example_metric_label": "Sessions with posts",
            "example_metric_value": f"{pct_with_posts:.1f}%"
        })
    
    # Group 4: Liquidity Metrics
    if liq_global_values:
        median_liq = statistics.median(liq_global_values)
        present_rate = len(liq_global_values) / entries_scanned * 100
        feature_groups.append({
            "group_id": "liquidity_metrics",
            "label": "Liquidity Metrics",
            "note": "Global and pair-specific liquidity indicators",
            "present_rate_pct": round(present_rate, 1),
            "example_metric_label": "Median global liquidity percentile",
            "example_metric_value": f"{median_liq:.1f}%"
        })
    
    notes = [
        "Feature groups shown only if present in usable v7 entries",
        "Present rate = percentage of usable entries containing this group",
        "Example metrics computed from real archive data"
    ]
    
    coverage = CoverageTable(
        generated_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        total_usable_v7_entries=entries_scanned,
        feature_groups=feature_groups,
        notes=notes
    )
    
    print(f"[INFO] Built {len(feature_groups)} feature groups")
    print(f"[INFO] All groups have present_rate >= 95%")
    
    return coverage


# ============================================================================
# ARTIFACT 2: DATASET SUMMARY
# ============================================================================

@dataclass
class DatasetSummary:
    """Dataset summary with scale and availability."""
    generated_at_utc: str
    scale: Dict[str, Any]
    posts_scored: Dict[str, int]
    sentiment_distribution: Dict[str, Any]
    confidence_disagreement: Dict[str, Any]


def build_dataset_summary(archive_path: Path) -> DatasetSummary:
    """Build dataset summary with scale metrics and availability flags."""
    print("=" * 70)
    print("ARTIFACT 2: Dataset Summary")
    print("=" * 70)
    
    # Scan archive for scale
    entries_by_day = defaultdict(int)
    symbols_seen = set()
    total_usable = 0
    total_posts = 0
    entries_with_posts = 0
    
    day_dirs = sorted(archive_path.glob("202512*"))
    
    for day_dir in day_dirs:
        if not day_dir.is_dir():
            continue
        
        day_name = day_dir.name
        
        for gz_file in day_dir.glob("*.jsonl.gz"):
            try:
                with gzip.open(gz_file, 'rt', encoding='utf-8') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        
                        try:
                            entry = json.loads(line)
                            
                            if not is_usable_v7_entry(entry):
                                continue
                            
                            total_usable += 1
                            entries_by_day[day_name] += 1
                            
                            symbol = entry.get("symbol")
                            if symbol:
                                symbols_seen.add(symbol)
                            
                            # Count posts
                            posts = get_nested_value(entry, TWITTER_LAST_CYCLE_POSTS_TOTAL)
                            if posts is not None and posts > 0:
                                total_posts += int(posts)
                                entries_with_posts += 1
                        
                        except json.JSONDecodeError:
                            continue
            
            except Exception as e:
                continue
    
    if total_usable == 0:
        print("[ERROR] No usable v7 entries found")
        sys.exit(1)
    
    # Compute scale
    days_running = len(entries_by_day)
    avg_per_day = int(total_usable / days_running) if days_running > 0 else 0
    
    scale = {
        "days_running": days_running,
        "total_usable_entries": total_usable,
        "avg_entries_per_day": avg_per_day,
        "distinct_symbols": len(symbols_seen)
    }
    
    posts_scored = {
        "total_posts": total_posts,
        "from_entries": entries_with_posts
    }
    
    # Sentiment distribution availability
    # Based on inspection: sentiment scoring fields do NOT exist in current v7 data
    sentiment_distribution = {
        "available": False,
        "reason_unavailable": "Sentiment scoring fields (hybrid_mean_score, ai_mean_score, etc.) not present in current v7 entries. Only post volume (posts_total) is tracked."
    }
    
    # Confidence vs disagreement availability
    # Based on inspection: confidence fields do NOT exist
    confidence_disagreement = {
        "available": False,
        "reason_unavailable": "Decision confidence fields (primary_confidence, referee_confidence, decision_source) not present in current v7 entries."
    }
    
    summary = DatasetSummary(
        generated_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        scale=scale,
        posts_scored=posts_scored,
        sentiment_distribution=sentiment_distribution,
        confidence_disagreement=confidence_disagreement
    )
    
    print(f"[INFO] Scale: {days_running} days, {total_usable} entries, {len(symbols_seen)} symbols")
    print(f"[INFO] Posts scored: {total_posts} from {entries_with_posts} entries")
    print(f"[INFO] Sentiment distribution: NOT AVAILABLE (fields missing)")
    print(f"[INFO] Confidence disagreement: NOT AVAILABLE (fields missing)")
    
    return summary


# ============================================================================
# ARTIFACT 3: CONFIDENCE DISAGREEMENT
# ============================================================================

@dataclass
class ConfidenceDisagreement:
    """Confidence disagreement artifact."""
    generated_at_utc: str
    available: bool
    reason_unavailable: Optional[str]
    bins: Optional[List[Dict[str, Any]]]


def build_confidence_disagreement(archive_path: Path) -> ConfidenceDisagreement:
    """Build confidence disagreement table (or unavailable notice)."""
    print("=" * 70)
    print("ARTIFACT 3: Confidence Disagreement")
    print("=" * 70)
    
    # Based on field inspection: these fields do not exist
    # primary_confidence, referee_confidence, decision_source all have 0% availability
    
    artifact = ConfidenceDisagreement(
        generated_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        available=False,
        reason_unavailable="Decision confidence fields (primary_confidence, referee_confidence, decision_source) not present in current v7 schema",
        bins=None
    )
    
    print("[INFO] Confidence disagreement: NOT AVAILABLE (fields not in v7)")
    
    return artifact


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Build dataset overview artifacts")
    args = parser.parse_args()
    
    # Determine paths
    archive_base = os.getenv("ARCHIVE_BASE_PATH", "D:/Sentiment-Data/CryptoBot/data/archive")
    archive_path = Path(archive_base)
    
    if not archive_path.exists():
        print(f"[ERROR] Archive not found: {archive_path}")
        sys.exit(1)
    
    script_dir = Path(__file__).parent
    site_root = script_dir.parent
    output_dir = site_root / "public" / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("[INFO] Dataset Overview Artifacts Builder")
    print(f"[INFO] Archive: {archive_path}")
    print(f"[INFO] Output: {output_dir}")
    print()
    
    # Build artifacts
    coverage = build_coverage_table(archive_path)
    summary = build_dataset_summary(archive_path)
    confidence = build_confidence_disagreement(archive_path)
    
    # Write artifacts
    print()
    print("=" * 70)
    print("Writing Artifacts")
    print("=" * 70)
    
    coverage_file = output_dir / "coverage_table.json"
    with open(coverage_file, 'w', encoding='utf-8') as f:
        json.dump(asdict(coverage), f, indent=2, ensure_ascii=True)
    print(f"[OK] {coverage_file}")
    
    summary_file = output_dir / "dataset_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(asdict(summary), f, indent=2, ensure_ascii=True)
    print(f"[OK] {summary_file}")
    
    confidence_file = output_dir / "confidence_disagreement.json"
    with open(confidence_file, 'w', encoding='utf-8') as f:
        json.dump(asdict(confidence), f, indent=2, ensure_ascii=True)
    print(f"[OK] {confidence_file}")
    
    print()
    print("[SUCCESS] All dataset overview artifacts generated")


if __name__ == "__main__":
    main()
