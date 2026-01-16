#!/usr/bin/env python3
"""
Tier 3 Parquet Verification Script

Validates Tier 3 daily parquet exports for correctness and completeness.
Downloads from R2 (or uses local files) and runs comprehensive checks.

Usage:
    # Default: verify ALL days in R2
    python3 scripts/verify_tier3_parquet.py

    # Verify specific dates
    python3 scripts/verify_tier3_parquet.py --date 2026-01-13 --date 2026-01-14

    # Verify from local files
    python3 scripts/verify_tier3_parquet.py --local output/tier3_daily/2026-01-13

Outputs:
    Reports are written to output/verify_tier3/report_YYYYMMDD_HHMMSS.md
    Per-day artifacts are written to output/verify_tier3/{date}/
"""

import argparse
import hashlib
import json
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
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

VERIFY_CACHE_DIR = Path("./output/verify_tier3")

# Expected top-level columns based on v7 schema
REQUIRED_COLUMNS = [
    "symbol",
    "meta",
    "flags",
    "derived",
]

# Columns that should exist (check at least one)
SPOT_COLUMNS = ["spot_raw", "spot_prices"]
TWITTER_COLUMNS = ["twitter_sentiment_windows", "twitter_sentiment_meta"]
OPTIONAL_COLUMNS = ["scores", "futures_raw", "diag"]

# Columns that are intentionally dropped in Tier3 export (always empty in v7)
DROPPED_COLUMNS = ["norm", "labels"]

# Seed for reproducible random sampling
RANDOM_SEED = 20260115

# Expected duration range (seconds) - ~100-150 min window
MIN_DURATION_SEC = 6000
MAX_DURATION_SEC = 9000


# ==============================================================================
# Data Classes
# ==============================================================================

@dataclass
class VerificationResult:
    """Results from verifying a single date's export."""
    date: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: dict = field(default_factory=dict)
    
    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0
    
    @property
    def status(self) -> str:
        if self.errors:
            return "❌ FAIL"
        elif self.warnings:
            return "⚠️ WARN"
        return "✅ PASS"


# ==============================================================================
# R2 Download
# ==============================================================================

def get_s3_client(config: R2Config):
    """Create boto3 S3 client for R2."""
    return boto3.client(
        "s3",
        endpoint_url=config.endpoint,
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
    )


def download_from_r2(
    config: R2Config,
    date_str: str,
    cache_dir: Path,
) -> tuple[Optional[Path], Optional[Path]]:
    """
    Download parquet and manifest from R2 for a given date.
    
    Returns:
        Tuple of (parquet_path, manifest_path), or (None, None) if not found.
    """
    s3 = get_s3_client(config)
    
    prefix = f"tier3/daily/{date_str}/"
    parquet_key = f"{prefix}data.parquet"
    manifest_key = f"{prefix}manifest.json"
    
    # Create cache directory
    date_cache = cache_dir / date_str
    date_cache.mkdir(parents=True, exist_ok=True)
    
    parquet_path = date_cache / "data.parquet"
    manifest_path = date_cache / "manifest.json"
    
    try:
        # Check if objects exist first
        s3.head_object(Bucket=config.bucket, Key=parquet_key)
        s3.head_object(Bucket=config.bucket, Key=manifest_key)
    except Exception as e:
        print(f"[ERROR] Objects not found in R2 for {date_str}: {e}", file=sys.stderr)
        return None, None
    
    # Download parquet
    print(f"  Downloading {parquet_key}...")
    s3.download_file(config.bucket, parquet_key, str(parquet_path))
    
    # Download manifest
    print(f"  Downloading {manifest_key}...")
    s3.download_file(config.bucket, manifest_key, str(manifest_path))
    
    return parquet_path, manifest_path


def get_r2_object_sizes(config: R2Config, date_str: str) -> dict[str, int]:
    """Get file sizes from R2 without downloading."""
    s3 = get_s3_client(config)
    prefix = f"tier3/daily/{date_str}/"
    
    sizes = {}
    for key_suffix in ["data.parquet", "manifest.json"]:
        key = f"{prefix}{key_suffix}"
        try:
            response = s3.head_object(Bucket=config.bucket, Key=key)
            sizes[key_suffix] = response["ContentLength"]
        except Exception:
            sizes[key_suffix] = 0
    
    return sizes


