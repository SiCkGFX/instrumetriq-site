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
        print(f"[FAIL] FAIL: {name} not found at {file_path}")
        return False
    print(f"[PASS] PASS: {name} exists")
    return True


def test_valid_json(file_path: Path, name: str):
    """Test that file is valid JSON."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"[PASS] PASS: {name} is valid JSON")
        return data
    except json.JSONDecodeError as e:
        print(f"[FAIL] FAIL: {name} is not valid JSON: {e}")
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
            print(f"[FAIL] FAIL: Missing key '{key}'")
            return False
    
    print(f"[PASS] PASS: All required top-level keys present")
    
    # Check feature groups
    groups = data["feature_groups"]
    if not isinstance(groups, list):
        print(f"[FAIL] FAIL: 'feature_groups' is not a list")
        return False
    
    # Only verify groups that should exist (verified fields only)
    required_groups = [
        "market_microstructure",
        "spot_prices",
        "activity_and_silence",
    ]
    
    found_groups = {g["group"] for g in groups}
    missing_groups = set(required_groups) - found_groups
    if missing_groups:
        print(f"[FAIL] FAIL: Missing feature groups: {missing_groups}")
        return False
    
    print(f"[PASS] PASS: All required feature groups present ({len(groups)} groups)")
    
    # Check no empty example metrics
    empty_metrics = []
    for group in groups:
        if not group.get("example_metric_label") or group.get("example_metric_value") is None:
            # Allow string explanations for unavailable groups
            if group["present_rate_pct"] == 0.0 and isinstance(group.get("example_metric_value"), str):
                continue
            if group.get("example_metric_label") != "N/A":
                empty_metrics.append(group["group"])
    
    if empty_metrics:
        print(f"[FAIL] FAIL: Groups with empty example metrics: {empty_metrics}")
        return False
    
    print(f"[PASS] PASS: No empty example metrics")
    
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
            print(f"[FAIL] FAIL: Missing section '{section}'")
            return False
    
    print(f"[PASS] PASS: All required sections present")
    
    # Check scale
    scale = data["scale"]
    scale_keys = ["days_running", "total_usable_entries", "avg_entries_per_day", "distinct_symbols"]
    for key in scale_keys:
        if key not in scale:
            print(f"[FAIL] FAIL: Missing scale key '{key}'")
            return False
    
    print(f"[PASS] PASS: Scale section valid")
    
    # Check sentiment buckets
    buckets = data["sentiment_buckets"]["buckets"]
    if not isinstance(buckets, list):
        print(f"[FAIL] FAIL: sentiment_buckets.buckets is not a list")
        return False
    
    print(f"[PASS] PASS: Sentiment buckets section valid ({len(buckets)} buckets)")
    
    # Check activity regimes
    activity_bins = data["activity_regimes"]["bins"]
    if not isinstance(activity_bins, list):
        print(f"[FAIL] FAIL: activity_regimes.bins is not a list")
        return False
    
    if len(activity_bins) < 3:
        print(f"[FAIL] FAIL: Activity regimes has fewer than 3 bins (found {len(activity_bins)})")
        return False
    
    print(f"[PASS] PASS: Activity regimes has {len(activity_bins)} bins (>= 3)")
    
    # Check volume-based (not boolean)
    for bin_data in activity_bins:
        if "label" not in bin_data or "min" not in bin_data or "max" not in bin_data:
            print(f"[FAIL] FAIL: Activity bin missing required keys")
            return False
    
    print(f"[PASS] PASS: Activity regimes are volume-based (not boolean)")
    
    return True


def test_symbol_table(data: dict) -> bool:
    """Test symbol_table.json structure."""
    print("\n--- Testing symbol_table.json ---")
    
    if not data:
        return False
    
    # Check required keys
    if "symbols" not in data:
        print(f"[FAIL] FAIL: Missing 'symbols' key")
        return False
    
    symbols = data["symbols"]
    if not isinstance(symbols, list):
        print(f"[FAIL] FAIL: 'symbols' is not a list")
        return False
    
    if len(symbols) == 0:
        print(f"[FAIL] FAIL: Symbol table is empty")
        return False
    
    print(f"[PASS] PASS: Symbol table has {len(symbols)} symbols")
    
    # Check first symbol structure (verified fields only)
    first_symbol = symbols[0]
    required_keys = ["symbol", "sessions", "activity", "market_context"]
    for key in required_keys:
        if key not in first_symbol:
            print(f"[FAIL] FAIL: Missing key '{key}' in symbol entry")
            return False
    
    # Check activity sub-keys
    activity = first_symbol["activity"]
    activity_keys = [
        "median_posts_last_cycle",
        "p90_posts_last_cycle",
        "silence_rate_pct",
    ]
    for key in activity_keys:
        if key not in activity:
            print(f"[FAIL] FAIL: Missing activity key '{key}'")
            return False
    
    print(f"[PASS] PASS: Symbol table structure valid (verified fields only)")
    
    return True


def test_cross_file_consistency(coverage: dict, summary: dict, symbols: dict) -> bool:
    """Test cross-file consistency invariants."""
    print("\n--- Testing cross-file consistency ---")
    
    all_pass = True
    
    # Symbol counts must match
    summary_symbols = summary["scale"]["distinct_symbols"]
    symbol_table_total = symbols["total_symbols"]
    symbol_table_count = len(symbols["symbols"])
    
    if summary_symbols == symbol_table_total == symbol_table_count:
        print(f"[PASS] PASS: Symbol counts match ({summary_symbols})")
    else:
        print(f"[FAIL] FAIL: Symbol counts mismatch - summary={summary_symbols}, symbol_table.total={symbol_table_total}, symbol_table.len={symbol_table_count}")
        all_pass = False
    
    # Activity regime bins sum must equal total usable
    regimes = summary.get("activity_regimes", {})
    bins = regimes.get("bins", [])
    if bins:
        bins_sum = sum(b["n_entries"] for b in bins)
        summary_usable = summary["scale"]["total_usable_entries"]
        
        if bins_sum == summary_usable:
            print(f"[PASS] PASS: Activity bins sum matches total ({bins_sum})")
        else:
            print(f"[FAIL] FAIL: Activity bins sum mismatch - bins_sum={bins_sum}, total={summary_usable}")
            all_pass = False
    
    # Coverage total must match summary total
    coverage_total = coverage["total_entries"]
    summary_usable = summary["scale"]["total_usable_entries"]
    
    if coverage_total == summary_usable:
        print(f"[PASS] PASS: Coverage total matches summary ({coverage_total})")
    else:
        print(f"[FAIL] FAIL: Coverage total mismatch - coverage={coverage_total}, summary={summary_usable}")
        all_pass = False
    
    # Check partial_scan consistency
    is_partial_coverage = coverage.get("partial_scan", False)
    is_partial_summary = summary.get("partial_scan", False)
    
    if is_partial_coverage == is_partial_summary:
        if is_partial_coverage:
            print(f"[PASS] PASS: Both artifacts marked as partial_scan")
        else:
            print(f"[PASS] PASS: Neither artifact marked as partial_scan")
    else:
        print(f"[FAIL] FAIL: Partial scan mismatch - coverage={is_partial_coverage}, summary={is_partial_summary}")
        all_pass = False
    
    return all_pass


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
    coverage_data = None
    summary_data = None
    symbol_data = None
    
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
    
    # Test cross-file consistency (only if all files loaded)
    if coverage_data and summary_data and symbol_data:
        if not test_cross_file_consistency(coverage_data, summary_data, symbol_data):
            all_pass = False
    
    # Final result
    print("\n" + "=" * 60)
    if all_pass:
        print("[SUCCESS] ALL TESTS PASSED")
        return 0
    else:
        print("[FAIL] SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit(main())

