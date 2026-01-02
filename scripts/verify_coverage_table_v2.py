#!/usr/bin/env python3
"""
Verify Coverage Table v2 (Phase 1B-check2)

Confirms that coverage_table.json examples are:
1) Computed (not hardcoded)
2) Deterministic across rebuilds
3) Reasonable (not suspicious constants)
4) Match Phase 1A SSOT
"""

import json
import math
import os
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


def get_nested_value(obj, path):
    """Safely navigate nested dict using dot-separated path."""
    parts = path.split('.')
    current = obj
    for part in parts:
        if not isinstance(current, dict):
            return None
        if part not in current:
            return None
        current = current[part]
    return current


def extract_numeric_values(entries, path):
    """Extract all valid numeric values from entries for a given path."""
    values = []
    for entry in entries:
        val = get_nested_value(entry, path)
        if val is not None:
            if isinstance(val, (int, float)):
                if not math.isnan(val) and not math.isinf(val):
                    values.append(val)
    return values


def parse_example_value(example_str):
    """Parse example string to numeric value, handling K/M/B/% suffixes."""
    if not example_str:
        return None
    
    s = str(example_str).strip()
    
    # Handle percentage
    if s.endswith('%'):
        try:
            return float(s[:-1])
        except:
            return None
    
    # Handle K/M/B suffix
    multipliers = {'K': 1000, 'M': 1000000, 'B': 1000000000}
    for suffix, mult in multipliers.items():
        if s.endswith(suffix):
            try:
                return float(s[:-1]) * mult
            except:
                return None
    
    # Handle ranges (take midpoint)
    if ' to ' in s or '-' in s:
        parts = s.replace(' to ', ' ').replace('-', ' ').split()
        try:
            nums = [float(p) for p in parts if p.replace('.', '').replace('-', '').isdigit()]
            if nums:
                return statistics.mean(nums)
        except:
            pass
    
    # Plain number
    try:
        return float(s)
    except:
        return None


def check_determinism():
    """Check 1: Rebuild twice and ensure determinism."""
    print("\n" + "=" * 70)
    print("CHECK 1: Determinism (Rebuild Twice)")
    print("=" * 70)
    
    root = Path(__file__).resolve().parent.parent
    output_file = root / 'public' / 'data' / 'coverage_table.json'
    
    # Delete existing file
    if output_file.exists():
        output_file.unlink()
        print("  Deleted existing coverage_table.json")
    
    # Build 1
    print("  Building coverage table (run 1)...")
    result = subprocess.run(
        ['python', 'scripts/build_coverage_table.py'],
        cwd=root,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"  FAIL: Build 1 failed: {result.stderr}")
        return False, [f"Build 1 failed: {result.stderr}"]
    
    with open(output_file, 'r', encoding='utf-8') as f:
        obj_a = json.load(f)
    
    # Build 2
    print("  Building coverage table (run 2)...")
    result = subprocess.run(
        ['python', 'scripts/build_coverage_table.py'],
        cwd=root,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"  FAIL: Build 2 failed: {result.stderr}")
        return False, [f"Build 2 failed: {result.stderr}"]
    
    with open(output_file, 'r', encoding='utf-8') as f:
        obj_b = json.load(f)
    
    # Remove timestamp keys
    obj_a_no_ts = {k: v for k, v in obj_a.items() if 'generated' not in k.lower()}
    obj_b_no_ts = {k: v for k, v in obj_b.items() if 'generated' not in k.lower()}
    
    # Compare
    if obj_a_no_ts == obj_b_no_ts:
        print("  PASS: Builds are deterministic (identical except timestamp)")
        return True, []
    else:
        # Find first difference
        errors = []
        for i, (row_a, row_b) in enumerate(zip(obj_a_no_ts.get('rows', []), obj_b_no_ts.get('rows', []))):
            if row_a != row_b:
                errors.append(f"Difference in row {i} ({row_a.get('label', 'unknown')})")
                for j, (check_a, check_b) in enumerate(zip(row_a.get('checks', []), row_b.get('checks', []))):
                    if check_a != check_b:
                        errors.append(f"  Check {j}: {check_a.get('label')} vs {check_b.get('label')}")
                        errors.append(f"    A: {check_a.get('example')}")
                        errors.append(f"    B: {check_b.get('example')}")
                        break
                break
        
        print(f"  FAIL: Builds differ: {errors[0] if errors else 'unknown difference'}")
        return False, errors


