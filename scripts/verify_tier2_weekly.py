#!/usr/bin/env python3
"""
Tier 2 Weekly Parquet Verification Script (Flat Schema)

Validates Tier 2 weekly parquet exports for correctness and completeness.
Downloads from R2 (or uses local files) and runs comprehensive checks.

Tier 2 uses a FLAT SCHEMA with:
- Market structure fields (spot_raw, derived, scores)
- twitter_sentiment_meta (provenance/timing context)
- 7 flat sentiment outcome columns (no twitter_sentiment_windows internals)
- platform_engagement nested struct

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

# Tier 2 FLAT schema column policy
# 7 flat sentiment fields + 1 nested platform_engagement struct
SENTIMENT_FLAT_FIELDS = [
    "sentiment_is_silent",
    "sentiment_score",
    "sentiment_posts_total",
    "sentiment_posts_pos",
    "sentiment_posts_neg",
    "sentiment_posts_neu",
    "sentiment_confidence",
]

PLATFORM_ENGAGEMENT_FIELD = "platform_engagement"

# Required columns in Tier 2 flat schema
TIER2_REQUIRED_COLUMNS = [
    "symbol",
    "snapshot_ts",
    "meta",
    "spot_raw",
    "derived",
    "scores",
    "twitter_sentiment_meta",
] + SENTIMENT_FLAT_FIELDS + [PLATFORM_ENGAGEMENT_FIELD]

# Excluded columns (Tier 3 only)
TIER2_EXCLUDED_COLUMNS = [
    "futures_raw",
    "spot_prices",
    "flags",
    "diag",
    "twitter_sentiment_windows",  # Tier 3 only - Tier 2 uses flat fields instead
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
        prefix = prefix_obj.get("Prefix", "")
        parts = prefix.rstrip("/").split("/")
        if len(parts) >= 3:
            end_day = parts[2]
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
        s3.head_object(Bucket=config.bucket, Key=parquet_key)
        s3.head_object(Bucket=config.bucket, Key=manifest_key)
    except Exception as e:
        print(f"[ERROR] Objects not found in R2 for week {end_day}: {e}", file=sys.stderr)
        return None, None
    
    print(f"  Downloading {parquet_key}...")
    s3.download_file(config.bucket, parquet_key, str(parquet_path))
    
    print(f"  Downloading {manifest_key}...")
    s3.download_file(config.bucket, manifest_key, str(manifest_path))
    
    return parquet_path, manifest_path


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
    
    # Load manifest
    try:
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
    except json.JSONDecodeError as e:
        result.errors.append(f"Manifest is not valid JSON: {e}")
        return
    
    result.info["manifest"] = manifest
    
    # Verify SHA256
    expected_sha = None
    if "files" in manifest and "main" in manifest["files"]:
        expected_sha = manifest["files"]["main"].get("sha256")
    
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


def check_window_semantics(
    result: VerificationResult,
    end_day: str,
):
    """Check B: Window semantics."""
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
    
    # Check tier2_schema_version (new for flat schema)
    tier2_schema = manifest.get("tier2_schema_version")
    if tier2_schema:
        result.info["tier2_schema_version"] = tier2_schema
        if tier2_schema != "flat_v1":
            result.warnings.append(f"tier2_schema_version != 'flat_v1' (got: {tier2_schema})")
    
    # Check window structure
    window = manifest.get("window", {})
    manifest_end_day = window.get("week_end_day") or window.get("end_day")
    manifest_start_day = window.get("week_start_day") or window.get("start_day")
    
    if manifest_end_day != end_day:
        result.errors.append(f"Manifest end_day ({manifest_end_day}) != folder name ({end_day})")
    
    days_expected = window.get("days_expected", [])
    days_included = window.get("days_included", [])
    
    result.info["days_expected"] = days_expected
    result.info["days_included"] = days_included
    result.info["window_start"] = manifest_start_day
    result.info["window_end"] = manifest_end_day


def check_schema_columns(
    result: VerificationResult,
    parquet_path: Path,
) -> Optional[pa.Table]:
    """Check C: Schema / column policy for FLAT schema."""
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
        result.errors.append(f"Excluded columns present (should be Tier 3 only): {present_excluded}")
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
    
    # Check flat sentiment fields have correct types
    check_flat_sentiment_fields(result, table)
    
    return table


def check_nested_sanity(result: VerificationResult, table: pa.Table):
    """Check nested struct fields (meta, spot_raw, etc.)."""
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
    
    # Check derived and scores are structs
    for col_name in ["derived", "scores"]:
        if col_name in table.column_names:
            col_field = schema.field(col_name)
            if not pa.types.is_struct(col_field.type):
                result.warnings.append(f"{col_name} is not a struct type: {col_field.type}")


def check_flat_sentiment_fields(result: VerificationResult, table: pa.Table):
    """Check the 7 flat sentiment fields have correct types."""
    expected_types = {
        "sentiment_is_silent": pa.bool_(),
        "sentiment_score": pa.float64(),
        "sentiment_posts_total": pa.int64(),
        "sentiment_posts_pos": pa.int64(),
        "sentiment_posts_neg": pa.int64(),
        "sentiment_posts_neu": pa.int64(),
        "sentiment_confidence": pa.float64(),
    }
    
    schema = table.schema
    type_issues = []
    
    for field_name, expected_type in expected_types.items():
        if field_name in table.column_names:
            actual_type = schema.field(field_name).type
            # Allow null type as well
            if actual_type != expected_type and not pa.types.is_null(actual_type):
                type_issues.append(f"{field_name}: expected {expected_type}, got {actual_type}")
    
    if type_issues:
        result.warnings.append(f"Sentiment field type mismatches: {type_issues}")
    else:
        result.info["sentiment_field_types_ok"] = True


def check_data_quality(result: VerificationResult, table: pa.Table):
    """Check D: Data quality summaries."""
    manifest = result.info.get("manifest", {})
    num_rows = table.num_rows
    
    # Compare row count to manifest
    manifest_row_count = manifest.get("row_count")
    if manifest_row_count is None and "files" in manifest:
        manifest_row_count = manifest["files"].get("main", {}).get("row_count")
    
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
        except Exception:
            result.info["distinct_symbols"] = "unknown"
    
    # Sentiment coverage analysis
    # Check how many entries have sentiment data (sentiment_is_silent not null = has coverage)
    if "sentiment_is_silent" in table.column_names:
        silent_col = table.column("sentiment_is_silent")
        try:
            # Count non-null (has coverage) vs null (no coverage)
            has_coverage = 0
            no_coverage = 0
            silent_count = 0
            for v in silent_col:
                val = v.as_py()
                if val is None:
                    no_coverage += 1
                else:
                    has_coverage += 1
                    if val is True:
                        silent_count += 1
            
            coverage_rate = has_coverage / num_rows if num_rows > 0 else 0
            result.info["sentiment_coverage"] = {
                "has_coverage": has_coverage,
                "no_coverage": no_coverage,
                "silent_periods": silent_count,
                "coverage_rate": round(coverage_rate, 4),
            }
            
            # This is informational, not a warning - some symbols don't have sentiment data yet
            if coverage_rate < 0.5:
                result.info["sentiment_coverage_note"] = f"Only {coverage_rate*100:.1f}% of entries have sentiment data"
        except Exception:
            pass
    
    # Check platform_engagement field exists
    if PLATFORM_ENGAGEMENT_FIELD in table.column_names:
        result.info["platform_engagement_present"] = True
    else:
        result.warnings.append(f"Missing {PLATFORM_ENGAGEMENT_FIELD} field")
    
    # Sentiment score stats (for entries with coverage)
    if "sentiment_score" in table.column_names:
        score_col = table.column("sentiment_score")
        try:
            scores = [v.as_py() for v in score_col if v.as_py() is not None]
            if scores:
                result.info["sentiment_score_stats"] = {
                    "min": min(scores),
                    "max": max(scores),
                    "mean": round(statistics.mean(scores), 4),
                    "median": round(statistics.median(scores), 4),
                    "count": len(scores),
                }
        except Exception:
            pass


# ==============================================================================
# Verification Runner
# ==============================================================================

def verify_week(
    end_day: str,
    parquet_path: Optional[Path] = None,
    manifest_path: Optional[Path] = None,
    from_r2: bool = False,
    config: Optional[R2Config] = None,
) -> VerificationResult:
    """Run all verification checks on a single week."""
    result = VerificationResult(end_day=end_day)
    
    # Download from R2 if needed
    if from_r2 and config:
        print(f"\n[WEEK] {end_day} (from R2)")
        parquet_path, manifest_path = download_from_r2(
            config, end_day, VERIFY_CACHE_DIR
        )
    elif parquet_path and manifest_path:
        print(f"\n[WEEK] {end_day} (from local)")
    else:
        result.errors.append("No parquet/manifest paths provided and not downloading from R2")
        return result
    
    # Check A: Presence + integrity
    print("  [A] Checking presence and integrity...")
    check_presence_and_integrity(result, parquet_path, manifest_path)
    if result.has_errors:
        return result
    
    # Check B: Window semantics
    print("  [B] Checking window semantics...")
    check_window_semantics(result, end_day)
    
    # Check C: Schema columns
    print("  [C] Checking schema columns (flat schema)...")
    table = check_schema_columns(result, parquet_path)
    if table is None:
        return result
    
    # Check D: Data quality
    print("  [D] Checking data quality...")
    check_data_quality(result, table)
    
    # Summary
    print(f"  {result.status_symbol} {result.status}")
    if result.errors:
        for err in result.errors:
            print(f"      ERROR: {err}")
    if result.warnings:
        for warn in result.warnings[:3]:
            print(f"      WARN: {warn}")
        if len(result.warnings) > 3:
            print(f"      ... and {len(result.warnings) - 3} more warnings")
    
    return result


# ==============================================================================
# Report Generation
# ==============================================================================

def generate_report(results: list[VerificationResult], report_path: Path):
    """Generate markdown verification report."""
    lines = [
        "# Tier 2 Weekly Parquet Verification Report (Flat Schema)",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Summary",
        "",
        f"| Week | Status | Rows | Size (MB) | Errors | Warnings |",
        f"|------|--------|------|-----------|--------|----------|",
    ]
    
    for r in results:
        rows = r.info.get("row_count", "?")
        size = r.info.get("parquet_size_mb", "?")
        lines.append(
            f"| {r.end_day} | {r.status} | {rows:,} | {size} | {len(r.errors)} | {len(r.warnings)} |"
        )
    
    lines.append("")
    lines.append("## Flat Schema Columns")
    lines.append("")
    lines.append("Tier 2 uses a **flat schema** with 17 columns:")
    lines.append("- 7 core columns: symbol, snapshot_ts, meta, spot_raw, derived, scores, twitter_sentiment_meta")
    lines.append("- 10 flat sentiment outcome fields extracted from twitter_sentiment_windows.last_cycle")
    lines.append("")
    lines.append("**Sentiment fields:**")
    for field in SENTIMENT_FLAT_FIELDS:
        lines.append(f"- `{field}`")
    lines.append("")
    
    lines.append("## Details")
    lines.append("")
    
    for r in results:
        lines.append(f"### {r.end_day} - {r.status}")
        lines.append("")
        
        if r.errors:
            lines.append("**Errors:**")
            for err in r.errors:
                lines.append(f"- {err}")
            lines.append("")
        
        if r.warnings:
            lines.append("**Warnings:**")
            for warn in r.warnings:
                lines.append(f"- {warn}")
            lines.append("")
        
        # Info
        lines.append("**Info:**")
        lines.append(f"- Rows: {r.info.get('row_count', '?'):,}")
        lines.append(f"- Size: {r.info.get('parquet_size_mb', '?')} MB")
        lines.append(f"- Columns: {r.info.get('column_count', '?')}")
        lines.append(f"- Distinct symbols: {r.info.get('distinct_symbols', '?')}")
        
        score_stats = r.info.get("sentiment_score_stats")
        if score_stats:
            lines.append(f"- Sentiment score: min={score_stats['min']:.3f}, max={score_stats['max']:.3f}, mean={score_stats['mean']:.3f}")
        
        lines.append("")
    
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        f.write("\n".join(lines))
    
    print(f"\n[REPORT] Written to {report_path}")


# ==============================================================================
# CLI
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Verify Tier 2 weekly parquet exports (flat schema)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument("--end-day", type=str, default=None,
                        help="Specific week end date to verify (YYYY-MM-DD)")
    parser.add_argument("--local", type=str, default=None,
                        help="Local directory path (instead of R2)")
    parser.add_argument("--r2", action="store_true",
                        help="Force download from R2 (default if --local not set)")
    parser.add_argument("--all", action="store_true",
                        help="Verify all weeks in R2")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("TIER 2 WEEKLY PARQUET VERIFICATION (FLAT SCHEMA)")
    print("=" * 60)
    
    results = []
    
    if args.local:
        # Local verification
        local_path = Path(args.local)
        if not local_path.exists():
            print(f"[ERROR] Local path not found: {local_path}", file=sys.stderr)
            sys.exit(1)
        
        end_day = local_path.name
        parquet_path = local_path / "dataset_entries_7d.parquet"
        manifest_path = local_path / "manifest.json"
        
        result = verify_week(end_day, parquet_path, manifest_path)
        results.append(result)
    
    else:
        # R2 verification
        config = get_r2_config()
        
        if args.all or args.end_day is None:
            # Verify all weeks
            weeks = list_tier2_weeks(config)
            if not weeks:
                print("[WARN] No Tier 2 weeks found in R2")
                sys.exit(0)
            
            if args.end_day:
                weeks = [args.end_day]
            
            print(f"\n[INFO] Found {len(weeks)} weeks to verify: {weeks}")
            
            for end_day in weeks:
                result = verify_week(end_day, from_r2=True, config=config)
                results.append(result)
        else:
            result = verify_week(args.end_day, from_r2=True, config=config)
            results.append(result)
    
    # Generate report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = VERIFY_CACHE_DIR / f"report_{timestamp}.md"
    generate_report(results, report_path)
    
    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    pass_count = sum(1 for r in results if r.status == "PASS")
    warn_count = sum(1 for r in results if r.status == "WARN")
    fail_count = sum(1 for r in results if r.status == "FAIL")
    
    print(f"PASS: {pass_count}  WARN: {warn_count}  FAIL: {fail_count}")
    
    if fail_count > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
