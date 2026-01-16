#!/usr/bin/env python3
"""
Tier 2 Weekly Parquet Build

Derives Tier 2 weekly dataset from already-uploaded Tier 3 daily parquets in R2.
Tier 2 = Tier 3 minus: futures_raw, spot_prices, flags, diag

Weekly cadence:
- Cron runs Monday 00:05 UTC
- Builds previous 7 full UTC days (Tue-Mon inclusive if run on Tuesday)
- end_day = yesterday UTC, start_day = end_day - 6 days

Usage:
    # Dry-run for last 7 days (no upload)
    python3 scripts/build_tier2_weekly.py --dry-run

    # Build specific week ending on a date
    python3 scripts/build_tier2_weekly.py --end-day 2026-01-15 --upload

    # Force overwrite existing R2 objects
    python3 scripts/build_tier2_weekly.py --end-day 2026-01-15 --upload --force

Output:
    Local:  output/tier2_weekly/YYYY-MM-DD/dataset_entries_7d.parquet
            output/tier2_weekly/YYYY-MM-DD/manifest.json
    R2:     tier2/weekly/YYYY-MM-DD/dataset_entries_7d.parquet
            tier2/weekly/YYYY-MM-DD/manifest.json
"""

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple

# Add scripts directory to path for local imports
sys.path.insert(0, str(Path(__file__).parent))

from r2_config import get_r2_config, R2Config

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:
    print("[ERROR] pyarrow is required. Install with: pip install pyarrow", file=sys.stderr)
    sys.exit(1)

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    print("[ERROR] boto3 is required. Install with: pip install boto3", file=sys.stderr)
    sys.exit(1)


# ==============================================================================
# Configuration
# ==============================================================================

# Default output directory
DEFAULT_OUTPUT_DIR = Path("./output/tier2_weekly")

# Parquet compression
PARQUET_COMPRESSION = "zstd"

# Minimum days required to build a Tier 2 weekly export
# Set to 5 to allow 2 missing days in a 7-day window
MIN_DAYS_DEFAULT = 5

# Tier 2 column policy
# Columns to EXCLUDE from Tier 2 (present in Tier 3)
TIER2_EXCLUDED_COLUMNS = [
    "futures_raw",   # Entire futures block (preserve Tier 3 value)
    "spot_prices",   # Spot price time-series arrays
    "flags",         # Boolean flags block (preserve Tier 3 value)
    "diag",          # Diagnostics block (preserve Tier 3 value)
    # twitter_sentiment_windows contains dynamic-key structs (tag_counts, mention_counts,
    # url_domain_counts, cashtag_counts) where keys are actual hashtags/handles/domains.
    # These differ between days causing schema mismatch during concatenation.
    # twitter_sentiment_meta preserves the essential metadata.
    "twitter_sentiment_windows",
]

# Columns that MUST be present in Tier 2 output
TIER2_REQUIRED_COLUMNS = [
    "symbol",
    "snapshot_ts",
    "meta",
    "spot_raw",
    "derived",
    "scores",
    "twitter_sentiment_meta",
]

# R2 path patterns
TIER3_DAILY_PREFIX = "tier3/daily"
TIER2_WEEKLY_PREFIX = "tier2/weekly"


# ==============================================================================
# S3/R2 Client
# ==============================================================================

def get_s3_client(config: R2Config):
    """Create boto3 S3 client configured for R2."""
    return boto3.client(
        "s3",
        endpoint_url=config.endpoint,
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
    )


# ==============================================================================
# Date Range Calculation
# ==============================================================================

def calculate_week_range(end_day: str, days: int = 7) -> Tuple[str, str, List[str]]:
    """
    Calculate the date range for a weekly build.
    
    Args:
        end_day: End date in YYYY-MM-DD format
        days: Number of days to include (default 7)
    
    Returns:
        Tuple of (start_day, end_day, list of all days)
    """
    end_date = datetime.strptime(end_day, "%Y-%m-%d").date()
    start_date = end_date - timedelta(days=days - 1)
    
    all_days = []
    current = start_date
    while current <= end_date:
        all_days.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    
    return start_date.strftime("%Y-%m-%d"), end_day, all_days


