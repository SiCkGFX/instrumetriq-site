#!/usr/bin/env python3
"""
Generate secure tokens for Patreon tier access.

This script generates cryptographically secure random tokens (32 bytes, base64url encoded)
for controlling access to tier-specific download pages.

Also uploads token state to R2 so Cloudflare Pages can access it for validation.

Usage:
    python3 scripts/generate_tier_tokens.py --tier tier1
    python3 scripts/generate_tier_tokens.py --all
    python3 scripts/generate_tier_tokens.py --tier tier2 --position next
"""

import argparse
import json
import secrets
import base64
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add scripts directory to path for r2_config import
sys.path.insert(0, str(Path(__file__).parent))
from r2_config import get_r2_config
import boto3

TOKEN_FILE = Path("/etc/instrumetriq/tier_tokens.json")
TOKEN_BYTES = 32  # 32 bytes = 256 bits of entropy


def generate_token() -> str:
    """Generate a cryptographically secure random token."""
    random_bytes = secrets.token_bytes(TOKEN_BYTES)
    # Use base64url encoding (URL-safe, no padding)
    token = base64.urlsafe_b64encode(random_bytes).decode('ascii').rstrip('=')
    return token


def load_token_state() -> dict:
    """Load the current token state from disk."""
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(f"Token file not found: {TOKEN_FILE}")
    
    with TOKEN_FILE.open('r') as f:
        return json.load(f)


def save_token_state(state: dict) -> None:
    """Save the token state to disk and upload to R2."""
    state['last_updated'] = datetime.now(timezone.utc).isoformat()
    
    # Save to local file
    with TOKEN_FILE.open('w') as f:
        json.dump(state, f, indent=2)
    
    # Ensure secure permissions
    TOKEN_FILE.chmod(0o600)
    
    # Upload to R2 for Cloudflare Pages access
    try:
        cfg = get_r2_config()
        s3 = boto3.client(
            's3',
            endpoint_url=cfg.endpoint,
            aws_access_key_id=cfg.access_key_id,
            aws_secret_access_key=cfg.secret_access_key,
            region_name='auto'
        )
        
        s3.put_object(
            Bucket=cfg.bucket,
            Key='config/tier_tokens.json',
            Body=json.dumps(state, indent=2),
            ContentType='application/json'
        )
        print(f"[OK] Token state uploaded to R2: config/tier_tokens.json")
    except Exception as e:
        print(f"[WARN] Failed to upload token state to R2: {e}", file=sys.stderr)
        print("[WARN] Cloudflare Pages won't have updated tokens until R2 upload succeeds", file=sys.stderr)


def generate_tokens_for_tier(state: dict, tier: str, position: str = 'current') -> str:
    """
    Generate a new token for the specified tier and position.
    
    Args:
        state: Token state dictionary
        tier: Tier name (tier1, tier2, tier3)
        position: 'current' or 'next'
    
    Returns:
        The generated token string
    """
    if tier not in state['tiers']:
        raise ValueError(f"Invalid tier: {tier}. Must be one of: tier1, tier2, tier3")
    
    if position not in ('current', 'next'):
        raise ValueError(f"Invalid position: {position}. Must be 'current' or 'next'")
    
    token = generate_token()
    timestamp = datetime.now(timezone.utc).isoformat()
    
    token_key = f"{position}_token"
    created_key = f"{position}_token_created"
    
    state['tiers'][tier][token_key] = token
    state['tiers'][tier][created_key] = timestamp
    
    return token


def main():
    parser = argparse.ArgumentParser(
        description='Generate secure tokens for Patreon tier access'
    )
    parser.add_argument(
        '--tier',
        choices=['tier1', 'tier2', 'tier3'],
        help='Generate token for specific tier'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Generate tokens for all tiers'
    )
    parser.add_argument(
        '--position',
        choices=['current', 'next'],
        default='current',
        help='Token position (current or next). Default: current'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Generate tokens but do not save to file'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.tier and not args.all:
        parser.error("Must specify either --tier or --all")
    
    if args.tier and args.all:
        parser.error("Cannot specify both --tier and --all")
    
    # Load current state
    try:
        state = load_token_state()
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return 1
    
    # Determine which tiers to process
    if args.all:
        tiers_to_process = ['tier1', 'tier2', 'tier3']
    else:
        tiers_to_process = [args.tier]
    
    # Generate tokens
    print(f"\n{'='*70}")
    print(f"GENERATING TOKENS - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"{'='*70}\n")
    
    generated_tokens = {}
    
    for tier in tiers_to_process:
        token = generate_tokens_for_tier(state, tier, args.position)
        generated_tokens[tier] = token
        
        tier_name = tier.upper().replace('TIER', 'Tier ')
        print(f"{tier_name} ({args.position}):")
        print(f"  Token: {token}")
        print(f"  Length: {len(token)} characters")
        print(f"  Entropy: {TOKEN_BYTES * 8} bits")
        print()
    
    # Save state (unless dry-run)
    if args.dry_run:
        print("DRY RUN: Tokens generated but NOT saved to disk")
    else:
        save_token_state(state)
        print(f"✓ Tokens saved to: {TOKEN_FILE}")
    
    print(f"\n{'='*70}\n")
    
    return 0


if __name__ == '__main__':
    exit(main())