def list_tier3_days(config: R2Config) -> list[str]:
    """List all Tier 3 daily dates available in R2."""
    s3 = get_s3_client(config)
    
    response = s3.list_objects_v2(
        Bucket=config.bucket,
        Prefix="tier3/daily/",
        Delimiter="/",
    )
    
    days = []
    for prefix_obj in response.get("CommonPrefixes", []):
        # tier3/daily/2026-01-13/
        prefix = prefix_obj.get("Prefix", "")
        parts = prefix.rstrip("/").split("/")
        if len(parts) >= 3:
            date_str = parts[2]
            # Validate date format
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
                days.append(date_str)
            except ValueError:
                pass
    
    return sorted(days)


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


def check_presence_and_size(
    result: VerificationResult,
    parquet_path: Optional[Path],
    manifest_path: Optional[Path],
    r2_sizes: Optional[dict[str, int]] = None,
):
    """Check 1: Presence + size sanity."""
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
    
    if r2_sizes:
        result.info["r2_parquet_size"] = r2_sizes.get("data.parquet", 0)
        result.info["r2_manifest_size"] = r2_sizes.get("manifest.json", 0)
    
    # Sanity checks
    if parquet_size < 1_000_000:  # < 1 MB
        result.errors.append(f"Parquet file too small: {parquet_size} bytes (expected > 1 MB)")
    
    if manifest_size < 50:
        result.errors.append(f"Manifest file too small: {manifest_size} bytes (expected > 50 bytes)")


def check_manifest_correctness(
    result: VerificationResult,
    parquet_path: Path,
    manifest_path: Path,
):
    """Check 2: Manifest correctness and SHA256 verification."""
    try:
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
    except json.JSONDecodeError as e:
        result.errors.append(f"Manifest is not valid JSON: {e}")
        return
    
    result.info["manifest"] = manifest
    
    # Required manifest fields
    required_fields = ["date_utc", "created_ts_utc", "row_count"]
    sha_field_names = ["sha256", "parquet_sha256"]  # Accept either
    optional_fields = ["min_added_ts", "max_added_ts", "schema_versions", "file_size_bytes"]
    
    for field_name in required_fields:
        # Handle alternate field names
        actual_name = field_name
        if field_name == "date_utc" and "date" in manifest:
            actual_name = "date"
        
        if actual_name not in manifest and field_name not in manifest:
            result.errors.append(f"Manifest missing required field: {field_name}")
    
    # Check SHA field (accept multiple names)
    sha_field = None
    for name in sha_field_names:
        if name in manifest:
            sha_field = name
            break
    
    if sha_field is None:
        result.errors.append(f"Manifest missing SHA256 field (expected one of: {sha_field_names})")
    
    # Check timestamp fields (may have alternate names)
    if "min_added_ts" not in manifest and "min_timestamp" not in manifest:
        result.warnings.append("Manifest missing min_added_ts/min_timestamp")
    if "max_added_ts" not in manifest and "max_timestamp" not in manifest:
        result.warnings.append("Manifest missing max_added_ts/max_timestamp")
    
    # Verify SHA256
    if sha_field:
        expected_sha = manifest[sha_field]
        actual_sha = compute_sha256(parquet_path)
        
        result.info["expected_sha256"] = expected_sha
        result.info["actual_sha256"] = actual_sha
        result.info["sha256_match"] = expected_sha == actual_sha
        
        if expected_sha != actual_sha:
            result.errors.append(f"SHA256 mismatch! Expected: {expected_sha[:16]}... Got: {actual_sha[:16]}...")
    else:
        result.warnings.append("Manifest does not contain sha256 field")
    
    # Check hours completeness (partition semantics)
    hours_expected = manifest.get("hours_expected")
    hours_found = manifest.get("hours_found")
    partition_basis = manifest.get("partition_basis")
    is_partial = manifest.get("is_partial", False)
    missing_hours = manifest.get("missing_hours", [])
    coverage_ratio = manifest.get("coverage_ratio")
    rows_by_hour = manifest.get("rows_by_hour", {})
    min_hours_threshold = manifest.get("min_hours_threshold", 20)
    
    if hours_expected is not None and hours_found is not None:
        result.info["hours_expected"] = hours_expected
        result.info["hours_found"] = hours_found
        result.info["hours_complete"] = hours_found == hours_expected
        result.info["is_partial"] = is_partial
        result.info["missing_hours"] = missing_hours
        result.info["coverage_ratio"] = coverage_ratio
        result.info["min_hours_threshold"] = min_hours_threshold
        result.info["rows_by_hour"] = rows_by_hour
        
        # Check if coverage meets minimum threshold
        if hours_found < min_hours_threshold:
            result.errors.append(
                f"Insufficient coverage: {hours_found}/{min_hours_threshold} minimum hours"
            )
        elif is_partial:
            # Partial but meets threshold - WARN, not error
            result.warnings.append(
                f"Partial day: {hours_found}/{hours_expected} hours (missing: {missing_hours})"
            )
    
    if partition_basis:
        result.info["partition_basis"] = partition_basis


