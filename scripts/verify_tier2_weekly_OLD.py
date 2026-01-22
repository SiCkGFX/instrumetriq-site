#!/usr/bin/env python3
"""
Tier 2 Weekly Parquet Verification Script

Validates Tier 2 weekly parquet exports for correctness and completeness.
Downloads from R2 (or uses local files) and runs comprehensive checks.

Usage:
    # Default: verify ALL weeks in R2
    python3 scripts/verify_tier2_weekly.py

    # Verify specific week by end date
    python3 scripts/verify_tier2_weekly.py --end-day 2025-12-28

    # Verify from local files
    python3 scripts/verify_tier2_weekly.py --local output/tier2_weekly/2025-12-28

    # Verify from R2 explicitly
    python3 scripts/verify_tier2_weekly.py --r2 --end-day 2025-12-28

Outputs:
    Reports are written to output/verify_tier2/report_YYYYMMDD_HHMMSS.md
    Per-week artifacts are written to output/verify_tier2/{end-day}/
"""

import argparse
import hashlib
import json
import statistics
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

try:
    import pyarrow.parquet as pq
    import pyarrow as pa
except ImportError:
    print("[ERROR] pyarrow not installed. Run: pip install pyarrow", file=sys.stderr)
    sys.exit(1)

try:
    import boto3
except ImportError:
    print("[ERROR] boto3 not installed. Run: pip install boto3", file=sys.stderr)
    sys.exit(1)

# Add scripts directory to path for r2_config import
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from r2_config import get_r2_config, R2Config


# ==============================================================================
# Constants
# ==============================================================================

VERIFY_CACHE_DIR = Path("./output/verify_tier2")

# Tier 2 column policy (per spec in tiers datasets explanations.txt)
# twitter_sentiment_windows IS INCLUDED with dynamic-key fields extracted to sidecar
TIER2_REQUIRED_COLUMNS = [
    "symbol",
    "snapshot_ts",
    "meta",
    "spot_raw",
    "derived",
    "scores",
    "twitter_sentiment_meta",
    "twitter_sentiment_windows",  # Now included per spec
]

TIER2_EXCLUDED_COLUMNS = [
    "futures_raw",
    "spot_prices",
    "flags",
    "diag",
    "norm",
    "labels",
    # NOTE: twitter_sentiment_windows is NO LONGER excluded
]

# Dynamic-key fields (extracted to sidecar, not in main parquet's twitter_sentiment_windows)
DYNAMIC_KEY_FIELDS = [
    "tag_counts",
    "cashtag_counts",
    "mention_counts",
    "url_domain_counts",
]

# Static fields expected in twitter_sentiment_windows.last_cycle
SENTIMENT_WINDOW_EXPECTED_FIELDS = [
    "ai_sentiment",
    "author_stats",
    "category_counts",
    "content_stats",
    "hybrid_decision_stats",
    "lexicon_sentiment",
    "platform_engagement",
    "top_terms",
]

# Expected meta sub-fields
META_EXPECTED_FIELDS = [
    "added_ts",
    "expires_ts",
    "duration_sec",
    "archive_schema_version",
]

# Expected spot_raw sub-fields
SPOT_RAW_EXPECTED_FIELDS = [
    "mid",
    "bid",
    "ask",
    "spread_bps",
]


# ==============================================================================
# Data Classes
# ==============================================================================

@dataclass
class VerificationResult:
    """Results from verifying a single week's export."""
    end_day: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: dict = field(default_factory=dict)
    
    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0
    
    @property
    def status(self) -> str:
        if self.errors:
            return "FAIL"
        elif self.warnings:
            return "WARN"
        return "PASS"
    
    @property
    def status_symbol(self) -> str:
        if self.errors:
            return "[FAIL]"
        elif self.warnings:
            return "[WARN]"
        return "[PASS]"


# ==============================================================================
# R2 Helpers
# ==============================================================================

def get_s3_client(config: R2Config):
    """Create boto3 S3 client for R2."""
    return boto3.client(
        "s3",
        endpoint_url=config.endpoint,
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
    )


def list_tier2_weeks(config: R2Config) -> list[str]:
    """List all Tier 2 weekly end dates available in R2."""
    s3 = get_s3_client(config)
    
    response = s3.list_objects_v2(
        Bucket=config.bucket,
        Prefix="tier2/weekly/",
        Delimiter="/",
    )
    
    weeks = []
    for prefix_obj in response.get("CommonPrefixes", []):
        # tier2/weekly/2025-12-28/
        prefix = prefix_obj.get("Prefix", "")
        parts = prefix.rstrip("/").split("/")
        if len(parts) >= 3:
            end_day = parts[2]
            # Validate date format
            try:
                datetime.strptime(end_day, "%Y-%m-%d")
                weeks.append(end_day)
            except ValueError:
                pass
    
    return sorted(weeks)


