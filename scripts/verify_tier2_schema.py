#!/usr/bin/env python3
"""
Verify Tier 2 weekly parquet schema.

Tier 2 includes 8 top-level columns:
- symbol, snapshot_ts (scalars)
- meta, spot_raw, derived, scores, twitter_sentiment_meta (full structs)
- twitter_sentiment_windows (with only last_cycle, filtered fields)

Run: python scripts/verify_tier2_schema.py --week 2025-01-05
     python scripts/verify_tier2_schema.py --all
"""

import argparse
import json
from pathlib import Path

import pyarrow.parquet as pq


# Expected top-level columns for Tier 2 weekly parquet (8 columns)
EXPECTED_COLUMNS = [
    'symbol',
    'snapshot_ts',
    'meta',
    'spot_raw',
    'derived',
    'scores',
    'twitter_sentiment_meta',
    'twitter_sentiment_windows',
]

# Fields that must be present in last_cycle
LAST_CYCLE_REQUIRED_FIELDS = [
    'ai_sentiment',
    'author_stats',
    'bucket_has_valid_sentiment',
    'bucket_min_posts_for_score',
    'bucket_status',
    'cashtag_counts',
    'category_counts',
    'hybrid_decision_stats',
    'platform_engagement',
    'posts_neg',
    'posts_neu',
    'posts_pos',
    'posts_total',
    'sentiment_activity',
]

# Fields that must NOT be in last_cycle (excluded for Tier 2)
LAST_CYCLE_FORBIDDEN_FIELDS = [
    'content_stats',
    'lexicon_sentiment',
    'media_count',
    'mention_counts',
    'tag_counts',
    'top_terms',
    'url_domain_counts',
]


