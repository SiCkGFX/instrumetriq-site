#!/usr/bin/env python3
"""
Generate Sample JSON/JSONL Files from Each Tier

Pulls 5 random rows with all columns from each tier to create human-readable sample files.

Usage:
    # Generate samples from R2 (default)
    python3 scripts/generate_tier_samples.py

    # Specify output directory
    python3 scripts/generate_tier_samples.py --output-dir output/samples

    # Use specific dates
    python3 scripts/generate_tier_samples.py --tier3-date 2026-01-05 --tier2-date 2025-12-28 --tier1-date 2025-12-28

Output:
    {output_dir}/tier1_sample.jsonl  - 5 random rows from Tier 1 (one JSON object per line)
    {output_dir}/tier2_sample.jsonl  - 5 random rows from Tier 2 (one JSON object per line)
    {output_dir}/tier3_sample.jsonl  - 5 random rows from Tier 3 (one JSON object per line)
"""

import argparse
import json
import random
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

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

DEFAULT_OUTPUT_DIR = Path("./output/samples")
DEFAULT_SAMPLE_SIZE = 5


# ==============================================================================
# JSON Serialization Helpers
# ==============================================================================

def arrow_to_python(value: Any) -> Any:
    """Convert Arrow/PyArrow values to JSON-serializable Python types."""
    if value is None:
        return None
    
    # Handle PyArrow scalar types
    if hasattr(value, 'as_py'):
        return arrow_to_python(value.as_py())
    
    # Handle datetime objects
    if isinstance(value, datetime):
        return value.isoformat()
    
    # Handle bytes
    if isinstance(value, bytes):
        try:
            return value.decode('utf-8')
        except UnicodeDecodeError:
            import base64
            return base64.b64encode(value).decode('ascii')
    
    # Handle lists/arrays
    if isinstance(value, (list, tuple)):
        return [arrow_to_python(v) for v in value]
    
    # Handle dicts
    if isinstance(value, dict):
        return {k: arrow_to_python(v) for k, v in value.items()}
    
    # Pass through basic types
    if isinstance(value, (str, int, float, bool)):
        return value
    
    # Fallback: convert to string
    return str(value)


def table_to_jsonl(table: pa.Table) -> list[dict]:
    """Convert Arrow table to list of JSON-serializable dicts."""
    # Convert to Python dicts via pandas-style iteration
    records = []
    for i in range(table.num_rows):
        row = {}
        for col_name in table.column_names:
            col = table.column(col_name)
            value = col[i]
            row[col_name] = arrow_to_python(value)
        records.append(row)
    return records


def write_jsonl(records: list[dict], path: Path, indent: bool = False) -> None:
    """Write records as JSONL (one JSON object per line)."""
    with open(path, 'w', encoding='utf-8') as f:
        for record in records:
            if indent:
                # Pretty print each record (still one per line block)
                f.write(json.dumps(record, indent=2, ensure_ascii=False))
                f.write('\n\n')  # Extra blank line between records for readability
            else:
                f.write(json.dumps(record, ensure_ascii=False))
                f.write('\n')


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


def find_latest_date(s3_client, bucket: str, prefix: str) -> Optional[str]:
    """Find the latest date folder under a prefix."""
    response = s3_client.list_objects_v2(
        Bucket=bucket,
        Prefix=prefix,
        Delimiter="/",
    )
    
    dates = []
    for prefix_obj in response.get("CommonPrefixes", []):
        # Extract date from path like "tier3/daily/2026-01-05/"
        prefix_path = prefix_obj.get("Prefix", "")
        parts = prefix_path.rstrip("/").split("/")
        if len(parts) >= 3:
            date_str = parts[-1]
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
                dates.append(date_str)
            except ValueError:
                pass
    
    return sorted(dates)[-1] if dates else None


def download_parquet(s3_client, bucket: str, key: str) -> pa.Table:
    """Download a parquet file from R2 and return as Arrow table."""
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=True) as tmp:
        s3_client.download_file(bucket, key, tmp.name)
        return pq.read_table(tmp.name)


# ==============================================================================
# Sampling Logic
# ==============================================================================