def download_from_r2(
    config: R2Config,
    end_day: str,
    cache_dir: Path,
) -> tuple[Optional[Path], Optional[Path], Optional[Path]]:
    """
    Download parquet, sidecar, and manifest from R2 for a given week.
    
    Returns:
        Tuple of (parquet_path, manifest_path, sidecar_path), or (None, None, None) if not found.
        sidecar_path may be None if sidecar doesn't exist (old format or skip-sidecar build).
    """
    s3 = get_s3_client(config)
    
    prefix = f"tier2/weekly/{end_day}/"
    parquet_key = f"{prefix}dataset_entries_7d.parquet"
    manifest_key = f"{prefix}manifest.json"
    sidecar_key = f"{prefix}sentiment_counts.parquet"
    
    # Create cache directory
    week_cache = cache_dir / end_day
    week_cache.mkdir(parents=True, exist_ok=True)
    
    parquet_path = week_cache / "dataset_entries_7d.parquet"
    manifest_path = week_cache / "manifest.json"
    sidecar_path = week_cache / "sentiment_counts.parquet"
    
    try:
        # Check if main objects exist first
        s3.head_object(Bucket=config.bucket, Key=parquet_key)
        s3.head_object(Bucket=config.bucket, Key=manifest_key)
    except Exception as e:
        print(f"[ERROR] Objects not found in R2 for week {end_day}: {e}", file=sys.stderr)
        return None, None, None
    
    # Download parquet
    print(f"  Downloading {parquet_key}...")
    s3.download_file(config.bucket, parquet_key, str(parquet_path))
    
    # Download manifest
    print(f"  Downloading {manifest_key}...")
    s3.download_file(config.bucket, manifest_key, str(manifest_path))
    
    # Try to download sidecar (optional - may not exist for old format or skip-sidecar builds)
    try:
        s3.head_object(Bucket=config.bucket, Key=sidecar_key)
        print(f"  Downloading {sidecar_key}...")
        s3.download_file(config.bucket, sidecar_key, str(sidecar_path))
    except Exception:
        print(f"  [INFO] No sidecar file found (may be old format or --skip-sidecar build)")
        sidecar_path = None
    
    return parquet_path, manifest_path, sidecar_path


def get_r2_object_size(config: R2Config, end_day: str) -> int:
    """Get parquet file size from R2 without downloading."""
    s3 = get_s3_client(config)
    key = f"tier2/weekly/{end_day}/dataset_entries_7d.parquet"
    
    try:
        response = s3.head_object(Bucket=config.bucket, Key=key)
        return response["ContentLength"]
    except Exception:
        return 0


# ==============================================================================
# Verification Checks
# ==============================================================================

def compute_sha256(filepath: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def check_presence_and_integrity(
    result: VerificationResult,
    parquet_path: Optional[Path],
    manifest_path: Optional[Path],
    r2_size: Optional[int] = None,
):
    """Check A: Object presence + integrity."""
    if parquet_path is None or manifest_path is None:
        result.errors.append("Missing parquet or manifest file")
        return
    
    if not parquet_path.exists():
        result.errors.append(f"Parquet file not found: {parquet_path}")
        return
    
    if not manifest_path.exists():
        result.errors.append(f"Manifest file not found: {manifest_path}")
        return
    
    parquet_size = parquet_path.stat().st_size
    manifest_size = manifest_path.stat().st_size
    
    result.info["parquet_size_bytes"] = parquet_size
    result.info["parquet_size_mb"] = round(parquet_size / (1024 * 1024), 2)
    result.info["manifest_size_bytes"] = manifest_size
    
    if r2_size:
        result.info["r2_parquet_size"] = r2_size
    
    # Load manifest
    try:
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
    except json.JSONDecodeError as e:
        result.errors.append(f"Manifest is not valid JSON: {e}")
        return
    
    result.info["manifest"] = manifest
    
    # Verify SHA256 (support multiple field locations)
    expected_sha = None
    sha_location = None
    
    # Check new location: files.main.sha256
    if "files" in manifest and "main" in manifest["files"]:
        if "sha256" in manifest["files"]["main"]:
            expected_sha = manifest["files"]["main"]["sha256"]
            sha_location = "files.main.sha256"
    
    # Fallback to legacy top-level fields
    if expected_sha is None:
        for name in ["parquet_sha256", "sha256"]:
            if name in manifest:
                expected_sha = manifest[name]
                sha_location = name
                break
    
    if expected_sha:
        actual_sha = compute_sha256(parquet_path)
        
        result.info["expected_sha256"] = expected_sha
        result.info["actual_sha256"] = actual_sha
        result.info["sha256_match"] = expected_sha == actual_sha
        
        if expected_sha != actual_sha:
            result.errors.append(
                f"SHA256 mismatch! Expected: {expected_sha[:16]}... Got: {actual_sha[:16]}..."
            )
    else:
        result.warnings.append("Manifest does not contain SHA256 field")
    
    # Compare file size to manifest (check both locations)
    manifest_size_bytes = None
    
    # Check new location: files.main.size_bytes
    if "files" in manifest and "main" in manifest["files"]:
        manifest_size_bytes = manifest["files"]["main"].get("size_bytes")
    
    # Fallback to legacy top-level field
    if manifest_size_bytes is None:
        manifest_size_bytes = manifest.get("parquet_size_bytes")
    
    if manifest_size_bytes is not None:
        if parquet_size != manifest_size_bytes:
            result.warnings.append(
                f"Parquet size differs from manifest: actual={parquet_size}, manifest={manifest_size_bytes}"
            )
        else:
            result.info["size_match"] = True


def check_window_semantics(
    result: VerificationResult,
    end_day: str,
):
    """Check B: Window semantics (allows partial weeks)."""
    manifest = result.info.get("manifest", {})
    
    # Required top-level fields
    required_top = ["tier", "schema_version", "window", "build_ts_utc", "source_inputs", "row_count"]
    for field_name in required_top:
        if field_name not in manifest:
            result.errors.append(f"Manifest missing required field: {field_name}")
    
    # Check tier
    tier = manifest.get("tier")
    if tier != "tier2":
        result.errors.append(f"Manifest tier != 'tier2' (got: {tier})")
    
    # Check schema_version
    schema_version = manifest.get("schema_version")
    if schema_version != "v7":
        result.errors.append(f"Manifest schema_version != 'v7' (got: {schema_version})")
    
    # Check window structure
    window = manifest.get("window", {})
    
    # Support both old (end_day) and new (week_end_day) field names
    manifest_end_day = window.get("week_end_day") or window.get("end_day")
    manifest_start_day = window.get("week_start_day") or window.get("start_day")
    window_basis = window.get("window_basis", "end_day")
    
    if manifest_end_day != end_day:
        result.errors.append(f"Manifest end_day ({manifest_end_day}) != folder name ({end_day})")
    
    # Get days_expected if available, else fall back to days_included
    days_expected = window.get("days_expected") or window.get("days_included", [])
    days_included = window.get("days_included", [])
    
    result.info["days_expected"] = days_expected
    result.info["days_included"] = days_included
    result.info["window_start"] = manifest_start_day
    result.info["window_end"] = manifest_end_day
    result.info["window_basis"] = window_basis
    
    # Verify days_expected has 7 items
    if len(days_expected) != 7:
        result.errors.append(f"Manifest days_expected should have 7 items, got {len(days_expected)}")
    
    # Verify days are consecutive
    if len(days_expected) == 7:
        try:
            dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in days_expected]
            dates_sorted = sorted(dates)
            
            # Check consecutive
            for i in range(1, len(dates_sorted)):
                expected = dates_sorted[i-1] + timedelta(days=1)
                if dates_sorted[i] != expected:
                    result.errors.append(
                        f"Manifest days_expected not consecutive: gap between {dates_sorted[i-1]} and {dates_sorted[i]}"
                    )
                    break
            
            # Check end_day matches last day
            if dates_sorted[-1].strftime("%Y-%m-%d") != end_day:
                result.errors.append(
                    f"Last day in days_expected ({dates_sorted[-1]}) != end_day ({end_day})"
                )
        except ValueError as e:
            result.errors.append(f"Invalid date format in days_expected: {e}")
    
    # Check source_inputs matches days_included
    source_inputs = manifest.get("source_inputs", [])
    result.info["source_inputs_count"] = len(source_inputs)
    
    # source_inputs should match days_included (not days_expected)
    if len(source_inputs) != len(days_included):
        result.errors.append(
            f"source_inputs count ({len(source_inputs)}) != days_included count ({len(days_included)})"
        )


