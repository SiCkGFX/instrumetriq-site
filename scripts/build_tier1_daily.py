#!/usr/bin/env python3
"""
Tier 1 Daily Parquet Build

Derives Tier 1 "Starter" dataset from Tier 3 daily parquet.
Flattens nested fields into a simple 19-column schema.

Tier 1 columns (19 flattened fields):
- Identity: symbol, snapshot_ts
- Meta (4): meta_added_ts, meta_expires_ts, meta_duration_sec, meta_archive_schema_version
- Spot (4): spot_mid, spot_spread_bps, spot_range_pct_24h, spot_ticker24_chg
- Derived (2): derived_liq_global_pct, derived_spread_bps
- Scores (1): score_final
- Sentiment (6): sentiment_posts_total, sentiment_posts_pos, sentiment_posts_neu,
                 sentiment_posts_neg, sentiment_mean_score, sentiment_is_silent

EXCLUDES: All futures data, sentiment internals, spot_prices time-series

Usage:
    # Build yesterday (cron mode) and upload
    python3 scripts/build_tier1_daily.py --upload

    # Dry-run for specific date
    python3 scripts/build_tier1_daily.py --date 2026-01-18 --dry-run

    # Build date range with upload
    python3 scripts/build_tier1_daily.py --from-date 2026-01-15 --to-date 2026-01-18 --upload

    # Force overwrite existing
    python3 scripts/build_tier1_daily.py --date 2026-01-18 --upload --force

Cron (daily at 00:30 UTC):
    30 0 * * * cd /srv/instrumetriq && python3 scripts/build_tier1_daily.py --upload >> /var/log/tier1_daily.log 2>&1
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
TIER1_PREFIX = "tier1/daily"
OUTPUT_DIR = Path("./output/tier1_daily")

# DuckDB column selection - flatten nested fields into 19 columns
# Reference: TIER1_FIELD_SPEC in build_tier1_weekly.py
TIER1_COL_SELECT = """
    -- Identity
    symbol,
    snapshot_ts,
    
    -- Meta (flattened)
    meta.added_ts AS meta_added_ts,
    meta.expires_ts AS meta_expires_ts,
    meta.duration_sec AS meta_duration_sec,
    meta.archive_schema_version AS meta_archive_schema_version,
    
    -- Spot (flattened)
    spot_raw.mid AS spot_mid,
    spot_raw.spread_bps AS spot_spread_bps,
    spot_raw.range_pct_24h AS spot_range_pct_24h,
    spot_raw.ticker24_chg AS spot_ticker24_chg,
    
    -- Derived (flattened)
    derived.liq_global_pct AS derived_liq_global_pct,
    derived.spread_bps AS derived_spread_bps,
    
    -- Scores (flattened)
    scores.final AS score_final,
    
    -- Sentiment (flattened from twitter_sentiment_windows.last_cycle)
    twitter_sentiment_windows.last_cycle.posts_total AS sentiment_posts_total,
    twitter_sentiment_windows.last_cycle.posts_pos AS sentiment_posts_pos,
    twitter_sentiment_windows.last_cycle.posts_neu AS sentiment_posts_neu,
    twitter_sentiment_windows.last_cycle.posts_neg AS sentiment_posts_neg,
    twitter_sentiment_windows.last_cycle.hybrid_decision_stats.mean_score AS sentiment_mean_score,
    twitter_sentiment_windows.last_cycle.sentiment_activity.is_silent AS sentiment_is_silent
