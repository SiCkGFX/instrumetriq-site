#!/usr/bin/env python3
"""
Tier 3 Daily Parquet Export

Exports all archive entries for a given UTC day to a Parquet file and uploads
to Cloudflare R2. Tier 3 is the "maximal" export containing all stored fields.

Usage:
    # Dry run for yesterday (no upload)
    python3 scripts/export_tier3_daily.py --dry-run

    # Export specific date with upload
    python3 scripts/export_tier3_daily.py --date 2026-01-14 --upload

    # Export date range (inclusive)
    python3 scripts/export_tier3_daily.py --from-date 2025-12-14 --to-date 2026-01-17 --upload

    # Force overwrite existing R2 objects
    python3 scripts/export_tier3_daily.py --date 2026-01-14 --upload --force

    # Self-test mode (validates schema on sample)
    python3 scripts/export_tier3_daily.py --self-test

Output:
    Local:  {out-dir}/YYYY-MM-DD/data.parquet
            {out-dir}/YYYY-MM-DD/manifest.json
    R2:     tier3/daily/YYYY-MM-DD/data.parquet
            tier3/daily/YYYY-MM-DD/manifest.json
"""

import argparse
import gzip
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, Optional

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

# Default archive path on VPS
DEFAULT_ARCHIVE_PATH = Path("/srv/cryptobot/data/archive")

# Default output directory
DEFAULT_OUTPUT_DIR = Path("./output/tier3_daily")

# Parquet compression
PARQUET_COMPRESSION = "zstd"

# Expected hours for a complete day (00-23)
EXPECTED_HOURS = [f"{h:02d}" for h in range(24)]  # ["00", "01", ..., "23"]

# Minimum hours required for a valid export (allows partial days)
# Set to 1 to allow any day with at least 1 hour of data
MIN_HOURS_DEFAULT = 1

# Required top-level keys for schema validation
REQUIRED_TOP_LEVEL_KEYS = [
    "symbol",
    "snapshot_ts",
    "meta",
    "spot_raw",
    "derived",
    "scores",
    "flags",
]

# Optional top-level keys (may be null or missing)
OPTIONAL_TOP_LEVEL_KEYS = [
    "futures_raw",
    "norm",
    "diag",
    "labels",
    "twitter_sentiment_windows",
    "twitter_sentiment_meta",
    "spot_prices",
]


# ==============================================================================
# Archive Reading
# ==============================================================================

def get_date_folder(archive_path: Path, date_str: str) -> Optional[Path]:
    """
    Get the archive folder for a specific UTC date.
    
    Args:
        archive_path: Root archive directory
        date_str: Date in YYYY-MM-DD format
        
    Returns:
        Path to date folder, or None if not found
    """
    # Convert YYYY-MM-DD to YYYYMMDD folder format
    folder_name = date_str.replace("-", "")
    folder_path = archive_path / folder_name
    
    if folder_path.exists() and folder_path.is_dir():
        return folder_path
    return None


def get_hour_files(date_folder: Path) -> list[Path]:
    """
    Get all hour files for a date folder, sorted by hour.
    
    Args:
        date_folder: Path to YYYYMMDD folder
        
    Returns:
        List of .jsonl.gz file paths sorted by hour
    """
    files = list(date_folder.glob("*.jsonl.gz"))
    # Sort by filename (hour)
    files.sort(key=lambda p: p.stem)
    return files


def check_hour_completeness(date_folder: Path) -> tuple[list[str], list[str]]:
    """
    Check if a date folder has all 24 hour files.
    
    Args:
        date_folder: Path to YYYYMMDD folder
        
    Returns:
        Tuple of (found_hours, missing_hours)
    """
    hour_files = get_hour_files(date_folder)
    
    # Extract hour from filename (e.g., "05.jsonl.gz" -> "05")
    found_hours = []
    for f in hour_files:
        # Handle both "05.jsonl.gz" and "05.jsonl" naming
        stem = f.stem
        if stem.endswith(".jsonl"):
            stem = stem[:-6]  # Remove .jsonl suffix
        if len(stem) == 2 and stem.isdigit():
            found_hours.append(stem)
    
    missing_hours = [h for h in EXPECTED_HOURS if h not in found_hours]
    
    return sorted(found_hours), sorted(missing_hours)


