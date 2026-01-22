#!/usr/bin/env python3
"""
Tier 3 Schema Verification Script

Lightweight verification that:
1. Reads parquet metadata (no data load)
2. Reads ONE row only
3. Checks all columns have data
4. Reports any nulls or missing fields

Usage:
    python3 scripts/verify_tier3_schema.py [--date 2026-01-17]
    python3 scripts/verify_tier3_schema.py --all
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

try:
    import pyarrow.parquet as pq
except ImportError:
    print("[ERROR] pyarrow required: pip install pyarrow", file=sys.stderr)
    sys.exit(1)


# ==============================================================================
# Expected Schema Definition
# ==============================================================================

EXPECTED_TOP_COLUMNS = [
    'symbol',
    'snapshot_ts', 
    'meta',
    'spot_raw',
    'futures_raw',
    'derived',
    'scores',
    'flags',
    'diag',
    'twitter_sentiment_windows',
    'twitter_sentiment_meta',
    'spot_prices',
]

# Fields we expect in twitter_sentiment_windows.last_cycle
EXPECTED_SENTIMENT_FIELDS = [
    'posts_total',
    'posts_pos',
    'posts_neg', 
    'posts_neu',
    'platform_engagement',
    'sentiment_activity',
    'ai_sentiment',
    'lexicon_sentiment',
]


# ==============================================================================
# Verification Functions
# ==============================================================================

def verify_schema_only(parquet_path: Path) -> dict:
    """Verify schema without loading any data."""
    pf = pq.ParquetFile(parquet_path)
    schema = pf.schema_arrow
    
    result = {
        'rows': pf.metadata.num_rows,
        'columns': pf.metadata.num_columns,
        'column_names': [f.name for f in schema],
        'missing_columns': [],
        'extra_columns': [],
    }
    
    # Check expected columns
    for col in EXPECTED_TOP_COLUMNS:
        if col not in result['column_names']:
            result['missing_columns'].append(col)
    
    # Check for extra columns
    for col in result['column_names']:
        if col not in EXPECTED_TOP_COLUMNS:
            result['extra_columns'].append(col)
    
    return result


def verify_one_row(parquet_path: Path) -> dict:
    """Read exactly ONE row and check all fields have data."""
    pf = pq.ParquetFile(parquet_path)
    
    # Read just first row of first row group, one column at a time
    result = {
        'row_data': {},
        'null_columns': [],
        'populated_columns': [],
        'sentiment_check': {},
    }
    
    for field in pf.schema_arrow:
        col_name = field.name
        
        # Read just this one column, first row
        table = pf.read_row_group(0, columns=[col_name])
        
        # Get first value using to_pylist on just one element
        first_chunk = table.column(0).chunk(0)
        if len(first_chunk) > 0:
            # Use as_py() on scalar for efficiency
            val = first_chunk[0].as_py()
            
            if val is None:
                result['null_columns'].append(col_name)
            else:
                result['populated_columns'].append(col_name)
                
                # Store summary, not full value
                if isinstance(val, dict):
                    result['row_data'][col_name] = f"dict({len(val)} keys)"
                elif isinstance(val, list):
                    result['row_data'][col_name] = f"list({len(val)} items)"
                elif isinstance(val, str) and len(val) > 50:
                    result['row_data'][col_name] = val[:50] + "..."
                else:
                    result['row_data'][col_name] = val
                
                # Deep check twitter_sentiment_windows
                if col_name == 'twitter_sentiment_windows' and isinstance(val, dict):
                    result['sentiment_check'] = check_sentiment_structure(val)
        else:
            result['null_columns'].append(col_name)
    
    return result


def check_sentiment_structure(tsw: dict) -> dict:
    """Check twitter_sentiment_windows structure."""
    check = {
        'has_last_cycle': False,
        'last_cycle_keys': [],
        'missing_sentiment_fields': [],
        'found_sentiment_fields': [],
        'platform_engagement_ok': False,
        'sentiment_activity_ok': False,
    }
    
    if 'last_cycle' in tsw and tsw['last_cycle']:
        check['has_last_cycle'] = True
        lc = tsw['last_cycle']
        check['last_cycle_keys'] = list(lc.keys())
        
        for field in EXPECTED_SENTIMENT_FIELDS:
            if field in lc:
                check['found_sentiment_fields'].append(field)
                
                # Check nested structures
                if field == 'platform_engagement' and lc[field]:
                    pe = lc[field]
                    if isinstance(pe, dict) and 'total_likes' in pe:
                        check['platform_engagement_ok'] = True
                
                if field == 'sentiment_activity' and lc[field]:
                    sa = lc[field]
                    if isinstance(sa, dict) and 'is_silent' in sa:
                        check['sentiment_activity_ok'] = True
            else:
                check['missing_sentiment_fields'].append(field)
    
    return check


def verify_day(date_str: str, tier3_dir: Path) -> dict:
    """Verify a single day's Tier 3 parquet."""
    day_dir = tier3_dir / date_str
    parquet_path = day_dir / 'data.parquet'
    manifest_path = day_dir / 'manifest.json'
    
    result = {
        'date': date_str,
        'exists': False,
        'manifest_ok': False,
        'schema_ok': False,
        'data_ok': False,
        'errors': [],
    }
    
    if not parquet_path.exists():
        result['errors'].append(f"Parquet not found: {parquet_path}")
        return result
    
    result['exists'] = True
    
    # Check manifest
    if manifest_path.exists():
        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
            result['manifest_ok'] = True
            result['manifest'] = {
                'rows': manifest.get('row_count'),
                'coverage': manifest.get('coverage_pct'),
                'hours': manifest.get('hours_available'),
            }
        except Exception as e:
            result['errors'].append(f"Manifest error: {e}")
    else:
        result['errors'].append("Manifest not found")
    
    # Check schema (no data load)
    try:
        schema_result = verify_schema_only(parquet_path)
        result['schema'] = schema_result
        if not schema_result['missing_columns']:
            result['schema_ok'] = True
        else:
            result['errors'].append(f"Missing columns: {schema_result['missing_columns']}")
    except Exception as e:
        result['errors'].append(f"Schema error: {e}")
        return result
    
    # Check one row of data
    try:
        row_result = verify_one_row(parquet_path)
        result['row_check'] = row_result
        
        if not row_result['null_columns']:
            result['data_ok'] = True
        else:
            # Some nulls are OK (like futures_raw for spot-only coins)
            critical_nulls = [c for c in row_result['null_columns'] 
                           if c not in ['futures_raw', 'diag']]
            if critical_nulls:
                result['errors'].append(f"Critical null columns: {critical_nulls}")
            else:
                result['data_ok'] = True
        
        # Check sentiment structure (warnings only, not errors)
        sc = row_result.get('sentiment_check', {})
        if sc:
            result['sentiment_warnings'] = []
            if not sc.get('has_last_cycle'):
                result['sentiment_warnings'].append("twitter_sentiment_windows.last_cycle missing in sampled row")
            if not sc.get('platform_engagement_ok'):
                result['sentiment_warnings'].append("platform_engagement structure incomplete in sampled row")
            if not sc.get('sentiment_activity_ok'):
                result['sentiment_warnings'].append("sentiment_activity structure incomplete in sampled row")
    except Exception as e:
        result['errors'].append(f"Row check error: {e}")
    
    return result