def check_source_coverage(
    result: VerificationResult,
):
    """Check E: Source coverage metadata (new for partial week support)."""
    manifest = result.info.get("manifest", {})
    source_coverage = manifest.get("source_coverage")
    
    if source_coverage is None:
        # Old manifest format - warn but don't fail
        result.warnings.append("Manifest missing source_coverage block (old format)")
        return
    
    # Required fields in source_coverage
    required_fields = [
        "days_expected", "days_present", "days_missing", "per_day",
        "present_days_count", "missing_days_count", "partial_days_count",
        "min_days_threshold_used", "coverage_note"
    ]
    
    for field_name in required_fields:
        if field_name not in source_coverage:
            result.errors.append(f"source_coverage missing field: {field_name}")
    
    # Extract coverage info for reporting
    result.info["source_coverage"] = source_coverage
    
    days_present = source_coverage.get("days_present", [])
    days_missing = source_coverage.get("days_missing", [])
    per_day = source_coverage.get("per_day", {})
    present_count = source_coverage.get("present_days_count", len(days_present))
    missing_count = source_coverage.get("missing_days_count", len(days_missing))
    partial_count = source_coverage.get("partial_days_count", 0)
    min_days_threshold = source_coverage.get("min_days_threshold_used", 5)
    
    result.info["present_days_count"] = present_count
    result.info["missing_days_count"] = missing_count
    result.info["partial_days_count"] = partial_count
    result.info["min_days_threshold"] = min_days_threshold
    result.info["days_missing_list"] = days_missing
    
    # FAIL if present_days_count < min_days_threshold
    if present_count < min_days_threshold:
        result.errors.append(
            f"Insufficient days: {present_count}/{min_days_threshold} required"
        )
    
    # WARN if any missing days
    if missing_count > 0:
        result.warnings.append(
            f"Missing days: {missing_count}/7 ({', '.join(days_missing)})"
        )
    
    # WARN if any partial days
    if partial_count > 0:
        partial_days = [d for d in days_present if per_day.get(d, {}).get("is_partial", False)]
        partial_info = []
        for d in partial_days:
            hours = per_day.get(d, {}).get("hours_found", "?")
            missing_hours = per_day.get(d, {}).get("missing_hours", [])
            partial_info.append(f"{d}: {hours}/24 hours (missing {missing_hours})")
        
        result.warnings.append(
            f"Partial days: {partial_count} ({'; '.join(partial_info[:3])})"
            + ("..." if len(partial_info) > 3 else "")
        )
    
    result.info["per_day_coverage"] = per_day


