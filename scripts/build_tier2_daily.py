#!/usr/bin/env python3
"""
Tier 2 Daily Parquet Build

Derives Tier 2 from Tier 3 daily parquet with reduced column footprint.

Tier 2 columns (8):
- symbol, snapshot_ts
- meta, spot_raw, derived, scores (full structs)
- twitter_sentiment_meta (full struct)
- twitter_sentiment_last_cycle (selected fields from last_cycle only)

EXCLUDES: futures_raw, spot_prices, flags, diag, last_2_cycles,
          dynamic-key fields (tag_counts, mention_counts, etc.)

Usage:
    # Build yesterday (cron mode) and upload
    python3 scripts/build_tier2_daily.py --upload

    # Dry-run for specific date
    python3 scripts/build_tier2_daily.py --date 2026-01-18 --dry-run

    # Build date range with upload
    python3 scripts/build_tier2_daily.py --from-date 2026-01-15 --to-date 2026-01-18 --upload

    # Force overwrite existing
    python3 scripts/build_tier2_daily.py --date 2026-01-18 --upload --force

Cron (daily at 00:20 UTC):
    20 0 * * * cd /srv/instrumetriq && python3 scripts/build_tier2_daily.py --upload >> /var/log/tier2_daily.log 2>&1
"""

import argparse
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
TIER2_PREFIX = "tier2/daily"
OUTPUT_DIR = Path("./output/tier2_daily")

# DuckDB column selection - extract only Tier 2 fields
# Excludes from Tier 3: futures_raw, spot_prices, flags, diag, last_2_cycles
# Excludes from last_cycle: bucket_min_posts_for_score (config noise)
# Note: sentiment_activity already cleaned in Tier 3 (no config, recent_posts_1h/4h/24h)
TIER2_COL_SELECT = """
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


# ==============================================================================
# Helpers
# ==============================================================================

def get_s3():
    cfg = get_r2_config()
    return boto3.client(
        "s3",
        endpoint_url=cfg.endpoint,
        aws_access_key_id=cfg.access_key_id,
        aws_secret_access_key=cfg.secret_access_key
    ), cfg.bucket


def yesterday_utc():
    """Return yesterday's date in YYYY-MM-DD format."""
    return (datetime.now(timezone.utc).date() - timedelta(days=1)).strftime("%Y-%m-%d")


def sha256_file(path: Path) -> str:
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def date_range(from_date: str, to_date: str) -> list[str]:
    """Generate list of dates from from_date to to_date (inclusive)."""
    start = datetime.strptime(from_date, "%Y-%m-%d").date()
    end = datetime.strptime(to_date, "%Y-%m-%d").date()
    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return dates


# ==============================================================================
# Core Build Logic
# ==============================================================================

