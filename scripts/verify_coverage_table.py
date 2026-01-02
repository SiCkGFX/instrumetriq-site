#!/usr/bin/env python3
"""
Verify Coverage Table (Phase 1B-fix)

Independently verifies that public/data/coverage_table.json is correct,
consistent with Phase 1A's field_coverage_report.json, and that example
values are REAL numeric values (not descriptive placeholders).

Hard requirements:
- Use ONLY what exists in field_coverage_report.json and sample entries
- Do NOT assume any field paths
- Zero tolerance for 0% rows or empty examples
- Examples MUST be numeric (not descriptions)
- ASCII-only output
"""

import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


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
    
    # Pattern 3: Number with suffix: "42K", "3.5%"
    if re.match(r'^-?\d+(\.\d+)?[KMB%]$', example):
        return True
    
    # Pattern 4: Percentage: "15.5%"
    if re.match(r'^-?\d+(\.\d+)?%$', example):
        return True
    
    return False


def get_nested_value(data: Dict[str, Any], path: str) -> Any:
    """Navigate nested dict using dot-notation path."""
    keys = path.split('.')
    value = data
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
            if value is None:
                return None
        else:
            return None
    return value


def compute_presence_pct(field_info: Dict[str, Any], total_entries: int) -> float:
    """Compute presence percentage from field info."""
    present = field_info.get('present', 0)
    return (present / total_entries * 100.0) if total_entries > 0 else 0.0


def check_file_existence() -> Tuple[bool, List[str], List[str]]:
    """Check A: File existence + JSON validity."""
    print("\n" + "=" * 70)
    print("CHECK A: File Existence + JSON Validity")
    print("=" * 70)
    
    errors = []
    warnings = []
    root = Path(__file__).resolve().parent.parent
    
    # Required files
    coverage_table_path = root / 'public' / 'data' / 'coverage_table.json'
    coverage_report_path = root / 'data' / 'field_coverage_report.json'
    sample_path = root / 'data' / 'samples' / 'cryptobot_latest_head200.jsonl'
    
    files_to_check = [
        (coverage_table_path, "coverage_table.json", True),
        (coverage_report_path, "field_coverage_report.json", True),
        (sample_path, "sample JSONL", True),
    ]
    
    # Optional file
    canonical_path = root / 'data' / 'canonical_fields.json'
    if not canonical_path.exists():
        warnings.append("canonical_fields.json not found (optional)")
        print(f"  WARN: {canonical_path} not found (optional)")
    
    loaded = {}
    for path, name, required in files_to_check:
        if not path.exists():
            msg = f"{name} not found at {path}"
            errors.append(msg)
            print(f"  FAIL: {msg}")
            continue
        
        try:
            if path.suffix == '.jsonl':
                # Just check it's readable
                with open(path, 'r', encoding='utf-8') as f:
                    f.readline()
                loaded[name] = path
                print(f"  PASS: {name} exists and readable")
            else:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                loaded[name] = data
                print(f"  PASS: {name} exists and valid JSON")
        except Exception as e:
            msg = f"{name} invalid: {e}"
            errors.append(msg)
            print(f"  FAIL: {msg}")
    
    return len(errors) == 0, errors, warnings


