#!/usr/bin/env python3
"""
Tier 1 Daily Parquet Verification Script

Validates Tier 1 daily parquet exports for correctness and completeness.
Tier 1 has 19 flattened columns.

Usage:
    # Verify specific date
    python3 scripts/verify_tier1_daily.py --date 2026-01-18

    # Verify all available dates
    python3 scripts/verify_tier1_daily.py --all

    # Quick schema-only check (no data validation)
    python3 scripts/verify_tier1_daily.py --date 2026-01-18 --schema-only
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

try:
    import pyarrow.parquet as pq
except ImportError:
    print("[ERROR] pyarrow required: pip install pyarrow", file=sys.stderr)
    sys.exit(1)

try:
    import boto3
except ImportError:
    print("[ERROR] boto3 required: pip install boto3", file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))
from r2_config import get_r2_config


# ==============================================================================
# Expected Schema (19 flat columns)
# ==============================================================================

TIER1_EXPECTED_COLUMNS = [
    # Identity + timing (2)
    "symbol",
    "snapshot_ts",
    # Meta (4)
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
    # Sentiment (6)
    "sentiment_posts_total",
    "sentiment_posts_pos",
    "sentiment_posts_neu",
    "sentiment_posts_neg",
    "sentiment_mean_score",
    "sentiment_is_silent",
]


# ==============================================================================
# Helpers
# ==============================================================================

def get_s3():
    cfg = get_r2_config()
    return boto3.client(
        "s3",
        endpoint_url=cfg.endpoint,
        aws_access_key_id=cfg.access_key_id,
        aws_secret_access_key=cfg.secret_access_key
    ), cfg.bucket


def list_available_dates(s3, bucket: str) -> list[str]:
    """List all available Tier 1 daily dates in R2."""
    resp = s3.list_objects_v2(Bucket=bucket, Prefix="tier1/daily/")
    dates = set()
    for obj in resp.get("Contents", []):
        parts = obj["Key"].split("/")
        if len(parts) >= 3 and "data.parquet" in obj["Key"]:
            dates.add(parts[2])
    return sorted(dates)


def download_parquet(s3, bucket: str, date: str) -> Path:
    """Download Tier 1 parquet for date to temp file."""
    import tempfile
    key = f"tier1/daily/{date}/data.parquet"
    tmp = Path(tempfile.mkdtemp()) / "data.parquet"
    s3.download_file(bucket, key, str(tmp))
    return tmp


# ==============================================================================
# Verification Functions
# ==============================================================================

def verify_schema(parquet_path: Path) -> dict:
    """Verify schema matches expected 19 columns."""
    pf = pq.ParquetFile(parquet_path)
    schema = pf.schema_arrow
    
    actual_cols = [f.name for f in schema]
    
    result = {
        "rows": pf.metadata.num_rows,
        "columns": len(actual_cols),
        "column_names": actual_cols,
        "missing_columns": [],
        "extra_columns": [],
        "schema_valid": True,
    }
    
    # Check expected columns
    for col in TIER1_EXPECTED_COLUMNS:
        if col not in actual_cols:
            result["missing_columns"].append(col)
            result["schema_valid"] = False
    
    # Check for extra columns
    for col in actual_cols:
        if col not in TIER1_EXPECTED_COLUMNS:
            result["extra_columns"].append(col)
            result["schema_valid"] = False
    
    return result


def verify_data(parquet_path: Path) -> dict:
    """Sample data and check for nulls/issues."""
    table = pq.read_table(parquet_path)
    df = table.to_pandas()
    
    result = {
        "total_rows": len(df),
        "symbols": df["symbol"].nunique(),
        "null_counts": {},
        "sample_symbols": df["symbol"].head(5).tolist(),
        "data_valid": True,
    }
    
    # Check null counts
    for col in TIER1_EXPECTED_COLUMNS:
        if col in df.columns:
            null_count = df[col].isna().sum()
            if null_count > 0:
                result["null_counts"][col] = int(null_count)
    
    # Critical columns should never be null
    critical = ["symbol", "snapshot_ts", "spot_mid"]
    for col in critical:
        if col in result["null_counts"] and result["null_counts"][col] > 0:
            result["data_valid"] = False
    
    return result


def verify_date(s3, bucket: str, date: str, schema_only: bool = False) -> dict:
    """Full verification for a single date."""
    print(f"\n{'='*60}")
    print(f"Verifying Tier 1 for {date}")
    print(f"{'='*60}")
    
    result = {"date": date, "status": "PASS"}
    
    # Download
    try:
        parquet_path = download_parquet(s3, bucket, date)
    except Exception as e:
        print(f"  [ERROR] Failed to download: {e}")
        return {"date": date, "status": "FAIL", "error": str(e)}
    
    # Schema check
    schema_result = verify_schema(parquet_path)
    result["schema"] = schema_result
    
    print(f"  Rows: {schema_result['rows']:,}")
    print(f"  Columns: {schema_result['columns']} (expected 19)")
    
    if schema_result["missing_columns"]:
        print(f"  [ERROR] Missing columns: {schema_result['missing_columns']}")
        result["status"] = "FAIL"
    
    if schema_result["extra_columns"]:
        print(f"  [WARN] Extra columns: {schema_result['extra_columns']}")
    
    if schema_result["schema_valid"]:
        print(f"  [OK] Schema valid (19 columns)")
    
    # Data check
    if not schema_only:
        data_result = verify_data(parquet_path)
        result["data"] = data_result
        
        print(f"  Symbols: {data_result['symbols']}")
        
        if data_result["null_counts"]:
            print(f"  Nulls: {data_result['null_counts']}")
        else:
            print(f"  [OK] No nulls in any column")
        
        if not data_result["data_valid"]:
            result["status"] = "FAIL"
    
    # Cleanup
    parquet_path.unlink(missing_ok=True)
    parquet_path.parent.rmdir()
    
    print(f"  Result: {result['status']}")
    return result


# ==============================================================================
# Main
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Verify Tier 1 daily parquet exports")
    parser.add_argument("--date", help="Specific date to verify (YYYY-MM-DD)")
    parser.add_argument("--all", action="store_true", help="Verify all available dates")
    parser.add_argument("--schema-only", action="store_true", help="Only check schema, skip data validation")
    args = parser.parse_args()
    
    s3, bucket = get_s3()
    
    if args.all:
        dates = list_available_dates(s3, bucket)
        print(f"Found {len(dates)} Tier 1 daily exports")
    elif args.date:
        dates = [args.date]
    else:
        # Default: verify latest
        dates = list_available_dates(s3, bucket)
        if dates:
            dates = [dates[-1]]
        else:
            print("[ERROR] No Tier 1 daily exports found")
            sys.exit(1)
    
    results = []
    for date in dates:
        result = verify_date(s3, bucket, date, schema_only=args.schema_only)
        results.append(result)
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    print(f"  Total: {len(results)}")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    
    if failed > 0:
        print("\nFailed dates:")
        for r in results:
            if r["status"] == "FAIL":
                print(f"  - {r['date']}")
        sys.exit(1)
    else:
        print("\n[OK] All Tier 1 daily exports verified successfully")


if __name__ == "__main__":
    main()