def check_parquet_readability(
    result: VerificationResult,
    parquet_path: Path,
) -> Optional[pa.Table]:
    """Check 3: Parquet readability + schema overview."""
    try:
        table = pq.read_table(parquet_path)
    except Exception as e:
        result.errors.append(f"Failed to read parquet file: {e}")
        return None
    
    result.info["row_count"] = table.num_rows
    result.info["column_count"] = table.num_columns
    result.info["columns"] = table.column_names
    
    # Summarize schema (top-level only to avoid huge output)
    schema_summary = []
    for field in table.schema:
        type_str = str(field.type)
        # Truncate long nested type descriptions
        if len(type_str) > 80:
            type_str = type_str[:77] + "..."
        schema_summary.append(f"  {field.name}: {type_str}")
    
    result.info["schema_summary"] = schema_summary
    
    # Verify row count matches manifest
    manifest = result.info.get("manifest", {})
    manifest_row_count = manifest.get("row_count")
    if manifest_row_count is not None:
        if table.num_rows != manifest_row_count:
            result.errors.append(
                f"Row count mismatch: parquet has {table.num_rows}, manifest says {manifest_row_count}"
            )
        else:
            result.info["row_count_match"] = True
    
    return table


def check_required_columns(
    result: VerificationResult,
    table: pa.Table,
):
    """Check 4: Required top-level fields presence."""
    columns = set(table.column_names)
    
    # Check required columns
    for col in REQUIRED_COLUMNS:
        if col not in columns:
            result.errors.append(f"Missing required column: {col}")
    
    # Check spot columns (at least one)
    has_spot = any(col in columns for col in SPOT_COLUMNS)
    result.info["spot_columns_present"] = [c for c in SPOT_COLUMNS if c in columns]
    if not has_spot:
        result.errors.append(f"No spot data column found (expected one of: {SPOT_COLUMNS})")
    
    # Check twitter columns (at least one)
    has_twitter = any(col in columns for col in TWITTER_COLUMNS)
    result.info["twitter_columns_present"] = [c for c in TWITTER_COLUMNS if c in columns]
    if not has_twitter:
        result.errors.append(f"No twitter column found (expected one of: {TWITTER_COLUMNS})")
    
    # Check optional columns (just report)
    result.info["optional_columns_present"] = [c for c in OPTIONAL_COLUMNS if c in columns]
    result.info["all_columns"] = list(columns)
    
    # Verify dropped columns are absent (norm, labels should NOT be present)
    dropped_found = [c for c in DROPPED_COLUMNS if c in columns]
    result.info["dropped_columns_absent"] = len(dropped_found) == 0
    if dropped_found:
        result.warnings.append(f"Expected-dropped columns still present: {dropped_found}")
    else:
        result.info["confirmed_dropped"] = DROPPED_COLUMNS


