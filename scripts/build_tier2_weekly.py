#!/usr/bin/env python3
"""
Tier 2 Weekly Parquet Build - DuckDB VERSION (memory efficient)

Uses DuckDB for schema-safe parquet merging with low memory footprint.

Tier 2 columns (8):
- symbol, snapshot_ts
- meta, spot_raw, derived, scores (full structs)
- twitter_sentiment_meta (full struct)
- twitter_sentiment_windows.last_cycle only (drop last_2_cycles)

EXCLUDES: futures_raw, spot_prices, flags, diag, last_2_cycles
"""

import argparse
import gc
import hashlib
import json
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from r2_config import get_r2_config

import boto3
import duckdb

# ==============================================================================
# Config
# ==============================================================================

TIER3_PREFIX = "tier3/daily"
TIER2_PREFIX = "tier2/weekly"
OUTPUT_DIR = Path("./output/tier2_weekly")
MIN_DAYS = 5

# Columns to SELECT from Tier 3
TIER2_COLUMNS = [
    "symbol",
    "snapshot_ts",
    "meta",
    "spot_raw",
    "derived",
    "scores",
    "twitter_sentiment_meta",
    "twitter_sentiment_windows",
]

# ==============================================================================
# Helpers
# ==============================================================================

def get_s3():
    cfg = get_r2_config()
    return boto3.client("s3", endpoint_url=cfg.endpoint,
                        aws_access_key_id=cfg.access_key_id,
                        aws_secret_access_key=cfg.secret_access_key), cfg.bucket

def previous_sunday():
    today = datetime.now(timezone.utc).date()
    days_back = (today.weekday() + 1) % 7
    if days_back == 0:
        days_back = 7
    return (today - timedelta(days=days_back)).strftime("%Y-%m-%d")

def week_days(end_day):
    end = datetime.strptime(end_day, "%Y-%m-%d").date()
    return [(end - timedelta(days=6-i)).strftime("%Y-%m-%d") for i in range(7)]

def discover_weeks(s3, bucket, min_days=5):
    """Find all calendaristic weeks with enough Tier 3 data."""
    paginator = s3.get_paginator('list_objects_v2')
    days = set()
    for page in paginator.paginate(Bucket=bucket, Prefix=f"{TIER3_PREFIX}/", Delimiter='/'):
        for p in page.get('CommonPrefixes', []):
            d = p['Prefix'].rstrip('/').split('/')[-1]
            if len(d) == 10:
                days.add(d)
    
    if not days:
        return []
    
    min_dt = datetime.strptime(min(days), "%Y-%m-%d").date()
    first_sun = min_dt + timedelta(days=(6 - min_dt.weekday()) % 7)
    
    today = datetime.now(timezone.utc).date()
    last_sun = today - timedelta(days=(today.weekday() + 1) % 7 or 7)
    
    weeks = []
    sun = first_sun
    while sun <= last_sun:
        wk_days = week_days(sun.strftime("%Y-%m-%d"))
        present = [d for d in wk_days if d in days]
        if len(present) >= min_days:
            weeks.append(sun.strftime("%Y-%m-%d"))
        sun += timedelta(days=7)
    
    return weeks

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

# ==============================================================================
# Core Processing with DuckDB
# ==============================================================================

def download_day(s3, bucket, day, temp_dir):
    """Download one day's parquet."""
    key = f"{TIER3_PREFIX}/{day}/data.parquet"
    local_path = Path(temp_dir) / f"{day}.parquet"
    s3.download_file(bucket, key, str(local_path))
    return local_path