def sample_table(table: pa.Table, n: int = DEFAULT_SAMPLE_SIZE, seed: int = 42) -> pa.Table:
    """Sample n random rows from a table."""
    num_rows = table.num_rows
    
    if num_rows <= n:
        return table
    
    # Set seed for reproducibility
    random.seed(seed)
    
    # Generate random indices
    indices = sorted(random.sample(range(num_rows), n))
    
    # Take rows at those indices
    return table.take(indices)


def get_tier3_sample(s3_client, bucket: str, date: Optional[str], n: int) -> pa.Table:
    """Get sample from Tier 3 daily parquet."""
    if date is None:
        date = find_latest_date(s3_client, bucket, "tier3/daily/")
        if date is None:
            raise RuntimeError("No Tier 3 daily data found in R2")
    
    key = f"tier3/daily/{date}/data.parquet"
    print(f"  Downloading tier3/daily/{date}/data.parquet...")
    
    table = download_parquet(s3_client, bucket, key)
    print(f"  Source: {table.num_rows} rows, {table.num_columns} columns")
    
    return sample_table(table, n)


def get_tier2_sample(s3_client, bucket: str, date: Optional[str], n: int) -> pa.Table:
    """Get sample from Tier 2 weekly parquet."""
    if date is None:
        date = find_latest_date(s3_client, bucket, "tier2/weekly/")
        if date is None:
            raise RuntimeError("No Tier 2 weekly data found in R2")
    
    key = f"tier2/weekly/{date}/dataset_entries_7d.parquet"
    print(f"  Downloading tier2/weekly/{date}/dataset_entries_7d.parquet...")
    
    table = download_parquet(s3_client, bucket, key)
    print(f"  Source: {table.num_rows} rows, {table.num_columns} columns")
    
    return sample_table(table, n)


def get_tier1_sample(s3_client, bucket: str, date: Optional[str], n: int) -> pa.Table:
    """Get sample from Tier 1 weekly parquet."""
    if date is None:
        date = find_latest_date(s3_client, bucket, "tier1/weekly/")
        if date is None:
            raise RuntimeError("No Tier 1 weekly data found in R2")
    
    key = f"tier1/weekly/{date}/dataset_entries_7d.parquet"
    print(f"  Downloading tier1/weekly/{date}/dataset_entries_7d.parquet...")
    
    table = download_parquet(s3_client, bucket, key)
    print(f"  Source: {table.num_rows} rows, {table.num_columns} columns")
    
    return sample_table(table, n)


