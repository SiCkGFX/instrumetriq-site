#!/usr/bin/env python3
"""
Tier 1 Weekly Parquet Verification Script

Validates Tier 1 weekly parquet exports for correctness and completeness.
Downloads from R2 (or uses local files) and runs comprehensive checks.

Tier 1 uses a flattened schema (22 fields) with aggregated sentiment.

Usage:
    # Default: verify ALL weeks in R2
    python3 scripts/verify_tier1_weekly.py

    # Verify specific week by end date
    python3 scripts/verify_tier1_weekly.py --end-day 2025-12-28

    # Verify from local files
    python3 scripts/verify_tier1_weekly.py --local output/tier1_weekly/2025-12-28

    # Verify from R2 explicitly
    python3 scripts/verify_tier1_weekly.py --r2 --end-day 2025-12-28

Outputs:
    Reports are written to output/verify_tier1/report_YYYYMMDD_HHMMSS.md
    Per-week artifacts are written to output/verify_tier1/{end-day}/
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

VERIFY_CACHE_DIR = Path("./output/verify_tier1")

# Tier 1 flattened schema (22 required fields)
TIER1_REQUIRED_COLUMNS = [
    # Identity + Timing (6)
    "symbol",
    "snapshot_ts",
    "meta_added_ts",
    "meta_expires_ts",
    "meta_duration_sec",
    "meta_archive_schema_version",
    # Spot (4)
    "spot_mid",
    "spot_spread_bps",
    "spot_range_pct_24h",
    "spot_ticker24_chg",
    # Derived (2)
    "derived_liq_global_pct",
    "derived_spread_bps",
    # Score (1)
    "score_final",
    # Sentiment (9)
    "sentiment_posts_total",
    "sentiment_posts_pos",
    "sentiment_posts_neu",
    "sentiment_posts_neg",
    "sentiment_mean_score",
    "sentiment_is_silent",
    "sentiment_recent_posts_count",
    "sentiment_has_recent_activity",
    "sentiment_hours_since_latest_tweet",
]

# Expected column types (loose matching)
COLUMN_TYPES = {
    "symbol": "string",
    "snapshot_ts": "string",
    "meta_added_ts": "string",
    "meta_expires_ts": "string",
    "meta_duration_sec": "double",
    "meta_archive_schema_version": "int64",
    "spot_mid": "double",
    "spot_spread_bps": "double",
    "spot_range_pct_24h": "double",
    "spot_ticker24_chg": "double",
    "derived_liq_global_pct": "double",
    "derived_spread_bps": "double",
    "score_final": "double",
    "sentiment_posts_total": "int64",
    "sentiment_posts_pos": "int64",
    "sentiment_posts_neu": "int64",
    "sentiment_posts_neg": "int64",
    "sentiment_mean_score": "double",
    "sentiment_is_silent": "bool",
    "sentiment_recent_posts_count": "int64",
    "sentiment_has_recent_activity": "bool",
    "sentiment_hours_since_latest_tweet": "double",
}

# Critical columns that MUST have < 99.5% nulls
CRITICAL_COLUMNS = [
    "symbol",
    "snapshot_ts",
    "meta_added_ts",
    "spot_mid",
    "score_final",
]

# Columns that should have < 95% nulls (WARN otherwise)
EXPECTED_COLUMNS = [
    "meta_duration_sec",
    "spot_spread_bps",
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


def list_tier1_weeks(config: R2Config) -> list[str]:
    """List all Tier 1 weekly end dates available in R2."""
    s3 = get_s3_client(config)
    
    response = s3.list_objects_v2(
        Bucket=config.bucket,
        Prefix="tier1/weekly/",
        Delimiter="/",
    )
    
    weeks = []
    for prefix_obj in response.get("CommonPrefixes", []):
        # tier1/weekly/2025-12-28/
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
) -> tuple[Optional[Path], Optional[Path]]:
    """
    Download parquet and manifest from R2 for a given week.
    
    Returns:
        Tuple of (parquet_path, manifest_path), or (None, None) if not found.
    """
    s3 = get_s3_client(config)
    
    prefix = f"tier1/weekly/{end_day}/"
    parquet_key = f"{prefix}dataset_entries_7d.parquet"
    manifest_key = f"{prefix}manifest.json"
    
    # Create cache directory
    week_cache = cache_dir / end_day
    week_cache.mkdir(parents=True, exist_ok=True)
    
    parquet_path = week_cache / "dataset_entries_7d.parquet"
    manifest_path = week_cache / "manifest.json"
    
    try:
        # Check if objects exist first
        s3.head_object(Bucket=config.bucket, Key=parquet_key)
        s3.head_object(Bucket=config.bucket, Key=manifest_key)
    except Exception as e:
        print(f"[ERROR] Objects not found in R2 for week {end_day}: {e}", file=sys.stderr)
        return None, None
    
    # Download parquet
    print(f"  Downloading {parquet_key}...")
    s3.download_file(config.bucket, parquet_key, str(parquet_path))
    
    # Download manifest
    print(f"  Downloading {manifest_key}...")
    s3.download_file(config.bucket, manifest_key, str(manifest_path))
    
    return parquet_path, manifest_path


def get_r2_object_size(config: R2Config, end_day: str) -> int:
    """Get parquet file size from R2 without downloading."""
    s3 = get_s3_client(config)
    key = f"tier1/weekly/{end_day}/dataset_entries_7d.parquet"
    
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
    """Check 1: Object presence + integrity."""
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
    
    # Verify SHA256 (support both field names)
    sha_field = None
    for name in ["parquet_sha256", "sha256"]:
        if name in manifest:
            sha_field = name
            break
    
    if sha_field:
        expected_sha = manifest[sha_field]
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
    
    # Compare file size to manifest
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
    """Check 2: Window semantics (Mon-Sun, 7 days)."""
    manifest = result.info.get("manifest", {})
    
    # Required top-level fields
    required_top = ["tier", "schema_version", "window", "build_ts_utc", "source_inputs", "row_count"]
    for field_name in required_top:
        if field_name not in manifest:
            result.errors.append(f"Manifest missing required field: {field_name}")
    
    # Check tier
    tier = manifest.get("tier")
    if tier != "tier1":
        result.errors.append(f"Manifest tier != 'tier1' (got: {tier})")
    
    # Check schema_version
    schema_version = manifest.get("schema_version")
    if schema_version != "v7":
        result.errors.append(f"Manifest schema_version != 'v7' (got: {schema_version})")
    
    # Check window structure
    window = manifest.get("window", {})
    
    # Support both old and new field names
    manifest_end_day = window.get("week_end_day") or window.get("end_day")
    manifest_start_day = window.get("week_start_day") or window.get("start_day")
    window_basis = window.get("window_basis", "end_day")
    
    if manifest_end_day != end_day:
        result.errors.append(f"Manifest end_day ({manifest_end_day}) != folder name ({end_day})")
    
    # Get days_expected if available
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
    
    # Verify end_day is a Sunday (WARN if not)
    try:
        end_date = datetime.strptime(end_day, "%Y-%m-%d").date()
        if end_date.weekday() != 6:  # Sunday = 6
            day_name = end_date.strftime("%A")
            result.warnings.append(f"end_day {end_day} is a {day_name}, not a Sunday")
    except ValueError:
        result.errors.append(f"Invalid end_day format: {end_day}")
    
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


def check_source_coverage(
    result: VerificationResult,
):
    """Check 3: Source coverage metadata."""
    manifest = result.info.get("manifest", {})
    source_coverage = manifest.get("source_coverage")
    
    if source_coverage is None:
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
    
    # Extract coverage info
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
    """Check 4: Parquet schema (22 flattened fields)."""
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
    for col in TIER1_REQUIRED_COLUMNS:
        if col not in columns:
            missing_required.append(col)
    
    if missing_required:
        result.errors.append(f"Missing required columns: {missing_required}")
    else:
        result.info["required_columns_ok"] = True
    
    # Check for unexpected columns (WARN only)
    expected_set = set(TIER1_REQUIRED_COLUMNS)
    unexpected = columns - expected_set
    if unexpected:
        result.warnings.append(f"Unexpected extra columns: {sorted(unexpected)}")
    
    # Write schema to file for artifacts
    schema_lines = []
    for fld in table.schema:
        type_str = str(fld.type)
        if len(type_str) > 100:
            type_str = type_str[:97] + "..."
        schema_lines.append(f"{fld.name}: {type_str}")
    result.info["schema_lines"] = schema_lines
    
    # Check column types (lightweight)
    type_mismatches = []
    for col_name, expected_type in COLUMN_TYPES.items():
        if col_name not in columns:
            continue
        actual_type = str(table.schema.field(col_name).type)
        
        # Loose type matching
        if expected_type == "string" and not ("string" in actual_type or "utf8" in actual_type):
            type_mismatches.append(f"{col_name}: expected string-like, got {actual_type}")
        elif expected_type == "double" and "double" not in actual_type and "float" not in actual_type:
            type_mismatches.append(f"{col_name}: expected double/float, got {actual_type}")
        elif expected_type == "int64" and "int" not in actual_type:
            type_mismatches.append(f"{col_name}: expected int-like, got {actual_type}")
        elif expected_type == "bool" and "bool" not in actual_type:
            # Allow int 0/1 as bool
            if "int" not in actual_type:
                type_mismatches.append(f"{col_name}: expected bool/int, got {actual_type}")
    
    if type_mismatches:
        for mismatch in type_mismatches:
            result.warnings.append(f"Type mismatch: {mismatch}")
    
    result.info["column_types"] = {col: str(table.schema.field(col).type) for col in table.column_names}
    
    return table


def check_data_quality(result: VerificationResult, table: pa.Table):
    """Check 5: Data quality stats."""
    manifest = result.info.get("manifest", {})
    num_rows = table.num_rows
    
    # Compare row count to manifest
    manifest_row_count = manifest.get("row_count")
    if manifest_row_count is not None:
        if num_rows != manifest_row_count:
            result.errors.append(
                f"Row count mismatch: parquet={num_rows}, manifest={manifest_row_count}"
            )
        else:
            result.info["row_count_match"] = True
    
    # Distinct symbols
    if "symbol" in table.column_names:
        symbol_col = table.column("symbol")
        try:
            symbols = symbol_col.unique()
            result.info["distinct_symbols"] = len(symbols)
            
            # Top 10 symbols by frequency
            symbol_dict = {}
            for i in range(min(10000, num_rows)):
                s = symbol_col[i].as_py()
                if s:
                    symbol_dict[s] = symbol_dict.get(s, 0) + 1
            top_symbols = sorted(symbol_dict.items(), key=lambda x: -x[1])[:10]
            result.info["top_symbols"] = top_symbols
        except Exception:
            result.info["distinct_symbols"] = "unknown"
    
    # Null ratios per column
    null_ratios = {}
    for col_name in table.column_names:
        col = table.column(col_name)
        null_count = col.null_count
        null_ratio = null_count / num_rows if num_rows > 0 else 0
        null_ratios[col_name] = {
            "null_count": null_count,
            "null_ratio": round(null_ratio, 4),
        }
        
        # FAIL if critical column > 99.5% null
        if col_name in CRITICAL_COLUMNS and null_ratio > 0.995:
            result.errors.append(
                f"Critical column '{col_name}' has {null_ratio*100:.2f}% nulls (>99.5%)"
            )
        # WARN if expected column > 95% null
        elif col_name in EXPECTED_COLUMNS and null_ratio > 0.95:
            result.warnings.append(
                f"Column '{col_name}' has {null_ratio*100:.2f}% nulls (>95%)"
            )
    
    result.info["null_ratios"] = null_ratios
    
    # Numeric stats for key columns
    numeric_stats = {}
    
    # spot_spread_bps
    if "spot_spread_bps" in table.column_names:
        col = table.column("spot_spread_bps")
        vals = [v.as_py() for v in col if v.as_py() is not None]
        if vals:
            vals_sorted = sorted(vals)
            numeric_stats["spot_spread_bps"] = {
                "min": vals_sorted[0],
                "max": vals_sorted[-1],
                "median": statistics.median(vals_sorted),
                "sample_count": len(vals),
            }
            # WARN if negative spread
            if vals_sorted[0] < 0:
                result.warnings.append(f"spot_spread_bps has negative values (min={vals_sorted[0]})")
    
    # meta_duration_sec
    if "meta_duration_sec" in table.column_names:
        col = table.column("meta_duration_sec")
        vals = [v.as_py() for v in col if v.as_py() is not None]
        if vals:
            vals_sorted = sorted(vals)
            numeric_stats["meta_duration_sec"] = {
                "min": vals_sorted[0],
                "max": vals_sorted[-1],
                "median": statistics.median(vals_sorted),
                "sample_count": len(vals),
            }
            # WARN if <= 0
            if vals_sorted[0] <= 0:
                result.warnings.append(f"meta_duration_sec has non-positive values (min={vals_sorted[0]})")
    
    # score_final
    if "score_final" in table.column_names:
        col = table.column("score_final")
        vals = [v.as_py() for v in col if v.as_py() is not None]
        if vals:
            vals_sorted = sorted(vals)
            numeric_stats["score_final"] = {
                "min": vals_sorted[0],
                "max": vals_sorted[-1],
                "mean": statistics.mean(vals),
                "sample_count": len(vals),
            }
    
    # sentiment_mean_score
    if "sentiment_mean_score" in table.column_names:
        col = table.column("sentiment_mean_score")
        vals = [v.as_py() for v in col if v.as_py() is not None]
        if vals:
            vals_sorted = sorted(vals)
            numeric_stats["sentiment_mean_score"] = {
                "min": vals_sorted[0],
                "max": vals_sorted[-1],
                "mean": statistics.mean(vals),
                "sample_count": len(vals),
            }
    
    # sentiment_posts_total
    if "sentiment_posts_total" in table.column_names:
        col = table.column("sentiment_posts_total")
        vals = [v.as_py() for v in col if v.as_py() is not None]
        if vals:
            vals_sorted = sorted(vals)
            numeric_stats["sentiment_posts_total"] = {
                "min": vals_sorted[0],
                "max": vals_sorted[-1],
                "sum": sum(vals),
                "sample_count": len(vals),
            }
            # FAIL if negative counts
            if vals_sorted[0] < 0:
                result.errors.append(f"sentiment_posts_total has negative values (min={vals_sorted[0]})")
    
    result.info["numeric_stats"] = numeric_stats
    
    # Sample row (safe fields only)
    if num_rows > 0:
        sample_row = {}
        safe_fields = ["symbol", "snapshot_ts", "score_final", "sentiment_posts_total", "sentiment_mean_score"]
        for col_name in safe_fields:
            if col_name in table.column_names:
                val = table.column(col_name)[0].as_py()
                sample_row[col_name] = val
        result.info["sample_row"] = sample_row


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
            f.write("Tier 1 Weekly Parquet Schema\n")
            f.write(f"Week ending: {end_day}\n")
            f.write("=" * 50 + "\n\n")
            for line in schema_lines:
                f.write(line + "\n")
    
    # stats.json
    stats = {
        "end_day": end_day,
        "status": result.status,
        "row_count": result.info.get("row_count"),
        "column_count": result.info.get("column_count"),
        "parquet_size_bytes": result.info.get("parquet_size_bytes"),
        "sha256_match": result.info.get("sha256_match"),
        "required_columns_ok": result.info.get("required_columns_ok"),
        "distinct_symbols": result.info.get("distinct_symbols"),
        "present_days_count": result.info.get("present_days_count"),
        "missing_days_count": result.info.get("missing_days_count"),
        "partial_days_count": result.info.get("partial_days_count"),
        "numeric_stats": result.info.get("numeric_stats"),
        "null_ratios": result.info.get("null_ratios"),
        "errors": result.errors,
        "warnings": result.warnings,
    }
    
    stats_path = week_dir / "stats.json"
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2, default=str)


# ==============================================================================
# Report Generation
# ==============================================================================

def generate_report(results: list[VerificationResult], report_path: Path):
    """Generate markdown verification report."""
    lines = [
        "# Tier 1 Weekly Parquet Verification Report",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "Tier 1 uses a flattened schema with 22 fields (identity, spot, derived, score, sentiment).",
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
        
        rows = info.get('row_count', 0)
        rows_str = f"{rows:,}" if rows else "N/A"
        
        lines.append(
            f"| {r.end_day} | {r.status_symbol} | {days_str} | {partial_str} | "
            f"{rows_str} | {info.get('parquet_size_mb', 'N/A')} | {sha_match} |"
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
    
    # Source Coverage section
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
    
    # Schema section
    lines.append("---")
    lines.append("")
    lines.append("## Schema Checks")
    lines.append("")
    
    for r in results:
        lines.append(f"### Week {r.end_day}")
        lines.append("")
        lines.append(f"**Columns:** {r.info.get('column_count', 'N/A')} (expected 22)")
        lines.append("")
        
        columns = r.info.get("columns", [])
        column_types = r.info.get("column_types", {})
        
        if columns:
            lines.append("| Column | Type |")
            lines.append("|--------|------|")
            for col in columns:
                ctype = column_types.get(col, "?")
                if len(ctype) > 40:
                    ctype = ctype[:37] + "..."
                lines.append(f"| {col} | {ctype} |")
        
        lines.append("")
    
    # Quality stats section
    lines.append("---")
    lines.append("")
    lines.append("## Data Quality")
    lines.append("")
    
    for r in results:
        lines.append(f"### Week {r.end_day}")
        lines.append("")
        lines.append(f"- **Distinct symbols:** {r.info.get('distinct_symbols', 'N/A')}")
        
        top_symbols = r.info.get("top_symbols", [])
        if top_symbols:
            top_str = ", ".join([f"{s[0]} ({s[1]})" for s in top_symbols[:5]])
            lines.append(f"- **Top symbols:** {top_str}")
        
        lines.append("")
        
        # Numeric stats
        numeric_stats = r.info.get("numeric_stats", {})
        if numeric_stats:
            lines.append("**Key field stats:**")
            lines.append("| Field | Min | Max | Mean/Median |")
            lines.append("|-------|-----|-----|-------------|")
            
            for field, stats in numeric_stats.items():
                min_val = stats.get("min", "N/A")
                max_val = stats.get("max", "N/A")
                if "mean" in stats:
                    mid_val = f"{stats['mean']:.3f}"
                elif "median" in stats:
                    mid_val = f"{stats['median']:.1f}"
                else:
                    mid_val = "N/A"
                
                # Format numbers
                if isinstance(min_val, float):
                    min_val = f"{min_val:.3f}"
                if isinstance(max_val, float):
                    max_val = f"{max_val:.3f}"
                
                lines.append(f"| {field} | {min_val} | {max_val} | {mid_val} |")
            
            lines.append("")
        
        # Null ratios (only notable ones)
        null_ratios = r.info.get("null_ratios", {})
        notable_nulls = {k: v for k, v in null_ratios.items() if v["null_ratio"] > 0.01}
        if notable_nulls:
            lines.append("**Notable null ratios (>1%):**")
            for col, stats in sorted(notable_nulls.items(), key=lambda x: -x[1]["null_ratio"]):
                pct = stats['null_ratio'] * 100
                lines.append(f"- {col}: {pct:.2f}%")
            lines.append("")
        
        # Sample row
        sample_row = r.info.get("sample_row")
        if sample_row:
            lines.append("**Sample row:**")
            lines.append("```json")
            lines.append(json.dumps(sample_row, indent=2, default=str))
            lines.append("```")
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

def verify_week(
    end_day: str,
    parquet_path: Path,
    manifest_path: Path,
    r2_size: Optional[int] = None,
) -> VerificationResult:
    """Run all verification checks for a single week."""
    result = VerificationResult(end_day=end_day)
    
    print(f"\n[Verifying week ending {end_day}]")
    
    # Check 1: Presence + integrity
    print("  1. Checking presence and integrity...")
    check_presence_and_integrity(result, parquet_path, manifest_path, r2_size)
    if result.has_errors:
        return result
    
    # Check 2: Window semantics
    print("  2. Checking window semantics...")
    check_window_semantics(result, end_day)
    
    # Check 3: Source coverage
    print("  3. Checking source coverage...")
    check_source_coverage(result)
    
    # Check 4: Schema / column policy
    print("  4. Checking schema (22 flattened fields)...")
    table = check_schema_columns(result, parquet_path)
    if table is None:
        return result
    
    # Check 5: Data quality
    print("  5. Checking data quality...")
    check_data_quality(result, table)
    
    print(f"  -> Status: {result.status_symbol}")
    if result.errors:
        print(f"  -> Errors: {len(result.errors)}")
    if result.warnings:
        print(f"  -> Warnings: {len(result.warnings)}")
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Verify Tier 1 weekly parquet exports for correctness"
    )
    parser.add_argument(
        "--end-day",
        type=str,
        help="Week end date to verify (YYYY-MM-DD). If not specified, verifies ALL weeks in R2.",
    )
    parser.add_argument(
        "--local",
        type=str,
        help="Path to local tier1 weekly directory (contains dataset_entries_7d.parquet and manifest.json)",
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
    report_path = cache_dir / f"report_{timestamp}.md"
    
    results = []
    
    if args.local:
        # Local mode
        local_path = Path(args.local)
        parquet_path = local_path / "dataset_entries_7d.parquet"
        manifest_path = local_path / "manifest.json"
        
        # Derive end_day from folder name or use provided
        if args.end_day:
            end_day = args.end_day
        else:
            end_day = local_path.name  # Assume folder is named YYYY-MM-DD
        
        print(f"[Mode] Verifying from local path: {local_path}")
        result = verify_week(end_day, parquet_path, manifest_path)
        results.append(result)
        
        # Write artifacts
        write_artifacts(result, cache_dir)
        
    else:
        # R2 mode (default)
        print("[Mode] Verifying from R2")
        config = get_r2_config()
        
        # List all available weeks
        available_weeks = list_tier1_weeks(config)
        if not available_weeks:
            print("[ERROR] No Tier 1 weeks found in R2", file=sys.stderr)
            sys.exit(1)
        
        if args.end_day:
            # Verify specific week
            weeks_to_verify = [args.end_day]
            print(f"[INFO] Verifying specific week: {args.end_day}")
        else:
            # Verify ALL weeks
            weeks_to_verify = available_weeks
            print(f"[INFO] Found {len(available_weeks)} weeks in R2, verifying ALL")
        
        for end_day in weeks_to_verify:
            r2_size = get_r2_object_size(config, end_day)
            parquet_path, manifest_path = download_from_r2(config, end_day, cache_dir)
            
            if parquet_path is None:
                result = VerificationResult(end_day=end_day)
                result.errors.append(f"Failed to download from R2")
                results.append(result)
                continue
            
            result = verify_week(end_day, parquet_path, manifest_path, r2_size)
            results.append(result)
            
            # Write artifacts
            write_artifacts(result, cache_dir)
    
    # Generate report
    print(f"\n[Generating report: {report_path}]")
    all_pass = generate_report(results, report_path)
    
    # Print summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    for r in results:
        print(f"  {r.end_day}: {r.status_symbol}")
        if r.errors:
            for e in r.errors[:3]:
                print(f"    ERROR: {e}")
        if r.warnings:
            for w in r.warnings[:3]:
                print(f"    WARN: {w}")
    print(f"\nReport written to: {report_path}")
    print(f"Artifacts written to: {cache_dir}/")
    print("=" * 60)
    
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