def verify_week(week_dir: Path, verbose: bool = False) -> tuple[bool, list[str], list[str]]:
    """
    Verify a single Tier 2 week directory.
    Returns (success, errors, warnings).
    """
    errors = []
    warnings = []
    
    parquet_path = week_dir / 'dataset_entries_7d.parquet'
    manifest_path = week_dir / 'manifest.json'
    
    if not parquet_path.exists():
        errors.append(f"Missing parquet file: {parquet_path}")
        return False, errors, warnings
    
    if not manifest_path.exists():
        warnings.append(f"Missing manifest.json")
    
    try:
        pf = pq.ParquetFile(parquet_path)
        schema = pf.schema_arrow
        columns = schema.names
        
        # Check expected columns
        missing_cols = set(EXPECTED_COLUMNS) - set(columns)
        extra_cols = set(columns) - set(EXPECTED_COLUMNS)
        
        if missing_cols:
            errors.append(f"Missing columns: {missing_cols}")
        if extra_cols:
            warnings.append(f"Extra columns (ok): {extra_cols}")
        
        # Read ONE row to verify structure
        if pf.metadata.num_rows == 0:
            errors.append("Parquet is empty (0 rows)")
            return False, errors, warnings
        
        table = pf.read_row_group(0)
        row = {col: table.column(col)[0].as_py() for col in columns if col in table.schema.names}
        
        # Verify symbol exists
        if not row.get('symbol'):
            errors.append("symbol is empty/null")
        
        # Verify snapshot_ts exists
        if not row.get('snapshot_ts'):
            errors.append("snapshot_ts is empty/null")
        
        # Verify sentiment fields (can be null for silent entries)
        # For Tier 2, check twitter_sentiment_windows structure
        tsw = row.get('twitter_sentiment_windows')
        if tsw is not None:
            if not isinstance(tsw, dict):
                errors.append(f"twitter_sentiment_windows is not a dict: {type(tsw)}")
            else:
                # Should only have last_cycle, NOT last_2_cycles
                if 'last_2_cycles' in tsw:
                    errors.append("twitter_sentiment_windows contains last_2_cycles (should be filtered)")
                
                last_cycle = tsw.get('last_cycle')
                if last_cycle is None:
                    warnings.append("twitter_sentiment_windows.last_cycle is null")
                elif isinstance(last_cycle, dict):
                    # Check required fields
                    lc_keys = set(last_cycle.keys())
                    missing_lc = set(LAST_CYCLE_REQUIRED_FIELDS) - lc_keys
                    if missing_lc:
                        warnings.append(f"last_cycle missing required fields: {missing_lc}")
                    
                    # Check forbidden fields are NOT present
                    forbidden_present = set(LAST_CYCLE_FORBIDDEN_FIELDS) & lc_keys
                    if forbidden_present:
                        errors.append(f"last_cycle contains forbidden fields: {forbidden_present}")
                    
                    # Verify sentiment_activity.is_silent structure (should only have is_silent)
                    sa = last_cycle.get('sentiment_activity')
                    if sa is not None and isinstance(sa, dict):
                        # For Tier 2, sentiment_activity should only have is_silent
                        if 'is_silent' not in sa:
                            warnings.append("sentiment_activity missing is_silent")
                        extra_sa = set(sa.keys()) - {'is_silent'}
                        if extra_sa:
                            errors.append(f"sentiment_activity contains extra fields: {extra_sa}")
                    
                    # Verify platform_engagement structure if present
                    pe = last_cycle.get('platform_engagement')
                    if pe is not None and isinstance(pe, dict):
                        expected_pe_keys = {
                            'total_likes', 'total_retweets', 'total_replies', 
                            'total_quotes', 'total_bookmarks',
                            'avg_likes', 'avg_retweets', 'avg_replies', 'avg_views',
                            'total_impressions', 'total_views'
                        }
                        missing_pe = expected_pe_keys - set(pe.keys())
                        if missing_pe:
                            warnings.append(f"platform_engagement missing keys: {missing_pe}")
                else:
                    errors.append(f"last_cycle is not a dict: {type(last_cycle)}")
        
        # Verify manifest content
        if manifest_path.exists():
            with open(manifest_path) as f:
                manifest = json.load(f)
            
            manifest_rows = manifest.get('row_count', 0)
            actual_rows = pf.metadata.num_rows
            if manifest_rows != actual_rows:
                errors.append(f"Manifest row_count ({manifest_rows}) != actual ({actual_rows})")
            
            # Check source coverage
            source_cov = manifest.get('source_coverage', {})
            if not source_cov:
                warnings.append("Manifest missing source_coverage")
        
        if verbose:
            print(f"  Columns: {len(columns)}")
            print(f"  Rows: {pf.metadata.num_rows:,}")
            print(f"  Sample symbol: {row.get('symbol')}")
            print(f"  Sample ts: {row.get('snapshot_ts')}")
            # Extract nested fields for display
            tsw = row.get('twitter_sentiment_windows') or {}
            last_cycle = tsw.get('last_cycle') or {}
            sa = last_cycle.get('sentiment_activity') or {}
            print(f"  last_cycle present: {bool(last_cycle)}")
            print(f"  is_silent: {sa.get('is_silent')}")
            print(f"  posts_total: {last_cycle.get('posts_total')}")
        
        return len(errors) == 0, errors, warnings
        
    except Exception as e:
        errors.append(f"Exception reading parquet: {e}")
        return False, errors, warnings


def main():
    parser = argparse.ArgumentParser(description='Verify Tier 2 weekly parquet schema')
    parser.add_argument('--week', help='Week ending date (YYYY-MM-DD)')
    parser.add_argument('--all', action='store_true', help='Verify all weeks')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show details')
    args = parser.parse_args()
    
    tier2_dir = Path('output/tier2_weekly')
    
    if args.all:
        weeks = sorted([d for d in tier2_dir.iterdir() if d.is_dir()])
    elif args.week:
        weeks = [tier2_dir / args.week]
    else:
        parser.error('Specify --week YYYY-MM-DD or --all')
    
    total = 0
    passed = 0
    failed = 0
    with_warnings = 0
    
    for week_dir in weeks:
        if not week_dir.exists():
            print(f"❌ {week_dir.name}: Directory not found")
            failed += 1
            total += 1
            continue
        
        total += 1
        success, errors, warnings = verify_week(week_dir, args.verbose)
        
        if success:
            passed += 1
            if warnings:
                with_warnings += 1
                print(f"⚠️  {week_dir.name}: PASS with warnings")
                for w in warnings:
                    print(f"     ⚠️  {w}")
            else:
                print(f"✅ {week_dir.name}: PASS")
        else:
            failed += 1
            print(f"❌ {week_dir.name}: FAIL")
            for e in errors:
                print(f"     ❌ {e}")
            for w in warnings:
                print(f"     ⚠️  {w}")
    
    print()
    print(f"Summary: {passed}/{total} passed, {failed} failed, {with_warnings} with warnings")
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    exit(main())
