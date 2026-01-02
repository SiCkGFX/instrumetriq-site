#!/usr/bin/env python3
"""
Test Phase 2A Artifacts

Validates that all 3 Phase 2A artifacts are:
- Valid JSON
- ASCII-only
- Deterministic (except timestamp)
- Contain required metadata
- Bins/histograms sum correctly
"""

import json
import subprocess
import sys
from pathlib import Path


def test_artifact_exists(artifact_name: str, root: Path) -> bool:
    """Test that artifact file exists."""
    artifact_file = root / 'public' / 'data' / artifact_name
    if not artifact_file.exists():
        print(f"  FAIL: {artifact_name} not found")
        return False
    print(f"  PASS: {artifact_name} exists")
    return True


def test_json_valid(artifact_name: str, root: Path) -> tuple:
    """Test that artifact is valid JSON."""
    artifact_file = root / 'public' / 'data' / artifact_name
    try:
        with open(artifact_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"  PASS: {artifact_name} is valid JSON")
        return True, data
    except Exception as e:
        print(f"  FAIL: {artifact_name} invalid JSON: {e}")
        return False, None


def test_ascii_only(artifact_name: str, root: Path) -> bool:
    """Test that artifact is ASCII-only."""
    artifact_file = root / 'public' / 'data' / artifact_name
    try:
        with open(artifact_file, 'rb') as f:
            content = f.read()
        
        for i, byte in enumerate(content):
            if byte > 127:
                print(f"  FAIL: {artifact_name} has non-ASCII byte {byte} at position {i}")
                return False
        
        print(f"  PASS: {artifact_name} is ASCII-only")
        return True
    except Exception as e:
        print(f"  FAIL: {artifact_name} ASCII check failed: {e}")
        return False


def test_metadata_present(artifact_name: str, data: dict) -> bool:
    """Test that required metadata is present."""
    required = ['generated_at_utc', 'entries_scanned', 'source']
    
    errors = []
    for field in required:
        if field not in data:
            errors.append(f"Missing field: {field}")
        elif field == 'entries_scanned' and (not isinstance(data[field], int) or data[field] <= 0):
            errors.append(f"entries_scanned must be positive int, got: {data[field]}")
        elif field == 'generated_at_utc':
            # Verify UTC format ends with Z
            if not isinstance(data[field], str) or not data[field].endswith('Z'):
                errors.append(f"generated_at_utc must be ISO string ending with 'Z', got: {data[field]}")
    
    if errors:
        print(f"  FAIL: {artifact_name} metadata issues:")
        for err in errors:
            print(f"    - {err}")
        return False
    
    print(f"  PASS: {artifact_name} has required metadata")
    return True


def test_activity_regimes(data: dict) -> bool:
    """Test activity_regimes.json specific requirements."""
    print("\n[TEST] activity_regimes.json specifics")
    
    if 'regimes' not in data:
        print("  FAIL: Missing 'regimes' field")
        return False
    
    regimes = data['regimes']
    total_binned = data.get('total_binned', 0)
    
    # Check bin sum
    sum_n = sum(r.get('n_entries', 0) for r in regimes)
    
    if sum_n != total_binned:
        print(f"  FAIL: Bin entries sum ({sum_n}) != total_binned ({total_binned})")
        return False
    
    # Check share_pct sum (should be ~100%)
    sum_pct = sum(r.get('share_pct', 0) for r in regimes)
    if abs(sum_pct - 100.0) > 1.0:
        print(f"  FAIL: share_pct sum ({sum_pct:.1f}%) not ~100%")
        return False
    
    print(f"  PASS: {len(regimes)} bins, totals consistent")
    return True


def test_sampling_density(data: dict) -> bool:
    """Test sampling_density.json specific requirements."""
    print("\n[TEST] sampling_density.json specifics")
    
    errors = []
    
    # Check histogram if present
    if 'sample_count_histogram' in data and data['sample_count_histogram']:
        histogram = data['sample_count_histogram']
        n_entries = data.get('sample_count_stats', {}).get('n_entries', 0)
        
        if n_entries > 0:
            sum_hist = sum(h.get('count', 0) for h in histogram)
            if sum_hist != n_entries:
                errors.append(f"Histogram sum ({sum_hist}) != n_entries ({n_entries})")
    
    if errors:
        print("  FAIL:")
        for err in errors:
            print(f"    - {err}")
        return False
    
    print("  PASS: Histogram and stats consistent")
    return True


