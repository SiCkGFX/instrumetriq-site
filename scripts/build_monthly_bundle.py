#!/usr/bin/env python3
"""
Monthly Bundle Builder

Merges daily parquet files for a given month and tier into a single monthly parquet file.
Designed for Tier 1, Tier 2, and Tier 3.

Strategy:
1. Identify all days in the target month.
2. Download valid daily parquets from R2 (Source of Truth) to a temp directory.
3. Merge them using PyArrow.
4. Upload the result to R2 as `tierX/monthly/YYYY-MM/data.parquet`.

Usage:
    # Build Tier 3 for Jan 2026 and upload
    python3 scripts/build_monthly_bundle.py --tier tier3 --month 2026-01 --upload

    # Dry run (verify what would happen)
    python3 scripts/build_monthly_bundle.py --tier tier1 --month 2025-12

"""

import argparse
import boto3
import sys
import shutil
import tempfile
import calendar
import json
import hashlib
from pathlib import Path
from datetime import datetime, date, timedelta, timezone

# Add scripts directory to path for local imports
sys.path.insert(0, str(Path(__file__).parent))

from r2_config import get_r2_config

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:
    print("[ERROR] pyarrow is required. Install with: pip install pyarrow", file=sys.stderr)
    sys.exit(1)


def get_days_in_month(year, month):
    """Return a list of date objects for every day in the month."""
    num_days = calendar.monthrange(year, month)[1]
    days = [date(year, month, day) for day in range(1, num_days + 1)]
    return days


def get_last_finished_month():
    """
    Determine the last complete calendar month.
    
    Returns:
        str: Month in YYYY-MM format (e.g., "2025-12")
    
    Logic:
        - If today is Jan 27, returns "2025-12"
        - If today is Feb 1, returns "2026-01"
        - Always returns: (first day of current month) - 1 day
    """
    today = datetime.now(timezone.utc)
    first_of_this_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day_of_prev_month = first_of_this_month - timedelta(days=1)
    return last_day_of_prev_month.strftime("%Y-%m")