def check_row_content_sanity(
    result: VerificationResult,
    table: pa.Table,
    date_str: str,
):
    """Check 5: Row-level spot checks (content sanity)."""
    # Use seeded RNG for reproducibility
    rng = random.Random(RANDOM_SEED + hash(date_str))
    
    num_rows = table.num_rows
    sample_size = min(20, num_rows)
    sample_indices = rng.sample(range(num_rows), sample_size)
    
    result.info["sampled_row_count"] = sample_size
    result.info["sampled_indices"] = sorted(sample_indices)
    
    # Work with PyArrow directly (no pandas dependency)
    issues = []
    duration_values = []
    spot_found_count = 0
    
    # Get column indices
    col_names = table.column_names
    symbol_idx = col_names.index("symbol") if "symbol" in col_names else None
    meta_idx = col_names.index("meta") if "meta" in col_names else None
    spot_raw_idx = col_names.index("spot_raw") if "spot_raw" in col_names else None
    spot_prices_idx = col_names.index("spot_prices") if "spot_prices" in col_names else None
    derived_idx = col_names.index("derived") if "derived" in col_names else None
    
    for idx in sample_indices:
        row_issues = []
        
        # Check symbol
        if symbol_idx is not None:
            symbol_val = table.column(symbol_idx)[idx].as_py()
            if symbol_val is None or (isinstance(symbol_val, str) and len(symbol_val) == 0):
                row_issues.append(f"Row {idx}: symbol is empty or null")
        
        # Check meta.added_ts (just verify it exists and is parseable, not date range)
        if meta_idx is not None:
            meta = table.column(meta_idx)[idx].as_py()
            if meta is None:
                row_issues.append(f"Row {idx}: meta is null")
            elif isinstance(meta, dict):
                added_ts = meta.get("added_ts")
                if added_ts is None:
                    row_issues.append(f"Row {idx}: meta.added_ts is null")
                else:
                    # Just verify it's parseable (not checking date range since partition
                    # is by archive folder day, not meta.added_ts)
                    if isinstance(added_ts, str):
                        try:
                            datetime.fromisoformat(added_ts.replace("Z", "+00:00"))
                        except ValueError:
                            try:
                                float(added_ts)
                            except ValueError:
                                row_issues.append(f"Row {idx}: meta.added_ts unparseable: {added_ts}")
                
                # Check duration_sec
                duration = meta.get("duration_sec")
                if duration is not None:
                    duration_values.append(duration)
                    if duration < MIN_DURATION_SEC or duration > MAX_DURATION_SEC:
                        row_issues.append(
                            f"Row {idx}: meta.duration_sec ({duration}) outside expected range "
                            f"({MIN_DURATION_SEC}-{MAX_DURATION_SEC})"
                        )
        
        # Check spot data presence
        has_spot = False
        if spot_raw_idx is not None:
            spot_raw = table.column(spot_raw_idx)[idx].as_py()
            if spot_raw is not None and spot_raw:
                has_spot = True
        if not has_spot and spot_prices_idx is not None:
            spot_prices = table.column(spot_prices_idx)[idx].as_py()
            if spot_prices is not None and spot_prices:
                has_spot = True
        if has_spot:
            spot_found_count += 1
        
        # Check derived.spread_bps
        if derived_idx is not None:
            derived = table.column(derived_idx)[idx].as_py()
            if derived is not None and isinstance(derived, dict):
                spread_bps = derived.get("spread_bps")
                if spread_bps is not None and spread_bps < 0:
                    row_issues.append(f"Row {idx}: derived.spread_bps is negative ({spread_bps})")
        
        issues.extend(row_issues)
    
    result.info["spot_found_in_sample"] = spot_found_count
    result.info["spot_sample_ratio"] = spot_found_count / sample_size if sample_size > 0 else 0
    
    if duration_values:
        result.info["duration_min"] = min(duration_values)
        result.info["duration_max"] = max(duration_values)
        result.info["duration_avg"] = sum(duration_values) / len(duration_values)
    
    # Only report first 5 issues to avoid spam
    if issues:
        for issue in issues[:5]:
            result.warnings.append(issue)
        if len(issues) > 5:
            result.warnings.append(f"... and {len(issues) - 5} more row-level issues")


def check_futures_sanity(
    result: VerificationResult,
    table: pa.Table,
):
    """Check 6: Futures block sanity."""
    columns = set(table.column_names)
    
    # Check if futures column exists
    if "futures_raw" not in columns:
        result.info["futures_column_exists"] = False
        result.warnings.append("futures_raw column not present in schema")
        return
    
    result.info["futures_column_exists"] = True
    
    # Count non-null futures rows using PyArrow directly
    futures_col = table.column("futures_raw")
    total_rows = table.num_rows
    
    non_null_count = 0
    has_content_count = 0
    
    for i in range(total_rows):
        val = futures_col[i].as_py()
        if val is not None:
            non_null_count += 1
            if isinstance(val, dict) and len(val) > 0:
                has_content_count += 1
            elif not isinstance(val, dict):
                has_content_count += 1
    
    result.info["futures_non_null_count"] = non_null_count
    result.info["futures_has_content_count"] = has_content_count
    result.info["futures_total_rows"] = total_rows
    result.info["futures_present_pct"] = round(100 * has_content_count / total_rows, 1) if total_rows > 0 else 0
    
    if has_content_count == 0:
        result.warnings.append(
            f"futures_raw has 0% rows with content ({has_content_count}/{total_rows})"
        )
    elif has_content_count < total_rows * 0.1:
        result.warnings.append(
            f"futures_raw has low presence: {result.info['futures_present_pct']}% "
            f"({has_content_count}/{total_rows})"
        )