def check_schema_columns(
    result: VerificationResult,
    parquet_path: Path,
) -> Optional[pa.Table]:
    """Check C: Schema / column policy."""
    try:
        table = pq.read_table(parquet_path)
    except Exception as e:
        result.errors.append(f"Failed to read parquet file: {e}")
        return None
    
    columns = set(table.column_names)
    result.info["row_count"] = table.num_rows
    result.info["column_count"] = table.num_columns
    result.info["columns"] = table.column_names
    
    # Check required columns
    missing_required = []
    for col in TIER2_REQUIRED_COLUMNS:
        if col not in columns:
            missing_required.append(col)
    
    if missing_required:
        result.errors.append(f"Missing required columns: {missing_required}")
    else:
        result.info["required_columns_ok"] = True
    
    # Check excluded columns are absent
    present_excluded = []
    for col in TIER2_EXCLUDED_COLUMNS:
        if col in columns:
            present_excluded.append(col)
    
    if present_excluded:
        result.errors.append(f"Excluded columns present (should be absent): {present_excluded}")
    else:
        result.info["excluded_columns_ok"] = True
    
    # Write schema to file for artifacts
    schema_lines = []
    for fld in table.schema:
        type_str = str(fld.type)
        if len(type_str) > 100:
            type_str = type_str[:97] + "..."
        schema_lines.append(f"{fld.name}: {type_str}")
    result.info["schema_lines"] = schema_lines
    
    # Check nested sanity for struct columns
    check_nested_sanity(result, table)
    
    return table


def check_nested_sanity(result: VerificationResult, table: pa.Table):
    """Lightweight check on nested struct fields."""
    schema = table.schema
    
    # Check meta sub-fields
    if "meta" in table.column_names:
        meta_field = schema.field("meta")
        if pa.types.is_struct(meta_field.type):
            meta_field_names = [f.name for f in meta_field.type]
            result.info["meta_fields"] = meta_field_names
            
            missing_meta = [f for f in META_EXPECTED_FIELDS if f not in meta_field_names]
            if missing_meta:
                result.warnings.append(f"meta missing expected fields: {missing_meta}")
        else:
            result.warnings.append(f"meta is not a struct type: {meta_field.type}")
    
    # Check spot_raw sub-fields
    if "spot_raw" in table.column_names:
        spot_field = schema.field("spot_raw")
        if pa.types.is_struct(spot_field.type):
            spot_field_names = [f.name for f in spot_field.type]
            result.info["spot_raw_fields"] = spot_field_names
            
            missing_spot = [f for f in SPOT_RAW_EXPECTED_FIELDS if f not in spot_field_names]
            if missing_spot:
                result.warnings.append(f"spot_raw missing expected fields: {missing_spot}")
        else:
            result.warnings.append(f"spot_raw is not a struct type: {spot_field.type}")
    
    # Check derived and scores are structs
    for col_name in ["derived", "scores"]:
        if col_name in table.column_names:
            col_field = schema.field(col_name)
            if not pa.types.is_struct(col_field.type):
                result.warnings.append(f"{col_name} is not a struct type: {col_field.type}")
    
    # Check twitter_sentiment_windows structure
    if "twitter_sentiment_windows" in table.column_names:
        tsw_field = schema.field("twitter_sentiment_windows")
        if pa.types.is_struct(tsw_field.type):
            tsw_field_names = [f.name for f in tsw_field.type]
            result.info["twitter_sentiment_windows_fields"] = tsw_field_names
            
            # Check for last_cycle
            if "last_cycle" not in tsw_field_names:
                result.errors.append("twitter_sentiment_windows missing last_cycle")
            else:
                # Get last_cycle sub-fields
                last_cycle_type = None
                for f in tsw_field.type:
                    if f.name == "last_cycle":
                        last_cycle_type = f.type
                        break
                
                if last_cycle_type and pa.types.is_struct(last_cycle_type):
                    last_cycle_fields = [f.name for f in last_cycle_type]
                    result.info["last_cycle_fields"] = last_cycle_fields
                    
                    # Check expected static fields are present
                    missing_sentiment = [f for f in SENTIMENT_WINDOW_EXPECTED_FIELDS if f not in last_cycle_fields]
                    if missing_sentiment:
                        result.warnings.append(f"last_cycle missing expected fields: {missing_sentiment}")
                    
                    # Check dynamic-key fields are NOT present (extracted to sidecar)
                    dynamic_present = [f for f in DYNAMIC_KEY_FIELDS if f in last_cycle_fields]
                    if dynamic_present:
                        result.warnings.append(f"last_cycle contains dynamic-key fields (should be in sidecar): {dynamic_present}")
        else:
            result.warnings.append(f"twitter_sentiment_windows is not a struct type: {tsw_field.type}")


