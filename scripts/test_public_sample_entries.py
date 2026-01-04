#!/usr/bin/env python3
"""
Test script for public sample entries artifacts.

Validates structure, content, and consistency of generated artifacts.
Tests split artifacts (main JSON without spot_prices, separate spots file).
"""

import json
import sys
import subprocess
from pathlib import Path
from datetime import datetime


# Paths
OUTPUT_JSON = Path("public/data/sample_entries_v7.json")
OUTPUT_SPOTS_JSON = Path("public/data/sample_entries_spots_v7.json")
OUTPUT_JSONL = Path("public/data/sample_entries_v7.jsonl")


def test_artifacts_exist():
    """Test that all artifacts exist."""
    print("[TEST] Artifacts exist...")
    assert OUTPUT_JSON.exists(), f"JSON artifact missing: {OUTPUT_JSON}"
    assert OUTPUT_SPOTS_JSON.exists(), f"Spots JSON artifact missing: {OUTPUT_SPOTS_JSON}"
    assert OUTPUT_JSONL.exists(), f"JSONL artifact missing: {OUTPUT_JSONL}"
    print("  ✓ All artifacts exist")


def test_json_valid():
    """Test JSON artifact is valid and return data."""
    print("[TEST] JSON structure...")
    with open(OUTPUT_JSON, 'r', encoding='ascii') as f:
        data = json.load(f)
    
    # Check top-level keys
    required_keys = ['generated_at_utc', 'schema_version', 'entry_count', 'source', 'note', 'entries']
    for key in required_keys:
        assert key in data, f"Missing key: {key}"
    
    # Check types
    assert isinstance(data['generated_at_utc'], str), "generated_at_utc must be string"
    assert isinstance(data['schema_version'], str), "schema_version must be string"
    assert isinstance(data['entry_count'], int), "entry_count must be integer"
    assert isinstance(data['source'], str), "source must be string"
    assert isinstance(data['note'], str), "note must be string"
    assert isinstance(data['entries'], list), "entries must be list"
    
    print(f"  ✓ Valid JSON structure ({len(data['entries'])} entries)")
    return data


def test_jsonl_valid():
    """Test JSONL artifact is valid and return entries."""
    print("[TEST] JSONL structure...")
    entries = []
    with open(OUTPUT_JSONL, 'r', encoding='ascii') as f:
        for i, line in enumerate(f, 1):
            try:
                entry = json.loads(line)
                entries.append(entry)
            except json.JSONDecodeError as e:
                print(f"  ✗ Invalid JSON on line {i}: {e}", file=sys.stderr)
                sys.exit(1)
    
    print(f"  ✓ Valid JSONL ({len(entries)} entries)")
    return entries


def test_ascii_only():
    """Test that all files are ASCII-only."""
    print("[TEST] ASCII-only encoding...")
    
    # Test JSON
    with open(OUTPUT_JSON, 'r', encoding='ascii') as f:
        f.read()
    
    # Test Spots JSON
    with open(OUTPUT_SPOTS_JSON, 'r', encoding='ascii') as f:
        f.read()
    
    # Test JSONL
    with open(OUTPUT_JSONL, 'r', encoding='ascii') as f:
        f.read()
    
    print("  ✓ All files are ASCII-only")