def test_session_lifecycle(data: dict) -> bool:
    """Test session_lifecycle.json specific requirements."""
    print("\n[TEST] session_lifecycle.json specifics")
    
    if 'definition' not in data:
        print("  FAIL: Missing 'definition' field")
        return False
    
    if 'session' not in data['definition']:
        print("  FAIL: Missing 'session' definition")
        return False
    
    # note_sample_bias is OPTIONAL - if present, must be a string
    if 'note_sample_bias' in data:
        if not isinstance(data['note_sample_bias'], str):
            print("  FAIL: note_sample_bias must be a string if present")
            return False
        print("  INFO: note_sample_bias present (sample concentration detected)")
    
    print("  PASS: Session definition present")
    return True


def test_determinism(root: Path) -> bool:
    """Test that rebuilding produces identical output (except timestamp)."""
    print("\n[TEST] Determinism")
    
    # Build once
    print("  Building artifacts (run 1)...")
    result = subprocess.run(
        ['python', 'scripts/build_phase2a_artifacts.py'],
        cwd=root,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"  FAIL: Build 1 failed: {result.stderr}")
        return False
    
    # Load artifacts
    artifacts_a = {}
    for name in ['activity_regimes.json', 'sampling_density.json', 'session_lifecycle.json']:
        with open(root / 'public' / 'data' / name, 'r') as f:
            artifacts_a[name] = json.load(f)
    
    # Build again
    print("  Building artifacts (run 2)...")
    result = subprocess.run(
        ['python', 'scripts/build_phase2a_artifacts.py'],
        cwd=root,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"  FAIL: Build 2 failed: {result.stderr}")
        return False
    
    # Load artifacts again
    artifacts_b = {}
    for name in ['activity_regimes.json', 'sampling_density.json', 'session_lifecycle.json']:
        with open(root / 'public' / 'data' / name, 'r') as f:
            artifacts_b[name] = json.load(f)
    
    # Compare (remove timestamps)
    errors = []
    for name in artifacts_a.keys():
        a = {k: v for k, v in artifacts_a[name].items() if 'generated' not in k.lower()}
        b = {k: v for k, v in artifacts_b[name].items() if 'generated' not in k.lower()}
        
        if a != b:
            errors.append(f"{name}: Builds differ")
    
    if errors:
        print("  FAIL:")
        for err in errors:
            print(f"    - {err}")
        return False
    
    print("  PASS: Builds are deterministic")
    return True


def main():
    """Run all tests."""
    print("=" * 70)
    print("Testing Phase 2A Artifacts")
    print("=" * 70)
    
    root = Path(__file__).resolve().parent.parent
    artifacts = ['activity_regimes.json', 'sampling_density.json', 'session_lifecycle.json']
    
    all_passed = True
    
    # Test each artifact
    for artifact in artifacts:
        print(f"\n[TEST] {artifact}")
        
        # Existence
        if not test_artifact_exists(artifact, root):
            all_passed = False
            continue
        
        # JSON validity
        passed, data = test_json_valid(artifact, root)
        if not passed:
            all_passed = False
            continue
        
        # ASCII-only
        if not test_ascii_only(artifact, root):
            all_passed = False
        
        # Metadata
        if not test_metadata_present(artifact, data):
            all_passed = False
    
    # Artifact-specific tests
    artifacts_data = {}
    for artifact in artifacts:
        with open(root / 'public' / 'data' / artifact, 'r') as f:
            artifacts_data[artifact] = json.load(f)
    
    if not test_activity_regimes(artifacts_data['activity_regimes.json']):
        all_passed = False
    
    if not test_sampling_density(artifacts_data['sampling_density.json']):
        all_passed = False
    
    if not test_session_lifecycle(artifacts_data['session_lifecycle.json']):
        all_passed = False
    
    # Determinism test
    if not test_determinism(root):
        all_passed = False
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    if all_passed:
        print("RESULT: PASS")
        print("\nAll Phase 2A artifacts validated successfully.")
        return 0
    else:
        print("RESULT: FAIL")
        print("\nSome tests failed. Review output above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