def build_week(s3, bucket, end_day, upload=False, force=False):
    """Build one week's Tier 2 parquet using DuckDB - one file at a time."""
    print(f"\n{'='*60}")
    print(f"Building week ending {end_day}")
    print(f"{'='*60}")
    
    days = week_days(end_day)
    start_day = days[0]
    
    # Check which days exist
    present = []
    for d in days:
        try:
            s3.head_object(Bucket=bucket, Key=f"{TIER3_PREFIX}/{d}/data.parquet")
            present.append(d)
        except:
            pass
    
    print(f"Window: {start_day} to {end_day}")
    print(f"Days present: {len(present)}/7 - {present}")
    
    if len(present) < MIN_DAYS:
        print(f"[SKIP] Not enough days ({len(present)} < {MIN_DAYS})")
        return False
    
    # Setup output
    out_dir = OUTPUT_DIR / end_day
    out_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = out_dir / "dataset_entries_7d.parquet"
    manifest_path = out_dir / "manifest.json"
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        
        # Process each day one at a time
        print(f"\nProcessing {len(present)} days...")
        total_rows = 0
        
        # Column list - select only tier2 columns
        # For twitter_sentiment_last_cycle, select only allowed fields
        # EXCLUDE: top_terms, tag_counts, mention_counts, lexicon_sentiment, 
        #          content_stats, media_count, url_domain_counts, cashtag_counts
        col_select = """
            symbol,
            snapshot_ts, 
            meta,
            spot_raw,
            derived,
            scores,
            twitter_sentiment_meta,
            {
                'ai_sentiment': twitter_sentiment_windows.last_cycle.ai_sentiment,
                'author_stats': twitter_sentiment_windows.last_cycle.author_stats,
                'bucket_has_valid_sentiment': twitter_sentiment_windows.last_cycle.bucket_has_valid_sentiment,
                'bucket_min_posts_for_score': twitter_sentiment_windows.last_cycle.bucket_min_posts_for_score,
                'bucket_status': twitter_sentiment_windows.last_cycle.bucket_status,
                'category_counts': twitter_sentiment_windows.last_cycle.category_counts,
                'hybrid_decision_stats': twitter_sentiment_windows.last_cycle.hybrid_decision_stats,
                'platform_engagement': twitter_sentiment_windows.last_cycle.platform_engagement,
                'posts_neg': twitter_sentiment_windows.last_cycle.posts_neg,
                'posts_neu': twitter_sentiment_windows.last_cycle.posts_neu,
                'posts_pos': twitter_sentiment_windows.last_cycle.posts_pos,
                'posts_total': twitter_sentiment_windows.last_cycle.posts_total,
                'sentiment_activity': twitter_sentiment_windows.last_cycle.sentiment_activity
            } AS twitter_sentiment_last_cycle
        """
        
        for i, day in enumerate(present):
            t0 = time.time()
            print(f"  [{i+1}/{len(present)}] {day}...", end=" ", flush=True)
            
            # Download
            src_path = download_day(s3, bucket, day, temp_dir)
            out_path = temp_dir_path / f"tier2_{day}.parquet"
            
            # Process with DuckDB - one file only
            con = duckdb.connect(":memory:")
            con.execute("SET memory_limit='6GB'")
            con.execute("SET threads=1")
            con.execute("SET preserve_insertion_order=false")
            
            query = f"""
                COPY (SELECT {col_select} FROM read_parquet('{src_path}'))
                TO '{out_path}' (FORMAT PARQUET, COMPRESSION ZSTD)
            """
            con.execute(query)
            
            # Get row count
            rows = con.execute(f"SELECT COUNT(*) FROM read_parquet('{out_path}')").fetchone()[0]
            total_rows += rows
            
            con.close()
            
            # Delete source to free disk space
            src_path.unlink()
            gc.collect()
            
            print(f"{rows:,} rows ({time.time()-t0:.1f}s)")
        
        # Merge all tier2 files into one - using PyArrow (simpler schemas now)
        print(f"\nMerging {len(present)} processed files...")
        t0 = time.time()
        
        tier2_files = sorted(temp_dir_path.glob("tier2_*.parquet"))
        
        # Read and concat with PyArrow - schemas should match now
        import pyarrow.parquet as pq
        import pyarrow as pa
        
        tables = []
        for f in tier2_files:
            t = pq.read_table(f)
            tables.append(t)
            print(f"    Read {f.name}: {t.num_rows} rows")
        
        # Concat - this should work since schemas match after DuckDB processing
        merged = pa.concat_tables(tables, promote_options="permissive")
        pq.write_table(merged, parquet_path, compression="zstd")
        
        del tables
        del merged
        gc.collect()
        
        print(f"  Done in {time.time()-t0:.1f}s")
    
    # Write manifest
    size_mb = parquet_path.stat().st_size / (1024*1024)
    print(f"\nOutput: {parquet_path}")
    print(f"  Rows: {total_rows:,}")
    print(f"  Size: {size_mb:.2f} MB")
    
    manifest = {
        "schema_version": "v7",
        "tier": "tier2",
        "window": {"start": start_day, "end": end_day},
        "days_present": present,
        "days_missing": [d for d in days if d not in present],
        "row_count": total_rows,
        "build_ts": datetime.now(timezone.utc).isoformat(),
        "parquet_sha256": sha256(parquet_path),
        "parquet_size_bytes": parquet_path.stat().st_size,
    }
    
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  Manifest: {manifest_path}")
    
    # Upload
    if upload:
        print(f"\nUploading to R2...")
        r2_prefix = f"{TIER2_PREFIX}/{end_day}"
        
        for local, key in [(parquet_path, f"{r2_prefix}/dataset_entries_7d.parquet"),
                           (manifest_path, f"{r2_prefix}/manifest.json")]:
            if not force:
                try:
                    s3.head_object(Bucket=bucket, Key=key)
                    print(f"  [SKIP] {key} exists (use --force)")
                    continue
                except:
                    pass
            s3.upload_file(str(local), bucket, key)
            print(f"  [OK] {key}")
    
    return True


# ==============================================================================
# CLI
# ==============================================================================

def main():
    global MIN_DAYS
    
    parser = argparse.ArgumentParser(description="Build Tier 2 weekly from Tier 3")
    parser.add_argument("--all", action="store_true", help="Build all available weeks")
    parser.add_argument("--upload", action="store_true", help="Upload to R2")
    parser.add_argument("--force", action="store_true", help="Overwrite existing")
    parser.add_argument("--min-days", type=int, default=MIN_DAYS)
    args = parser.parse_args()
    
    MIN_DAYS = args.min_days
    
    s3, bucket = get_s3()
    
    if args.all:
        print("Discovering calendaristic weeks...")
        weeks = discover_weeks(s3, bucket, args.min_days)
        print(f"Found {len(weeks)} weeks: {weeks}")
    else:
        weeks = [previous_sunday()]
        print(f"Default: building week ending {weeks[0]}")
    
    success = 0
    for week in weeks:
        if build_week(s3, bucket, week, args.upload, args.force):
            success += 1
    
    print(f"\n{'='*60}")
    print(f"Done: {success}/{len(weeks)} weeks built")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