# ==============================================================================
# Main
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generate sample JSONL files from each tier",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR),
                        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--tier3-date", type=str, default=None,
                        help="Tier 3 date (YYYY-MM-DD), defaults to latest")
    parser.add_argument("--tier2-date", type=str, default=None,
                        help="Tier 2 week end date (YYYY-MM-DD), defaults to latest")
    parser.add_argument("--tier1-date", type=str, default=None,
                        help="Tier 1 week end date (YYYY-MM-DD), defaults to latest")
    parser.add_argument("-n", "--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE,
                        help=f"Number of sample rows (default: {DEFAULT_SAMPLE_SIZE})")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility (default: 42)")
    parser.add_argument("--compact", action="store_true",
                        help="Output compact JSONL (one line per record) instead of pretty-printed")
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("TIER SAMPLE GENERATOR (JSONL)")
    print("=" * 60)
    print(f"Output directory: {output_dir}")
    print(f"Sample size: {args.sample_size} rows per tier")
    print(f"Random seed: {args.seed}")
    print(f"Format: {'compact JSONL' if args.compact else 'pretty-printed JSONL'}")
    print()
    
    # Connect to R2
    print("[STEP 1] Connecting to R2...")
    config = get_r2_config()
    s3_client = get_s3_client(config)
    print(f"[OK] Connected to bucket: {config.bucket}")
    print()
    
    # Generate Tier 3 sample
    print("[STEP 2] Generating Tier 3 sample...")
    try:
        tier3_sample = get_tier3_sample(s3_client, config.bucket, args.tier3_date, args.sample_size)
        
        # Write Parquet
        tier3_parquet_path = output_dir / "tier3_sample.parquet"
        pq.write_table(tier3_sample, tier3_parquet_path)
        
        # Write JSONL
        tier3_records = table_to_jsonl(tier3_sample)
        tier3_path = output_dir / "tier3_sample.jsonl"
        write_jsonl(tier3_records, tier3_path, indent=not args.compact)
        
        tier3_size_kb_json = tier3_path.stat().st_size / 1024
        tier3_size_kb_pq = tier3_parquet_path.stat().st_size / 1024
        print(f"[OK] Wrote {tier3_path} ({len(tier3_records)} rows, {tier3_size_kb_json:.1f} KB)")
        print(f"[OK] Wrote {tier3_parquet_path} ({tier3_size_kb_pq:.1f} KB)")
    except Exception as e:
        print(f"[ERROR] Tier 3 sample failed: {e}")
        tier3_sample = None
        tier3_records = None
    print()
    
    # Generate Tier 2 sample
    print("[STEP 3] Generating Tier 2 sample...")
    try:
        tier2_sample = get_tier2_sample(s3_client, config.bucket, args.tier2_date, args.sample_size)
        
        # Write Parquet
        tier2_parquet_path = output_dir / "tier2_sample.parquet"
        pq.write_table(tier2_sample, tier2_parquet_path)
        
        # Write JSONL
        tier2_records = table_to_jsonl(tier2_sample)
        tier2_path = output_dir / "tier2_sample.jsonl"
        write_jsonl(tier2_records, tier2_path, indent=not args.compact)
        
        tier2_size_kb_json = tier2_path.stat().st_size / 1024
        tier2_size_kb_pq = tier2_parquet_path.stat().st_size / 1024
        print(f"[OK] Wrote {tier2_path} ({len(tier2_records)} rows, {tier2_size_kb_json:.1f} KB)")
        print(f"[OK] Wrote {tier2_parquet_path} ({tier2_size_kb_pq:.1f} KB)")
    except Exception as e:
        print(f"[ERROR] Tier 2 sample failed: {e}")
        tier2_sample = None
        tier2_records = None
    print()
    
    # Generate Tier 1 sample
    print("[STEP 4] Generating Tier 1 sample...")
    try:
        tier1_sample = get_tier1_sample(s3_client, config.bucket, args.tier1_date, args.sample_size)
        
        # Write Parquet
        tier1_parquet_path = output_dir / "tier1_sample.parquet"
        pq.write_table(tier1_sample, tier1_parquet_path)

        # Write JSONL
        tier1_records = table_to_jsonl(tier1_sample)
        tier1_path = output_dir / "tier1_sample.jsonl"
        write_jsonl(tier1_records, tier1_path, indent=not args.compact)
        
        tier1_size_kb_json = tier1_path.stat().st_size / 1024
        tier1_size_kb_pq = tier1_parquet_path.stat().st_size / 1024
        print(f"[OK] Wrote {tier1_path} ({len(tier1_records)} rows, {tier1_size_kb_json:.1f} KB)")
        print(f"[OK] Wrote {tier1_parquet_path} ({tier1_size_kb_pq:.1f} KB)")
    except Exception as e:
        print(f"[ERROR] Tier 1 sample failed: {e}")
        tier1_sample = None
        tier1_records = None
    print()
    
    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    if tier3_sample is not None:
        print(f"Tier 3: {args.sample_size} rows, {tier3_sample.num_columns} columns")
        print(f"        Columns: {tier3_sample.column_names}")
    
    if tier2_sample is not None:
        print(f"Tier 2: {args.sample_size} rows, {tier2_sample.num_columns} columns")
        print(f"        Columns: {tier2_sample.column_names}")
    
    if tier1_sample is not None:
        print(f"Tier 1: {args.sample_size} rows, {tier1_sample.num_columns} columns")
        print(f"        Columns: {tier1_sample.column_names}")
    
    print()
    print(f"Output files:")
    for f in sorted(output_dir.glob("tier*_sample.jsonl")):
        print(f"  {f}")
    
    print("=" * 60)
    print("[DONE]")


if __name__ == "__main__":
    main()
