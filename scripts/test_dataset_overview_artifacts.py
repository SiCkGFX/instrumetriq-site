#!/usr/bin/env python3
"""
Test Dataset Overview Artifacts
Validates structure, content, and invariants for dataset overview artifacts.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any
import math


def test_artifact_exists(artifact_path: Path, artifact_name: str) -> bool:
    """Test that artifact file exists."""
    if not artifact_path.exists():
        print(f"[FAIL] {artifact_name} does not exist: {artifact_path}")
        return False
    print(f"[OK] {artifact_name} exists")
    return True


def test_valid_json(artifact_path: Path, artifact_name: str) -> tuple:
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
    required_fields = ["generated_at_utc", "total_usable_v7_entries", "feature_groups", "notes"]
    for field in required_fields:
        if field not in data:
            print(f"[FAIL] Missing required field: {field}")
            all_pass = False
        else:
            print(f"[OK] Field '{field}' present")
    
    # Check total_usable_v7_entries is valid
    total_entries = data.get("total_usable_v7_entries", 0)
    if total_entries <= 0:
        print(f"[FAIL] total_usable_v7_entries must be > 0, got {total_entries}")
        all_pass = False
    else:
        print(f"[OK] total_usable_v7_entries = {total_entries}")
    
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
            "group_id", "label", "note", "present_rate_pct",
            "example_metric_label", "example_metric_value"
        ]
        for field in required_group_fields:
            if field not in group:
                print(f"[FAIL] Feature group {idx} missing field: {field}")
                all_pass = False
        
        # Check NO NaN present_rate
        present_rate = group.get("present_rate_pct")
        if present_rate is not None:
            if math.isnan(present_rate):
                print(f"[FAIL] Feature group {idx} has NaN present_rate_pct")
                all_pass = False
        
        # Check NO 0% present rate shown
        if present_rate == 0:
            print(f"[FAIL] Feature group {idx} has 0% present rate (should not be shown)")
            all_pass = False
        
        # Check NO empty example_metric_value
        example_val = group.get("example_metric_value", "")
        if not example_val or example_val.strip() == "":
            print(f"[FAIL] Feature group {idx} has empty example_metric_value")
            all_pass = False
        
        # Check no placeholder text
        for field in ["label", "note", "example_metric_label", "example_metric_value"]:
            value = group.get(field, "")
            if isinstance(value, str):
                if any(x in value.upper() for x in ["TODO", "PLACEHOLDER", "TBD", "NOT AVAILABLE YET"]):
                    print(f"[FAIL] Feature group {idx} field '{field}' contains placeholder: {value}")
                    all_pass = False
    
    if all_pass:
        print("[OK] coverage_table.json structure valid")
    
    return all_pass


def test_dataset_summary(data: Dict[str, Any]) -> bool:
    """Test dataset_summary.json structure and content."""
    print("\nTesting dataset_summary.json structure...")
    
    all_pass = True
    
    # Check required fields
    required_fields = ["generated_at_utc", "scale", "posts_scored", "sentiment_distribution", "confidence_disagreement"]
    for field in required_fields:
        if field not in data:
            print(f"[FAIL] Missing required field: {field}")
            all_pass = False
        else:
            print(f"[OK] Field '{field}' present")
    
    # Check scale structure
    scale = data.get("scale", {})
    required_scale_fields = ["days_running", "total_usable_entries", "avg_entries_per_day", "distinct_symbols"]
    for field in required_scale_fields:
        if field not in scale:
            print(f"[FAIL] scale missing field: {field}")
            all_pass = False
        else:
            val = scale[field]
            if not isinstance(val, int) or val <= 0:
                print(f"[FAIL] scale.{field} must be int > 0, got {val}")
                all_pass = False
    
    if all_pass:
        print(f"[OK] scale: {scale['days_running']} days, {scale['total_usable_entries']} entries")
    
    # Check posts_scored structure
    posts_scored = data.get("posts_scored", {})
    if "total_posts" not in posts_scored or "from_entries" not in posts_scored:
        print("[FAIL] posts_scored missing required fields")
        all_pass = False
    else:
        print(f"[OK] posts_scored: {posts_scored['total_posts']} posts from {posts_scored['from_entries']} entries")
    
    # Check sentiment_distribution availability
    sent_dist = data.get("sentiment_distribution", {})
    if "available" not in sent_dist:
        print("[FAIL] sentiment_distribution missing 'available' field")
        all_pass = False
    else:
        available = sent_dist["available"]
        print(f"[OK] sentiment_distribution.available = {available}")
        
        if not available:
            if "reason_unavailable" not in sent_dist:
                print("[FAIL] sentiment_distribution.available=false but no reason_unavailable")
                all_pass = False
            else:
                reason = sent_dist["reason_unavailable"]
                if not reason or reason.strip() == "":
                    print("[FAIL] sentiment_distribution.reason_unavailable is empty")
                    all_pass = False
                else:
                    print(f"[OK] sentiment_distribution.reason_unavailable: {reason[:60]}...")
    
    # Check confidence_disagreement availability
    conf_dis = data.get("confidence_disagreement", {})
    if "available" not in conf_dis:
        print("[FAIL] confidence_disagreement missing 'available' field")
        all_pass = False
    else:
        available = conf_dis["available"]
        print(f"[OK] confidence_disagreement.available = {available}")
        
        if not available:
            if "reason_unavailable" not in conf_dis:
                print("[FAIL] confidence_disagreement.available=false but no reason_unavailable")
                all_pass = False
            else:
                reason = conf_dis["reason_unavailable"]
                if not reason or reason.strip() == "":
                    print("[FAIL] confidence_disagreement.reason_unavailable is empty")
                    all_pass = False
                else:
                    print(f"[OK] confidence_disagreement.reason_unavailable: {reason[:60]}...")
    
    if all_pass:
        print("[OK] dataset_summary.json structure valid")
    
    return all_pass


def test_confidence_disagreement(data: Dict[str, Any]) -> bool:
    """Test confidence_disagreement.json structure and content."""
    print("\nTesting confidence_disagreement.json structure...")
    
    all_pass = True
    
    # Check required fields
    required_fields = ["generated_at_utc", "available"]
    for field in required_fields:
        if field not in data:
            print(f"[FAIL] Missing required field: {field}")
            all_pass = False
        else:
            print(f"[OK] Field '{field}' present")
    
    available = data.get("available", False)
    print(f"[OK] available = {available}")
    
    if available:
        # If available, must have bins
        if "bins" not in data:
            print("[FAIL] available=true but 'bins' field missing")
            all_pass = False
        elif data["bins"] is None or len(data["bins"]) == 0:
            print("[FAIL] available=true but bins is null or empty")
            all_pass = False
        else:
            print(f"[OK] bins has {len(data['bins'])} entries")
    else:
        # If not available, must have reason
        if "reason_unavailable" not in data:
            print("[FAIL] available=false but no reason_unavailable")
            all_pass = False
        else:
            reason = data["reason_unavailable"]
            if not reason or reason.strip() == "":
                print("[FAIL] reason_unavailable is empty")
                all_pass = False
            else:
                print(f"[OK] reason_unavailable: {reason[:60]}...")
    
    if all_pass:
        print("[OK] confidence_disagreement.json structure valid")
    
    return all_pass


def test_cross_artifact_invariants(
    coverage_data: Dict[str, Any],
    summary_data: Dict[str, Any]
) -> bool:
    """Test invariants across multiple artifacts."""
    print("\nTesting cross-artifact invariants...")
    
    all_pass = True
    
    # Total entries should match
    cov_total = coverage_data.get("total_usable_v7_entries", 0)
    sum_total = summary_data.get("scale", {}).get("total_usable_entries", 0)
    
    print(f"[INFO] Coverage total: {cov_total}")
    print(f"[INFO] Summary total: {sum_total}")
    
    if cov_total != sum_total:
        print(f"[FAIL] Entry counts do not match: coverage={cov_total}, summary={sum_total}")
        all_pass = False
    else:
        print("[OK] Entry counts match across artifacts")
    
    return all_pass


def main():
    """Main test runner."""
    script_dir = Path(__file__).parent
    site_root = script_dir.parent
    data_dir = site_root / "public" / "data"
    
    print("=" * 70)
    print("Dataset Overview Artifacts Tests")
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
    
    # Test 2: dataset_summary.json
    print("\n" + "=" * 70)
    print("TEST 2: dataset_summary.json")
    print("=" * 70)
    summary_path = data_dir / "dataset_summary.json"
    if test_artifact_exists(summary_path, "dataset_summary.json"):
        if test_no_unicode(summary_path, "dataset_summary.json"):
            success, summary_data = test_valid_json(summary_path, "dataset_summary.json")
            if success:
                if not test_dataset_summary(summary_data):
                    all_tests_pass = False
            else:
                all_tests_pass = False
        else:
            all_tests_pass = False
    else:
        all_tests_pass = False
    
    # Test 3: confidence_disagreement.json
    print("\n" + "=" * 70)
    print("TEST 3: confidence_disagreement.json")
    print("=" * 70)
    confidence_path = data_dir / "confidence_disagreement.json"
    if test_artifact_exists(confidence_path, "confidence_disagreement.json"):
        if test_no_unicode(confidence_path, "confidence_disagreement.json"):
            success, confidence_data = test_valid_json(confidence_path, "confidence_disagreement.json")
            if success:
                if not test_confidence_disagreement(confidence_data):
                    all_tests_pass = False
            else:
                all_tests_pass = False
        else:
            all_tests_pass = False
    else:
        all_tests_pass = False
    
    # Test 4: Cross-artifact invariants
    print("\n" + "=" * 70)
    print("TEST 4: Cross-artifact invariants")
    print("=" * 70)
    if 'coverage_data' in locals() and 'summary_data' in locals():
        if not test_cross_artifact_invariants(coverage_data, summary_data):
            all_tests_pass = False
    else:
        print("[SKIP] Cannot test cross-artifact invariants (some artifacts failed to load)")
    
    # Final report
    print("\n" + "=" * 70)
    print("FINAL REPORT")
    print("=" * 70)
    if all_tests_pass:
        print("[SUCCESS] All tests passed!")
        print()
        print("VERIFIED:")
        print("- No NaN present rates")
        print("- No 0% present rate rows shown")
        print("- No empty example_metric_value")
        print("- Proper availability flags with verified reasons")
        print("- Entry counts match across artifacts")
        return 0
    else:
        print("[FAILURE] Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