def check_not_hardcoded():
    """Check 2: Cross-check one example against recomputed median."""
    print("\n" + "=" * 70)
    print("CHECK 2: Not Hardcoded (Sample Median Cross-check)")
    print("=" * 70)
    
    root = Path(__file__).resolve().parent.parent
    coverage_file = root / 'public' / 'data' / 'coverage_table.json'
    sample_file = root / 'data' / 'samples' / 'cryptobot_latest_head200.jsonl'
    
    # Load coverage table
    with open(coverage_file, 'r', encoding='utf-8') as f:
        table = json.load(f)
    
    # Load sample entries
    entries = []
    with open(sample_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line))
    
    # Pick a field with high variability for testing
    test_path = 'derived.spread_bps'
    test_label = 'Spread (bps)'
    
    # Find this check in the table
    table_example = None
    for row in table.get('rows', []):
        for check in row.get('checks', []):
            if check.get('path') == test_path:
                table_example = check.get('example')
                break
    
    if not table_example:
        print(f"  FAIL: Test path '{test_path}' not found in table")
        return False, [f"Test path '{test_path}' not found"]
    
    # Compute median from sample
    values = extract_numeric_values(entries, test_path)
    if not values:
        print(f"  FAIL: No values found for path '{test_path}' in sample")
        return False, [f"No values for '{test_path}'"]
    
    computed_median = statistics.median(values)
    
    # Parse table example
    table_value = parse_example_value(table_example)
    if table_value is None:
        print(f"  FAIL: Could not parse table example '{table_example}'")
        return False, [f"Could not parse '{table_example}'"]
    
    # Compare with tolerance
    tolerance = 0.2  # bps tolerance
    diff = abs(computed_median - table_value)
    
    print(f"  Test field: {test_label}")
    print(f"  Path: {test_path}")
    print(f"  Computed median: {computed_median:.1f}")
    print(f"  Table example: {table_example}")
    print(f"  Difference: {diff:.2f}")
    
    if diff <= tolerance:
        print("  PASS: Example matches computed median (within tolerance)")
        return True, []
    else:
        print(f"  FAIL: Difference {diff:.2f} exceeds tolerance {tolerance}")
        return False, [f"Median mismatch: computed={computed_median:.1f}, table={table_example}, diff={diff:.2f}"]


def check_zero_values():
    """Check 3: Audit zero values."""
    print("\n" + "=" * 70)
    print("CHECK 3: Zero-Value Audit")
    print("=" * 70)
    
    root = Path(__file__).resolve().parent.parent
    coverage_file = root / 'public' / 'data' / 'coverage_table.json'
    sample_file = root / 'data' / 'samples' / 'cryptobot_latest_head200.jsonl'
    
    # Load coverage table
    with open(coverage_file, 'r', encoding='utf-8') as f:
        table = json.load(f)
    
    # Load sample entries
    entries = []
    with open(sample_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line))
    
    # Find all checks with 0/0.0 examples
    zero_checks = []
    errors = []
    
    for row in table.get('rows', []):
        for check in row.get('checks', []):
            example = check.get('example', '')
            path = check.get('path', '')
            label = check.get('label', '')
            
            # Check if example is "0" or "0.0"
            if example in ['0', '0.0', '0.00', '0.000']:
                # Verify by computing median from sample
                values = extract_numeric_values(entries, path)
                if values:
                    computed_median = statistics.median(values)
                    
                    zero_checks.append({
                        'label': label,
                        'path': path,
                        'table_example': example,
                        'computed_median': computed_median
                    })
                    
                    # If computed median is not near zero, this is suspicious
                    if abs(computed_median) > 0.5:
                        errors.append(f"{label}: table={example} but computed median={computed_median:.2f}")
                        print(f"  WARN: {label} - table=0.0 but computed={computed_median:.2f}")
    
    print(f"  Found {len(zero_checks)} checks with zero examples")
    
    if zero_checks:
        for zc in zero_checks:
            print(f"    {zc['label']}: {zc['table_example']} (computed median: {zc['computed_median']:.3f})")
    
    if errors:
        print(f"  FAIL: {len(errors)} suspicious zero values")
        return False, errors
    else:
        print("  PASS: All zero values confirmed by sample data")
        return True, []