def check_null_ratios(
    result: VerificationResult,
    table: pa.Table,
):
    """Check 7: Null / empty struct normalization sanity."""
    num_rows = table.num_rows
    
    null_ratios = []
    for col_name in table.column_names:
        col = table.column(col_name)
        null_count = col.null_count
        null_ratio = null_count / num_rows if num_rows > 0 else 0
        null_ratios.append((col_name, null_ratio, null_count))
    
    # Sort by null ratio descending
    null_ratios.sort(key=lambda x: x[1], reverse=True)
    
    # Report top 10
    result.info["top_null_columns"] = [
        {"column": col, "null_ratio": round(ratio, 3), "null_count": count}
        for col, ratio, count in null_ratios[:10]
    ]
    
    # Check if meta is ever null (ERROR)
    meta_nulls = 0
    if "meta" in table.column_names:
        meta_nulls = table.column("meta").null_count
    
    if meta_nulls > 0:
        result.errors.append(f"meta column has {meta_nulls} null values (should be 0)")
    
    # Check for columns that are 100% null (suspicious)
    fully_null_cols = [col for col, ratio, _ in null_ratios if ratio >= 1.0]
    if fully_null_cols:
        result.warnings.append(f"Columns that are 100% null: {fully_null_cols}")


# ==============================================================================
# Report Generation
# ==============================================================================