def check_data_quality(result: VerificationResult, table: pa.Table):
    """Check D: Data quality summaries."""
    manifest = result.info.get("manifest", {})
    num_rows = table.num_rows
    
    # Compare row count to manifest (check both locations)
    manifest_row_count = manifest.get("row_count")
    
    # Also check files.main.row_count
    if manifest_row_count is None:
        if "files" in manifest and "main" in manifest["files"]:
            manifest_row_count = manifest["files"]["main"].get("row_count")
    
    if manifest_row_count is not None:
        if num_rows != manifest_row_count:
            result.errors.append(
                f"Row count mismatch: parquet={num_rows}, manifest={manifest_row_count}"
            )
        else:
            result.info["row_count_match"] = True
    
    # Distinct symbols (use dictionary if available, else sample)
    if "symbol" in table.column_names:
        symbol_col = table.column("symbol")
        try:
            # Try to get unique values efficiently
            symbols = symbol_col.unique()
            result.info["distinct_symbols"] = len(symbols)
        except Exception:
            result.info["distinct_symbols"] = "unknown"
    
    # Duration stats
    if "meta" in table.column_names:
        durations = []
        meta_col = table.column("meta")
        
        # Sample up to 1000 rows for performance
        sample_size = min(1000, num_rows)
        step = max(1, num_rows // sample_size)
        
        for i in range(0, num_rows, step):
            meta = meta_col[i].as_py()
            if meta and isinstance(meta, dict):
                dur = meta.get("duration_sec")
                if dur is not None:
                    durations.append(dur)
        
        if durations:
            durations_sorted = sorted(durations)
            result.info["duration_stats"] = {
                "min": durations_sorted[0],
                "median": statistics.median(durations_sorted),
                "p95": durations_sorted[int(len(durations_sorted) * 0.95)] if len(durations_sorted) > 20 else durations_sorted[-1],
                "max": durations_sorted[-1],
                "sample_count": len(durations),
            }
            
            # Warn if max is absurd (> 24 hours)
            if durations_sorted[-1] > 86400:
                result.warnings.append(
                    f"duration_sec max is very high: {durations_sorted[-1]} seconds"
                )
    
    # Null ratios for struct columns
    struct_cols = ["meta", "spot_raw", "derived", "scores", "twitter_sentiment_meta", "twitter_sentiment_windows"]
    null_ratios = {}
    
    for col_name in struct_cols:
        if col_name in table.column_names:
            col = table.column(col_name)
            null_count = col.null_count
            null_ratio = null_count / num_rows if num_rows > 0 else 0
            null_ratios[col_name] = {
                "null_count": null_count,
                "null_ratio": round(null_ratio, 4),
            }
            
            # Warn if > 1% null
            if null_ratio > 0.01:
                result.warnings.append(
                    f"{col_name} has {null_ratio*100:.2f}% null values ({null_count}/{num_rows})"
                )
    
    result.info["null_ratios"] = null_ratios
    
    # Snapshot_ts stats
    if "snapshot_ts" in table.column_names:
        ts_col = table.column("snapshot_ts")
        ts_type = ts_col.type
        result.info["snapshot_ts_type"] = str(ts_type)
        
        # Try to get min/max
        try:
            # snapshot_ts may be string or numeric
            first_val = ts_col[0].as_py()
            last_val = ts_col[num_rows - 1].as_py()
            result.info["snapshot_ts_first"] = str(first_val)
            result.info["snapshot_ts_last"] = str(last_val)
        except Exception:
            pass


# ==============================================================================
# Artifact Writers
# ==============================================================================

def write_artifacts(result: VerificationResult, cache_dir: Path):
    """Write per-week artifacts (schema.txt, stats.json)."""
    end_day = result.end_day
    week_dir = cache_dir / end_day
    week_dir.mkdir(parents=True, exist_ok=True)
    
    # schema.txt
    schema_lines = result.info.get("schema_lines", [])
    if schema_lines:
        schema_path = week_dir / "schema.txt"
        with open(schema_path, "w") as f:
            f.write("Tier 2 Weekly Parquet Schema\n")
            f.write(f"Week ending: {end_day}\n")
            f.write("=" * 50 + "\n\n")
            for line in schema_lines:
                f.write(line + "\n")
    
    # stats.json
    stats = {
        "end_day": end_day,
        "status": result.status,
        "row_count": result.info.get("row_count"),
        "parquet_size_bytes": result.info.get("parquet_size_bytes"),
        "sha256_match": result.info.get("sha256_match"),
        "required_columns_ok": result.info.get("required_columns_ok"),
        "excluded_columns_ok": result.info.get("excluded_columns_ok"),
        "distinct_symbols": result.info.get("distinct_symbols"),
        "duration_stats": result.info.get("duration_stats"),
        "null_ratios": result.info.get("null_ratios"),
        # Sidecar stats
        "sidecar_status": result.info.get("sidecar_status"),
        "sidecar_row_count": result.info.get("sidecar_row_count"),
        "sidecar_size_mb": result.info.get("sidecar_size_mb"),
        "sidecar_count_types": result.info.get("sidecar_count_types"),
        "sidecar_cycles": result.info.get("sidecar_cycles"),
        "errors": result.errors,
        "warnings": result.warnings,
    }
    
    stats_path = week_dir / "stats.json"
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2)


# ==============================================================================
# Report Generation
# ==============================================================================