def iter_entries_from_file(filepath: Path) -> Iterator[dict]:
    """
    Iterate over entries in a gzipped JSONL file.
    
    Args:
        filepath: Path to .jsonl.gz file
        
    Yields:
        Parsed JSON entry dicts
    """
    try:
        with gzip.open(filepath, "rt", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as e:
                    print(f"[WARN] JSON decode error in {filepath.name}:{line_num}: {e}", file=sys.stderr)
                    continue
    except Exception as e:
        print(f"[WARN] Error reading {filepath}: {e}", file=sys.stderr)


def load_day_entries(archive_path: Path, date_str: str) -> tuple[list[dict], dict]:
    """
    Load all entries for a specific UTC day.
    
    Args:
        archive_path: Root archive directory
        date_str: Date in YYYY-MM-DD format
        
    Returns:
        Tuple of (entries list, hour_info dict with found/expected hours and rows_by_hour)
    """
    date_folder = get_date_folder(archive_path, date_str)
    
    if not date_folder:
        print(f"[ERROR] No archive folder found for date: {date_str}", file=sys.stderr)
        # Initialize rows_by_hour with 0 for all hours
        rows_by_hour = {h: 0 for h in EXPECTED_HOURS}
        return [], {
            "hours_found": 0,
            "hours_expected": 24,
            "found_hours": [],
            "missing_hours": EXPECTED_HOURS,
            "rows_by_hour": rows_by_hour,
            "coverage_ratio": 0.0,
            "is_partial": True,
        }
    
    # Check hour completeness
    found_hours, missing_hours = check_hour_completeness(date_folder)
    
    # Initialize rows_by_hour with 0 for all hours
    rows_by_hour = {h: 0 for h in EXPECTED_HOURS}
    
    hour_files = get_hour_files(date_folder)
    
    if not hour_files:
        print(f"[ERROR] No hour files found in {date_folder}", file=sys.stderr)
        return [], {
            "hours_found": 0,
            "hours_expected": 24,
            "found_hours": [],
            "missing_hours": EXPECTED_HOURS,
            "archive_day": date_folder.name,
            "rows_by_hour": rows_by_hour,
            "coverage_ratio": 0.0,
            "is_partial": True,
        }
    
    print(f"[INFO] Loading from {len(hour_files)} hour files in {date_folder.name}/")
    
    entries = []
    for filepath in hour_files:
        file_entries = list(iter_entries_from_file(filepath))
        entries.extend(file_entries)
        
        # Extract hour from filename and record row count
        stem = filepath.stem
        if stem.endswith(".jsonl"):
            stem = stem[:-6]
        if len(stem) == 2 and stem.isdigit():
            rows_by_hour[stem] = len(file_entries)
        
        print(f"  {filepath.name}: {len(file_entries)} entries")
    
    # Compute coverage ratio
    coverage_ratio = round(len(found_hours) / 24, 4)
    is_partial = len(found_hours) < 24
    
    hour_info = {
        "hours_found": len(found_hours),
        "hours_expected": 24,
        "found_hours": found_hours,
        "missing_hours": missing_hours,
        "archive_day": date_folder.name,
        "rows_by_hour": rows_by_hour,
        "coverage_ratio": coverage_ratio,
        "is_partial": is_partial,
    }
    
    return entries, hour_info


# ==============================================================================
# Schema Validation
# ==============================================================================

def validate_entry_schema(entry: dict, entry_idx: int = 0) -> list[str]:
    """
    Validate that an entry has required fields.
    
    Args:
        entry: Entry dict to validate
        entry_idx: Entry index for error messages
        
    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []
    
    for key in REQUIRED_TOP_LEVEL_KEYS:
        if key not in entry:
            errors.append(f"Entry {entry_idx}: missing required key '{key}'")
    
    # Check meta.schema_version exists
    meta = entry.get("meta", {})
    if not isinstance(meta, dict):
        errors.append(f"Entry {entry_idx}: 'meta' is not a dict")
    elif "schema_version" not in meta:
        errors.append(f"Entry {entry_idx}: missing 'meta.schema_version'")
    
    return errors


def self_test(archive_path: Path) -> bool:
    """
    Run self-test by validating schema on sample entries.
    
    Args:
        archive_path: Root archive directory
        
    Returns:
        True if test passes, False otherwise
    """
    print("[INFO] Running self-test...")
    
    # Find most recent date folder
    date_folders = [
        d for d in archive_path.iterdir()
        if d.is_dir() and d.name.isdigit() and len(d.name) == 8
    ]
    
    if not date_folders:
        print("[ERROR] No date folders found in archive", file=sys.stderr)
        return False
    
    latest_folder = sorted(date_folders, key=lambda d: d.name, reverse=True)[0]
    hour_files = get_hour_files(latest_folder)
    
    if not hour_files:
        print("[ERROR] No hour files found", file=sys.stderr)
        return False
    
    # Load first 10 entries from first file
    sample_file = hour_files[0]
    print(f"[INFO] Sampling from {latest_folder.name}/{sample_file.name}")
    
    sample_entries = []
    for entry in iter_entries_from_file(sample_file):
        sample_entries.append(entry)
        if len(sample_entries) >= 10:
            break
    
    if not sample_entries:
        print("[ERROR] No entries found in sample file", file=sys.stderr)
        return False
    
    print(f"[INFO] Validating {len(sample_entries)} sample entries...")
    
    all_errors = []
    schema_versions = set()
    has_futures = 0
    has_twitter = 0
    
    for i, entry in enumerate(sample_entries):
        errors = validate_entry_schema(entry, i)
        all_errors.extend(errors)
        
        # Collect stats
        meta = entry.get("meta", {})
        if "schema_version" in meta:
            schema_versions.add(meta["schema_version"])
        
        if entry.get("futures_raw") is not None:
            has_futures += 1
        
        if entry.get("twitter_sentiment_windows") is not None:
            has_twitter += 1
    
    if all_errors:
        print("[FAIL] Schema validation errors:", file=sys.stderr)
        for err in all_errors[:10]:  # Show first 10
            print(f"  - {err}", file=sys.stderr)
        return False
    
    print(f"[OK] Schema versions observed: {schema_versions}")
    print(f"[OK] Entries with futures_raw: {has_futures}/{len(sample_entries)}")
    print(f"[OK] Entries with twitter_sentiment_windows: {has_twitter}/{len(sample_entries)}")
    print("[PASS] Self-test completed successfully")
    return True


# ==============================================================================
# Schema Transformation (Tier 3 specific)
# ==============================================================================

# Fields to rename in futures_raw (fix historical _1h -> _5m naming)
FUTURES_FIELD_RENAMES = {
    "open_interest_1h_delta_pct": "open_interest_5m_delta_pct",
    "top_long_short_accounts_1h": "top_long_short_accounts_5m",
    "top_long_short_positions_1h": "top_long_short_positions_5m",
}

# Fields to drop from sentiment_activity (meaningless in daily aggregations)
SENTIMENT_ACTIVITY_FIELDS_TO_DROP = [
    "recent_posts_1h",
    "recent_posts_4h",
    "recent_posts_24h",
    "config",  # Redundant config constants (same for all rows)
]

# Fields to drop from sentiment windows (dynamic dicts that explode into 30k+ sparse columns)
SENTIMENT_WINDOW_FIELDS_TO_DROP = [
    "tag_counts",           # Hashtags in tweets - explodes to 6000+ sparse columns
    "cashtag_counts",       # Cashtags mentioned - explodes to 2800+ sparse columns  
    "mention_counts",       # Twitter accounts mentioned - explodes to 15000+ sparse columns
    "url_domain_counts",    # URL domains linked - explodes to 2400+ sparse columns
    "bucket_min_posts_for_score",  # Always 5, redundant config constant
]


def transform_entry_for_tier3(entry: dict) -> dict:
    """
    Apply Tier 3 schema transformations to an entry.
    
    Transformations:
    1. Rename futures_raw.*_1h fields to *_5m (fixes historical naming debt)
    2. Drop sentiment_activity.recent_posts_1h/4h/24h (meaningless in aggregations)
    3. Drop sentiment_activity.config (redundant constants)
    4. Drop dynamic count dicts (tag_counts, cashtag_counts, mention_counts, url_domain_counts)
       - These explode into 30,000+ sparse columns in Parquet format
       - Use source .jsonl.gz archive if you need raw co-mention data
    5. Drop bucket_min_posts_for_score (always 5, redundant)
    6. Drop diag.backfill_normalized (internal memo, not for external users)
    
    Args:
        entry: Raw entry dict from archive
        
    Returns:
        Transformed entry with corrected schema
    """
    # Drop internal diag fields
    diag = entry.get("diag")
    if diag and isinstance(diag, dict):
        diag.pop("backfill_normalized", None)
    
    # Transform futures_raw field names
    futures_raw = entry.get("futures_raw")
    if futures_raw and isinstance(futures_raw, dict):
        for old_name, new_name in FUTURES_FIELD_RENAMES.items():
            if old_name in futures_raw:
                futures_raw[new_name] = futures_raw.pop(old_name)
    
    # Transform twitter_sentiment_windows (both last_cycle and last_2_cycles)
    twitter_windows = entry.get("twitter_sentiment_windows")
    if twitter_windows and isinstance(twitter_windows, dict):
        for window_key in ["last_cycle", "last_2_cycles"]:
            window = twitter_windows.get(window_key)
            if window and isinstance(window, dict):
                # Drop window-level fields (dynamic dicts, config constants)
                for field_to_drop in SENTIMENT_WINDOW_FIELDS_TO_DROP:
                    window.pop(field_to_drop, None)
                
                # Drop sentiment_activity sub-fields
                sentiment_activity = window.get("sentiment_activity")
                if sentiment_activity and isinstance(sentiment_activity, dict):
                    for field_to_drop in SENTIMENT_ACTIVITY_FIELDS_TO_DROP:
                        sentiment_activity.pop(field_to_drop, None)
    
    return entry


# ==============================================================================
# Parquet Export
# ==============================================================================

def normalize_entry_for_parquet(entry: dict) -> dict:
    """
    Normalize an entry for Parquet export.
    
    Handles edge cases like empty dicts that PyArrow cannot serialize
    as struct types with no child fields.
    
    Args:
        entry: Raw entry dict
        
    Returns:
        Normalized entry safe for Parquet export
    """
    def normalize_value(val):
        if isinstance(val, dict):
            if len(val) == 0:
                # Empty dict -> None (PyArrow can't write empty structs)
                return None
            return {k: normalize_value(v) for k, v in val.items()}
        elif isinstance(val, list):
            return [normalize_value(item) for item in val]
        else:
            return val
    
    return normalize_value(entry)


# Columns to drop from Tier3 export (always empty in v7 schema)
COLUMNS_TO_DROP = ["norm", "labels"]


def entries_to_parquet(entries: list[dict], output_path: Path) -> dict:
    """
    Convert entries to Parquet file.
    
    Args:
        entries: List of entry dicts
        output_path: Path to write .parquet file
        
    Returns:
        Dict with metadata (row_count, schema_versions, min/max added_ts, dropped_columns)
    """
    if not entries:
        raise ValueError("No entries to export")
    
    # Collect schema versions and timestamps
    schema_versions = set()
    added_timestamps = []
    
    for entry in entries:
        meta = entry.get("meta", {})
        if "schema_version" in meta:
            schema_versions.add(meta["schema_version"])
        if "added_ts" in meta:
            added_timestamps.append(meta["added_ts"])
    
    # Apply Tier 3 schema transformations (renames, drops)
    transformed_entries = [transform_entry_for_tier3(e) for e in entries]
    
    # Normalize entries for Parquet (handle empty dicts, etc.)
    normalized_entries = [normalize_entry_for_parquet(e) for e in transformed_entries]
    
    # Create PyArrow table from list of dicts
    # PyArrow will infer nested schema automatically
    table = pa.Table.from_pylist(normalized_entries)
    
    # Drop always-empty columns (norm, labels) to reduce clutter
    dropped_columns = []
    for col_name in COLUMNS_TO_DROP:
        if col_name in table.column_names:
            table = table.drop(col_name)
            dropped_columns.append(col_name)
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write with zstd compression
    pq.write_table(
        table,
        output_path,
        compression=PARQUET_COMPRESSION,
    )
    
    # Calculate min/max timestamps
    min_added_ts = min(added_timestamps) if added_timestamps else None
    max_added_ts = max(added_timestamps) if added_timestamps else None
    
    return {
        "row_count": len(entries),
        "schema_versions": sorted(schema_versions),
        "min_added_ts": min_added_ts,
        "max_added_ts": max_added_ts,
        "dropped_columns": dropped_columns,
    }


def compute_file_sha256(filepath: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def create_manifest(
    date_str: str,
    parquet_path: Path,
    metadata: dict,
    min_hours: int = MIN_HOURS_DEFAULT,
) -> dict:
    """
    Create manifest dict for the export.
    
    Args:
        date_str: UTC date string (YYYY-MM-DD)
        parquet_path: Path to parquet file
        metadata: Metadata from parquet export
        min_hours: Minimum hours threshold used for this export
        
    Returns:
        Manifest dict
    """
    # Get archive day folder name (YYYYMMDD format)
    archive_day = date_str.replace("-", "")
    
    manifest = {
        "date_utc": date_str,
        "created_ts_utc": datetime.now(timezone.utc).isoformat(),
        "row_count": metadata["row_count"],
        "schema_versions": metadata["schema_versions"],
        "min_added_ts": metadata["min_added_ts"],
        "max_added_ts": metadata["max_added_ts"],
        "parquet_sha256": compute_file_sha256(parquet_path),
        "compression": PARQUET_COMPRESSION,
        "tier": "tier3",
        "export_version": "1.3",
        # Partition semantics
        "partition_basis": "archive_folder_day",
        "archive_day": metadata.get("archive_day", archive_day),
        # Coverage metadata
        "hours_expected": 24,
        "hours_found": metadata.get("hours_found", 24),
        "missing_hours": metadata.get("missing_hours", []),
        "coverage_ratio": metadata.get("coverage_ratio", 1.0),
        "is_partial": metadata.get("is_partial", False),
        "rows_by_hour": metadata.get("rows_by_hour", {}),
        "min_hours_threshold": min_hours,
        # Schema notes
        "dropped_columns": metadata.get("dropped_columns", []),
        "null_semantics": {
            "futures_raw": "NULL means no futures contract available or data unavailable for this symbol",
            "optional_structs": "NULL in struct columns indicates empty/unavailable data block",
        },
    }
    return manifest


# ==============================================================================
# R2 Upload
# ==============================================================================

def create_s3_client(config: R2Config):
    """Create boto3 S3 client for R2."""
    return boto3.client(
        "s3",
        endpoint_url=config.endpoint,
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
    )


def check_r2_objects_exist(client, bucket: str, date_str: str) -> list[str]:
    """
    Check which R2 objects already exist for a date.
    
    Returns:
        List of existing object keys
    """
    prefix = f"tier3/daily/{date_str}/"
    existing = []
    
    try:
        response = client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        for obj in response.get("Contents", []):
            existing.append(obj["Key"])
    except ClientError as e:
        print(f"[WARN] Error checking R2: {e}", file=sys.stderr)
    
    return existing


def upload_to_r2(
    client,
    bucket: str,
    local_path: Path,
    r2_key: str,
    content_type: str = "application/octet-stream",
) -> bool:
    """
    Upload a file to R2.
    
    Returns:
        True if successful
    """
    try:
        with open(local_path, "rb") as f:
            client.put_object(
                Bucket=bucket,
                Key=r2_key,
                Body=f,
                ContentType=content_type,
            )
        return True
    except ClientError as e:
        print(f"[ERROR] Upload failed for {r2_key}: {e}", file=sys.stderr)
        return False


# ==============================================================================
# Main Export Logic
# ==============================================================================

def export_tier3_daily(
    date_str: str,
    archive_path: Path,
    output_dir: Path,
    upload: bool = False,
    force: bool = False,
    allow_incomplete: bool = False,
    min_hours: int = MIN_HOURS_DEFAULT,
) -> int:
    """
    Main export function.
    
    Args:
        date_str: UTC date to export (YYYY-MM-DD)
        archive_path: Path to archive root
        output_dir: Local output directory
        upload: Whether to upload to R2
        force: Whether to overwrite existing R2 objects
        allow_incomplete: Allow export of today's date (inherently incomplete)
        min_hours: Minimum hours required for export (default 20)
        
    Returns:
        Exit code (0 = success)
    """
    print(f"\n{'='*60}")
    print(f"TIER 3 DAILY EXPORT: {date_str}")
    print(f"{'='*60}")
    
    # Validate archive path
    if not archive_path.exists():
        print(f"[ERROR] Archive path not found: {archive_path}", file=sys.stderr)
        return 1
    
    # Load entries
    print(f"\n[STEP 1] Loading entries from archive...")
    entries, hour_info = load_day_entries(archive_path, date_str)
    
    if not entries:
        print(f"[ERROR] No entries found for {date_str}", file=sys.stderr)
        return 1
    
    print(f"[OK] Loaded {len(entries)} entries")
    print(f"    Hours found: {hour_info['hours_found']}/{hour_info['hours_expected']}")
    print(f"    Coverage ratio: {hour_info['coverage_ratio']*100:.1f}%")
    
    # Check minimum hours threshold
    if hour_info['hours_found'] < min_hours:
        print(f"\n[ERROR] Insufficient coverage: {hour_info['hours_found']}/{min_hours} hours minimum", file=sys.stderr)
        print(f"    Missing hours: {hour_info['missing_hours']}", file=sys.stderr)
        print(f"[HINT] Use --min-hours to lower the threshold (current: {min_hours})", file=sys.stderr)
        return 1
    
    # Report partial day status (info only, not blocking)
    if hour_info['is_partial']:
        print(f"[INFO] Partial day: missing hours {hour_info['missing_hours']}")
        print(f"[INFO] Proceeding with {hour_info['hours_found']}/{hour_info['hours_expected']} hours (>= {min_hours} threshold)")
    
    # Validate sample
    print(f"\n[STEP 2] Validating schema...")
    sample_errors = []
    for i, entry in enumerate(entries[:5]):
        sample_errors.extend(validate_entry_schema(entry, i))
    
    if sample_errors:
        print("[ERROR] Schema validation failed:", file=sys.stderr)
        for err in sample_errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    
    print("[OK] Schema validation passed")
    
    # Create output paths
    local_dir = output_dir / date_str
    parquet_path = local_dir / "data.parquet"
    manifest_path = local_dir / "manifest.json"
    
    # Export to parquet
    print(f"\n[STEP 3] Exporting to Parquet...")
    try:
        metadata = entries_to_parquet(entries, parquet_path)
    except Exception as e:
        print(f"[ERROR] Parquet export failed: {e}", file=sys.stderr)
        return 1
    
    parquet_size_mb = parquet_path.stat().st_size / (1024 * 1024)
    print(f"[OK] Wrote {parquet_path} ({parquet_size_mb:.2f} MB)")
    print(f"    Row count: {metadata['row_count']}")
    print(f"    Schema versions: {metadata['schema_versions']}")
    
    # Merge hour info into metadata for manifest
    metadata.update(hour_info)
    
    # Create manifest
    print(f"\n[STEP 4] Creating manifest...")
    manifest = create_manifest(date_str, parquet_path, metadata, min_hours)
    
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    
    print(f"[OK] Wrote {manifest_path}")
    
    # Upload to R2 if requested
    if upload:
        print(f"\n[STEP 5] Uploading to R2...")
        
        config = get_r2_config()
        client = create_s3_client(config)
        
        # Check for existing objects
        month_str = date_str[:7]
        r2_parquet_key = f"tier3/daily/{month_str}/{date_str}/instrumetriq_tier3_daily_{date_str}.parquet"
        r2_manifest_key = f"tier3/daily/{month_str}/{date_str}/manifest.json"
        
        # We need to manually check these keys now since check_r2_objects_exist likely uses the old path logic.
        # Ideally we refactor check_r2_objects_exist but inline check is fine for now.
        try:
            client.head_object(Bucket=config.bucket, Key=r2_parquet_key)
            existing = [r2_parquet_key]
        except:
            existing = []
        
        if existing and not force:
            print(f"[ERROR] Objects already exist in R2 for {date_str}:", file=sys.stderr)
            for key in existing:
                print(f"  - {key}", file=sys.stderr)
            print("[HINT] Use --force to overwrite", file=sys.stderr)
            return 1
        
        if existing and force:
            print(f"[WARN] Overwriting {len(existing)} existing objects (--force)")
        
        # Upload parquet
        print(f"  Uploading {r2_parquet_key}...")
        if not upload_to_r2(client, config.bucket, parquet_path, r2_parquet_key, "application/octet-stream"):
            return 1
        
        # Upload manifest
        print(f"  Uploading {r2_manifest_key}...")
        if not upload_to_r2(client, config.bucket, manifest_path, r2_manifest_key, "application/json"):
            return 1
        
        print(f"[OK] Upload complete to {config.bucket}")
    else:
        print(f"\n[INFO] Dry run - skipping R2 upload (use --upload to upload)")
    
    # Summary
    print(f"\n{'='*60}")
    print("EXPORT SUMMARY")
    print(f"{'='*60}")
    print(f"Date:           {date_str}")
    print(f"Rows:           {metadata['row_count']}")
    print(f"Parquet size:   {parquet_size_mb:.2f} MB")
    print(f"Local path:     {local_dir}/")
    if upload:
        print(f"R2 prefix:      tier3/daily/{date_str}/")
    print(f"{'='*60}\n")
    
    return 0


# ==============================================================================
# CLI
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Export Tier 3 daily dataset to Parquet and upload to R2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/export_tier3_daily.py --dry-run
  python3 scripts/export_tier3_daily.py --date 2026-01-14 --upload
  python3 scripts/export_tier3_daily.py --from-date 2025-12-14 --to-date 2026-01-17 --upload
  python3 scripts/export_tier3_daily.py --date 2026-01-14 --upload --force
  python3 scripts/export_tier3_daily.py --self-test
        """,
    )
    
    parser.add_argument(
        "--date",
        type=str,
        help="UTC date to export (YYYY-MM-DD). Default: yesterday UTC",
    )
    
    parser.add_argument(
        "--from-date",
        type=str,
        help="Start of date range (inclusive, YYYY-MM-DD). Use with --to-date.",
    )
    
    parser.add_argument(
        "--to-date",
        type=str,
        help="End of date range (inclusive, YYYY-MM-DD). Use with --from-date.",
    )
    
    parser.add_argument(
        "--archive-path",
        type=Path,
        default=DEFAULT_ARCHIVE_PATH,
        help=f"Path to archive root. Default: {DEFAULT_ARCHIVE_PATH}",
    )
    
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Local output directory. Default: {DEFAULT_OUTPUT_DIR}",
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build locally only, do not upload to R2",
    )
    
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Upload to R2 after building",
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing R2 objects",
    )
    
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run schema validation self-test and exit",
    )
    
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Allow export of today's date (day is inherently incomplete)",
    )
    
    parser.add_argument(
        "--min-hours",
        type=int,
        default=MIN_HOURS_DEFAULT,
        help=f"Minimum hours required for export (default: {MIN_HOURS_DEFAULT}). Use 24 to require complete days.",
    )
    
    args = parser.parse_args()
    
    # Self-test mode
    if args.self_test:
        success = self_test(args.archive_path)
        sys.exit(0 if success else 1)
    
    # Get current UTC date for comparison
    now_utc = datetime.now(timezone.utc)
    today_utc = now_utc.strftime("%Y-%m-%d")
    yesterday_utc = (now_utc - timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Determine upload mode
    do_upload = args.upload and not args.dry_run
    
    if args.dry_run and args.upload:
        print("[WARN] --dry-run overrides --upload; will not upload", file=sys.stderr)
    
    # Build list of dates to process
    dates_to_process = []
    
    if args.from_date and args.to_date:
        # Date range mode
        try:
            start_date = datetime.strptime(args.from_date, "%Y-%m-%d").date()
            end_date = datetime.strptime(args.to_date, "%Y-%m-%d").date()
        except ValueError as e:
            print(f"[ERROR] Invalid date format: {e}. Use YYYY-MM-DD", file=sys.stderr)
            sys.exit(1)
        
        if start_date > end_date:
            print(f"[ERROR] --from-date ({args.from_date}) must be <= --to-date ({args.to_date})", file=sys.stderr)
            sys.exit(1)
        
        current = start_date
        while current <= end_date:
            dates_to_process.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)
        
        print(f"[INFO] Date range: {args.from_date} to {args.to_date} ({len(dates_to_process)} days)")
    
    elif args.from_date or args.to_date:
        # Only one of from/to specified
        print("[ERROR] Both --from-date and --to-date must be specified together", file=sys.stderr)
        sys.exit(1)
    
    elif args.date:
        # Single date mode
        date_str = args.date
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            print(f"[ERROR] Invalid date format: {date_str}. Use YYYY-MM-DD", file=sys.stderr)
            sys.exit(1)
        
        # Disallow "today UTC" without --allow-incomplete
        if date_str == today_utc and not args.allow_incomplete:
            print(f"[ERROR] Cannot export today's date ({today_utc}) - day is not complete.", file=sys.stderr)
            print("[HINT] Use --allow-incomplete to bypass this check (may result in partial export)", file=sys.stderr)
            sys.exit(1)
        
        dates_to_process = [date_str]
    
    else:
        # Default to yesterday UTC
        dates_to_process = [yesterday_utc]
        print(f"[INFO] No --date specified, defaulting to yesterday UTC: {yesterday_utc}")
    
    # Process all dates
    success_count = 0
    fail_count = 0
    skip_count = 0
    
    for i, date_str in enumerate(dates_to_process):
        if len(dates_to_process) > 1:
            print(f"\n[{i+1}/{len(dates_to_process)}] Processing {date_str}...")
        
        # Skip today unless --allow-incomplete
        if date_str == today_utc and not args.allow_incomplete:
            print(f"  [SKIP] Skipping today ({today_utc}) - day not complete")
            skip_count += 1
            continue
        
        exit_code = export_tier3_daily(
            date_str=date_str,
            archive_path=args.archive_path,
            output_dir=args.out_dir,
            upload=do_upload,
            force=args.force,
            allow_incomplete=args.allow_incomplete,
            min_hours=args.min_hours,
        )
        
        if exit_code == 0:
            success_count += 1
        else:
            fail_count += 1
    
    # Summary for multi-date runs
    if len(dates_to_process) > 1:
        print(f"\n{'='*60}")
        print(f"BATCH SUMMARY")
        print(f"{'='*60}")
        print(f"Total days:   {len(dates_to_process)}")
        print(f"Success:      {success_count}")
        print(f"Failed:       {fail_count}")
        print(f"Skipped:      {skip_count}")
        print(f"{'='*60}")
    
    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
