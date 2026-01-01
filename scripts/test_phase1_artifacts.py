#!/usr/bin/env python3
"""
Test script for Phase 1 dataset artifacts.
Validates structure, content, and invariants.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List


def test_artifact_exists(artifact_path: Path, artifact_name: str) -> bool:
    """Test that artifact file exists."""
    if not artifact_path.exists():
        print(f"[FAIL] {artifact_name} does not exist: {artifact_path}")
        return False
    print(f"[OK] {artifact_name} exists")
    return True


def test_valid_json(artifact_path: Path, artifact_name: str) -> tuple[bool, Any]:
    """Test that artifact is valid JSON."""
    try:
        with open(artifact_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"[OK] {artifact_name} is valid JSON")
        return True, data
    except json.JSONDecodeError as e:
        print(f"[FAIL] {artifact_name} is not valid JSON: {e}")
        return False, None


def test_no_unicode(artifact_path: Path, artifact_name: str) -> bool:
    """Test that artifact contains no unicode characters."""
    with open(artifact_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for non-ASCII characters
    non_ascii = [c for c in content if ord(c) > 127]
    if non_ascii:
        print(f"[FAIL] {artifact_name} contains unicode characters: {set(non_ascii)}")
        return False
    print(f"[OK] {artifact_name} contains no unicode characters")
    return True


def test_coverage_table(data: Dict[str, Any]) -> bool:
    """Test coverage_table.json structure and content."""
    print("\nTesting coverage_table.json structure...")
    
    all_pass = True
    
    # Check required fields
    required_fields = ["generated_at", "total_entries_scanned", "feature_groups", "notes"]
    for field in required_fields:
        if field not in data:
            print(f"[FAIL] Missing required field: {field}")
            all_pass = False
        else:
            print(f"[OK] Field '{field}' present")
    
    # Check feature_groups is a list
    if not isinstance(data.get("feature_groups"), list):
        print("[FAIL] feature_groups is not a list")
        return False
    
    # Check no empty feature groups
    if len(data["feature_groups"]) == 0:
        print("[FAIL] feature_groups is empty")
        all_pass = False
    else:
        print(f"[OK] feature_groups has {len(data['feature_groups'])} groups")
    
    # Check each feature group structure
    for idx, group in enumerate(data["feature_groups"]):
        required_group_fields = [
            "label", "description", "availability_pct",
            "example_metric_label", "example_metric_value"
        ]
        for field in required_group_fields:
            if field not in group:
                print(f"[FAIL] Feature group {idx} missing field: {field}")
                all_pass = False
        
        # Check no "0%" availability
        if group.get("availability_pct") == 0:
            print(f"[FAIL] Feature group {idx} has 0% availability")
            all_pass = False
        
        # Check no placeholder text
        for field in ["label", "description", "example_metric_label", "example_metric_value"]:
            value = group.get(field, "")
            if isinstance(value, str):
                if "TODO" in value.upper() or "PLACEHOLDER" in value.upper() or "TBD" in value.upper():
                    print(f"[FAIL] Feature group {idx} field '{field}' contains placeholder: {value}")
                    all_pass = False
    
    if all_pass:
        print("[OK] coverage_table.json structure valid")
    
    return all_pass


def test_activity_stats(data: Dict[str, Any]) -> bool:
    """Test activity_vs_silence_stats.json structure and content."""
    print("\nTesting activity_vs_silence_stats.json structure...")
    
    all_pass = True
    
    # Check required fields
    required_fields = ["generated_at", "total_entries_analyzed", "bins", "notes"]
    for field in required_fields:
        if field not in data:
            print(f"[FAIL] Missing required field: {field}")
            all_pass = False
        else:
            print(f"[OK] Field '{field}' present")
    
    # Check bins is a list
    if not isinstance(data.get("bins"), list):
        print("[FAIL] bins is not a list")
        return False
    
    # Check no empty bins
    if len(data["bins"]) == 0:
        print("[FAIL] bins is empty")
        all_pass = False
    else:
        print(f"[OK] bins has {len(data['bins'])} bins")
    
    # Check each bin structure
    for idx, bin_data in enumerate(data["bins"]):
        required_bin_fields = ["label", "posts_range", "n_entries"]
        for field in required_bin_fields:
            if field not in bin_data:
                print(f"[FAIL] Bin {idx} missing required field: {field}")
                all_pass = False
        
        # Optional fields should not be null if present
        for field in ["median_spread_bps"]:
            if field in bin_data and bin_data[field] is None:
                print(f"[FAIL] Bin {idx} field '{field}' is None (should be omitted)")
                all_pass = False
    
    if all_pass:
        print("[OK] activity_vs_silence_stats.json structure valid")
    
    return all_pass


def test_sampling_density_stats(data: Dict[str, Any]) -> bool:
    """Test sampling_density_stats.json structure and content."""
    print("\nTesting sampling_density_stats.json structure...")
    
    all_pass = True
    
    # Check required fields
    required_fields = [
        "generated_at", "total_entries_analyzed",
        "median_samples_per_session", "p10_samples", "p90_samples",
        "distribution", "notes"
    ]
    for field in required_fields:
        if field not in data:
            print(f"[FAIL] Missing required field: {field}")
            all_pass = False
        else:
            print(f"[OK] Field '{field}' present")
    
    # Check distribution is a list
    if not isinstance(data.get("distribution"), list):
        print("[FAIL] distribution is not a list")
        return False
    
    # Check distribution not empty
    if len(data["distribution"]) == 0:
        print("[FAIL] distribution is empty")
        all_pass = False
    else:
        print(f"[OK] distribution has {len(data['distribution'])} buckets")
    
    # Check each distribution bucket
    for idx, bucket in enumerate(data["distribution"]):
        required_bucket_fields = ["bucket", "count", "percentage"]
        for field in required_bucket_fields:
            if field not in bucket:
                print(f"[FAIL] Distribution bucket {idx} missing field: {field}")
                all_pass = False
    
    # Check percentile ordering
    if data.get("p10_samples", 0) > data.get("median_samples_per_session", 0):
        print("[FAIL] P10 should be <= median")
        all_pass = False
    if data.get("median_samples_per_session", 0) > data.get("p90_samples", 0):
        print("[FAIL] Median should be <= P90")
        all_pass = False
    
    if all_pass:
        print("[OK] sampling_density_stats.json structure valid")
    
    return all_pass


def test_cross_file_invariants(
    coverage_data: Dict[str, Any],
    activity_data: Dict[str, Any],
    sampling_data: Dict[str, Any]
) -> bool:
    """Test invariants across multiple artifacts."""
    print("\nTesting cross-file invariants...")
    
    all_pass = True
    
    # All should have same or compatible entry counts (if same scan)
    cov_entries = coverage_data.get("total_entries_scanned", 0)
    act_entries = activity_data.get("total_entries_analyzed", 0)
    samp_entries = sampling_data.get("total_entries_analyzed", 0)
    
    print(f"[INFO] Coverage entries: {cov_entries}")
    print(f"[INFO] Activity entries: {act_entries}")
    print(f"[INFO] Sampling entries: {samp_entries}")
    
    # They should match if full scan, but may differ in partial scans
    if cov_entries == act_entries == samp_entries:
        print("[OK] All artifacts scanned same number of entries")
    else:
        print("[WARN] Artifacts scanned different numbers of entries (OK for partial scans)")
    
    return all_pass


def main():
    """Main test runner."""
    script_dir = Path(__file__).parent
    site_root = script_dir.parent
    data_dir = site_root / "public" / "data"
    
    print("=" * 70)
    print("Phase 1 Artifact Tests")
    print("=" * 70)
    print(f"Data directory: {data_dir}")
    print()
    
    all_tests_pass = True
    
    # Test 1: coverage_table.json
    print("=" * 70)
    print("TEST 1: coverage_table.json")
    print("=" * 70)
    coverage_path = data_dir / "coverage_table.json"
    if test_artifact_exists(coverage_path, "coverage_table.json"):
        if test_no_unicode(coverage_path, "coverage_table.json"):
            success, coverage_data = test_valid_json(coverage_path, "coverage_table.json")
            if success:
                if not test_coverage_table(coverage_data):
                    all_tests_pass = False
            else:
                all_tests_pass = False
        else:
            all_tests_pass = False
    else:
        all_tests_pass = False
    
    # Test 2: activity_vs_silence_stats.json
    print("\n" + "=" * 70)
    print("TEST 2: activity_vs_silence_stats.json")
    print("=" * 70)
    activity_path = data_dir / "activity_vs_silence_stats.json"
    if test_artifact_exists(activity_path, "activity_vs_silence_stats.json"):
        if test_no_unicode(activity_path, "activity_vs_silence_stats.json"):
            success, activity_data = test_valid_json(activity_path, "activity_vs_silence_stats.json")
            if success:
                if not test_activity_stats(activity_data):
                    all_tests_pass = False
            else:
                all_tests_pass = False
        else:
            all_tests_pass = False
    else:
        all_tests_pass = False
    
    # Test 3: sampling_density_stats.json
    print("\n" + "=" * 70)
    print("TEST 3: sampling_density_stats.json")
    print("=" * 70)
    sampling_path = data_dir / "sampling_density_stats.json"
    if test_artifact_exists(sampling_path, "sampling_density_stats.json"):
        if test_no_unicode(sampling_path, "sampling_density_stats.json"):
            success, sampling_data = test_valid_json(sampling_path, "sampling_density_stats.json")
            if success:
                if not test_sampling_density_stats(sampling_data):
                    all_tests_pass = False
            else:
                all_tests_pass = False
        else:
            all_tests_pass = False
    else:
        all_tests_pass = False
    
    # Test 4: Cross-file invariants
    print("\n" + "=" * 70)
    print("TEST 4: Cross-file invariants")
    print("=" * 70)
    if 'coverage_data' in locals() and 'activity_data' in locals() and 'sampling_data' in locals():
        if not test_cross_file_invariants(coverage_data, activity_data, sampling_data):
            all_tests_pass = False
    else:
        print("[SKIP] Cannot test cross-file invariants (some artifacts failed to load)")
    
    # Final report
    print("\n" + "=" * 70)
    print("FINAL REPORT")
    print("=" * 70)
    if all_tests_pass:
        print("[SUCCESS] All tests passed!")
        return 0
    else:
        print("[FAILURE] Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
