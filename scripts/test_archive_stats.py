#!/usr/bin/env python3
"""
Test script for archive statistics artifact.

Validates structure, encoding, and data sanity.
"""

import json
import sys
from pathlib import Path
from datetime import datetime


# Path
ARCHIVE_STATS_FILE = Path("public/data/archive_stats.json")


def test_file_exists():
    """Test that archive stats file exists."""
    print("[TEST] File exists...")
    assert ARCHIVE_STATS_FILE.exists(), f"Archive stats missing: {ARCHIVE_STATS_FILE}"
    print("  ✓ File exists")


def test_ascii_only():
    """Test that file is ASCII-only."""
    print("[TEST] ASCII-only encoding...")
    with open(ARCHIVE_STATS_FILE, 'r', encoding='ascii') as f:
        f.read()
    print("  ✓ ASCII-only")


def test_json_valid():
    """Test JSON is valid and return data."""
    print("[TEST] JSON structure...")
    with open(ARCHIVE_STATS_FILE, 'r', encoding='ascii') as f:
        data = json.load(f)
    
    # Check required keys
    required_keys = [
        'total_entries_all_time',
        'total_days',
        'first_day_utc',
        'last_day_utc',
        'last_entry_ts_utc',
        'source_path',
        'generated_at_utc'
    ]
    
    for key in required_keys:
        assert key in data, f"Missing key: {key}"
    
    # Check types
    assert isinstance(data['total_entries_all_time'], int), "total_entries_all_time must be int"
    assert isinstance(data['total_days'], int), "total_days must be int"
    assert isinstance(data['first_day_utc'], str), "first_day_utc must be string"
    assert isinstance(data['last_day_utc'], str), "last_day_utc must be string"
    assert data['last_entry_ts_utc'] is None or isinstance(data['last_entry_ts_utc'], str), \
        "last_entry_ts_utc must be string or null"
    assert isinstance(data['source_path'], str), "source_path must be string"
    assert isinstance(data['generated_at_utc'], str), "generated_at_utc must be string"
    
    print(f"  ✓ Valid JSON structure")
    return data


def test_data_sanity(data: dict):
    """Test data values are sane."""
    print("[TEST] Data sanity...")
    
    # Check counts are positive
    assert data['total_entries_all_time'] > 0, \
        f"total_entries_all_time must be positive, got {data['total_entries_all_time']}"
    assert data['total_days'] > 0, \
        f"total_days must be positive, got {data['total_days']}"
    
    # Check date formats
    try:
        first_day = datetime.fromisoformat(data['first_day_utc'])
        last_day = datetime.fromisoformat(data['last_day_utc'])
    except ValueError as e:
        print(f"  ✗ Invalid date format: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Check date ordering
    assert last_day >= first_day, \
        f"last_day ({data['last_day_utc']}) must be >= first_day ({data['first_day_utc']})"
    
    # Check generated_at timestamp
    try:
        datetime.fromisoformat(data['generated_at_utc'].replace('Z', '+00:00'))
    except ValueError as e:
        print(f"  ✗ Invalid generated_at_utc format: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Check last_entry_ts if present
    if data['last_entry_ts_utc']:
        try:
            datetime.fromisoformat(data['last_entry_ts_utc'].replace('Z', '+00:00'))
        except ValueError as e:
            print(f"  ✗ Invalid last_entry_ts_utc format: {e}", file=sys.stderr)
            sys.exit(1)
    
    print(f"  ✓ Data sanity checks passed")
    print(f"    Total entries: {data['total_entries_all_time']:,}")
    print(f"    Total days: {data['total_days']}")
    print(f"    Date range: {data['first_day_utc']} to {data['last_day_utc']}")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Archive Statistics Test Suite")
    print("=" * 60)
    print()
    
    # Test 1: File exists
    test_file_exists()
    
    # Test 2: ASCII-only
    test_ascii_only()
    
    # Test 3: JSON valid
    data = test_json_valid()
    
    # Test 4: Data sanity
    test_data_sanity(data)
    
    print()
    print("[SUCCESS] All tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