def generate_report(results: list[VerificationResult], report_path: Path):
    """Generate markdown verification report."""
    lines = [
        "# Tier 3 Parquet Verification Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Summary",
        "",
        "| Date | Status | Rows | Size (MB) | SHA Match | Hours | Coverage | Futures % |",
        "|------|--------|------|-----------|-----------|-------|----------|-----------|",
    ]
    
    for r in results:
        info = r.info
        sha_match = "✅" if info.get("sha256_match") else "❌"
        
        # Format hours coverage
        hours_found = info.get("hours_found", "N/A")
        hours_expected = info.get("hours_expected", 24)
        is_partial = info.get("is_partial", False)
        hours_str = f"{hours_found}/{hours_expected}"
        if is_partial:
            hours_str += " ⚠️"
        
        coverage_ratio = info.get("coverage_ratio")
        if coverage_ratio is not None:
            coverage_str = f"{coverage_ratio*100:.0f}%"
        else:
            coverage_str = "N/A"
        
        futures_pct = info.get("futures_present_pct", "N/A")
        if isinstance(futures_pct, (int, float)):
            futures_pct = f"{futures_pct}%"
        
        lines.append(
            f"| {r.date} | {r.status} | {info.get('row_count', 'N/A')} | "
            f"{info.get('parquet_size_mb', 'N/A')} | {sha_match} | {hours_str} | {coverage_str} | {futures_pct} |"
        )
    
    lines.append("")
    
    # Overall status
    all_pass = all(not r.has_errors for r in results)
    any_warnings = any(r.warnings for r in results)
    
    lines.append("## Overall Status")
    lines.append("")
    if all_pass and not any_warnings:
        lines.append("✅ **All checks passed. OK to proceed.**")
    elif all_pass:
        lines.append("⚠️ **All critical checks passed, but there are warnings. Review before proceeding.**")
    else:
        lines.append("❌ **Verification failed. Do NOT proceed until errors are resolved.**")
    lines.append("")
    
    # Details per date
    for r in results:
        lines.append(f"---")
        lines.append(f"")
        lines.append(f"## {r.date}")
        lines.append(f"")
        lines.append(f"**Status:** {r.status}")
        lines.append(f"")
        
        # Errors
        if r.errors:
            lines.append("### ❌ Errors")
            lines.append("")
            for err in r.errors:
                lines.append(f"- {err}")
            lines.append("")
        
        # Warnings
        if r.warnings:
            lines.append("### ⚠️ Warnings")
            lines.append("")
            for warn in r.warnings:
                lines.append(f"- {warn}")
            lines.append("")
        
        # Info
        lines.append("### Info")
        lines.append("")
        
        info = r.info
        
        # File info
        lines.append(f"- **Parquet size:** {info.get('parquet_size_mb', 'N/A')} MB")
        lines.append(f"- **Row count:** {info.get('row_count', 'N/A')}")
        lines.append(f"- **Column count:** {info.get('column_count', 'N/A')}")
        lines.append("")
        
        # Coverage info
        if info.get("hours_found") is not None:
            coverage_pct = (info.get('coverage_ratio', 0) or 0) * 100
            partial_marker = " (PARTIAL)" if info.get("is_partial") else ""
            lines.append(f"**Coverage:{partial_marker}**")
            lines.append(f"- Hours: {info.get('hours_found')}/{info.get('hours_expected', 24)}")
            lines.append(f"- Coverage ratio: {coverage_pct:.1f}%")
            lines.append(f"- Min hours threshold: {info.get('min_hours_threshold', 20)}")
            
            missing_hours = info.get("missing_hours", [])
            if missing_hours:
                lines.append(f"- Missing hours: {missing_hours}")
            
            rows_by_hour = info.get("rows_by_hour", {})
            if rows_by_hour:
                # Show a compact summary of rows by hour
                lines.append("")
                lines.append("**Rows by hour:**")
                lines.append("```")
                # Group into 4 rows of 6 hours each
                hours_sorted = sorted(rows_by_hour.keys())
                for start_idx in range(0, 24, 6):
                    row_parts = []
                    for h in hours_sorted[start_idx:start_idx+6]:
                        count = rows_by_hour.get(h, 0)
                        marker = " " if count > 0 else "X"
                        row_parts.append(f"{h}:{count:>4}{marker}")
                    lines.append("  " + " | ".join(row_parts))
                lines.append("```")
            lines.append("")
        
        # Columns
        if "columns" in info:
            lines.append("**Columns:**")
            lines.append("```")
            for col in info["columns"]:
                lines.append(f"  {col}")
            lines.append("```")
            lines.append("")
        
        # Schema summary
        if "schema_summary" in info:
            lines.append("**Schema (top-level):**")
            lines.append("```")
            for schema_line in info["schema_summary"]:
                lines.append(schema_line)
            lines.append("```")
            lines.append("")
        
        # Spot columns
        if "spot_columns_present" in info:
            lines.append(f"- **Spot columns found:** {info['spot_columns_present']}")
        if "twitter_columns_present" in info:
            lines.append(f"- **Twitter columns found:** {info['twitter_columns_present']}")
        if "optional_columns_present" in info:
            lines.append(f"- **Optional columns found:** {info['optional_columns_present']}")
        lines.append("")
        
        # Duration stats
        if "duration_avg" in info:
            lines.append(f"- **Duration (sec):** min={info.get('duration_min'):.0f}, max={info.get('duration_max'):.0f}, avg={info.get('duration_avg'):.0f}")
        
        # Futures
        if "futures_present_pct" in info:
            lines.append(f"- **Futures presence:** {info['futures_present_pct']}% ({info.get('futures_has_content_count', 0)}/{info.get('futures_total_rows', 0)})")
        
        # Top null columns
        if "top_null_columns" in info:
            lines.append("")
            lines.append("**Top columns by null ratio:**")
            lines.append("```")
            for item in info["top_null_columns"][:5]:
                lines.append(f"  {item['column']}: {item['null_ratio']*100:.1f}% null ({item['null_count']} rows)")
            lines.append("```")
        
        lines.append("")
    
    # Write report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        f.write("\n".join(lines))
    
    return all_pass


# ==============================================================================
# Main Verification
# ==============================================================================

