#!/usr/bin/env python3
"""
Tier 2 Weekly Parquet Verification Script

Validates Tier 2 weekly parquet exports for correctness and completeness.
Downloads from R2 (or uses local files) and runs comprehensive checks.

Usage:
    # Default: verify most recent week in R2
    python3 scripts/verify_tier2_weekly.py

    # Verify specific week by end date
    python3 scripts/verify_tier2_weekly.py --end-day 2025-12-28

    # Verify from local files
    python3 scripts/verify_tier2_weekly.py --local output/tier2_weekly/2025-12-28

    # Verify from R2 explicitly
    python3 scripts/verify_tier2_weekly.py --r2 --end-day 2025-12-28
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

DEFAULT_REPORT_PATH = Path("./output/verify_tier2_report.md")
VERIFY_CACHE_DIR = Path("./output/verify_tier2")

# Tier 2 column policy (hardcoded from build_tier2_weekly.py)
TIER2_REQUIRED_COLUMNS = [
    "symbol",
    "snapshot_ts",
    "meta",
    "spot_raw",
    "derived",
    "scores",
    "twitter_sentiment_meta",
]

TIER2_EXCLUDED_COLUMNS = [
    "futures_raw",
    "spot_prices",
    "flags",
    "diag",
    "twitter_sentiment_windows",
    "norm",
    "labels",
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
) -> tuple[Optional[Path], Optional[Path]]:
    """
    Download parquet and manifest from R2 for a given week.
    
    Returns:
        Tuple of (parquet_path, manifest_path), or (None, None) if not found.
    """
    s3 = get_s3_client(config)
    
    prefix = f"tier2/weekly/{end_day}/"
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
    """Check B: Window semantics (must be strict)."""
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
    required_window = ["start_day", "end_day", "days_included"]
    for field_name in required_window:
        if field_name not in window:
            result.errors.append(f"Manifest window missing field: {field_name}")
    
    manifest_end_day = window.get("end_day")
    if manifest_end_day != end_day:
        result.errors.append(f"Manifest end_day ({manifest_end_day}) != folder name ({end_day})")
    
    days_included = window.get("days_included", [])
    result.info["days_included"] = days_included
    
    if len(days_included) != 7:
        result.errors.append(f"Manifest days_included should have 7 items, got {len(days_included)}")
    
    # Verify days are consecutive
    if len(days_included) == 7:
        try:
            dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in days_included]
            dates_sorted = sorted(dates)
            
            # Check consecutive
            for i in range(1, len(dates_sorted)):
                expected = dates_sorted[i-1] + timedelta(days=1)
                if dates_sorted[i] != expected:
                    result.errors.append(
                        f"Manifest days_included not consecutive: gap between {dates_sorted[i-1]} and {dates_sorted[i]}"
                    )
                    break
            
            # Check end_day matches last day
            if dates_sorted[-1].strftime("%Y-%m-%d") != end_day:
                result.errors.append(
                    f"Last day in days_included ({dates_sorted[-1]}) != end_day ({end_day})"
                )
            
            result.info["window_start"] = dates_sorted[0].strftime("%Y-%m-%d")
            result.info["window_end"] = dates_sorted[-1].strftime("%Y-%m-%d")
        except ValueError as e:
            result.errors.append(f"Invalid date format in days_included: {e}")
    
    # Check source_inputs
    source_inputs = manifest.get("source_inputs", [])
    result.info["source_inputs_count"] = len(source_inputs)
    
    if len(source_inputs) != 7:
        result.errors.append(f"Manifest source_inputs should have 7 items, got {len(source_inputs)}")
    
    # Verify source_inputs match expected Tier3 paths
    if len(days_included) == 7 and len(source_inputs) == 7:
        expected_inputs = [f"tier3/daily/{d}/data.parquet" for d in sorted(days_included)]
        actual_sorted = sorted(source_inputs)
        
        if expected_inputs != actual_sorted:
            result.warnings.append(
                f"source_inputs don't match expected Tier3 paths for days_included"
            )
        else:
            result.info["source_inputs_valid"] = True


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


def check_data_quality(result: VerificationResult, table: pa.Table):
    """Check D: Data quality summaries."""
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
    struct_cols = ["meta", "spot_raw", "derived", "scores", "twitter_sentiment_meta"]
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
        "| Week End | Status | Rows | Size (MB) | SHA Match | Required Cols | Excluded Cols |",
        "|----------|--------|------|-----------|-----------|---------------|---------------|",
    ]
    
    for r in results:
        info = r.info
        sha_match = "OK" if info.get("sha256_match") else "FAIL"
        req_ok = "OK" if info.get("required_columns_ok") else "FAIL"
        excl_ok = "OK" if info.get("excluded_columns_ok") else "FAIL"
        
        lines.append(
            f"| {r.end_day} | {r.status_symbol} | {info.get('row_count', 'N/A'):,} | "
            f"{info.get('parquet_size_mb', 'N/A')} | {sha_match} | {req_ok} | {excl_ok} |"
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
        lines.append(f"- **window.start_day:** {window.get('start_day', 'N/A')}")
        lines.append(f"- **window.end_day:** {window.get('end_day', 'N/A')}")
        lines.append(f"- **window.days_included:** {len(r.info.get('days_included', []))} days")
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

def verify_week(
    end_day: str,
    parquet_path: Path,
    manifest_path: Path,
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
        help="Week end date to verify (YYYY-MM-DD). Default: most recent week in R2.",
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
        "--out-report",
        type=str,
        default=str(DEFAULT_REPORT_PATH),
        help=f"Output report path (default: {DEFAULT_REPORT_PATH})",
    )
    
    args = parser.parse_args()
    
    report_path = Path(args.out_report)
    use_r2 = not args.local or args.r2
    
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
        
        result = verify_week(end_day, parquet_path, manifest_path)
        results.append(result)
        
        # Write artifacts
        write_artifacts(result, VERIFY_CACHE_DIR)
        
    else:
        # Download from R2
        print("\n[Connecting to R2...]")
        config = get_r2_config()
        print(f"  Bucket: {config.bucket}")
        
        # Find weeks to verify
        if args.end_day:
            weeks_to_verify = [args.end_day]
        else:
            # Get most recent week
            print("  Listing available weeks...")
            available_weeks = list_tier2_weeks(config)
            if not available_weeks:
                print("[ERROR] No Tier 2 weekly exports found in R2", file=sys.stderr)
                return 1
            
            # Verify the most recent
            weeks_to_verify = [available_weeks[-1]]
            print(f"  Found {len(available_weeks)} weeks, verifying most recent: {weeks_to_verify[0]}")
        
        print(f"Mode: R2 verification")
        print(f"Weeks to verify: {weeks_to_verify}")
        
        for end_day in weeks_to_verify:
            print(f"\n[Downloading week {end_day} from R2...]")
            
            # Get size first
            r2_size = get_r2_object_size(config, end_day)
            
            # Download files
            parquet_path, manifest_path = download_from_r2(
                config, end_day, VERIFY_CACHE_DIR
            )
            
            if parquet_path is None:
                result = VerificationResult(end_day=end_day)
                result.errors.append("Failed to download from R2")
                results.append(result)
                continue
            
            result = verify_week(end_day, parquet_path, manifest_path, r2_size)
            results.append(result)
            
            # Write artifacts
            write_artifacts(result, VERIFY_CACHE_DIR)
    
    # Generate report
    print("\n" + "=" * 60)
    print("GENERATING REPORT")
    print("=" * 60)
    
    all_pass = generate_report(results, report_path)
    
    print(f"\n[OK] Report written to: {report_path}")
    
    # Artifact locations
    print(f"[OK] Artifacts written to: {VERIFY_CACHE_DIR}/")
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
