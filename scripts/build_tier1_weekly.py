#!/usr/bin/env python3
"""
Tier 1 Weekly Parquet Build

Derives Tier 1 weekly dataset from already-uploaded Tier 3 daily parquets in R2.
Tier 1 is the "Starter — light entry table" with:
  - Identity/timing fields (flattened from meta)
  - Core spot snapshot (flattened from spot_raw)
  - Minimal derived (flattened from derived)
  - Minimal scoring (flattened from scores)
  - Aggregated sentiment (extracted from twitter_sentiment_windows.last_cycle)

NO: futures data, sentiment internals, time-series arrays, full nested structs.

Weekly cadence:
- Cron runs Monday 00:05 UTC with --previous-week
- Builds the most recent complete Mon-Sun week (end_day = previous Sunday UTC)
- Window: end_day - 6 days to end_day (7 days)

Usage:
    # Cron mode: build previous Mon-Sun week (for Monday 00:05 UTC cron)
    python3 scripts/build_tier1_weekly.py --previous-week --upload

    # Dry-run to see computed window
    python3 scripts/build_tier1_weekly.py --previous-week --dry-run

    # Manual/backfill: build specific week ending on a date
    python3 scripts/build_tier1_weekly.py --end-day 2026-01-04 --upload

    # Force overwrite existing R2 objects
    python3 scripts/build_tier1_weekly.py --end-day 2026-01-04 --upload --force

Output:
    Local:  output/tier1_weekly/YYYY-MM-DD/dataset_entries_7d.parquet
            output/tier1_weekly/YYYY-MM-DD/manifest.json
    R2:     tier1/weekly/YYYY-MM-DD/dataset_entries_7d.parquet
            tier1/weekly/YYYY-MM-DD/manifest.json
"""

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add scripts directory to path for local imports
sys.path.insert(0, str(Path(__file__).parent))

from r2_config import get_r2_config, R2Config

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    import pyarrow.compute as pc
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
DEFAULT_OUTPUT_DIR = Path("./output/tier1_weekly")

# Parquet compression
PARQUET_COMPRESSION = "zstd"

# Minimum days required to build a Tier 1 weekly export
# Set to 5 to allow 2 missing days in a 7-day window (same as Tier 2)
MIN_DAYS_DEFAULT = 5

# ==============================================================================
# Tier 1 Field Specification (SSOT)
# ==============================================================================
# Tier 1 is the "Starter — light entry table"
# Fields are FLATTENED, not carried as whole structs.
#
# INCLUDED fields (exact per plan):
#
# 1) Identity + timing:
#    - symbol (top-level)
#    - snapshot_ts (top-level)
#    - From meta: added_ts, expires_ts, duration_sec, archive_schema_version
#
# 2) Core spot snapshot (low surface area):
#    - From spot_raw: mid, spread_bps, range_pct_24h, ticker24_chg
#
# 3) Minimal derived (one-liners):
#    - From derived: liq_global_pct, spread_bps
#
# 4) Minimal scoring:
#    - From scores: final
#
# 5) Sentiment (aggregated only; no internals):
#    From twitter_sentiment_windows.last_cycle:
#    - posts_total, posts_pos, posts_neu, posts_neg
#    - hybrid_decision_stats.mean_score
#    From twitter_sentiment_windows.last_cycle.sentiment_activity:
#    - is_silent, recent_posts_count, has_recent_activity, hours_since_latest_tweet
#
# EXCLUDED:
# - Any futures data or futures_data_ok flag
# - All sentiment internals (decision_sources, conf_mean, top_terms, etc.)
# - spot_prices time-series arrays
# - All other columns not listed above