# ==============================================================================
# R2 Input Verification
# ==============================================================================

def verify_tier3_inputs_exist(
    s3_client,
    bucket: str,
    days: List[str]
) -> Tuple[List[str], List[str], List[str]]:
    """
    Verify which Tier 3 daily parquets and manifests exist in R2.
    
    Returns:
        Tuple of (present_days, missing_days, found_parquet_keys)
    """
    present_days = []
    missing_days = []
    found_keys = []
    
    for day in days:
        parquet_key = f"{TIER3_DAILY_PREFIX}/{day}/data.parquet"
        manifest_key = f"{TIER3_DAILY_PREFIX}/{day}/manifest.json"
        
        try:
            # Both parquet and manifest must exist
            s3_client.head_object(Bucket=bucket, Key=parquet_key)
            s3_client.head_object(Bucket=bucket, Key=manifest_key)
            present_days.append(day)
            found_keys.append(parquet_key)
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                missing_days.append(day)
            else:
                raise
    
    return present_days, missing_days, found_keys


def fetch_tier3_coverage(
    s3_client,
    bucket: str,
    day: str
) -> dict:
    """
    Fetch Tier 3 manifest and extract coverage metadata.
    
    Returns:
        Dict with coverage fields from Tier 3 manifest.
    """
    manifest_key = f"{TIER3_DAILY_PREFIX}/{day}/manifest.json"
    
    try:
        response = s3_client.get_object(Bucket=bucket, Key=manifest_key)
        manifest = json.loads(response["Body"].read())
        
        return {
            "hours_found": manifest.get("hours_found", 24),
            "hours_expected": manifest.get("hours_expected", 24),
            "is_partial": manifest.get("is_partial", False),
            "missing_hours": manifest.get("missing_hours", []),
            "rows_by_hour": manifest.get("rows_by_hour"),
            "row_count": manifest.get("row_count", 0),
        }
    except Exception as e:
        # If we can't read manifest, assume full coverage
        return {
            "hours_found": 24,
            "hours_expected": 24,
            "is_partial": False,
            "missing_hours": [],
            "rows_by_hour": None,
            "row_count": 0,
        }


# ==============================================================================
# Column Projection
# ==============================================================================

def get_tier2_columns(schema: pa.Schema) -> List[str]:
    """
    Get list of columns to include in Tier 2 output.
    
    Args:
        schema: PyArrow schema from Tier 3 parquet
    
    Returns:
        List of column names to include
    """
    all_columns = [field.name for field in schema]
    tier2_columns = [col for col in all_columns if col not in TIER2_EXCLUDED_COLUMNS]
    return tier2_columns


def verify_tier2_output(table: pa.Table) -> Tuple[bool, List[str]]:
    """
    Verify Tier 2 output has correct columns.
    
    Returns:
        Tuple of (is_valid, list of issues)
    """
    issues = []
    column_names = [field.name for field in table.schema]
    
    # Check excluded columns are NOT present
    for col in TIER2_EXCLUDED_COLUMNS:
        if col in column_names:
            issues.append(f"Excluded column '{col}' found in output")
    
    # Check required columns ARE present
    for col in TIER2_REQUIRED_COLUMNS:
        if col not in column_names:
            issues.append(f"Required column '{col}' missing from output")
    
    return len(issues) == 0, issues


# ==============================================================================
# Parquet Processing
# ==============================================================================

def download_and_project_parquet(
    s3_client,
    bucket: str,
    key: str,
    columns: Optional[List[str]] = None
) -> pa.Table:
    """
    Download a parquet from R2 and optionally project columns.
    
    Uses a temp file to avoid loading entire file into memory twice.
    """
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=True) as tmp:
        s3_client.download_file(bucket, key, tmp.name)
        
        if columns:
            table = pq.read_table(tmp.name, columns=columns)
        else:
            table = pq.read_table(tmp.name)
        
        return table