def verify_date(
    date_str: str,
    parquet_path: Path,
    manifest_path: Path,
    r2_sizes: Optional[dict[str, int]] = None,
) -> VerificationResult:
    """Run all verification checks for a single date."""
    result = VerificationResult(date=date_str)
    
    print(f"\n[Verifying {date_str}]")
    
    # Check 1: Presence + size
    print("  1. Checking presence and size...")
    check_presence_and_size(result, parquet_path, manifest_path, r2_sizes)
    if result.has_errors:
        return result
    
    # Check 2: Manifest correctness
    print("  2. Checking manifest correctness...")
    check_manifest_correctness(result, parquet_path, manifest_path)
    
    # Check 3: Parquet readability
    print("  3. Checking parquet readability...")
    table = check_parquet_readability(result, parquet_path)
    if table is None:
        return result
    
    # Check 4: Required columns
    print("  4. Checking required columns...")
    check_required_columns(result, table)
    
    # Check 5: Row content sanity
    print("  5. Checking row content sanity (sampling 20 rows)...")
    check_row_content_sanity(result, table, date_str)
    
    # Check 6: Futures sanity
    print("  6. Checking futures block sanity...")
    check_futures_sanity(result, table)
    
    # Check 7: Null ratios
    print("  7. Checking null ratios...")
    check_null_ratios(result, table)
    
    print(f"  → Status: {result.status}")
    if result.errors:
        print(f"  → Errors: {len(result.errors)}")
    if result.warnings:
        print(f"  → Warnings: {len(result.warnings)}")
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Verify Tier 3 parquet exports for correctness"
    )
    parser.add_argument(
        "--date",
        action="append",
        dest="dates",
        help="Date to verify (YYYY-MM-DD). Can be specified multiple times. If not specified, verifies ALL days in R2.",
    )
    parser.add_argument(
        "--local",
        type=str,
        help="Path to local tier3 daily directory (contains data.parquet and manifest.json)",
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
    
    print("=" * 60)
    print("TIER 3 PARQUET VERIFICATION")
    print("=" * 60)
    
    results = []
    
    if args.local:
        # Verify local files
        local_path = Path(args.local)
        
        # Derive date from folder name if not specified
        if args.dates:
            date_str = args.dates[0]
            if len(args.dates) > 1:
                print("[WARN] --local specified with multiple dates; only first date will use local path")
        else:
            date_str = local_path.name  # Assume folder is named YYYY-MM-DD
        
        print(f"Mode: Local verification")
        print(f"Path: {local_path}")
        print(f"Date: {date_str}")
        
        parquet_path = local_path / "data.parquet"
        manifest_path = local_path / "manifest.json"
        
        result = verify_date(date_str, parquet_path, manifest_path)
        results.append(result)
    else:
        # Download from R2
        print("\n[Connecting to R2...]")
        config = get_r2_config()
        print(f"  Bucket: {config.bucket}")
        
        # List all available days
        print("  Listing available days...")
        available_days = list_tier3_days(config)
        if not available_days:
            print("[ERROR] No Tier 3 daily exports found in R2", file=sys.stderr)
            return 1
        
        if args.dates:
            # Verify specific dates
            dates_to_verify = args.dates
            print(f"  Verifying specific dates: {dates_to_verify}")
        else:
            # Verify ALL days
            dates_to_verify = available_days
            print(f"  Found {len(available_days)} days, verifying ALL")
        
        print(f"Dates to verify: {len(dates_to_verify)} day(s)")
        
        for date_str in dates_to_verify:
            print(f"\n[Downloading {date_str} from R2...]")
            
            # Get sizes first
            r2_sizes = get_r2_object_sizes(config, date_str)
            
            # Download files
            parquet_path, manifest_path = download_from_r2(
                config, date_str, cache_dir
            )
            
            if parquet_path is None:
                result = VerificationResult(date=date_str)
                result.errors.append("Failed to download from R2")
                results.append(result)
                continue
            
            result = verify_date(date_str, parquet_path, manifest_path, r2_sizes)
            results.append(result)
    
    # Generate report
    print("\n" + "=" * 60)
    print("GENERATING REPORT")
    print("=" * 60)
    
    all_pass = generate_report(results, report_path)
    
    print(f"\n[OK] Report written to: {report_path}")
    print(f"[OK] Artifacts written to: {cache_dir}/")
    
    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    for r in results:
        print(f"  {r.date}: {r.status}")
        if r.errors:
            for err in r.errors[:3]:
                print(f"    ❌ {err}")
        if r.warnings:
            for warn in r.warnings[:3]:
                print(f"    ⚠️ {warn}")
    
    print()
    if all_pass:
        print("✅ All critical checks passed.")
    else:
        print("❌ Verification failed. See report for details.")
    
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