def check_ssot():
    """Check 4: SSOT match with Phase 1A."""
    print("\n" + "=" * 70)
    print("CHECK 4: SSOT Match (vs Phase 1A)")
    print("=" * 70)
    
    root = Path(__file__).resolve().parent.parent
    coverage_file = root / 'public' / 'data' / 'coverage_table.json'
    report_file = root / 'data' / 'field_coverage_report.json'
    
    # Load both files
    with open(coverage_file, 'r', encoding='utf-8') as f:
        table = json.load(f)
    
    with open(report_file, 'r', encoding='utf-8') as f:
        report = json.load(f)
    
    # Build lookup from Phase 1A
    total_entries = report.get('entries_scanned', 0)
    path_lookup = {}
    for group, fields in report.get('field_groups', {}).items():
        for path, info in fields.items():
            pct = (info['present'] / total_entries * 100.0) if total_entries > 0 else 0.0
            path_lookup[path] = pct
    
    # Check every path in table
    errors = []
    checked = 0
    
    for row in table.get('rows', []):
        for check in row.get('checks', []):
            path = check.get('path')
            table_pct = check.get('present_pct', 0)
            
            if not path:
                continue
            
            if path not in path_lookup:
                errors.append(f"{path}: not in Phase 1A report")
                continue
            
            phase1a_pct = path_lookup[path]
            diff = abs(table_pct - phase1a_pct)
            
            if diff > 0.1:
                errors.append(f"{path}: table={table_pct}% vs Phase1A={phase1a_pct}%")
            
            checked += 1
    
    print(f"  Checked {checked} paths against Phase 1A")
    
    if errors:
        print(f"  FAIL: {len(errors)} mismatches")
        for err in errors[:3]:
            print(f"    {err}")
        return False, errors
    else:
        print("  PASS: All paths match Phase 1A")
        return True, []


def check_ascii():
    """Check 5: ASCII-only."""
    print("\n" + "=" * 70)
    print("CHECK 5: ASCII-only")
    print("=" * 70)
    
    root = Path(__file__).resolve().parent.parent
    coverage_file = root / 'public' / 'data' / 'coverage_table.json'
    
    try:
        with open(coverage_file, 'rb') as f:
            content = f.read()
        
        for i, byte in enumerate(content):
            if byte > 127:
                print(f"  FAIL: Non-ASCII byte {byte} at position {i}")
                return False, [f"Non-ASCII byte at position {i}"]
        
        print(f"  PASS: All {len(content)} bytes are ASCII")
        return True, []
    except Exception as e:
        print(f"  FAIL: {e}")
        return False, [str(e)]


def main():
    """Run all verification checks."""
    print("\n" + "=" * 70)
    print("COVERAGE TABLE VERIFICATION V2 (Phase 1B-check2)")
    print("=" * 70)
    print("Determinism + Not Hardcoded + Sanity Audit")
    print()
    
    all_errors = []
    results = {}
    
    # Check 1: Determinism
    passed, errors = check_determinism()
    results['determinism'] = passed
    all_errors.extend(errors)
    
    # Check 2: Not hardcoded
    passed, errors = check_not_hardcoded()
    results['not_hardcoded'] = passed
    all_errors.extend(errors)
    
    # Check 3: Zero values
    passed, errors = check_zero_values()
    results['zero_values'] = passed
    all_errors.extend(errors)
    
    # Check 4: SSOT
    passed, errors = check_ssot()
    results['ssot'] = passed
    all_errors.extend(errors)
    
    # Check 5: ASCII
    passed, errors = check_ascii()
    results['ascii'] = passed
    all_errors.extend(errors)
    
    # Final summary
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY (V2)")
    print("=" * 70)
    print(f"Determinism:        {'PASS' if results['determinism'] else 'FAIL'}")
    print(f"Not Hardcoded:      {'PASS' if results['not_hardcoded'] else 'FAIL'}")
    print(f"Zero-Value Audit:   {'PASS' if results['zero_values'] else 'FAIL'}")
    print(f"SSOT Match:         {'PASS' if results['ssot'] else 'FAIL'}")
    print(f"ASCII-only:         {'PASS' if results['ascii'] else 'FAIL'}")
    print()
    
    if all_errors:
        print(f"ERRORS: {len(all_errors)}")
        for err in all_errors[:5]:
            print(f"  - {err}")
        print()
        print("RESULT: FAIL")
        return 1
    else:
        print("RESULT: PASS")
        print()
        print("Coverage table is deterministic, computed (not hardcoded),")
        print("sanity-checked, and consistent with Phase 1A SSOT.")
        return 0


if __name__ == '__main__':
    sys.exit(main())
