#!/usr/bin/env python3
"""
Test script for Phase 4E-1 semantic artifacts.
Verifies that all three JSON files are created correctly.
"""

import json
from pathlib import Path


def test_file_exists(file_path: Path, name: str) -> bool:
    """Test that file exists."""
    if not file_path.exists():
        print(f"❌ FAIL: {name} not found at {file_path}")
        return False
    print(f"✓ PASS: {name} exists")
    return True


def test_valid_json(file_path: Path, name: str):
    """Test that file is valid JSON."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"✓ PASS: {name} is valid JSON")
        return data
    except json.JSONDecodeError as e:
        print(f"❌ FAIL: {name} is not valid JSON: {e}")
        return None


def test_coverage_table(data: dict) -> bool:
    """Test coverage_table.json structure."""
    print("\n--- Testing coverage_table.json ---")
    
    if not data:
        return False
    
    # Check required top-level keys
    required_keys = ["generated_at_utc", "total_entries", "feature_groups"]
    for key in required_keys:
        if key not in data:
            print(f"❌ FAIL: Missing key '{key}'")
            return False
    
    print(f"✓ PASS: All required top-level keys present")
    
    # Check feature groups
    groups = data["feature_groups"]
    if not isinstance(groups, list):
        print(f"❌ FAIL: 'feature_groups' is not a list")
        return False
    
    required_groups = [
        "market_microstructure",
        "liquidity",
        "order_book_depth",
        "spot_prices",
        "lexicon_sentiment",
        "ai_sentiment",
        "activity_and_silence",
        "platform_engagement",
        "author_stats"
    ]
    
    found_groups = {g["group"] for g in groups}
    missing_groups = set(required_groups) - found_groups
    if missing_groups:
        print(f"❌ FAIL: Missing feature groups: {missing_groups}")
        return False
    
    print(f"✓ PASS: All required feature groups present ({len(groups)} groups)")
    
    # Check no empty example metrics
    empty_metrics = []
    for group in groups:
        if not group.get("example_metric_label") or group.get("example_metric_value") is None:
            # Allow string explanations for 0% groups
            if group["present_rate_pct"] == 0.0 and isinstance(group.get("example_metric_value"), str):
                continue
            if group.get("example_metric_label") != "N/A":
                empty_metrics.append(group["group"])
    
    if empty_metrics:
        print(f"❌ FAIL: Groups with empty example metrics: {empty_metrics}")
        return False
    
    print(f"✓ PASS: No empty example metrics")
    
    return True


def test_dataset_summary(data: dict) -> bool:
    """Test dataset_summary.json structure."""
    print("\n--- Testing dataset_summary.json ---")
    
    if not data:
        return False
    
    # Check required sections
    required_sections = ["scale", "posts_scored", "sentiment_buckets", "activity_regimes"]
    for section in required_sections:
        if section not in data:
            print(f"❌ FAIL: Missing section '{section}'")
            return False
    
    print(f"✓ PASS: All required sections present")
    
    # Check scale
    scale = data["scale"]
    scale_keys = ["days_running", "total_usable_entries", "avg_entries_per_day", "distinct_symbols"]
    for key in scale_keys:
        if key not in scale:
            print(f"❌ FAIL: Missing scale key '{key}'")
            return False
    
    print(f"✓ PASS: Scale section valid")
    
    # Check sentiment buckets
    buckets = data["sentiment_buckets"]["buckets"]
    if not isinstance(buckets, list):
        print(f"❌ FAIL: sentiment_buckets.buckets is not a list")
        return False
    
    print(f"✓ PASS: Sentiment buckets section valid ({len(buckets)} buckets)")
    
    # Check activity regimes
    activity_bins = data["activity_regimes"]["bins"]
    if not isinstance(activity_bins, list):
        print(f"❌ FAIL: activity_regimes.bins is not a list")
        return False
    
    if len(activity_bins) < 3:
        print(f"❌ FAIL: Activity regimes has fewer than 3 bins (found {len(activity_bins)})")
        return False
    
    print(f"✓ PASS: Activity regimes has {len(activity_bins)} bins (>= 3)")
    
    # Check volume-based (not boolean)
    for bin_data in activity_bins:
        if "label" not in bin_data or "min" not in bin_data or "max" not in bin_data:
            print(f"❌ FAIL: Activity bin missing required keys")
            return False
    
    print(f"✓ PASS: Activity regimes are volume-based (not boolean)")
    
    return True


def test_symbol_table(data: dict) -> bool:
    """Test symbol_table.json structure."""
    print("\n--- Testing symbol_table.json ---")
    
    if not data:
        return False
    
    # Check required keys
    if "symbols" not in data:
        print(f"❌ FAIL: Missing 'symbols' key")
        return False
    
    symbols = data["symbols"]
    if not isinstance(symbols, list):
        print(f"❌ FAIL: 'symbols' is not a list")
        return False
    
    if len(symbols) == 0:
        print(f"❌ FAIL: Symbol table is empty")
        return False
    
    print(f"✓ PASS: Symbol table has {len(symbols)} symbols")
    
    # Check first symbol structure
    first_symbol = symbols[0]
    required_keys = ["symbol", "sessions", "first_seen", "last_seen", "sentiment", "market_context"]
    for key in required_keys:
        if key not in first_symbol:
            print(f"❌ FAIL: Missing key '{key}' in symbol entry")
            return False
    
    # Check sentiment sub-keys
    sentiment = first_symbol["sentiment"]
    sentiment_keys = [
        "median_posts_last_cycle",
        "p90_posts_last_cycle",
        "pct_silent_sessions",
        "median_hybrid_mean_score",
        "p10_hybrid_mean_score",
        "p90_hybrid_mean_score"
    ]
    for key in sentiment_keys:
        if key not in sentiment:
            print(f"❌ FAIL: Missing sentiment key '{key}'")
            return False
    
    print(f"✓ PASS: Symbol table structure valid")
    
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("Phase 4E-1 Semantic Artifacts Test Suite")
    print("=" * 60)
    
    # Determine output directory
    import os
    output_dir = Path(os.getenv("OUTPUT_DIR", "public/data"))
    
    print(f"\nOutput directory: {output_dir}")
    
    # Test files
    coverage_path = output_dir / "coverage_table.json"
    summary_path = output_dir / "dataset_summary.json"
    symbol_path = output_dir / "symbol_table.json"
    
    all_pass = True
    
    # Test coverage_table.json
    if test_file_exists(coverage_path, "coverage_table.json"):
        coverage_data = test_valid_json(coverage_path, "coverage_table.json")
        if coverage_data:
            if not test_coverage_table(coverage_data):
                all_pass = False
        else:
            all_pass = False
    else:
        all_pass = False
    
    # Test dataset_summary.json
    if test_file_exists(summary_path, "dataset_summary.json"):
        summary_data = test_valid_json(summary_path, "dataset_summary.json")
        if summary_data:
            if not test_dataset_summary(summary_data):
                all_pass = False
        else:
            all_pass = False
    else:
        all_pass = False
    
    # Test symbol_table.json
    if test_file_exists(symbol_path, "symbol_table.json"):
        symbol_data = test_valid_json(symbol_path, "symbol_table.json")
        if symbol_data:
            if not test_symbol_table(symbol_data):
                all_pass = False
        else:
            all_pass = False
    else:
        all_pass = False
    
    # Final result
    print("\n" + "=" * 60)
    if all_pass:
        print("✅ ALL TESTS PASSED")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit(main())
