#!/usr/bin/env python3
"""
Test Coverage Table (Phase 1B-fix)

Validates that public/data/coverage_table.json meets all requirements:
- NO 0% rows
- NO empty examples
- ALL examples are REAL numeric values (not descriptive placeholders)
- All paths exist in field_coverage_report.json
- Valid group keys only
"""

import json
import re
import sys
from pathlib import Path


def is_numeric_example(example):
    """Check if example is a numeric value or numeric-formatted string."""
    if not example or example == '':
        return False
    
    example = str(example).strip()
    
    # Pattern 1: Simple number (int or float): "42", "3.14", "-0.5"
    if re.match(r'^-?\d+(\.\d+)?$', example):
        return True
    
    # Pattern 2: Range: "0.5 to 1.2", "10-20"
    if re.match(r'^-?\d+(\.\d+)?\s*(to|-)\s*-?\d+(\.\d+)?$', example):
        return True
    
    # Pattern 3: Number with suffix: "42K", "3.5%", "15.2%"
    if re.match(r'^-?\d+(\.\d+)?[KMB%]$', example):
        return True
    
    # Pattern 4: Percentage value: "15.5%"
    if re.match(r'^-?\d+(\.\d+)?%$', example):
        return True
    
    return False


def test_coverage_table():
    """Run all validation tests."""
    instrumetriq_root = Path(__file__).resolve().parent.parent
    coverage_table_file = instrumetriq_root / 'public' / 'data' / 'coverage_table.json'
    coverage_report_file = instrumetriq_root / 'data' / 'field_coverage_report.json'
    
    print("=" * 70)
    print("Testing Coverage Table")
    print("=" * 70)
    print()
    
    errors = []
    warnings = []
    
    # Load coverage table
    print("[TEST 1] Loading coverage_table.json...")
    try:
        with open(coverage_table_file, 'r', encoding='utf-8') as f:
            table = json.load(f)
        print("  PASS: Valid JSON")
    except Exception as e:
        errors.append(f"Invalid JSON: {e}")
        print(f"  FAIL: {e}")
        return 1
    
    # Load coverage report for validation
    print("[TEST 2] Loading field_coverage_report.json...")
    with open(coverage_report_file, 'r', encoding='utf-8') as f:
        coverage = json.load(f)
    
    # Build coverage lookup
    coverage_lookup = set()
    for group, fields in coverage['field_groups'].items():
        for path in fields.keys():
            coverage_lookup.add(path)
    print(f"  OK: {len(coverage_lookup)} paths available")
    
    # Test 3: Non-empty rows
    print("[TEST 3] Check rows is non-empty...")
    if 'rows' not in table or len(table['rows']) == 0:
        errors.append("rows is empty or missing")
        print("  FAIL: No rows found")
    else:
        print(f"  PASS: {len(table['rows'])} rows")
    
    # Test 4: No 0% rows
    print("[TEST 4] Check no row has 0% presence...")
    zero_pct_rows = [r for r in table.get('rows', []) if r.get('present_pct', 0) == 0]
    if zero_pct_rows:
        errors.append(f"Found {len(zero_pct_rows)} rows with 0% presence")
        print(f"  FAIL: {[r['label'] for r in zero_pct_rows]}")
    else:
        print("  PASS: No 0% rows")
    
    # Test 5: No 0% checks
    print("[TEST 5] Check no check has 0% presence...")
    zero_checks = []
    for row in table.get('rows', []):
        for check in row.get('checks', []):
            if check.get('present_pct', 0) == 0:
                zero_checks.append(f"{row['label']}: {check['label']}")
    
    if zero_checks:
        errors.append(f"Found {len(zero_checks)} checks with 0% presence")
        print(f"  FAIL: {zero_checks[:5]}")
    else:
        print("  PASS: No 0% checks")
    
    # Test 6: No empty examples
    print("[TEST 6] Check no empty examples...")
    empty_examples = []
    for row in table.get('rows', []):
        for check in row.get('checks', []):
            if not check.get('example') or check.get('example') == '':
                empty_examples.append(f"{row['label']}: {check['label']}")
    
    if empty_examples:
        errors.append(f"Found {len(empty_examples)} empty examples")
        print(f"  FAIL: {empty_examples}")
    else:
        print("  PASS: All examples populated")
    
    # Test 6b: All examples must be numeric (not descriptive)
    print("[TEST 6b] Check examples are numeric (not descriptive)...")
    non_numeric_examples = []
    for row in table.get('rows', []):
        for check in row.get('checks', []):
            example = check.get('example')
            if example and not is_numeric_example(example):
                non_numeric_examples.append(f"{row['label']}/{check['label']}: '{example}'")
    
    if non_numeric_examples:
        errors.append(f"Found {len(non_numeric_examples)} non-numeric examples")
        print(f"  FAIL: Examples must be numeric values, not descriptions")
        for ex in non_numeric_examples[:5]:
            print(f"       {ex}")
    else:
        print("  PASS: All examples are numeric")
    
    # Test 7: All paths exist in coverage report
    print("[TEST 7] Check all paths exist in coverage report...")
    missing_paths = []
    for row in table.get('rows', []):
        for check in row.get('checks', []):
            path = check.get('path')
            if path and path not in coverage_lookup:
                missing_paths.append(path)
    
    if missing_paths:
        errors.append(f"Found {len(missing_paths)} paths not in coverage report")
        print(f"  FAIL: {missing_paths[:5]}")
    else:
        print("  PASS: All paths verified")
    
    # Test 8: Valid group keys
    print("[TEST 8] Check group keys are valid...")
    allowed_groups = {
        'market_microstructure',
        'liquidity',
        'order_book_depth',
        'spot_prices',
        'sampling_density',
        'sentiment_last_cycle',
        'sentiment_last_2_cycles',
        'activity_vs_silence',
        'engagement_and_authors'
    }
    
    invalid_groups = []
    for row in table.get('rows', []):
        group = row.get('group')
        if group and group not in allowed_groups:
            invalid_groups.append(group)
    
    if invalid_groups:
        errors.append(f"Found invalid group keys: {set(invalid_groups)}")
        print(f"  FAIL: {invalid_groups}")
    else:
        print("  PASS: All groups valid")
    
    # Test 9: ASCII-only
    print("[TEST 9] Check ASCII-only output...")
    try:
        with open(coverage_table_file, 'r', encoding='ascii') as f:
            f.read()
        print("  PASS: ASCII-only")
    except UnicodeDecodeError:
        errors.append("Non-ASCII characters found")
        print("  FAIL: Non-ASCII detected")
    
    print()
    
    # Summary
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Rows: {len(table.get('rows', []))}")
    print(f"Total checks: {sum(len(r.get('checks', [])) for r in table.get('rows', []))}")
    print()
    
    if errors:
        print("ERRORS:")
        for err in errors:
            print(f"  - {err}")
        print()
        print("RESULT: FAIL")
        return 1
    
    if warnings:
        print("WARNINGS:")
        for warn in warnings:
            print(f"  - {warn}")
        print()
    
    print("RESULT: PASS")
    return 0


if __name__ == '__main__':
    sys.exit(test_coverage_table())