def build_tier2_from_tier3(
    s3_client,
    bucket: str,
    input_keys: List[str],
    output_path: Path
) -> Tuple[pa.Table, int]:
    """
    Build Tier 2 parquet from multiple Tier 3 daily parquets.
    
    Processes day-by-day to manage memory.
    
    Returns:
        Tuple of (combined table, total rows)
    """
    tables = []
    tier2_columns = None
    
    for i, key in enumerate(input_keys):
        day = key.split("/")[2]  # tier3/daily/YYYY-MM-DD/data.parquet
        print(f"  [{i+1}/{len(input_keys)}] Processing {day}...")
        
        # First file: determine columns to include
        if tier2_columns is None:
            # Read schema only first
            with tempfile.NamedTemporaryFile(suffix=".parquet", delete=True) as tmp:
                s3_client.download_file(bucket, key, tmp.name)
                schema = pq.read_schema(tmp.name)
                tier2_columns = get_tier2_columns(schema)
                table = pq.read_table(tmp.name, columns=tier2_columns)
        else:
            table = download_and_project_parquet(s3_client, bucket, key, tier2_columns)
        
        tables.append(table)
        print(f"      {table.num_rows} rows")
    
    # Concatenate all tables
    print("  Concatenating tables...")
    combined = pa.concat_tables(tables)
    
    # Free intermediate tables
    del tables
    
    return combined, combined.num_rows


# ==============================================================================
# Output Writing
# ==============================================================================