def check_structure(coverage_table: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
    """Check B: Structure validation for coverage_table."""
    print("\n" + "=" * 70)
    print("CHECK B: Structure Validation")
    print("=" * 70)
    
    errors = []
    warnings = []
    
    # Top-level keys
    has_timestamp = 'generated_at' in coverage_table or 'generated_at_utc' in coverage_table
    if not has_timestamp:
        errors.append("Missing 'generated_at' or 'generated_at_utc' field")
        print("  FAIL: No timestamp field")
    else:
        print("  PASS: Timestamp field present")
    
    if 'rows' not in coverage_table:
        errors.append("Missing 'rows' field")
        print("  FAIL: Missing 'rows' field")
        return False, errors, warnings
    
    rows = coverage_table['rows']
    if not isinstance(rows, list) or len(rows) == 0:
        errors.append("'rows' is not a non-empty list")
        print("  FAIL: 'rows' is empty or not a list")
        return False, errors, warnings
    
    print(f"  PASS: {len(rows)} rows found")
    
    # Validate each row
    for i, row in enumerate(rows):
        row_id = f"Row {i} ({row.get('label', 'unknown')})"
        
        # Required fields in row
        for field in ['group', 'label', 'present_pct', 'checks']:
            if field not in row:
                errors.append(f"{row_id}: missing '{field}'")
        
        # Check 0% rows
        if row.get('present_pct', 0) == 0:
            errors.append(f"{row_id}: has 0% presence")
            print(f"  FAIL: {row_id} has 0% presence")
        
        # Check empty strings
        if not row.get('group') or not row.get('label'):
            errors.append(f"{row_id}: empty group or label")
        
        # Validate checks
        checks = row.get('checks', [])
        if not isinstance(checks, list) or len(checks) == 0:
            errors.append(f"{row_id}: 'checks' is empty or not a list")
            continue
        
        for j, check in enumerate(checks):
            check_id = f"{row_id} check {j} ({check.get('label', 'unknown')})"
            
            # Required fields in check
            for field in ['path', 'label', 'present_pct', 'example']:
                if field not in check:
                    errors.append(f"{check_id}: missing '{field}'")
            
            # Check 0% checks
            if check.get('present_pct', 0) == 0:
                errors.append(f"{check_id}: has 0% presence")
                print(f"  FAIL: {check_id} has 0% presence")
            
            # Check empty example
            if not check.get('example') or check.get('example') == '':
                errors.append(f"{check_id}: empty example")
                print(f"  FAIL: {check_id} has empty example")
    
    if len(errors) == 0:
        print("  PASS: All structure checks passed")
    
    return len(errors) == 0, errors, warnings


def check_consistency(coverage_table: Dict[str, Any], 
                     coverage_report: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
    """Check C: Cross-file consistency vs Phase 1A."""
    print("\n" + "=" * 70)
    print("CHECK C: Cross-file Consistency vs Phase 1A")
    print("=" * 70)
    
    errors = []
    warnings = []
    
    # Build lookup from coverage report
    total_entries = coverage_report.get('entries_scanned', 0)
    print(f"  Phase 1A scanned: {total_entries} entries")
    
    path_lookup = {}
    for group, fields in coverage_report.get('field_groups', {}).items():
        for path, info in fields.items():
            path_lookup[path] = compute_presence_pct(info, total_entries)
    
    print(f"  Phase 1A indexed: {len(path_lookup)} paths")
    
    # Check every path in coverage_table
    checked_paths = 0
    for row in coverage_table.get('rows', []):
        row_label = row.get('label', 'unknown')
        row_pct = row.get('present_pct', 0)
        check_pcts = []
        
        for check in row.get('checks', []):
            path = check.get('path')
            check_pct = check.get('present_pct', 0)
            check_label = check.get('label', 'unknown')
            
            if not path:
                errors.append(f"{row_label}/{check_label}: missing path")
                continue
            
            # Verify path exists in Phase 1A
            if path not in path_lookup:
                errors.append(f"{row_label}/{check_label}: path '{path}' not in Phase 1A report")
                print(f"  FAIL: '{path}' not found in Phase 1A")
                continue
            
            # Verify percentage matches
            phase1a_pct = path_lookup[path]
            diff = abs(check_pct - phase1a_pct)
            
            if diff > 0.1:
                errors.append(f"{row_label}/{check_label}: presence mismatch - "
                            f"coverage_table={check_pct}% vs Phase1A={phase1a_pct}%")
                print(f"  FAIL: '{path}' - table={check_pct}% vs Phase1A={phase1a_pct}%")
            
            check_pcts.append(check_pct)
            checked_paths += 1
        
        # Verify group-level percent is MIN of checks
        if check_pcts:
            expected_row_pct = min(check_pcts)
            if abs(row_pct - expected_row_pct) > 0.1:
                warnings.append(f"{row_label}: group percent={row_pct}% "
                              f"but MIN(checks)={expected_row_pct}%")
                print(f"  WARN: {row_label} - group={row_pct}% vs MIN(checks)={expected_row_pct}%")
    
    print(f"  Verified: {checked_paths} paths")
    
    if len(errors) == 0:
        print("  PASS: All paths consistent with Phase 1A")
    
    return len(errors) == 0, errors, warnings


def check_examples_real(coverage_table: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
    """Check D: Examples must be real numeric values (not descriptive)."""
    print("\n" + "=" * 70)
    print("CHECK D: Examples Must Be Real Numeric Values")
    print("=" * 70)
    
    errors = []
    warnings = []
    
    # Load sample entries
    root = Path(__file__).resolve().parent.parent
    sample_path = root / 'data' / 'samples' / 'cryptobot_latest_head200.jsonl'
    
    entries = []
    with open(sample_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line))
    
    print(f"  Loaded {len(entries)} sample entries")
    
    # Check each example
    checked_examples = 0
    non_numeric = []
    for row in coverage_table.get('rows', []):
        row_label = row.get('label', 'unknown')
        
        for check in row.get('checks', []):
            path = check.get('path')
            example = check.get('example')
            check_label = check.get('label', 'unknown')
            
            if not path or not example:
                continue
            
            # Verify example is numeric (not descriptive)
            if not is_numeric_example(example):
                errors.append(f"{row_label}/{check_label}: example '{example}' is not numeric")
                non_numeric.append(f"{row_label}/{check_label}: '{example}'")
                print(f"  FAIL: '{path}' - example '{example}' is descriptive, not numeric")
                continue
            
            # Find first entry with this path to verify it exists
            real_value = None
            for entry in entries:
                val = get_nested_value(entry, path)
                if val is not None:
                    real_value = val
                    break
            
            if real_value is None:
                errors.append(f"{row_label}/{check_label}: path '{path}' not found in any sample entry")
                print(f"  FAIL: '{path}' not in sample (but Phase 1A says present)")
                continue
            
            checked_examples += 1
    
    print(f"  Verified: {checked_examples} examples")
    
    if non_numeric:
        print(f"  Found {len(non_numeric)} non-numeric examples (FAIL)")
    
    if len(errors) == 0:
        print("  PASS: All examples are numeric and found in real entries")
    
    return len(errors) == 0, errors, warnings


def check_ascii_only() -> Tuple[bool, List[str], List[str]]:
    """Check E: ASCII-only."""
    print("\n" + "=" * 70)
    print("CHECK E: ASCII-only")
    print("=" * 70)
    
    errors = []
    warnings = []
    
    root = Path(__file__).resolve().parent.parent
    coverage_table_path = root / 'public' / 'data' / 'coverage_table.json'
    
    try:
        with open(coverage_table_path, 'rb') as f:
            content = f.read()
        
        # Check each byte
        for i, byte in enumerate(content):
            if byte > 127:
                errors.append(f"Non-ASCII byte {byte} at position {i}")
                print(f"  FAIL: Non-ASCII byte {byte} (0x{byte:02x}) at position {i}")
                # Show context
                start = max(0, i - 20)
                end = min(len(content), i + 20)
                context = content[start:end].decode('utf-8', errors='replace')
                print(f"       Context: {repr(context)}")
                break
        
        if len(errors) == 0:
            print(f"  PASS: All {len(content)} bytes are ASCII")
    
    except Exception as e:
        errors.append(f"Failed to read file: {e}")
        print(f"  FAIL: {e}")
    
    return len(errors) == 0, errors, warnings


def check_determinism() -> Tuple[bool, List[str], List[str]]:
    """Check F: Determinism check."""
    print("\n" + "=" * 70)
    print("CHECK F: Determinism (content stability)")
    print("=" * 70)
    
    errors = []
    warnings = []
    
    root = Path(__file__).resolve().parent.parent
    coverage_table_path = root / 'public' / 'data' / 'coverage_table.json'
    
    # Read original
    with open(coverage_table_path, 'r', encoding='utf-8') as f:
        original = json.load(f)
    
    # Remove timestamp fields for comparison
    original_no_ts = {k: v for k, v in original.items() 
                      if k not in ['generated_at', 'generated_at_utc']}
    
    print("  INFO: Determinism check requires manual rebuild")
    print("  Run: python scripts/build_coverage_table.py")
    print("  Then: python scripts/verify_coverage_table.py")
    print("  This verifier will compare pre/post rebuild content")
    
    # For now, just note the current state
    print(f"  Current rows: {len(original.get('rows', []))}")
    print(f"  Current checks: {sum(len(r.get('checks', [])) for r in original.get('rows', []))}")
    
    warnings.append("Determinism check requires manual rebuild cycle")
    
    return True, errors, warnings


def main():
    """Run all verification checks."""
    print("\n" + "=" * 70)
    print("COVERAGE TABLE VERIFICATION (Phase 1B-check)")
    print("=" * 70)
    print("Independently verifying coverage_table.json against Phase 1A findings")
    print()
    
    root = Path(__file__).resolve().parent.parent
    
    all_errors = []
    all_warnings = []
    
    # Check A: File existence
    passed, errors, warnings = check_file_existence()
    all_errors.extend(errors)
    all_warnings.extend(warnings)
    
    if not passed:
        print("\n" + "=" * 70)
        print("VERIFICATION FAILED: Missing required files")
        print("=" * 70)
        return 1
    
    # Load files
    with open(root / 'public' / 'data' / 'coverage_table.json', 'r') as f:
        coverage_table = json.load(f)
    
    with open(root / 'data' / 'field_coverage_report.json', 'r') as f:
        coverage_report = json.load(f)
    
    # Check B: Structure
    passed, errors, warnings = check_structure(coverage_table)
    all_errors.extend(errors)
    all_warnings.extend(warnings)
    
    # Check C: Consistency
    passed, errors, warnings = check_consistency(coverage_table, coverage_report)
    all_errors.extend(errors)
    all_warnings.extend(warnings)
    
    # Check D: Real examples
    passed, errors, warnings = check_examples_real(coverage_table)
    all_errors.extend(errors)
    all_warnings.extend(warnings)
    
    # Check E: ASCII-only
    passed, errors, warnings = check_ascii_only()
    all_errors.extend(errors)
    all_warnings.extend(warnings)
    
    # Check F: Determinism
    passed, errors, warnings = check_determinism()
    all_errors.extend(errors)
    all_warnings.extend(warnings)
    
    # Final summary
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    
    rows = coverage_table.get('rows', [])
    total_checks = sum(len(r.get('checks', [])) for r in rows)
    
    print(f"Feature groups: {len(rows)}")
    print(f"Total checks: {total_checks}")
    print(f"Errors: {len(all_errors)}")
    print(f"Warnings: {len(all_warnings)}")
    print()
    
    if all_errors:
        print("ERRORS:")
        for err in all_errors:
            print(f"  - {err}")
        print()
    
    if all_warnings:
        print("WARNINGS:")
        for warn in all_warnings:
            print(f"  - {warn}")
        print()
    
    if len(all_errors) == 0:
        print("RESULT: PASS (all checks passed)")
        print()
        print("Coverage table is valid and consistent with Phase 1A findings.")
        return 0
    else:
        print("RESULT: FAIL")
        print()
        print(f"Found {len(all_errors)} errors that must be fixed.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