TIER1_FIELD_SPEC = {
    # Top-level identity fields
    "symbol": {"source": "top_level", "required": True},
    "snapshot_ts": {"source": "top_level", "required": True},
    
    # From meta
    "meta_added_ts": {"source": "meta.added_ts", "required": True},
    "meta_expires_ts": {"source": "meta.expires_ts", "required": True},
    "meta_duration_sec": {"source": "meta.duration_sec", "required": True},
    "meta_archive_schema_version": {"source": "meta.archive_schema_version", "required": True},
    
    # From spot_raw
    "spot_mid": {"source": "spot_raw.mid", "required": True},
    "spot_spread_bps": {"source": "spot_raw.spread_bps", "required": True},
    "spot_range_pct_24h": {"source": "spot_raw.range_pct_24h", "required": False},  # May be null
    "spot_ticker24_chg": {"source": "spot_raw.ticker24_chg", "required": False},  # May be null
    
    # From derived
    "derived_liq_global_pct": {"source": "derived.liq_global_pct", "required": False},
    "derived_spread_bps": {"source": "derived.spread_bps", "required": False},
    
    # From scores
    "score_final": {"source": "scores.final", "required": True},
    
    # From twitter_sentiment_windows.last_cycle (aggregated sentiment)
    "sentiment_posts_total": {"source": "twitter_sentiment_windows.last_cycle.posts_total", "required": False},
    "sentiment_posts_pos": {"source": "twitter_sentiment_windows.last_cycle.posts_pos", "required": False},
    "sentiment_posts_neu": {"source": "twitter_sentiment_windows.last_cycle.posts_neu", "required": False},
    "sentiment_posts_neg": {"source": "twitter_sentiment_windows.last_cycle.posts_neg", "required": False},
    "sentiment_mean_score": {"source": "twitter_sentiment_windows.last_cycle.hybrid_decision_stats.mean_score", "required": False},
    
    # From twitter_sentiment_windows.last_cycle.sentiment_activity
    "sentiment_is_silent": {"source": "twitter_sentiment_windows.last_cycle.sentiment_activity.is_silent", "required": False},
    "sentiment_recent_posts_count": {"source": "twitter_sentiment_windows.last_cycle.sentiment_activity.recent_posts_count", "required": False},
    "sentiment_has_recent_activity": {"source": "twitter_sentiment_windows.last_cycle.sentiment_activity.has_recent_activity", "required": False},
    "sentiment_hours_since_latest_tweet": {"source": "twitter_sentiment_windows.last_cycle.sentiment_activity.hours_since_latest_tweet", "required": False},
}

# Required source columns in Tier 3 parquet
REQUIRED_SOURCE_COLUMNS = [
    "symbol",
    "snapshot_ts",
    "meta",
    "spot_raw",
    "derived",
    "scores",
    "twitter_sentiment_windows",  # For sentiment extraction
]

# R2 path patterns
TIER3_DAILY_PREFIX = "tier3/daily"
TIER1_WEEKLY_PREFIX = "tier1/weekly"


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

def compute_previous_sunday() -> str:
    """
    Compute the most recent Sunday (UTC) strictly before today.
    
    For cron running Monday 00:05 UTC, this returns yesterday (Sunday).
    For any other day, it returns the most recent completed Sunday.
    
    Returns:
        Sunday date in YYYY-MM-DD format
    """
    today = datetime.now(timezone.utc).date()
    # weekday(): Monday=0, Sunday=6
    days_since_sunday = (today.weekday() + 1) % 7
    if days_since_sunday == 0:
        # Today is Sunday, so "previous Sunday" is 7 days ago
        days_since_sunday = 7
    previous_sunday = today - timedelta(days=days_since_sunday)
    return previous_sunday.strftime("%Y-%m-%d")


def validate_end_day_is_sunday(end_day: str) -> Tuple[bool, str]:
    """
    Validate that end_day is a Sunday.
    
    Returns:
        Tuple of (is_sunday, warning_message)
    """
    end_date = datetime.strptime(end_day, "%Y-%m-%d").date()
    if end_date.weekday() != 6:  # Sunday = 6
        day_name = end_date.strftime("%A")
        return False, f"WARNING: end_day {end_day} is a {day_name}, not a Sunday. Weekly windows should end on Sunday."
    return True, ""


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
# Field Extraction Functions
# ==============================================================================

