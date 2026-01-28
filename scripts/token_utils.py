#!/usr/bin/env python3
"""
Token validation utilities for Patreon tier access control.

This module provides functions to validate tokens against the token state file,
handling both current and next tokens during overlap windows.
"""

import json
from pathlib import Path
from typing import Optional, Dict, Tuple
from datetime import datetime, timezone

TOKEN_FILE = Path("/etc/instrumetriq/tier_tokens.json")


class TokenValidationError(Exception):
    """Raised when token validation fails."""
    pass


def load_token_state() -> dict:
    """
    Load the current token state from disk.
    
    Returns:
        dict: Token state dictionary
        
    Raises:
        TokenValidationError: If token file cannot be loaded
    """
    if not TOKEN_FILE.exists():
        raise TokenValidationError(f"Token file not found: {TOKEN_FILE}")
    
    try:
        with TOKEN_FILE.open('r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise TokenValidationError(f"Invalid JSON in token file: {e}")
    except Exception as e:
        raise TokenValidationError(f"Error loading token file: {e}")


def validate_token(token: str, tier: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a token for a specific tier.
    
    Args:
        token: The token string to validate
        tier: The tier name (tier1, tier2, tier3)
    
    Returns:
        Tuple of (is_valid, reason):
            - is_valid: True if token is valid, False otherwise
            - reason: None if valid, error message if invalid
    
    Examples:
        >>> is_valid, reason = validate_token("abc123...", "tier1")
        >>> if is_valid:
        ...     print("Access granted")
        ... else:
        ...     print(f"Access denied: {reason}")
    """
    # Validate tier name
    if tier not in ('tier1', 'tier2', 'tier3'):
        return False, f"Invalid tier: {tier}"
    
    # Load token state
    try:
        state = load_token_state()
    except TokenValidationError as e:
        return False, f"Token system error: {str(e)}"
    
    # Get tier config
    tier_config = state['tiers'].get(tier)
    if not tier_config:
        return False, f"Tier configuration not found: {tier}"
    
    current_token = tier_config.get('current_token')
    next_token = tier_config.get('next_token')
    overlap_active = tier_config.get('overlap_active', False)
    
    # Check if any tokens are configured
    if not current_token and not next_token:
        return False, "No tokens configured for this tier"
    
    # Validate against current token
    if current_token and token == current_token:
        return True, None
    
    # Validate against next token (only if overlap is active)
    if overlap_active and next_token and token == next_token:
        return True, None
    
    # Token didn't match
    return False, "Invalid or expired token"


def validate_token_raises(token: str, tier: str) -> None:
    """
    Validate a token for a specific tier, raising an exception if invalid.
    
    Args:
        token: The token string to validate
        tier: The tier name (tier1, tier2, tier3)
    
    Raises:
        TokenValidationError: If token is invalid or expired
    
    Examples:
        >>> try:
        ...     validate_token_raises("abc123...", "tier1")
        ...     print("Access granted")
        ... except TokenValidationError as e:
        ...     print(f"Access denied: {e}")
    """
    is_valid, reason = validate_token(token, tier)
    if not is_valid:
        raise TokenValidationError(reason)


def get_tier_info(tier: str) -> Dict[str, any]:
    """
    Get information about a tier's token configuration.
    
    Args:
        tier: The tier name (tier1, tier2, tier3)
    
    Returns:
        dict: Tier configuration including token metadata (tokens themselves are excluded)
    
    Raises:
        TokenValidationError: If tier configuration cannot be loaded
    """
    if tier not in ('tier1', 'tier2', 'tier3'):
        raise TokenValidationError(f"Invalid tier: {tier}")
    
    state = load_token_state()
    tier_config = state['tiers'].get(tier)
    
    if not tier_config:
        raise TokenValidationError(f"Tier configuration not found: {tier}")
    
    # Return metadata without exposing actual tokens
    return {
        'tier': tier,
        'has_current_token': bool(tier_config.get('current_token')),
        'has_next_token': bool(tier_config.get('next_token')),
        'overlap_active': tier_config.get('overlap_active', False),
        'current_token_created': tier_config.get('current_token_created'),
        'next_token_created': tier_config.get('next_token_created'),
        'last_rotation': tier_config.get('last_rotation'),
    }


def check_token_health() -> Dict[str, any]:
    """
    Check the health of the token system.
    
    Returns:
        dict: Health status including warnings and errors
    """
    try:
        state = load_token_state()
    except TokenValidationError as e:
        return {
            'healthy': False,
            'error': str(e),
            'tiers': {}
        }
    
    health = {
        'healthy': True,
        'warnings': [],
        'tiers': {}
    }
    
    for tier_name in ['tier1', 'tier2', 'tier3']:
        tier_config = state['tiers'][tier_name]
        tier_health = {
            'has_current_token': bool(tier_config.get('current_token')),
            'has_next_token': bool(tier_config.get('next_token')),
            'overlap_active': tier_config.get('overlap_active', False)
        }
        
        # Check for missing current token
        if not tier_health['has_current_token']:
            health['warnings'].append(f"{tier_name}: No current token configured")
            health['healthy'] = False
        
        # Check for overlap without next token
        if tier_health['overlap_active'] and not tier_health['has_next_token']:
            health['warnings'].append(f"{tier_name}: Overlap active but no next token")
            health['healthy'] = False
        
        health['tiers'][tier_name] = tier_health
    
    return health


if __name__ == '__main__':
    # Simple CLI for testing
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python3 token_utils.py <tier> <token>")
        print("   or: python3 token_utils.py --health")
        sys.exit(1)
    
    if sys.argv[1] == '--health':
        health = check_token_health()
        print(json.dumps(health, indent=2))
        sys.exit(0 if health['healthy'] else 1)
    
    tier = sys.argv[1]
    token = sys.argv[2]
    
    is_valid, reason = validate_token(token, tier)
    
    if is_valid:
        print(f"✓ Token valid for {tier}")
        sys.exit(0)
    else:
        print(f"✗ Token invalid: {reason}")
        sys.exit(1)