def generate_report(results: list[VerificationResult], report_path: Path):
    """Generate markdown verification report."""
    lines = [
        "# Tier 2 Weekly Parquet Verification Report",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "---",
        "",
        "## Verified Weeks",
        "",
        "| Week End | Status | Days | Partial | Rows | Size (MB) | SHA Match |",
        "|----------|--------|------|---------|------|-----------|-----------|",
    ]
    
    for r in results:
        info = r.info
        sha_match = "OK" if info.get("sha256_match") else "FAIL"
        
        # Days present/expected
        present = info.get("present_days_count", len(info.get("days_included", [])))
        days_str = f"{present}/7"
        if info.get("missing_days_count", 0) > 0:
            days_str += " ⚠️"
        
        # Partial days
        partial = info.get("partial_days_count", 0)
        partial_str = str(partial) if partial > 0 else "-"
        if partial > 0:
            partial_str += " ⚠️"
        
        # Format row count with comma (handle N/A gracefully)
        row_count = info.get("row_count")
        row_count_str = f"{row_count:,}" if isinstance(row_count, int) else "N/A"
        
        lines.append(
            f"| {r.end_day} | {r.status_symbol} | {days_str} | {partial_str} | "
            f"{row_count_str} | {info.get('parquet_size_mb', 'N/A')} | {sha_match} |"
        )
    
    lines.append("")
    
    # Overall status
    all_pass = all(not r.has_errors for r in results)
    any_warnings = any(r.warnings for r in results)
    
    lines.append("## Overall Status")
    lines.append("")
    if all_pass and not any_warnings:
        lines.append("[PASS] All checks passed.")
    elif all_pass:
        lines.append("[WARN] All critical checks passed, but there are warnings.")
    else:
        lines.append("[FAIL] Verification failed. Do NOT proceed until errors are resolved.")
    lines.append("")
    
    # Source Coverage section (new)
    lines.append("---")
    lines.append("")
    lines.append("## Source Coverage")
    lines.append("")
    
    for r in results:
        info = r.info
        source_coverage = info.get("source_coverage")
        
        lines.append(f"### Week {r.end_day}")
        lines.append("")
        
        if source_coverage:
            present = source_coverage.get("present_days_count", 0)
            missing = source_coverage.get("missing_days_count", 0)
            partial = source_coverage.get("partial_days_count", 0)
            threshold = source_coverage.get("min_days_threshold_used", 5)
            
            lines.append(f"- **Days present:** {present}/7")
            lines.append(f"- **Days missing:** {missing}")
            lines.append(f"- **Partial days:** {partial}")
            lines.append(f"- **Min days threshold:** {threshold}")
            
            days_missing_list = source_coverage.get("days_missing", [])
            if days_missing_list:
                lines.append(f"- **Missing days:** {', '.join(days_missing_list)}")
            
            # Per-day coverage details
            per_day = source_coverage.get("per_day", {})
            if per_day:
                lines.append("")
                lines.append("**Per-day coverage:**")
                lines.append("| Day | Hours | Status |")
                lines.append("|-----|-------|--------|")
                
                days_present = source_coverage.get("days_present", [])
                for day in sorted(days_present):
                    day_info = per_day.get(day, {})
                    hours = day_info.get("hours_found", 24)
                    is_partial = day_info.get("is_partial", False)
                    status = "PARTIAL" if is_partial else "OK"
                    lines.append(f"| {day} | {hours}/24 | {status} |")
            
            coverage_note = source_coverage.get("coverage_note")
            if coverage_note:
                lines.append("")
                lines.append(f"*{coverage_note}*")
        else:
            lines.append("*No source_coverage metadata (old manifest format)*")
        
        lines.append("")
    
    # Manifest checks section
    lines.append("---")
    lines.append("")
    lines.append("## Manifest Checks")
    lines.append("")
    
    for r in results:
        manifest = r.info.get("manifest", {})
        lines.append(f"### Week {r.end_day}")
        lines.append("")
        lines.append(f"- **tier:** {manifest.get('tier', 'N/A')}")
        lines.append(f"- **schema_version:** {manifest.get('schema_version', 'N/A')}")
        lines.append(f"- **build_ts_utc:** {manifest.get('build_ts_utc', 'N/A')}")
        
        window = manifest.get("window", {})
        window_basis = r.info.get("window_basis", window.get("window_basis", "N/A"))
        window_start = r.info.get("window_start", "N/A")
        window_end = r.info.get("window_end", "N/A")
        lines.append(f"- **window_basis:** {window_basis}")
        lines.append(f"- **week_start_day:** {window_start}")
        lines.append(f"- **week_end_day:** {window_end}")
        lines.append(f"- **days_included:** {len(r.info.get('days_included', []))} days")
        lines.append(f"- **source_inputs:** {r.info.get('source_inputs_count', 'N/A')} Tier 3 parquets")
        lines.append(f"- **row_count (manifest):** {manifest.get('row_count', 'N/A')}")
        lines.append("")
    
    # Schema checks section
    lines.append("---")
    lines.append("")
    lines.append("## Schema Checks")
    lines.append("")
    
    for r in results:
        lines.append(f"### Week {r.end_day}")
        lines.append("")
        lines.append(f"**Top-level columns ({r.info.get('column_count', 'N/A')}):**")
        columns = r.info.get("columns", [])
        if columns:
            lines.append("```")
            for col in columns:
                lines.append(f"  {col}")
            lines.append("```")
        lines.append("")
        
        # Nested fields
        meta_fields = r.info.get("meta_fields", [])
        if meta_fields:
            lines.append(f"**meta sub-fields ({len(meta_fields)}):** {', '.join(meta_fields[:10])}" + ("..." if len(meta_fields) > 10 else ""))
        
        spot_fields = r.info.get("spot_raw_fields", [])
        if spot_fields:
            lines.append(f"**spot_raw sub-fields ({len(spot_fields)}):** {', '.join(spot_fields[:10])}" + ("..." if len(spot_fields) > 10 else ""))
        
        # NOTE: twitter_sentiment_windows excluded from Tier 2 (full data in Tier 3)
        
        lines.append("")
    
    # Quality stats section
    lines.append("---")
    lines.append("")
    lines.append("## Quality Stats")
    lines.append("")
    
    for r in results:
        lines.append(f"### Week {r.end_day}")
        lines.append("")
        lines.append(f"- **Distinct symbols:** {r.info.get('distinct_symbols', 'N/A')}")
        
        duration_stats = r.info.get("duration_stats", {})
        if duration_stats:
            lines.append(
                f"- **duration_sec:** min={duration_stats.get('min', 'N/A'):.0f}, "
                f"median={duration_stats.get('median', 'N/A'):.0f}, "
                f"p95={duration_stats.get('p95', 'N/A'):.0f}, "
                f"max={duration_stats.get('max', 'N/A'):.0f} "
                f"(sampled {duration_stats.get('sample_count', 0)} rows)"
            )
        
        null_ratios = r.info.get("null_ratios", {})
        if null_ratios:
            lines.append("- **Null ratios:**")
            for col, stats in null_ratios.items():
                pct = stats['null_ratio'] * 100
                lines.append(f"  - {col}: {pct:.2f}% ({stats['null_count']} nulls)")
        
        lines.append(f"- **snapshot_ts type:** {r.info.get('snapshot_ts_type', 'N/A')}")
        lines.append("")
    
    # Warnings section
    all_warnings = []
    for r in results:
        for w in r.warnings:
            all_warnings.append(f"[{r.end_day}] {w}")
    
    if all_warnings:
        lines.append("---")
        lines.append("")
        lines.append("## Warnings")
        lines.append("")
        for w in all_warnings:
            lines.append(f"- {w}")
        lines.append("")
    
    # Errors section
    all_errors = []
    for r in results:
        for e in r.errors:
            all_errors.append(f"[{r.end_day}] {e}")
    
    if all_errors:
        lines.append("---")
        lines.append("")
        lines.append("## Errors")
        lines.append("")
        for e in all_errors:
            lines.append(f"- {e}")
        lines.append("")
    
    # Write report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        f.write("\n".join(lines))
    
    return all_pass