def build_day(s3, bucket: str, date: str, upload: bool = False, force: bool = False, dry_run: bool = False) -> bool:
    """
    Build Tier 2 daily parquet from Tier 3 source.
    
    Args:
        s3: Boto3 S3 client
        bucket: R2 bucket name
        date: Date in YYYY-MM-DD format
        upload: Whether to upload to R2
        force: Whether to overwrite existing files
        dry_run: If True, skip R2 upload
        
    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'='*60}")
    print(f"Building Tier 2 for {date}")
    print(f"{'='*60}")
    
    month_str = date[:7]
    tier3_key = f"{TIER3_PREFIX}/{month_str}/{date}/instrumetriq_tier3_daily_{date}.parquet"
    tier2_key = f"{TIER2_PREFIX}/{month_str}/{date}/instrumetriq_tier2_daily_{date}.parquet"
    manifest_key = f"{TIER2_PREFIX}/{month_str}/{date}/manifest.json"
    
    # Check if Tier 3 source exists
    try:
        tier3_head = s3.head_object(Bucket=bucket, Key=tier3_key)
        tier3_size = tier3_head['ContentLength']
        print(f"Source: {tier3_key} ({tier3_size/1024/1024:.2f} MB)")
    except s3.exceptions.ClientError:
        print(f"[ERROR] Tier 3 source not found: {tier3_key}")
        return False
    
    # Check if Tier 2 already exists
    if not force and not dry_run:
        try:
            s3.head_object(Bucket=bucket, Key=tier2_key)
            print(f"[SKIP] Already exists: {tier2_key} (use --force to overwrite)")
            return True  # Not an error, just skip
        except:
            pass  # Doesn't exist, proceed
    
    # Setup output directory
    out_dir = OUTPUT_DIR / date
    out_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = out_dir / "data.parquet"
    manifest_path = out_dir / "manifest.json"
    
    t0 = time.time()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        src_path = temp_path / "tier3.parquet"
        
        # Download Tier 3 source
        print(f"Downloading Tier 3 source...", end=" ", flush=True)
        s3.download_file(bucket, tier3_key, str(src_path))
        print(f"done ({time.time()-t0:.1f}s)")
        
        # Transform with DuckDB
        print(f"Transforming to Tier 2...", end=" ", flush=True)
        t1 = time.time()
        
        con = duckdb.connect(":memory:")
        con.execute("SET memory_limit='6GB'")
        con.execute("SET threads=2")
        
        query = f"""
            COPY (SELECT {TIER2_COL_SELECT} FROM read_parquet('{src_path}'))
            TO '{parquet_path}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """
        con.execute(query)
        
        # Get row count
        row_count = con.execute(f"SELECT COUNT(*) FROM read_parquet('{parquet_path}')").fetchone()[0]
        con.close()
        
        print(f"done ({time.time()-t1:.1f}s)")
    
    # Calculate stats
    file_size = parquet_path.stat().st_size
    file_hash = sha256_file(parquet_path)
    
    print(f"\nOutput: {parquet_path}")
    print(f"  Rows: {row_count:,}")
    print(f"  Size: {file_size/1024/1024:.2f} MB (was {tier3_size/1024/1024:.2f} MB, {100*file_size/tier3_size:.0f}%)")
    
    # Write manifest
    manifest = {
        "schema_version": "v7",
        "tier": "tier2",
        "tier_description": "Research — reduced column footprint with sentiment last_cycle",
        "date_utc": date,
        "source_tier3": tier3_key,
        "source_tier3_size_bytes": tier3_size,
        "row_count": row_count,
        "build_ts_utc": datetime.now(timezone.utc).isoformat(),
        "parquet_sha256": file_hash,
        "parquet_size_bytes": file_size,
        "column_policy": {
            "columns": [
                "symbol", "snapshot_ts", "meta", "spot_raw", "derived",
                "scores", "twitter_sentiment_meta", "twitter_sentiment_last_cycle"
            ],
            "excluded_from_tier3": [
                "futures_raw", "spot_prices", "flags", "diag"
            ],
            "sentiment_source": "twitter_sentiment_windows.last_cycle",
            "sentiment_excluded_fields": [
                "top_terms", "tag_counts", "mention_counts", "cashtag_counts",
                "url_domain_counts", "lexicon_sentiment", "content_stats", "media_count"
            ]
        }
    }
    
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  Manifest: {manifest_path}")
    
    # Upload to R2
    if upload and not dry_run:
        print(f"\nUploading to R2...")
        
        for local, key in [(parquet_path, tier2_key), (manifest_path, manifest_key)]:
            if not force:
                try:
                    s3.head_object(Bucket=bucket, Key=key)
                    print(f"  [SKIP] {key} exists (use --force)")
                    continue
                except:
                    pass
            s3.upload_file(str(local), bucket, key)
            print(f"  [OK] {key}")
    elif dry_run:
        print(f"\n[DRY-RUN] Would upload to:")
        print(f"  {tier2_key}")
        print(f"  {manifest_key}")
    
    total_time = time.time() - t0
    print(f"\nCompleted in {total_time:.1f}s")
    
    return True


# ==============================================================================
# CLI
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Build Tier 2 daily parquet from Tier 3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build yesterday and upload (cron mode)
  python3 scripts/build_tier2_daily.py --upload

  # Dry-run for specific date
  python3 scripts/build_tier2_daily.py --date 2026-01-18 --dry-run

  # Build date range
  python3 scripts/build_tier2_daily.py --from-date 2026-01-15 --to-date 2026-01-18 --upload
        """
    )
    parser.add_argument("--date", type=str, help="Date to build (YYYY-MM-DD). Default: yesterday")
    parser.add_argument("--from-date", type=str, help="Start date for range (YYYY-MM-DD)")
    parser.add_argument("--to-date", type=str, help="End date for range (YYYY-MM-DD)")
    parser.add_argument("--upload", action="store_true", help="Upload to R2")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    parser.add_argument("--dry-run", action="store_true", help="Local build only, no R2 upload")
    args = parser.parse_args()
    
    # Determine dates to process
    if args.from_date and args.to_date:
        dates = date_range(args.from_date, args.to_date)
        print(f"Building {len(dates)} days: {dates[0]} to {dates[-1]}")
    elif args.date:
        dates = [args.date]
    else:
        dates = [yesterday_utc()]
        print(f"Default: building yesterday ({dates[0]})")
    
    s3, bucket = get_s3()
    
    success = 0
    failed = 0
    
    for date in dates:
        try:
            if build_day(s3, bucket, date, args.upload, args.force, args.dry_run):
                success += 1
            else:
                failed += 1
        except Exception as e:
            print(f"[ERROR] Failed to build {date}: {e}")
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"Done: {success} succeeded, {failed} failed")
    print(f"{'='*60}")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