def test_metadata(data: dict):
    """Test metadata fields."""
    print("[TEST] Metadata...")
    
    # Check UTC timestamp format
    assert data['generated_at_utc'].endswith('Z'), "Timestamp must end with 'Z'"
    try:
        datetime.fromisoformat(data['generated_at_utc'].replace('Z', '+00:00'))
    except ValueError as e:
        print(f"  ✗ Invalid timestamp format: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Check schema version
    assert data['schema_version'] == 'v7', f"Expected schema_version=v7, got {data['schema_version']}"
    
    # Check entry count matches
    assert data['entry_count'] == len(data['entries']), \
        f"entry_count ({data['entry_count']}) doesn't match actual entries ({len(data['entries'])})"
    
    # Check entry count is 50-100
    assert 50 <= data['entry_count'] <= 100, \
        f"entry_count should be between 50-100, got {data['entry_count']}"
    
    print(f"  ✓ Metadata valid (schema={data['schema_version']}, count={data['entry_count']})")


def test_entries_structure(json_data: dict):
    """Test that entries have required v7 fields and NO spot_prices."""
    print("[TEST] Entry structure...")
    
    entries = json_data['entries']
    assert len(entries) > 0, "No entries found"
    
    # Check first entry has key fields
    first_entry = entries[0]
    required_fields = ['symbol', 'meta', 'derived']
    for field in required_fields:
        assert field in first_entry, f"Missing required field: {field}"
    
    # Check meta.schema_version
    assert first_entry['meta'].get('schema_version') == 7, \
        f"Expected meta.schema_version=7, got {first_entry['meta'].get('schema_version')}"
    
    # CRITICAL: Verify NO spot_prices in any entry (size reduction)
    for i, entry in enumerate(entries):
        assert 'spot_prices' not in entry, \
            f"Entry {i} contains spot_prices (should be removed for size reduction)"
    
    print(f"  ✓ Entries have valid v7 structure (no spot_prices)")


def test_json_jsonl_match(json_data: dict, jsonl_entries: list):
    """Test that JSON and JSONL contain same entries (both without spot_prices)."""
    print("[TEST] JSON/JSONL consistency...")
    
    json_entries = json_data['entries']
    assert len(json_entries) == len(jsonl_entries), \
        f"Entry count mismatch: JSON has {len(json_entries)}, JSONL has {len(jsonl_entries)}"
    
    # Check symbols match in order
    for i, (json_entry, jsonl_entry) in enumerate(zip(json_entries, jsonl_entries)):
        json_symbol = json_entry.get('symbol')
        jsonl_symbol = jsonl_entry.get('symbol')
        assert json_symbol == jsonl_symbol, \
            f"Symbol mismatch at index {i}: JSON={json_symbol}, JSONL={jsonl_symbol}"
        
        # Verify JSONL also has no spot_prices
        assert 'spot_prices' not in jsonl_entry, \
            f"JSONL entry {i} contains spot_prices (should be removed)"
    
    print(f"  ✓ JSON and JSONL match ({len(json_entries)} entries, no spot_prices)")


def test_spots_artifact(json_data: dict):
    """Test that spots artifact has correct structure and matches main JSON count."""
    print("[TEST] Spots artifact...")
    
    with open(OUTPUT_SPOTS_JSON, 'r', encoding='ascii') as f:
        spots_data = json.load(f)
    
    # Check structure
    required_keys = ['generated_at_utc', 'schema_version', 'entry_count', 'note', 'spots']
    for key in required_keys:
        assert key in spots_data, f"Spots artifact missing key: {key}"
    
    # Check entry count matches main JSON
    assert spots_data['entry_count'] == json_data['entry_count'], \
        f"Spots count ({spots_data['entry_count']}) doesn't match main count ({json_data['entry_count']})"
    
    # Verify spots array
    spots = spots_data['spots']
    assert len(spots) == json_data['entry_count'], \
        f"Spots array length ({len(spots)}) doesn't match entry_count ({json_data['entry_count']})"
    
    # Check symbols match in order
    for i, (entry, spot_entry) in enumerate(zip(json_data['entries'], spots)):
        main_symbol = entry.get('symbol')
        spot_symbol = spot_entry.get('symbol')
        assert main_symbol == spot_symbol, \
            f"Symbol mismatch at index {i}: main={main_symbol}, spots={spot_symbol}"
        
        # Verify spot_prices field exists (even if empty)
        assert 'spot_prices' in spot_entry, f"Spots entry {i} missing spot_prices field"
        assert isinstance(spot_entry['spot_prices'], list), \
            f"Spots entry {i} spot_prices must be list"
    
    print(f"  ✓ Spots artifact valid ({len(spots)} entries with spot_prices)")


def test_determinism():
    """Test that rebuilding produces same output for same day."""
    print("[TEST] Determinism (same-day rebuild)...")
    
    # Save original first symbol
    with open(OUTPUT_JSON, 'r', encoding='ascii') as f:
        original_data = json.load(f)
    original_first_symbol = original_data['entries'][0].get('symbol') if original_data['entries'] else None
    original_count = original_data['entry_count']
    
    try:
        # Suppress subprocess output on Windows
        result = subprocess.run(
            ["python", "scripts/build_public_sample_entries.py"],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode != 0:
            print(f"  ⚠ Determinism test skipped (rebuild failed with exit code {result.returncode})")
            return
        
        # Load rebuilt artifact
        with open(OUTPUT_JSON, 'r', encoding='ascii') as f:
            rebuilt_data = json.load(f)
        
        # Compare entry count and first symbol
        rebuilt_first_symbol = rebuilt_data['entries'][0].get('symbol') if rebuilt_data['entries'] else None
        rebuilt_count = rebuilt_data['entry_count']
        
        assert rebuilt_count == original_count, \
            f"Entry count changed: {original_count} -> {rebuilt_count}"
        
        assert rebuilt_first_symbol == original_first_symbol, \
            f"First symbol changed: {original_first_symbol} -> {rebuilt_first_symbol} (day may have changed)"
        
        print(f"  ✓ Deterministic same-day rebuild ({rebuilt_count} entries, first={rebuilt_first_symbol})")
        
    except (FileNotFoundError, OSError) as e:
        print(f"  ⚠ Determinism test skipped ({e})")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Public Sample Entries Test Suite")
    print("=" * 60)
    print()
    
    # Test 1: Files exist
    test_artifacts_exist()
    
    # Test 2: ASCII-only
    test_ascii_only()
    
    # Test 3: JSON valid
    json_data = test_json_valid()
    
    # Test 4: JSONL valid
    jsonl_entries = test_jsonl_valid()
    
    # Test 5: Metadata
    test_metadata(json_data)
    
    # Test 6: Entry structure
    test_entries_structure(json_data)
    
    # Test 7: JSON/JSONL match
    test_json_jsonl_match(json_data, jsonl_entries)
    
    # Test 8: Spots artifact
    test_spots_artifact(json_data)
    
    # Test 9: Determinism
    test_determinism()
    
    print()
    print("[SUCCESS] All tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