# ==============================================================================
# Main Verification
# ==============================================================================

def check_sidecar(result: VerificationResult, sidecar_path: Optional[Path]):
    """Check F: Sidecar file (sentiment_counts.parquet) presence and integrity."""
    manifest = result.info.get("manifest", {})
    files_block = manifest.get("files", {})
    sidecar_manifest = files_block.get("sidecar", {})
    
    # Check if manifest says sidecar should exist
    expected_filename = sidecar_manifest.get("filename")
    if expected_filename is None:
        # Sidecar was skipped during build
        result.warnings.append("Sidecar was skipped during build (--skip-sidecar flag used)")
        result.info["sidecar_status"] = "skipped"
        return
    
    if sidecar_path is None or not sidecar_path.exists():
        result.errors.append("Sidecar file missing but expected per manifest")
        result.info["sidecar_status"] = "missing"
        return
    
    # Read sidecar and validate schema
    try:
        sidecar_table = pq.read_table(sidecar_path)
    except Exception as e:
        result.errors.append(f"Failed to read sidecar file: {e}")
        result.info["sidecar_status"] = "unreadable"
        return
    
    sidecar_cols = set(sidecar_table.column_names)
    expected_cols = {"symbol", "snapshot_ts", "day", "cycle", "count_type", "key", "value"}
    
    missing_cols = expected_cols - sidecar_cols
    if missing_cols:
        result.errors.append(f"Sidecar missing required columns: {missing_cols}")
    
    # Check row count matches manifest
    manifest_row_count = sidecar_manifest.get("row_count")
    actual_row_count = sidecar_table.num_rows
    
    if manifest_row_count is not None and actual_row_count != manifest_row_count:
        result.errors.append(f"Sidecar row count mismatch: manifest={manifest_row_count}, actual={actual_row_count}")
    
    # Check file size
    actual_size = sidecar_path.stat().st_size
    manifest_size = sidecar_manifest.get("size_bytes")
    if manifest_size is not None and actual_size != manifest_size:
        result.warnings.append(f"Sidecar size mismatch: manifest={manifest_size}, actual={actual_size}")
    
    # Check SHA256 if present
    manifest_sha = sidecar_manifest.get("sha256")
    if manifest_sha:
        actual_sha = compute_sha256(sidecar_path)
        if actual_sha != manifest_sha:
            result.errors.append(f"Sidecar SHA256 mismatch: manifest={manifest_sha[:16]}..., actual={actual_sha[:16]}...")
    
    # Validate count_type values
    if "count_type" in sidecar_cols:
        count_types = sidecar_table.column("count_type").unique().to_pylist()
        expected_types = {"tag_counts", "cashtag_counts", "mention_counts", "url_domain_counts"}
        unexpected = set(count_types) - expected_types
        if unexpected:
            result.warnings.append(f"Sidecar contains unexpected count_types: {unexpected}")
    
    # Validate cycle values
    if "cycle" in sidecar_cols:
        cycles = sidecar_table.column("cycle").unique().to_pylist()
        expected_cycles = {"last_cycle", "last_2_cycles"}
        unexpected = set(cycles) - expected_cycles
        if unexpected:
            result.warnings.append(f"Sidecar contains unexpected cycles: {unexpected}")
    
    result.info["sidecar_status"] = "ok"
    result.info["sidecar_row_count"] = actual_row_count
    result.info["sidecar_size_bytes"] = actual_size
    result.info["sidecar_size_mb"] = round(actual_size / (1024 * 1024), 2)
    result.info["sidecar_count_types"] = count_types if "count_type" in sidecar_cols else []
    result.info["sidecar_cycles"] = cycles if "cycle" in sidecar_cols else []