def safe_get_nested_column(table: pa.Table, path: str) -> Optional[pa.Array]:
    """
    Safely extract a nested field from a PyArrow table.
    
    Args:
        table: PyArrow table
        path: Dot-separated path like "meta.added_ts" or 
              "twitter_sentiment_windows.last_cycle.posts_total"
    
    Returns:
        PyArrow array or None if path doesn't exist
    """
    parts = path.split(".")
    
    # Get top-level column
    if parts[0] not in table.schema.names:
        return None
    
    current = table.column(parts[0])
    
    # Navigate nested struct fields
    for i, part in enumerate(parts[1:], 1):
        if not pa.types.is_struct(current.type):
            return None
        
        # Find field in struct
        struct_type = current.type
        field_idx = None
        for j in range(struct_type.num_fields):
            if struct_type.field(j).name == part:
                field_idx = j
                break
        
        if field_idx is None:
            return None
        
        # Extract nested field
        try:
            current = pc.struct_field(current, field_idx)
        except Exception:
            return None
    
    return current


def extract_tier1_fields(table: pa.Table) -> Tuple[pa.Table, List[str], List[str]]:
    """
    Extract Tier 1 fields from a Tier 3 table, flattening nested fields.
    
    Returns:
        Tuple of (tier1_table, present_fields, missing_required_fields)
    """
    columns = {}
    present_fields = []
    missing_required = []
    
    for field_name, spec in TIER1_FIELD_SPEC.items():
        source_path = spec["source"]
        required = spec["required"]
        
        # Handle top-level fields
        if source_path == "top_level":
            if field_name in table.schema.names:
                columns[field_name] = table.column(field_name)
                present_fields.append(field_name)
            elif required:
                missing_required.append(field_name)
            continue
        
        # Handle nested fields
        array = safe_get_nested_column(table, source_path)
        
        if array is not None:
            columns[field_name] = array
            present_fields.append(field_name)
        elif required:
            missing_required.append(f"{field_name} (from {source_path})")
    
    # Create tier1 table from extracted columns
    if missing_required:
        return None, present_fields, missing_required
    
    # Build table maintaining field order from spec
    ordered_columns = []
    ordered_names = []
    for field_name in TIER1_FIELD_SPEC.keys():
        if field_name in columns:
            ordered_names.append(field_name)
            ordered_columns.append(columns[field_name])
    
    tier1_table = pa.table(dict(zip(ordered_names, ordered_columns)))
    return tier1_table, present_fields, missing_required


def verify_tier1_output(table: pa.Table) -> Tuple[bool, List[str]]:
    """
    Verify Tier 1 output has the expected fields.
    
    Returns:
        Tuple of (is_valid, list of issues)
    """
    issues = []
    column_names = set(table.schema.names)
    
    # Check all spec fields are either present or optional-and-missing
    for field_name, spec in TIER1_FIELD_SPEC.items():
        if field_name not in column_names and spec["required"]:
            issues.append(f"Required field '{field_name}' missing from output")
    
    # Check no unexpected columns
    expected = set(TIER1_FIELD_SPEC.keys())
    unexpected = column_names - expected
    if unexpected:
        issues.append(f"Unexpected columns in output: {sorted(unexpected)}")
    
    return len(issues) == 0, issues


# ==============================================================================
# Parquet Processing
# ==============================================================================

def download_parquet_to_table(
    s3_client,
    bucket: str,
    key: str,
) -> pa.Table:
    """
    Download a parquet from R2 to a PyArrow table.
    
    Uses a temp file to avoid loading entire file into memory twice.
    """
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=True) as tmp:
        s3_client.download_file(bucket, key, tmp.name)
        table = pq.read_table(tmp.name)
        return table


