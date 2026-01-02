#!/usr/bin/env python3
"""
Verify Canonical Field Selection (Phase 1B)

Validates that canonical_fields.json is correctly derived from
field_coverage_report.json with no errors or inconsistencies.
"""

import json
import sys
from pathlib import Path


def verify_canonical_fields():
    """Run all verification checks."""
    instrumetriq_root = Path(__file__).resolve().parent.parent
    coverage_file = instrumetriq_root / 'data' / 'field_coverage_report.json'
    canonical_file = instrumetriq_root / 'data' / 'canonical_fields.json'
    
    print("=" * 70)
    print("Canonical Fields Verification (Phase 1B)")
    print("=" * 70)
    print()
    
    # Load files
    print("[LOAD] Loading field_coverage_report.json...")
    with open(coverage_file, 'r', encoding='utf-8') as f:
        coverage = json.load(f)
    
    print("[LOAD] Loading canonical_fields.json...")
    with open(canonical_file, 'r', encoding='utf-8') as f:
        canonical = json.load(f)
    
    print()
    
    errors = []
    warnings = []
    
    # Check 1: entries_scanned matches
    print("[CHECK 1] Verify entries_scanned matches...")
    if canonical['entries_scanned'] != coverage['entries_scanned']:
        errors.append(f"entries_scanned mismatch: canonical={canonical['entries_scanned']} coverage={coverage['entries_scanned']}")
    else:
        print(f"  OK: {canonical['entries_scanned']} entries")
    
    # Check 2: Build coverage lookup
    print("[CHECK 2] Building coverage lookup...")
    coverage_lookup = {}
    for group, fields in coverage['field_groups'].items():
        for path, data in fields.items():
            pct = (data['present'] / coverage['entries_scanned']) * 100
            coverage_lookup[path] = {
                'present_pct': pct,
                'present': data['present'],
                'missing': data['missing']
            }
    print(f"  OK: {len(coverage_lookup)} paths indexed")
    
    # Check 3: Verify all included fields exist in coverage
    print("[CHECK 3] Verify all included fields exist in coverage report...")
    all_included = []
    for group, data in canonical['groups'].items():
        for field in data['included']:
            path = field['path']
            all_included.append(path)
            
            if path not in coverage_lookup:
                errors.append(f"Included field not in coverage: {path}")
            else:
                # Check presence_pct matches (within 0.1%)
                coverage_pct = coverage_lookup[path]['present_pct']
                canonical_pct = field['present_pct']
                diff = abs(coverage_pct - canonical_pct)
                
                if diff > 0.1:
                    errors.append(f"Presence % mismatch for {path}: canonical={canonical_pct:.1f}% coverage={coverage_pct:.1f}%")
    
    print(f"  OK: {len(all_included)} included fields verified")
    
    # Check 4: Verify all excluded fields exist in coverage
    print("[CHECK 4] Verify all excluded fields exist in coverage report...")
    all_excluded = []
    for group, data in canonical['groups'].items():
        for field in data['excluded']:
            path = field['path']
            all_excluded.append(path)
            
            if path not in coverage_lookup:
                errors.append(f"Excluded field not in coverage: {path}")
            else:
                coverage_pct = coverage_lookup[path]['present_pct']
                canonical_pct = field['present_pct']
                diff = abs(coverage_pct - canonical_pct)
                
                if diff > 0.1:
                    errors.append(f"Presence % mismatch for {path}: canonical={canonical_pct:.1f}% coverage={coverage_pct:.1f}%")
    
    print(f"  OK: {len(all_excluded)} excluded fields verified")
    
    # Check 5: No duplicate fields
    print("[CHECK 5] Check for duplicate fields across groups...")
    all_fields = all_included + all_excluded
    if len(all_fields) != len(set(all_fields)):
        duplicates = [f for f in all_fields if all_fields.count(f) > 1]
        errors.append(f"Duplicate fields found: {set(duplicates)}")
    else:
        print(f"  OK: No duplicates ({len(all_fields)} unique paths)")
    
    # Check 6: Fields below threshold have justification
    print("[CHECK 6] Check low-availability fields have justification...")
    min_threshold = canonical['selection_rules']['min_presence_pct']
    for group, data in canonical['groups'].items():
        for field in data['included']:
            if field['present_pct'] < min_threshold:
                if 'Critical' not in field['reason'] and 'availability' not in field['reason'].lower():
                    warnings.append(f"Field below {min_threshold}% without clear justification: {field['path']} ({field['present_pct']}%)")
    
    if len(warnings) > 0:
        print(f"  WARN: {len(warnings)} fields below threshold")
    else:
        print(f"  OK: All low-availability fields justified")
    
    # Check 7: Verify no unknown groups
    print("[CHECK 7] Check for unknown group names...")
    known_groups = {
        'market_microstructure', 'liquidity', 'spot_prices', 'sampling_density',
        'sentiment_last_cycle', 'sentiment_last_2_cycles', 'activity_vs_silence',
        'author_stats', 'sentiment_metadata', 'data_quality', 'entry_metadata',
        'scores', 'labels', 'other'
    }
    
    unknown = set(canonical['groups'].keys()) - known_groups
    if unknown:
        warnings.append(f"Unknown group names (may be intentional): {unknown}")
    else:
        print(f"  OK: All groups recognized")
    
    print()
    
    # Summary
    print("=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    print(f"Total included fields: {len(all_included)}")
    print(f"Total excluded fields: {len(all_excluded)}")
    print(f"Groups: {len(canonical['groups'])}")
    print()
    
    if errors:
        print("ERRORS:")
        for err in errors:
            print(f"  - {err}")
        print()
    
    if warnings:
        print("WARNINGS:")
        for warn in warnings:
            print(f"  - {warn}")
        print()
    
    if errors:
        print("RESULT: FAIL")
        return 1
    else:
        print("RESULT: PASS")
        if warnings:
            print(f"  ({len(warnings)} warnings)")
        return 0


if __name__ == '__main__':
    sys.exit(verify_canonical_fields())