def verify_week(
    end_day: str,
    parquet_path: Path,
    manifest_path: Path,
    sidecar_path: Optional[Path] = None,
    r2_size: Optional[int] = None,
) -> VerificationResult:
    """Run all verification checks for a single week."""
    result = VerificationResult(end_day=end_day)
    
    print(f"\n[Verifying week ending {end_day}]")
    
    # Check A: Presence + integrity
    print("  A. Checking presence and integrity...")
    check_presence_and_integrity(result, parquet_path, manifest_path, r2_size)
    if result.has_errors:
        return result
    
    # Check B: Window semantics
    print("  B. Checking window semantics...")
    check_window_semantics(result, end_day)
    
    # Check C: Schema / column policy
    print("  C. Checking schema and columns...")
    table = check_schema_columns(result, parquet_path)
    if table is None:
        return result
    
    # Check D: Data quality
    print("  D. Checking data quality...")
    check_data_quality(result, table)
    
    # Check E: Source coverage
    print("  E. Checking source coverage...")
    check_source_coverage(result)
    
    # Check F: Sidecar (sentiment_counts.parquet)
    print("  F. Checking sidecar file...")
    check_sidecar(result, sidecar_path)
    
    print(f"  -> Status: {result.status_symbol}")
    if result.errors:
        print(f"  -> Errors: {len(result.errors)}")
    if result.warnings:
        print(f"  -> Warnings: {len(result.warnings)}")
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Verify Tier 2 weekly parquet exports for correctness"
    )
    parser.add_argument(
        "--end-day",
        type=str,
        help="Week end date to verify (YYYY-MM-DD). If not specified, verifies ALL weeks in R2.",
    )
    parser.add_argument(
        "--local",
        type=str,
        help="Path to local tier2 weekly directory (contains dataset_entries_7d.parquet and manifest.json)",
    )
    parser.add_argument(
        "--r2",
        action="store_true",
        help="Download from R2 and verify (default if no --local specified)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help=f"Output directory for artifacts and reports (default: {VERIFY_CACHE_DIR})",
    )
    
    args = parser.parse_args()
    
    cache_dir = Path(args.output_dir) if args.output_dir else VERIFY_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate timestamped report path inside cache_dir
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = cache_dir / f"tier2_report_{timestamp}.md"
    
    print("=" * 60)
    print("TIER 2 WEEKLY PARQUET VERIFICATION")
    print("=" * 60)
    
    results = []
    
    if args.local:
        # Verify local files
        local_path = Path(args.local)
        
        # Infer end_day from path if not specified
        end_day = args.end_day
        if not end_day:
            # Try to get from folder name
            folder_name = local_path.name
            try:
                datetime.strptime(folder_name, "%Y-%m-%d")
                end_day = folder_name
            except ValueError:
                print("[ERROR] Cannot infer end_day from local path. Use --end-day.", file=sys.stderr)
                return 1
        
        print(f"Mode: Local verification")
        print(f"Path: {local_path}")
        print(f"Week end: {end_day}")
        
        parquet_path = local_path / "dataset_entries_7d.parquet"
        manifest_path = local_path / "manifest.json"
        sidecar_path = local_path / "sentiment_counts.parquet"
        
        # Check if sidecar exists
        if not sidecar_path.exists():
            sidecar_path = None
        
        result = verify_week(end_day, parquet_path, manifest_path, sidecar_path)
        results.append(result)
        
        # Write artifacts
        write_artifacts(result, cache_dir)
        
    else:
        # Download from R2
        print("\n[Connecting to R2...]")
        config = get_r2_config()
        print(f"  Bucket: {config.bucket}")
        
        # List all available weeks
        print("  Listing available weeks...")
        available_weeks = list_tier2_weeks(config)
        if not available_weeks:
            print("[ERROR] No Tier 2 weekly exports found in R2", file=sys.stderr)
            return 1
        
        if args.end_day:
            # Verify specific week
            weeks_to_verify = [args.end_day]
            print(f"  Verifying specific week: {args.end_day}")
        else:
            # Verify ALL weeks
            weeks_to_verify = available_weeks
            print(f"  Found {len(available_weeks)} weeks, verifying ALL")
        
        print(f"Mode: R2 verification")
        print(f"Weeks to verify: {weeks_to_verify}")
        
        for end_day in weeks_to_verify:
            print(f"\n[Downloading week {end_day} from R2...]")
            
            # Get size first
            r2_size = get_r2_object_size(config, end_day)
            
            # Download files (returns 3-tuple: parquet, manifest, sidecar)
            parquet_path, manifest_path, sidecar_path = download_from_r2(
                config, end_day, cache_dir
            )
            
            if parquet_path is None:
                result = VerificationResult(end_day=end_day)
                result.errors.append("Failed to download from R2")
                results.append(result)
                continue
            
            result = verify_week(end_day, parquet_path, manifest_path, sidecar_path, r2_size)
            results.append(result)
            
            # Write artifacts
            write_artifacts(result, cache_dir)
    
    # Generate report
    print("\n" + "=" * 60)
    print("GENERATING REPORT")
    print("=" * 60)
    
    all_pass = generate_report(results, report_path)
    
    print(f"\n[OK] Report written to: {report_path}")
    
    # Artifact locations
    print(f"[OK] Artifacts written to: {cache_dir}/")
    for r in results:
        print(f"     - {r.end_day}/manifest.json")
        print(f"     - {r.end_day}/schema.txt")
        print(f"     - {r.end_day}/stats.json")
    
    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    for r in results:
        print(f"  {r.end_day}: {r.status_symbol}")
        if r.errors:
            for err in r.errors[:3]:
                print(f"    [ERROR] {err}")
        if r.warnings:
            for warn in r.warnings[:3]:
                print(f"    [WARN] {warn}")
    
    print()
    if all_pass:
        print("[PASS] All critical checks passed.")
    else:
        print("[FAIL] Verification failed. See report for details.")
    
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
