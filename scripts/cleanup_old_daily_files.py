#!/usr/bin/env python3
"""
Daily Retention Management

Removes daily parquet files older than 7 days from R2 to manage storage costs.
Run after successful daily builds to maintain the rolling 7-day window.

Retention Policy:
- Daily files: Keep last 7 days, delete older
- MTD files: Overwrite at same key (no cleanup needed)
- Monthly files: Never delete (permanent archives)

Usage:
    # Clean all tiers
    python3 scripts/cleanup_old_daily_files.py --all
    
    # Clean specific tier
    python3 scripts/cleanup_old_daily_files.py --tier tier1
    
    # Dry run (show what would be deleted)
    python3 scripts/cleanup_old_daily_files.py --all --dry-run
"""

import argparse
import boto3
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Add scripts directory to path for local imports
sys.path.insert(0, str(Path(__file__).parent))

from r2_config import get_r2_config


def get_cutoff_date(retention_days=7):
    """
    Calculate the cutoff date for retention.
    Files older than this should be deleted.
    
    Args:
        retention_days: Number of days to retain (default 7)
    
    Returns:
        date object representing cutoff
    """
    return (datetime.now(timezone.utc) - timedelta(days=retention_days)).date()


def list_daily_files(s3, bucket, tier):
    """
    List all daily parquet files for a tier.
    
    Args:
        s3: boto3 S3 client
        bucket: R2 bucket name
        tier: Tier name (tier1, tier2, tier3)
    
    Returns:
        List of (key, date) tuples
    """
    prefix = f"{tier}/daily/"
    files = []
    
    print(f"[{tier.upper()}] Scanning daily files with prefix: {prefix}")
    
    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
    
    for page in pages:
        if 'Contents' not in page:
            continue
            
        for obj in page['Contents']:
            key = obj['Key']
            
            # Only process .parquet files (not manifest.json)
            if not key.endswith('.parquet'):
                continue
            
            # Extract date from key structure: tierX/daily/YYYY-MM/YYYY-MM-DD/file.parquet
            parts = key.split('/')
            if len(parts) >= 4:
                try:
                    date_str = parts[3]  # YYYY-MM-DD
                    file_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    files.append((key, file_date))
                except (ValueError, IndexError):
                    print(f"[WARN] Could not parse date from key: {key}")
                    continue
    
    return files


def delete_old_files(s3, bucket, tier, cutoff_date, dry_run=False):
    """
    Delete daily files older than cutoff date.
    
    Args:
        s3: boto3 S3 client
        bucket: R2 bucket name
        tier: Tier name
        cutoff_date: Files older than this will be deleted
        dry_run: If True, only show what would be deleted
    
    Returns:
        Count of files deleted (or would be deleted)
    """
    files = list_daily_files(s3, bucket, tier)
    
    if not files:
        print(f"[{tier.upper()}] No daily files found")
        return 0
    
    # Filter files older than cutoff
    old_files = [(key, date) for key, date in files if date < cutoff_date]
    
    if not old_files:
        print(f"[{tier.upper()}] No files older than {cutoff_date} (all files within retention window)")
        return 0
    
    print(f"[{tier.upper()}] Found {len(old_files)} files older than {cutoff_date}:")
    
    deleted_count = 0
    for key, file_date in sorted(old_files, key=lambda x: x[1]):
        age_days = (datetime.now(timezone.utc).date() - file_date).days
        
        if dry_run:
            print(f"  [DRY-RUN] Would delete: {key} (age: {age_days} days)")
        else:
            try:
                # Delete both parquet and manifest
                s3.delete_object(Bucket=bucket, Key=key)
                print(f"  ✓ Deleted: {key} (age: {age_days} days)")
                
                # Also delete corresponding manifest.json
                manifest_key = key.replace('.parquet', '_manifest.json')
                if manifest_key != key:  # Sanity check
                    try:
                        s3.delete_object(Bucket=bucket, Key=manifest_key)
                        print(f"  ✓ Deleted: {manifest_key}")
                    except Exception as e:
                        # Manifest might not exist, that's okay
                        pass
                
                deleted_count += 1
            except Exception as e:
                print(f"  ✗ Failed to delete {key}: {e}")
    
    return deleted_count


def main():
    parser = argparse.ArgumentParser(description="Clean up old daily parquet files from R2")
    parser.add_argument("--tier", choices=["tier1", "tier2", "tier3"], help="Specific tier to clean")
    parser.add_argument("--all", action="store_true", help="Clean all tiers")
    parser.add_argument("--retention-days", type=int, default=7, help="Number of days to retain (default: 7)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without actually deleting")
    args = parser.parse_args()
    
    if not args.tier and not args.all:
        print("[ERROR] Must specify --tier or --all", file=sys.stderr)
        sys.exit(1)
    
    # Determine tiers to process
    if args.all:
        tiers = ["tier1", "tier2", "tier3"]
    else:
        tiers = [args.tier]
    
    # Get R2 config
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
    
    cutoff_date = get_cutoff_date(args.retention_days)
    
    mode = "[DRY-RUN] " if args.dry_run else ""
    print(f"{mode}Starting retention cleanup")
    print(f"Cutoff date: {cutoff_date} (keeping files from {cutoff_date} onwards)")
    print(f"Retention: {args.retention_days} days")
    print(f"Tiers: {', '.join(tiers)}")
    print()
    
    total_deleted = 0
    for tier in tiers:
        deleted = delete_old_files(s3, cfg.bucket, tier, cutoff_date, dry_run=args.dry_run)
        total_deleted += deleted
    
    print()
    if args.dry_run:
        print(f"[DRY-RUN] Would delete {total_deleted} files total")
    else:
        print(f"✓ Cleanup complete: {total_deleted} files deleted")


if __name__ == "__main__":
    main()
