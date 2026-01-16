#!/usr/bin/env python3
"""
Initialize R2 Bucket Folder Structure

Creates the tier-based prefix structure in the instrumetriq-datasets R2 bucket
by uploading zero-byte .keep placeholder files.

Structure created:
    tier1/daily/.keep
    tier2/daily/.keep
    tier3/daily/.keep
    tier3/full/.keep

Usage:
    python3 scripts/init_r2_structure.py

Prerequisites:
    - boto3 installed (pip install boto3)
    - R2 credentials loaded via environment variables
"""

import sys
from pathlib import Path

# Add scripts directory to path for local imports
sys.path.insert(0, str(Path(__file__).parent))

from r2_config import get_r2_config

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    print("[ERROR] boto3 is required. Install with: pip install boto3", file=sys.stderr)
    sys.exit(1)


# Define the prefix structure to create
# Each entry is a prefix path where a .keep file will be placed
PREFIXES_TO_CREATE = [
    "tier1/daily/",
    "tier2/daily/",
    "tier3/daily/",
    "tier3/full/",
]


def create_s3_client(config):
    """Create an S3 client configured for R2."""
    return boto3.client(
        "s3",
        endpoint_url=config.endpoint,
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
    )


def ensure_prefix_exists(client, bucket: str, prefix: str) -> bool:
    """
    Ensure a prefix "folder" exists by creating a .keep placeholder.
    
    Args:
        client: boto3 S3 client
        bucket: Bucket name
        prefix: Prefix path (must end with /)
        
    Returns:
        True if created, False if already existed
    """
    key = f"{prefix}.keep"
    
    # Check if .keep already exists
    try:
        client.head_object(Bucket=bucket, Key=key)
        return False  # Already exists
    except ClientError as e:
        if e.response["Error"]["Code"] != "404":
            print(f"[ERROR] Failed to check {key}: {e.response['Error']['Message']}", file=sys.stderr)
            sys.exit(1)
    
    # Create zero-byte .keep file
    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=b"",
            ContentType="application/x-empty",
        )
        return True  # Created
    except ClientError as e:
        print(f"[ERROR] Failed to create {key}: {e.response['Error']['Message']}", file=sys.stderr)
        sys.exit(1)


def main():
    print("[INFO] Initializing R2 bucket structure...")
    
    # Load configuration
    config = get_r2_config()
    print(f"[INFO] Bucket: {config.bucket}")
    print(f"[INFO] Endpoint: {config.endpoint}")
    
    # Create S3 client
    client = create_s3_client(config)
    
    # Verify bucket access
    try:
        client.head_bucket(Bucket=config.bucket)
        print(f"[OK] Bucket '{config.bucket}' is accessible")
    except ClientError as e:
        print(f"[ERROR] Cannot access bucket: {e.response['Error']['Message']}", file=sys.stderr)
        sys.exit(1)
    
    # Create prefix structure
    created = []
    existed = []
    
    for prefix in PREFIXES_TO_CREATE:
        if ensure_prefix_exists(client, config.bucket, prefix):
            created.append(prefix)
            print(f"[CREATED] {prefix}.keep")
        else:
            existed.append(prefix)
            print(f"[EXISTS]  {prefix}.keep")
    
    # Summary
    print("\n" + "=" * 50)
    print("R2 STRUCTURE INITIALIZATION COMPLETE")
    print("=" * 50)
    print(f"\nBucket: {config.bucket}")
    print(f"\nPrefixes verified ({len(PREFIXES_TO_CREATE)} total):")
    for prefix in PREFIXES_TO_CREATE:
        status = "✓ created" if prefix in created else "· existed"
        print(f"  {status}  {prefix}")
    
    print(f"\nSummary: {len(created)} created, {len(existed)} already existed")
    print("[SUCCESS] R2 structure is ready.\n")


if __name__ == "__main__":
    main()