def print_result(result: dict):
    """Print verification result."""
    date = result['date']
    
    if result['exists'] and result['schema_ok'] and result['data_ok']:
        status = "✅ PASS"
    elif result['exists'] and result['schema_ok']:
        status = "⚠️  WARN"
    elif result['exists']:
        status = "❌ FAIL"
    else:
        status = "❌ MISSING"
    
    manifest = result.get('manifest', {})
    rows = manifest.get('rows', '?')
    coverage = manifest.get('coverage', '?')
    
    print(f"{date}  {status}  rows={rows}  coverage={coverage}%")
    
    if result.get('errors'):
        for err in result['errors']:
            print(f"    └─ ❌ {err}")
    
    if result.get('sentiment_warnings'):
        for warn in result['sentiment_warnings']:
            print(f"    └─ ⚠️  {warn}")


def main():
    parser = argparse.ArgumentParser(description='Verify Tier 3 schema and data')
    parser.add_argument('--date', help='Specific date to verify (YYYY-MM-DD)')
    parser.add_argument('--all', action='store_true', help='Verify all available days')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed output')
    args = parser.parse_args()
    
    tier3_dir = Path('output/tier3_daily')
    
    if not tier3_dir.exists():
        print(f"[ERROR] Tier 3 directory not found: {tier3_dir}", file=sys.stderr)
        sys.exit(1)
    
    print("=" * 60)
    print("TIER 3 SCHEMA VERIFICATION")
    print("=" * 60)
    print()
    
    if args.date:
        dates = [args.date]
    elif args.all:
        dates = sorted([d.name for d in tier3_dir.iterdir() if d.is_dir()])
    else:
        # Default: latest day
        dates = sorted([d.name for d in tier3_dir.iterdir() if d.is_dir()])
        if dates:
            dates = [dates[-1]]
        else:
            print("[ERROR] No Tier 3 days found", file=sys.stderr)
            sys.exit(1)
    
    print(f"Verifying {len(dates)} day(s)...")
    print()
    
    all_pass = True
    for date in dates:
        result = verify_day(date, tier3_dir)
        print_result(result)
        
        if args.verbose and result.get('row_check'):
            rc = result['row_check']
            print(f"    Populated columns: {len(rc['populated_columns'])}")
            print(f"    Null columns: {rc['null_columns']}")
            sc = rc.get('sentiment_check', {})
            if sc:
                print(f"    Sentiment fields found: {sc.get('found_sentiment_fields', [])}")
        
        if result.get('errors'):
            all_pass = False
    
    print()
    print("=" * 60)
    if all_pass:
        print("✅ ALL VERIFICATIONS PASSED")
    else:
        print("❌ SOME VERIFICATIONS FAILED")
    print("=" * 60)
    
    sys.exit(0 if all_pass else 1)


if __name__ == '__main__':
    main()