"""

# Field list for manifest
TIER1_FIELDS = [
    "symbol", "snapshot_ts",
    "meta_added_ts", "meta_expires_ts", "meta_duration_sec", "meta_archive_schema_version",
    "spot_mid", "spot_spread_bps", "spot_range_pct_24h", "spot_ticker24_chg",
    "derived_liq_global_pct", "derived_spread_bps",
    "score_final",
    "sentiment_posts_total", "sentiment_posts_pos", "sentiment_posts_neu",
    "sentiment_posts_neg", "sentiment_mean_score", "sentiment_is_silent"
]


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
    Build Tier 1 daily parquet from Tier 3 source.
    
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
    print(f"Building Tier 1 for {date}")
    print(f"{'='*60}")
    
    tier3_key = f"{TIER3_PREFIX}/{date}/data.parquet"
    tier1_key = f"{TIER1_PREFIX}/{date}/data.parquet"
    manifest_key = f"{TIER1_PREFIX}/{date}/manifest.json"
    
    # Check if Tier 3 source exists
    try:
        tier3_head = s3.head_object(Bucket=bucket, Key=tier3_key)
        tier3_size = tier3_head['ContentLength']
        print(f"Source: {tier3_key} ({tier3_size/1024/1024:.2f} MB)")
    except s3.exceptions.ClientError:
        print(f"[ERROR] Tier 3 source not found: {tier3_key}")
        return False
    
    # Check if Tier 1 already exists
    if not force and not dry_run:
        try:
            s3.head_object(Bucket=bucket, Key=tier1_key)
            print(f"[SKIP] Already exists: {tier1_key} (use --force to overwrite)")
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
        
        # Transform with DuckDB - flatten nested fields
        print(f"Transforming to Tier 1 (flattening)...", end=" ", flush=True)
        t1 = time.time()
        
        con = duckdb.connect(":memory:")
        con.execute("SET memory_limit='4GB'")
        con.execute("SET threads=2")
        
        query = f"""
            COPY (SELECT {TIER1_COL_SELECT} FROM read_parquet('{src_path}'))
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
    print(f"  Size: {file_size/1024:.1f} KB (was {tier3_size/1024/1024:.2f} MB, {100*file_size/tier3_size:.1f}%)")
    
    # Write manifest
    manifest = {
        "schema_version": "v7",
        "tier": "tier1",
        "tier_description": "Starter — light entry table with aggregated sentiment (no futures, no sentiment internals)",
        "date_utc": date,
        "source_tier3": tier3_key,
        "source_tier3_size_bytes": tier3_size,
        "row_count": row_count,
        "build_ts_utc": datetime.now(timezone.utc).isoformat(),
        "parquet_sha256": file_hash,
        "parquet_size_bytes": file_size,
        "field_policy": {
            "approach": "explicit_allowlist_flattened",
            "total_fields": len(TIER1_FIELDS),
            "fields": TIER1_FIELDS,
            "field_categories": {
                "identity_timing": TIER1_FIELDS[:6],
                "spot_snapshot": TIER1_FIELDS[6:10],
                "derived_metrics": TIER1_FIELDS[10:12],
                "scores": TIER1_FIELDS[12:13],
                "sentiment_aggregated": TIER1_FIELDS[13:]
            },
            "sentiment_source": "twitter_sentiment_windows.last_cycle",
            "sentiment_note": "Sentiment fields are aggregated-only from last_cycle. No internals included.",
            "exclusions": [
                "futures_raw (all futures data)",
                "flags.futures_data_ok (futures existence flag)",
                "spot_prices (time-series arrays)",
                "twitter_sentiment_windows (full struct)",
                "All sentiment internals: decision_sources, conf_mean, top_terms, category_counts, etc."
            ]
        }
    }
    
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  Manifest: {manifest_path}")
    
    # Upload to R2
    if upload and not dry_run:
        print(f"\nUploading to R2...")
        
        for local, key in [(parquet_path, tier1_key), (manifest_path, manifest_key)]:
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
        print(f"  {tier1_key}")
        print(f"  {manifest_key}")
    
    total_time = time.time() - t0
    print(f"\nCompleted in {total_time:.1f}s")
    
    return True


# ==============================================================================
# CLI
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Build Tier 1 daily parquet from Tier 3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build yesterday and upload (cron mode)
  python3 scripts/build_tier1_daily.py --upload

  # Dry-run for specific date
  python3 scripts/build_tier1_daily.py --date 2026-01-18 --dry-run

  # Build date range
  python3 scripts/build_tier1_daily.py --from-date 2026-01-15 --to-date 2026-01-18 --upload
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
            import traceback
            traceback.print_exc()
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"Done: {success} succeeded, {failed} failed")
    print(f"{'='*60}")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
