#!/usr/bin/env python3
"""
Download Index Generator

Creates JSON index files listing available downloads for each tier.
These index files are consumed by the website to display available data.

Generates:
- tier1.json: List of tier1 daily files + MTD
- tier2.json: List of tier2 daily files + MTD
- tier3.json: List of tier3 daily files + MTD

Structure of each index:
{
  "tier": "tier1",
  "generated_at": "2026-01-28T12:34:56Z",
  "daily": [
    {
      "date": "2026-01-27",
      "r2_key": "tier1/daily/2026-01/2026-01-27/instrumetriq_tier1_daily_2026-01-27.parquet",
      "manifest_key": "tier1/daily/2026-01/2026-01-27/manifest.json",
      "size_bytes": 123456,
      "last_modified": "2026-01-27T02:35:12Z"
    },
    ...
  ],
  "mtd": {
    "month": "2026-01",
    "r2_key": "tier1/mtd/2026-01/instrumetriq_tier1_mtd_2026-01.parquet",
    "manifest_key": "tier1/mtd/2026-01/manifest.json",
    "size_bytes": 5790000,
    "last_modified": "2026-01-27T02:45:00Z",
    "days_included": 27
  }
}

Usage:
    # Generate all tier indexes
    python3 scripts/generate_download_index.py --all
    
    # Generate specific tier
    python3 scripts/generate_download_index.py --tier tier1
    
    # Specify custom output directory
    python3 scripts/generate_download_index.py --all --output-dir /var/www/instrumetriq/private/download_index/
"""

import argparse
import boto3
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add scripts directory to path for local imports
sys.path.insert(0, str(Path(__file__).parent))

from r2_config import get_r2_config


def list_daily_files(s3, bucket, tier):
    """
    List all daily parquet files for a tier with metadata.
    
    Returns:
        List of dicts with date, r2_key, manifest_key, size_bytes, last_modified
    """
    prefix = f"{tier}/daily/"
    files = []
    
    print(f"[{tier.upper()}] Scanning daily files...")
    
    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
    
    for page in pages:
        if 'Contents' not in page:
            continue
            
        for obj in page['Contents']:
            key = obj['Key']
            
            # Only process .parquet files
            if not key.endswith('.parquet'):
                continue
            
            # Extract date from key structure: tierX/daily/YYYY-MM/YYYY-MM-DD/file.parquet
            parts = key.split('/')
            if len(parts) >= 4:
                try:
                    date_str = parts[3]  # YYYY-MM-DD
                    
                    # Construct manifest key
                    manifest_key = '/'.join(parts[:-1]) + '/manifest.json'
                    
                    files.append({
                        "date": date_str,
                        "r2_key": key,
                        "manifest_key": manifest_key,
                        "size_bytes": obj['Size'],
                        "last_modified": obj['LastModified'].isoformat()
                    })
                except (ValueError, IndexError):
                    print(f"[WARN] Could not parse date from key: {key}")
                    continue
    
    # Sort by date descending (newest first)
    files.sort(key=lambda x: x['date'], reverse=True)
    
    return files


def get_mtd_info(s3, bucket, tier):
    """
    Get MTD bundle info if it exists.
    
    Returns:
        Dict with mtd info or None if not found
    """
    # Current month
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    
    mtd_key = f"{tier}/mtd/{current_month}/instrumetriq_{tier}_mtd_{current_month}.parquet"
    manifest_key = f"{tier}/mtd/{current_month}/manifest.json"
    
    try:
        obj = s3.head_object(Bucket=bucket, Key=mtd_key)
        
        # Try to read manifest to get days_included
        days_included = None
        try:
            manifest_obj = s3.get_object(Bucket=bucket, Key=manifest_key)
            manifest_data = json.loads(manifest_obj['Body'].read())
            days_included = manifest_data.get('days_included')
        except Exception:
            pass  # Manifest might not exist yet
        
        return {
            "month": current_month,
            "r2_key": mtd_key,
            "manifest_key": manifest_key,
            "size_bytes": obj['ContentLength'],
            "last_modified": obj['LastModified'].isoformat(),
            "days_included": days_included
        }
    except Exception:
        return None


def generate_tier_index(s3, bucket, tier):
    """
    Generate index for a single tier.
    
    Returns:
        Dict with tier index data
    """
    print(f"\n=== Generating index for {tier.upper()} ===")
    
    daily_files = list_daily_files(s3, bucket, tier)
    mtd_info = get_mtd_info(s3, bucket, tier)
    
    index = {
        "tier": tier,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "daily": daily_files,
        "mtd": mtd_info
    }
    
    print(f"[{tier.upper()}] Found {len(daily_files)} daily files")
    if mtd_info:
        print(f"[{tier.upper()}] Found MTD bundle: {mtd_info['month']}")
    else:
        print(f"[{tier.upper()}] No MTD bundle found")
    
    return index


def main():
    parser = argparse.ArgumentParser(description="Generate download index files for website")
    parser.add_argument("--tier", choices=["tier1", "tier2", "tier3"], help="Specific tier to index")
    parser.add_argument("--all", action="store_true", help="Index all tiers")
    parser.add_argument("--output-dir", type=Path, default=Path("/var/www/instrumetriq/private/download_index"),
                       help="Output directory for index files")
    args = parser.parse_args()
    
    if not args.tier and not args.all:
        print("[ERROR] Must specify --tier or --all", file=sys.stderr)
        sys.exit(1)
    
    # Determine tiers to process
    if args.all:
        tiers = ["tier1", "tier2", "tier3"]
    else:
        tiers = [args.tier]
    
    # Create output directory if it doesn't exist
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
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
    
    print(f"Output directory: {args.output_dir}")
    print(f"Tiers: {', '.join(tiers)}\n")
    
    for tier in tiers:
        index = generate_tier_index(s3, cfg.bucket, tier)
        
        # Write to file
        output_file = args.output_dir / f"{tier}.json"
        with open(output_file, 'w') as f:
            json.dump(index, f, indent=2)
        
        print(f"✓ Wrote {output_file}")
    
    print(f"\n✓ Index generation complete")


if __name__ == "__main__":
    main()
