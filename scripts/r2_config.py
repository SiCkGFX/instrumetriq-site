#!/usr/bin/env python3
"""
R2 Configuration Loader

Loads Cloudflare R2 credentials from environment variables.
Validates all required variables are present and fails fast with clear errors.

Environment variables (set via ~/.r2_credentials on VPS):
    R2_ENDPOINT          - S3-compatible endpoint URL
    R2_ACCESS_KEY_ID     - Access key for R2
    R2_SECRET_ACCESS_KEY - Secret key for R2
    R2_BUCKET            - Target bucket name

Optional:
    CLOUDFLARE_API_TOKEN - For Cloudflare API calls (not S3/R2)

Usage:
    from r2_config import get_r2_config, get_cloudflare_api_token

    config = get_r2_config()
    # config.endpoint, config.access_key_id, config.secret_access_key, config.bucket
"""

import os
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class R2Config:
    """Immutable R2 configuration container."""
    endpoint: str
    access_key_id: str
    secret_access_key: str
    bucket: str


# Required environment variables for R2 S3-compatible access
_REQUIRED_R2_VARS = [
    "R2_ENDPOINT",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET",
]


def get_r2_config() -> R2Config:
    """
    Load and validate R2 configuration from environment variables.
    
    Returns:
        R2Config with all required fields populated.
        
    Raises:
        SystemExit: If any required environment variables are missing.
    """
    missing = [var for var in _REQUIRED_R2_VARS if not os.environ.get(var)]
    
    if missing:
        print(f"[ERROR] Missing required R2 environment variables: {', '.join(missing)}", file=sys.stderr)
        print("[ERROR] Ensure ~/.r2_credentials is sourced (run: source ~/.r2_credentials)", file=sys.stderr)
        sys.exit(1)
    
    return R2Config(
        endpoint=os.environ["R2_ENDPOINT"],
        access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        bucket=os.environ["R2_BUCKET"],
    )


def get_cloudflare_api_token() -> Optional[str]:
    """
    Get Cloudflare API token if available.
    
    This token is for Cloudflare API calls (not S3/R2 operations).
    Returns None if not set (non-fatal, since it's optional).
    """
    return os.environ.get("CLOUDFLARE_API_TOKEN")


# TODO: R2 upload logic will be added later


if __name__ == "__main__":
    # Quick validation check
    print("[INFO] Validating R2 configuration...")
    config = get_r2_config()
    print(f"[OK] R2_ENDPOINT: {config.endpoint}")
    print(f"[OK] R2_ACCESS_KEY_ID: {config.access_key_id[:8]}...")
    print(f"[OK] R2_SECRET_ACCESS_KEY: ****")
    print(f"[OK] R2_BUCKET: {config.bucket}")
    
    cf_token = get_cloudflare_api_token()
    if cf_token:
        print(f"[OK] CLOUDFLARE_API_TOKEN: {cf_token[:8]}...")
    else:
        print("[INFO] CLOUDFLARE_API_TOKEN: not set (optional)")
    
    print("\n[SUCCESS] R2 configuration is valid.")