def build_tier1_from_tier3(
    s3_client,
    bucket: str,
    input_keys: List[str],
) -> Tuple[pa.Table, int, List[str]]:
    """
    Build Tier 1 parquet from multiple Tier 3 daily parquets.
    
    Processes day-by-day to manage memory.
    Extracts and flattens fields per TIER1_FIELD_SPEC.
    
    Returns:
        Tuple of (combined table, total rows, list of present fields)
    """
    tables = []
    all_present_fields = None
    
    for i, key in enumerate(input_keys):
        day = key.split("/")[2]  # tier3/daily/YYYY-MM-DD/data.parquet
        print(f"  [{i+1}/{len(input_keys)}] Processing {day}...")
        
        # Download and read Tier 3 parquet
        tier3_table = download_parquet_to_table(s3_client, bucket, key)
        
        # Verify required source columns exist
        missing_source = set(REQUIRED_SOURCE_COLUMNS) - set(tier3_table.schema.names)
        if missing_source:
            raise ValueError(f"Tier 3 input {day} missing required columns: {missing_source}")
        
        # Extract Tier 1 fields
        tier1_table, present_fields, missing_required = extract_tier1_fields(tier3_table)
        
        if missing_required:
            raise ValueError(f"Tier 3 input {day} missing required Tier 1 fields: {missing_required}")
        
        # Track present fields (should be consistent across days)
        if all_present_fields is None:
            all_present_fields = set(present_fields)
        
        tables.append(tier1_table)
        print(f"      {tier1_table.num_rows} rows, {len(present_fields)} fields")
        
        # Free Tier 3 table memory
        del tier3_table
    
    # Concatenate all tables
    print("  Concatenating tables...")
    combined = pa.concat_tables(tables)
    
    # Free intermediate tables
    del tables
    
    return combined, combined.num_rows, sorted(all_present_fields) if all_present_fields else []


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
    present_fields: List[str],
    window_basis: str = "end_day"
) -> dict:
    """Create manifest for Tier 1 weekly output with source_coverage.
    
    Args:
        window_basis: "previous_week_utc" if built with --previous-week, else "end_day"
    """
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
    
    # Categorize fields by source
    identity_fields = [f for f in present_fields if f in ["symbol", "snapshot_ts"] or f.startswith("meta_")]
    spot_fields = [f for f in present_fields if f.startswith("spot_")]
    derived_fields = [f for f in present_fields if f.startswith("derived_")]
    score_fields = [f for f in present_fields if f.startswith("score_")]
    sentiment_fields = [f for f in present_fields if f.startswith("sentiment_")]
    
    return {
        "schema_version": "v7",
        "tier": "tier1",
        "tier_description": "Starter — light entry table with aggregated sentiment (no futures, no sentiment internals)",
        "window": {
            "window_basis": window_basis,
            "week_start_day": start_day,
            "week_end_day": end_day,
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
        "field_policy": {
            "approach": "explicit_allowlist_flattened",
            "total_fields": len(present_fields),
            "fields": present_fields,
            "field_categories": {
                "identity_timing": identity_fields,
                "spot_snapshot": spot_fields,
                "derived_metrics": derived_fields,
                "scores": score_fields,
                "sentiment_aggregated": sentiment_fields,
            },
            "sentiment_source": "twitter_sentiment_windows.last_cycle",
            "sentiment_note": "Sentiment fields are aggregated-only from last_cycle. No internals (decision_sources, conf_mean, top_terms, etc.) are included.",
            "exclusions": [
                "futures_raw (all futures data)",
                "flags.futures_data_ok (futures existence flag)",
                "spot_prices (time-series arrays)",
                "twitter_sentiment_windows (full struct)",
                "All sentiment internals: decision_sources, primary_conf_mean, referee_conf_mean, top_terms, category_counts, tag_counts, cashtag_counts, mention_counts, url_domain_counts, media_count, author_stats, content_stats, engagement stats",
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

def build_tier1_weekly(
    end_day: str,
    days: int = 7,
    min_days: int = MIN_DAYS_DEFAULT,
    output_dir: Optional[Path] = None,
    dry_run: bool = False,
    upload: bool = False,
    force: bool = False,
    window_basis: str = "end_day"
) -> bool:
    """
    Main entry point for Tier 1 weekly build.
    
    Args:
        end_day: End date for the week (YYYY-MM-DD)
        days: Number of days in the window (default 7)
        min_days: Minimum Tier 3 days required to proceed (default 5)
        output_dir: Local output directory
        dry_run: If True, skip R2 upload
        upload: If True, upload to R2
        force: If True, overwrite existing R2 objects
        window_basis: "previous_week_utc" if --previous-week, else "end_day"
    
    Returns:
        True if successful, False otherwise
    """
    print()
    print("=" * 60)
    print(f"TIER 1 WEEKLY BUILD: ending {end_day}")
    print("=" * 60)
    
    # Validate end_day is a Sunday (warn if not)
    is_sunday, warning = validate_end_day_is_sunday(end_day)
    if not is_sunday:
        print(f"\n[WARNING] {warning}")
    
    # Calculate date range
    start_day, end_day, all_days = calculate_week_range(end_day, days)
    print(f"\n[WINDOW] {start_day} to {end_day} ({len(all_days)} days)")
    print(f"[BASIS] {window_basis}")
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
    
    # Build Tier 1 from Tier 3
    print("\n[STEP 4] Building Tier 1 parquet (extracting flattened fields)...")
    print(f"    Extracting {len(TIER1_FIELD_SPEC)} fields per Tier 1 spec")
    combined_table, row_count, present_fields = build_tier1_from_tier3(
        s3_client, config.bucket, found_keys
    )
    
    # Verify output fields
    print("\n[STEP 5] Verifying output fields...")
    is_valid, issues = verify_tier1_output(combined_table)
    if not is_valid:
        print("[ERROR] Output verification failed:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    print("[OK] Output fields verified")
    print(f"    Fields ({len(present_fields)}): {present_fields}")
    
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
        present_fields=present_fields,
        window_basis=window_basis,
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
        r2_prefix = f"{TIER1_WEEKLY_PREFIX}/{end_day}"
        
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
    print(f"Fields:         {len(present_fields)}")
    print(f"  Identity:     {len([f for f in present_fields if f in ['symbol', 'snapshot_ts'] or f.startswith('meta_')])}")
    print(f"  Spot:         {len([f for f in present_fields if f.startswith('spot_')])}")
    print(f"  Derived:      {len([f for f in present_fields if f.startswith('derived_')])}")
    print(f"  Scores:       {len([f for f in present_fields if f.startswith('score_')])}")
    print(f"  Sentiment:    {len([f for f in present_fields if f.startswith('sentiment_')])}")
    print(f"Local path:     {output_dir}/")
    if upload and not dry_run:
        print(f"R2 prefix:      {TIER1_WEEKLY_PREFIX}/{end_day}/")
    print("=" * 60)
    
    return True


# ==============================================================================
# CLI
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Build Tier 1 weekly parquet from Tier 3 daily inputs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Date selection (mutually exclusive)
    date_group = parser.add_mutually_exclusive_group()
    
    date_group.add_argument(
        "--end-day",
        type=str,
        default=None,
        help="End date for the week (YYYY-MM-DD). Should be a Sunday. For manual/backfill runs."
    )
    
    date_group.add_argument(
        "--previous-week",
        action="store_true",
        help="Build the most recent complete Mon-Sun week (end_day = previous Sunday UTC). For cron."
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
        help="Local output directory (default: output/tier1_weekly/YYYY-MM-DD/)"
    )
    
    args = parser.parse_args()
    
    # Determine end_day and window_basis
    if args.previous_week:
        # Cron mode: compute most recent Sunday
        args.end_day = compute_previous_sunday()
        window_basis = "previous_week_utc"
        print(f"[INFO] --previous-week: computed end_day = {args.end_day} (most recent Sunday UTC)")
    elif args.end_day is not None:
        # Manual mode: use specified end_day
        window_basis = "end_day"
    else:
        # No args: default to yesterday UTC (legacy behavior)
        yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
        args.end_day = yesterday.strftime("%Y-%m-%d")
        window_basis = "end_day"
        print(f"[INFO] No --end-day or --previous-week specified, defaulting to yesterday UTC: {args.end_day}")
    
    # Parse local output directory
    output_dir = Path(args.local_out) if args.local_out else None
    
    # Run build
    success = build_tier1_weekly(
        end_day=args.end_day,
        days=args.days,
        min_days=args.min_days,
        output_dir=output_dir,
        dry_run=args.dry_run,
        upload=args.upload,
        force=args.force,
        window_basis=window_basis,
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