def main():
    parser = argparse.ArgumentParser(description="Build Monthly Parquet Bundle")
    parser.add_argument("--tier", required=True, choices=["tier1", "tier2", "tier3"], help="Tier to build (tier1, tier2, tier3)")
    parser.add_argument("--month", help="Target month (YYYY-MM). If not provided, auto-detects last finished month.")
    parser.add_argument("--upload", action="store_true", help="Upload result to R2")
    parser.add_argument("--force", action="store_true", help="Overwrite existing monthly file if present")
    parser.add_argument("--mtd", action="store_true", help="Build month-to-date (current month, day 1 through yesterday) instead of finished month")
    args = parser.parse_args()

    # Determine Month
    if args.mtd:
        # Month-to-date: current month
        target_month = datetime.now(timezone.utc).strftime("%Y-%m")
        print(f"[MTD] Building month-to-date for current month: {target_month}")
    elif args.month:
        target_month = args.month
    else:
        target_month = get_last_finished_month()
        print(f"[AUTO] No --month specified, using last finished month: {target_month}")

    # Parse Month
    try:
        dt = datetime.strptime(target_month, "%Y-%m")
        year, month = dt.year, dt.month
    except ValueError:
        print(f"[ERROR] Invalid month format: {target_month}. Use YYYY-MM.", file=sys.stderr)
        sys.exit(1)

    # Config
    try:
        cfg = get_r2_config()
    except Exception as e:
        print(f"[ERROR] Loading R2 config: {e}", file=sys.stderr)
        sys.exit(1)

    s3 = boto3.client(
        's3',
        endpoint_url=cfg.endpoint,
        aws_access_key_id=cfg.access_key_id,
        aws_secret_access_key=cfg.secret_access_key,
        region_name='auto'
    )

    # 1. Prepare Workspace
    if args.mtd:
        # MTD uses /mtd/ prefix
        target_key = f"{args.tier}/mtd/{target_month}/instrumetriq_{args.tier}_mtd_{target_month}.parquet"
    else:
        # Regular monthly uses /monthly/ prefix  
        target_key = f"{args.tier}/monthly/{target_month}/instrumetriq_{args.tier}_monthly_{target_month}.parquet"
    
    # Check if target exists
    if args.upload and not args.force:
        try:
            s3.head_object(Bucket=cfg.bucket, Key=target_key)
            print(f"[SKIP] Target already exists: {target_key} (Usage --force to overwrite)")
            return
        except:
            pass # Target does not exist, proceed

    days = get_days_in_month(year, month)
    
    # For MTD mode, only include days up through yesterday
    if args.mtd:
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
        days = [d for d in days if d <= yesterday]
        print(f"--- Building {args.tier} MTD for {target_month} (day 1 through {yesterday}, {len(days)} days) ---")
    else:
        print(f"--- Building {args.tier} bundle for {target_month} ({len(days)} potential days) ---")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        downloaded_files = []

        # 2. Download Daily Files
        print(">>> Checking/Downloading daily files from R2...")
        
        for day in days:
            day_str = day.strftime("%Y-%m-%d")
            # New structure: tierX/daily/YYYY-MM/YYYY-MM-DD/instrumetriq_tierX_daily_YYYY-MM-DD.parquet
            # target_month is YYYY-MM
            daily_key = f"{args.tier}/daily/{target_month}/{day_str}/instrumetriq_{args.tier}_daily_{day_str}.parquet"
            local_name = temp_path / f"{day_str}.parquet"

            try:
                # Check existance first (saves bandwidth on 404s, though head_object is an API call)
                # Just get_object is cleaner? No, head first avoids reading body errors.
                s3.head_object(Bucket=cfg.bucket, Key=daily_key)
                
                # Download
                print(f"    Downloading {day_str}...", end="", flush=True)
                s3.download_file(cfg.bucket, daily_key, str(local_name))
                downloaded_files.append(local_name)
                print(" OK")
            except Exception as e:
                # 404 is expected for future dates or missed days
                print(f"    MISSING {day_str} (Skipping)")

        if not downloaded_files:
            print("[ERROR] No daily files found for this month used to build bundle.")
            sys.exit(1)

        print(f"\n>>> Merging {len(downloaded_files)} files...")

        # 3. Merge with PyArrow
        # Read all tables and normalize schemas
        tables = []
        for f in downloaded_files:
            try:
                t = pq.read_table(f)
                
                # Remove internal fields that shouldn't be exposed externally
                # backfill_normalized: internal memo from Jan 15th futures backfill
                if 'diag' in t.schema.names:
                    diag_field = t.schema.field('diag')
                    diag_type = diag_field.type
                    
                    # Check if backfill_normalized exists in the diag struct
                    if hasattr(diag_type, 'get_field_index'):
                        try:
                            backfill_idx = diag_type.get_field_index('backfill_normalized')
                            # Field exists, remove it by reconstructing the struct
                            new_diag_fields = [diag_type[i] for i in range(len(diag_type)) if i != backfill_idx]
                            new_diag_type = pa.struct(new_diag_fields)
                            
                            # Rebuild schema without backfill_normalized
                            new_schema_fields = []
                            for field in t.schema:
                                if field.name == 'diag':
                                    new_schema_fields.append(pa.field('diag', new_diag_type))
                                else:
                                    new_schema_fields.append(field)
                            new_schema = pa.schema(new_schema_fields)
                            
                            # Cast to new schema (PyArrow will drop the field)
                            t = t.cast(new_schema)
                        except (KeyError, ValueError):
                            # Field doesn't exist, no action needed
                            pass
                
                tables.append(t)
            except Exception as e:
                print(f"[WARN] Failed to read parquet {f}: {e}")

        if not tables:
             print("[ERROR] No valid parquet tables loaded.")
             sys.exit(1)

        combined_table = pa.concat_tables(tables)
        
        # Write output locally
        output_file = temp_path / "monthly_bundle.parquet"
        pq.write_table(combined_table, output_file, compression='snappy')
        
        final_size_mb = output_file.stat().st_size / (1024 * 1024)
        final_size_bytes = output_file.stat().st_size
        print(f">>> Bundle Created: {final_size_mb:.2f} MB")
        print(f"    Rows: {combined_table.num_rows}")
        
        # Generate SHA256 hash
        sha256_hash = hashlib.sha256()
        with open(output_file, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256_hash.update(chunk)
        parquet_sha256 = sha256_hash.hexdigest()
        
        # Create manifest.json
        manifest = {
            "schema_version": "v7",
            "tier": args.tier,
            "bundle_type": "month_to_date" if args.mtd else "finished_month",
            "month": target_month,
            "coverage_start_date": days[0].strftime("%Y-%m-%d") if days else None,
            "coverage_end_date": days[-1].strftime("%Y-%m-%d") if days else None,
            "days_included": len(downloaded_files),
            "row_count": combined_table.num_rows,
            "build_ts_utc": datetime.now(timezone.utc).isoformat(),
            "parquet_sha256": parquet_sha256,
            "parquet_size_bytes": final_size_bytes,
            "parquet_filename": target_key.split('/')[-1],
            "source_daily_files": [f.name for f in downloaded_files]
        }
        
        manifest_file = temp_path / "manifest.json"
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        print(f">>> Manifest created: {len(downloaded_files)} days merged")

        # 4. Upload
        if args.upload:
            print(f"\n>>> Uploading parquet to {target_key}...")
            try:
                s3.upload_file(
                    str(output_file),
                    cfg.bucket,
                    target_key,
                    ExtraArgs={'StorageClass': 'STANDARD'}
                )
                print("SUCCESS: Parquet uploaded.")
            except Exception as e:
                print(f"[ERROR] Parquet upload failed: {e}")
                sys.exit(1)
            
            # Upload manifest.json
            manifest_key = target_key.replace('.parquet', '_manifest.json') if not target_key.endswith('/') else target_key.rstrip('/') + '/manifest.json'
            # Better: put it in same directory
            manifest_key = '/'.join(target_key.split('/')[:-1]) + '/manifest.json'
            
            print(f">>> Uploading manifest to {manifest_key}...")
            try:
                s3.upload_file(
                    str(manifest_file),
                    cfg.bucket,
                    manifest_key,
                    ExtraArgs={'ContentType': 'application/json'}
                )
                print("SUCCESS: Manifest uploaded.")
            except Exception as e:
                print(f"[ERROR] Manifest upload failed: {e}")
                sys.exit(1)
        else:
            print(f"\n[DRY RUN] Would upload to: {target_key}")
            print(f"          Local file available at: {output_file} (until script exits)")

if __name__ == "__main__":
    main()