def compute_sha256(filepath: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def create_manifest(
    end_day: str,
    start_day: str,
    days_expected: List[str],
    days_present: List[str],
    days_missing: List[str],
    per_day_coverage: dict,
    min_days_threshold: int,
    source_inputs: List[str],
    row_count: int,
    parquet_path: Path,
    tier2_columns: List[str]
) -> dict:
    """Create manifest for Tier 2 weekly output with source_coverage."""
    parquet_sha256 = compute_sha256(parquet_path)
    parquet_size = parquet_path.stat().st_size
    
    # Calculate coverage stats
    partial_days_count = sum(1 for d in days_present if per_day_coverage.get(d, {}).get("is_partial", False))
    
    # Build coverage note
    coverage_parts = []
    coverage_parts.append(f"This weekly export is derived from {len(days_present)}/7 daily partitions.")
    if partial_days_count > 0:
        coverage_parts.append(f"{partial_days_count} of the included days are partial.")
    if days_missing:
        coverage_parts.append(f"Missing days: {', '.join(days_missing)}.")
    if partial_days_count > 0 or days_missing:
        coverage_parts.append("See per_day for coverage details.")
    coverage_note = " ".join(coverage_parts)
    
    return {
        "schema_version": "v7",
        "tier": "tier2",
        "window": {
            "start_day": start_day,
            "end_day": end_day,
            "days_expected": days_expected,
            "days_included": days_present,
        },
        "build_ts_utc": datetime.now(timezone.utc).isoformat(),
        "source_inputs": source_inputs,
        "row_count": row_count,
        "source_coverage": {
            "days_expected": days_expected,
            "days_present": days_present,
            "days_missing": days_missing,
            "per_day": per_day_coverage,
            "present_days_count": len(days_present),
            "missing_days_count": len(days_missing),
            "partial_days_count": partial_days_count,
            "min_days_threshold_used": min_days_threshold,
            "coverage_note": coverage_note,
        },
        "column_policy": {
            "included_top_level_columns": tier2_columns,
            "excluded_top_level_columns": TIER2_EXCLUDED_COLUMNS,
            "explicit_exclusions": [
                "futures_raw",
                "spot_prices", 
                "flags",
                "diag",
            ],
        },
        "parquet_sha256": parquet_sha256,
        "parquet_size_bytes": parquet_size,
    }


def write_outputs(
    table: pa.Table,
    manifest: dict,
    output_dir: Path
) -> Tuple[Path, Path]:
    """Write parquet and manifest to local output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    parquet_path = output_dir / "dataset_entries_7d.parquet"
    manifest_path = output_dir / "manifest.json"
    
    # Write parquet with zstd compression
    pq.write_table(
        table,
        parquet_path,
        compression=PARQUET_COMPRESSION,
    )
    
    # Write manifest
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    
    return parquet_path, manifest_path


# ==============================================================================
# R2 Upload
# ==============================================================================

def upload_to_r2(
    s3_client,
    bucket: str,
    local_path: Path,
    r2_key: str,
    force: bool = False
) -> bool:
    """
    Upload a file to R2.
    
    Returns:
        True if uploaded, False if skipped (already exists and not force)
    """
    # Check if exists
    if not force:
        try:
            s3_client.head_object(Bucket=bucket, Key=r2_key)
            return False  # Already exists
        except ClientError as e:
            if e.response["Error"]["Code"] != "404":
                raise
    
    # Upload
    s3_client.upload_file(str(local_path), bucket, r2_key)
    return True


# ==============================================================================
# Main Build Logic
# ==============================================================================

def build_tier2_weekly(
    end_day: str,
    days: int = 7,
    min_days: int = MIN_DAYS_DEFAULT,
    output_dir: Optional[Path] = None,
    dry_run: bool = False,
    upload: bool = False,
    force: bool = False
) -> bool:
    """
    Main entry point for Tier 2 weekly build.
    
    Args:
        end_day: End date for the week (YYYY-MM-DD)
        days: Number of days in the window (default 7)
        min_days: Minimum Tier 3 days required to proceed (default 5)
        output_dir: Local output directory
        dry_run: If True, skip R2 upload
        upload: If True, upload to R2
        force: If True, overwrite existing R2 objects
    
    Returns:
        True if successful, False otherwise
    """
    print()
    print("=" * 60)
    print(f"TIER 2 WEEKLY BUILD: ending {end_day}")
    print("=" * 60)
    
    # Calculate date range
    start_day, end_day, all_days = calculate_week_range(end_day, days)
    print(f"\n[WINDOW] {start_day} to {end_day} ({len(all_days)} days)")
    print(f"[THRESHOLD] Minimum {min_days}/{len(all_days)} days required")
    
    # Set output directory
    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR / end_day
    
    # Get R2 config and client
    print("\n[STEP 1] Connecting to R2...")
    config = get_r2_config()
    s3_client = get_s3_client(config)
    print(f"[OK] Connected to bucket: {config.bucket}")
    
    # Verify Tier 3 inputs and get coverage
    print("\n[STEP 2] Checking Tier 3 inputs...")
    present_days, missing_days, found_keys = verify_tier3_inputs_exist(
        s3_client, config.bucket, all_days
    )
    
    print(f"    Present: {len(present_days)}/{len(all_days)} days")
    if present_days:
        print(f"    Days present: {present_days}")
    if missing_days:
        print(f"    Days missing: {missing_days}")
    
    # Check threshold
    if len(present_days) < min_days:
        print(f"\n[ERROR] Insufficient Tier 3 inputs: {len(present_days)}/{min_days} required")
        print(f"    Missing days: {missing_days}")
        print(f"[HINT] Use --min-days to lower the threshold (current: {min_days})")
        return False
    
    # Fetch coverage metadata for each present day
    print("\n[STEP 3] Fetching Tier 3 coverage metadata...")
    per_day_coverage = {}
    partial_count = 0
    for day in present_days:
        coverage = fetch_tier3_coverage(s3_client, config.bucket, day)
        per_day_coverage[day] = coverage
        if coverage.get("is_partial"):
            partial_count += 1
            print(f"    {day}: {coverage['hours_found']}/24 hours (PARTIAL)")
        else:
            print(f"    {day}: {coverage['hours_found']}/24 hours")
    
    if partial_count > 0:
        print(f"[INFO] {partial_count} partial day(s) included")
    if missing_days:
        print(f"[INFO] Proceeding with {len(present_days)}/{len(all_days)} days (>= {min_days} threshold)")
    else:
        print(f"[OK] All {len(present_days)} Tier 3 inputs found")
    
    # Build Tier 2 from Tier 3
    print("\n[STEP 4] Building Tier 2 parquet...")
    combined_table, row_count = build_tier2_from_tier3(
        s3_client, config.bucket, found_keys, output_dir
    )
    
    # Verify output columns
    print("\n[STEP 5] Verifying output columns...")
    is_valid, issues = verify_tier2_output(combined_table)
    print("\n[STEP 5] Verifying output columns...")
    is_valid, issues = verify_tier2_output(combined_table)
    if not is_valid:
        print("[ERROR] Output verification failed:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    print("[OK] Output columns verified")
    
    # Get tier2 columns for manifest
    tier2_columns = [field.name for field in combined_table.schema]
    
    # Write local outputs (always, even for dry-run)
    print("\n[STEP 6] Writing local outputs...")
    parquet_path, manifest_path = write_outputs(
        combined_table,
        {},  # Placeholder, will compute after write
        output_dir
    )
    
    # Now create actual manifest with hash and coverage
    manifest = create_manifest(
        end_day=end_day,
        start_day=start_day,
        days_expected=all_days,
        days_present=present_days,
        days_missing=missing_days,
        per_day_coverage=per_day_coverage,
        min_days_threshold=min_days,
        source_inputs=found_keys,
        row_count=row_count,
        parquet_path=parquet_path,
        tier2_columns=tier2_columns,
    )
    
    # Rewrite manifest with correct data
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    
    parquet_size_mb = parquet_path.stat().st_size / (1024 * 1024)
    print(f"[OK] Wrote {parquet_path} ({parquet_size_mb:.2f} MB)")
    print(f"[OK] Wrote {manifest_path}")
    
    # Upload to R2
    if upload and not dry_run:
        print("\n[STEP 7] Uploading to R2...")
        r2_prefix = f"{TIER2_WEEKLY_PREFIX}/{end_day}"
        
        parquet_key = f"{r2_prefix}/dataset_entries_7d.parquet"
        manifest_key = f"{r2_prefix}/manifest.json"
        
        print(f"  Uploading {parquet_key}...")
        uploaded_parquet = upload_to_r2(s3_client, config.bucket, parquet_path, parquet_key, force)
        if not uploaded_parquet and not force:
            print(f"  [SKIP] Already exists (use --force to overwrite)")
        
        print(f"  Uploading {manifest_key}...")
        uploaded_manifest = upload_to_r2(s3_client, config.bucket, manifest_path, manifest_key, force)
        
        print(f"[OK] Upload complete to {config.bucket}")
    elif dry_run:
        print("\n[INFO] Dry run - skipping R2 upload")
    else:
        print("\n[INFO] No --upload flag - skipping R2 upload")
    
    # Summary
    print()
    print("=" * 60)
    print("BUILD SUMMARY")
    print("=" * 60)
    print(f"Window:         {start_day} to {end_day}")
    print(f"Days present:   {len(present_days)}/{len(all_days)}")
    if missing_days:
        print(f"Days missing:   {missing_days}")
    if partial_count > 0:
        print(f"Partial days:   {partial_count}")
    print(f"Rows:           {row_count:,}")
    print(f"Parquet size:   {parquet_size_mb:.2f} MB")
    print(f"Local path:     {output_dir}/")
    if upload and not dry_run:
        print(f"R2 prefix:      {TIER2_WEEKLY_PREFIX}/{end_day}/")
    print("=" * 60)
    
    return True


# ==============================================================================
# CLI
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Build Tier 2 weekly parquet from Tier 3 daily inputs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--end-day",
        type=str,
        default=None,
        help="End date for the week (YYYY-MM-DD). Default: yesterday UTC"
    )
    
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to include (default: 7)"
    )
    
    parser.add_argument(
        "--min-days",
        type=int,
        default=MIN_DAYS_DEFAULT,
        help=f"Minimum Tier 3 days required to build (default: {MIN_DAYS_DEFAULT})"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write local files only, skip R2 upload"
    )
    
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Upload to R2 after local build"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing R2 objects"
    )
    
    parser.add_argument(
        "--local-out",
        type=str,
        default=None,
        help="Local output directory (default: output/tier2_weekly/YYYY-MM-DD/)"
    )
    
    args = parser.parse_args()
    
    # Default end-day to yesterday UTC
    if args.end_day is None:
        yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
        args.end_day = yesterday.strftime("%Y-%m-%d")
        print(f"[INFO] No --end-day specified, defaulting to yesterday UTC: {args.end_day}")
    
    # Parse local output directory
    output_dir = Path(args.local_out) if args.local_out else None
    
    # Run build
    success = build_tier2_weekly(
        end_day=args.end_day,
        days=args.days,
        min_days=args.min_days,
        output_dir=output_dir,
        dry_run=args.dry_run,
        upload=args.upload,
        force=args.force,
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
