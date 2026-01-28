/**
 * Token Validation Utility
 * 
 * Validates tier access tokens against the token state stored in R2.
 * Supports overlap window where both current and next tokens are valid.
 * 
 * Token state is stored in R2 at config/tier_tokens.json so both VPS
 * (for generation) and Cloudflare Pages (for validation) can access it.
 */

import { S3Client, GetObjectCommand } from '@aws-sdk/client-s3';

const R2_ENDPOINT = import.meta.env.R2_ENDPOINT || process.env.R2_ENDPOINT;
const R2_ACCESS_KEY_ID = import.meta.env.R2_ACCESS_KEY_ID || process.env.R2_ACCESS_KEY_ID;
const R2_SECRET_ACCESS_KEY = import.meta.env.R2_SECRET_ACCESS_KEY || process.env.R2_SECRET_ACCESS_KEY;
const R2_BUCKET = import.meta.env.R2_BUCKET || process.env.R2_BUCKET;

const TOKEN_STATE_KEY = 'config/tier_tokens.json';

export interface TokenState {
  version: number;
  last_updated: string;
  rotation_schedule: {
    announce_day: string;
    overlap_day: string;
    promote_day: string;
    timezone: string;
  };
  tiers: {
    [tier: string]: {
      current_token: string | null;
      next_token: string | null;
      overlap_active: boolean;
      current_generated_at: string | null;
      next_generated_at: string | null;
    };
  };
}

export interface ValidationResult {
  valid: boolean;
  reason?: string;
}

/**
 * Load token state from R2.
 * Cached for performance, reloaded on demand if state changes.
 */
let cachedState: TokenState | null = null;
let lastLoadTime = 0;
const CACHE_TTL = 60000; // 60 seconds

async function loadTokenState(): Promise<TokenState> {
  const now = Date.now();
  
  // Use cache if still fresh
  if (cachedState && (now - lastLoadTime) < CACHE_TTL) {
    return cachedState;
  }
  
  try {
    // Create R2 client
    if (!R2_ENDPOINT || !R2_ACCESS_KEY_ID || !R2_SECRET_ACCESS_KEY || !R2_BUCKET) {
      throw new Error('R2 credentials not configured');
    }
    
    const client = new S3Client({
      region: 'auto',
      endpoint: R2_ENDPOINT,
      credentials: {
        accessKeyId: R2_ACCESS_KEY_ID,
        secretAccessKey: R2_SECRET_ACCESS_KEY,
      },
    });
    
    const command = new GetObjectCommand({
      Bucket: R2_BUCKET,
      Key: TOKEN_STATE_KEY,
    });
    
    const response = await client.send(command);
    const body = await response.Body?.transformToString();
    
    if (!body) {
      throw new Error('Empty response from R2');
    }
    
    cachedState = JSON.parse(body);
    lastLoadTime = now;
    return cachedState!;
  } catch (error) {
    throw new Error(`Failed to load token state from R2: ${error}`);
  }
}

/**
 * Validate a token for a specific tier.
 * 
 * @param token - The token to validate (43-character base64url string)
 * @param tier - The tier to validate against ('tier1', 'tier2', 'tier3')
 * @returns ValidationResult with valid flag and optional reason
 */
export async function validateToken(token: string, tier: string): Promise<ValidationResult> {
  // Basic format validation
  if (!token || typeof token !== 'string') {
    return { valid: false, reason: 'Token is required' };
  }
  
  if (token.length !== 43) {
    return { valid: false, reason: 'Token has invalid length' };
  }
  
  // Tier validation
  const validTiers = ['tier1', 'tier2', 'tier3'];
  if (!validTiers.includes(tier)) {
    return { valid: false, reason: `Invalid tier: ${tier}` };
  }
  
  // Load state
  let state: TokenState;
  try {
    state = await loadTokenState();
  } catch (error) {
    console.error('[TokenValidator] Failed to load state:', error);
    return { valid: false, reason: 'Token validation unavailable' };
  }
  
  // Get tier info
  const tierInfo = state.tiers[tier];
  if (!tierInfo) {
    return { valid: false, reason: `No token configuration for tier: ${tier}` };
  }
  
  // Check current token
  if (tierInfo.current_token && token === tierInfo.current_token) {
    return { valid: true };
  }
  
  // Check next token (if overlap active)
  if (tierInfo.overlap_active && tierInfo.next_token && token === tierInfo.next_token) {
    return { valid: true };
  }
  
  // Token not found
  return { valid: false, reason: 'Invalid token for this tier' };
}

/**
 * Get tier metadata without exposing actual tokens.
 * Useful for debugging and health checks.
 * 
 * @param tier - The tier to query
 * @returns Metadata about the tier's token state
 */
export async function getTierInfo(tier: string) {
  const state = await loadTokenState();
  const tierInfo = state.tiers[tier];
  
  if (!tierInfo) {
    return null;
  }
  
  return {
    tier,
    has_current: !!tierInfo.current_token,
    has_next: !!tierInfo.next_token,
    overlap_active: tierInfo.overlap_active,
    current_generated_at: tierInfo.current_generated_at,
    next_generated_at: tierInfo.next_generated_at
  };
}

/**
 * Check if token validation system is healthy.
 * Returns warnings for missing tokens or configuration issues.
 */
export async function checkTokenHealth(): Promise<{ healthy: boolean; warnings: string[] }> {
  const warnings: string[] = [];
  
  try {
    const state = await loadTokenState();
    
    // Check each tier
    for (const tier of ['tier1', 'tier2', 'tier3']) {
      const tierInfo = state.tiers[tier];
      
      if (!tierInfo) {
        warnings.push(`Missing configuration for ${tier}`);
        continue;
      }
      
      if (!tierInfo.current_token) {
        warnings.push(`${tier} has no current token`);
      }
      
      if (tierInfo.overlap_active && !tierInfo.next_token) {
        warnings.push(`${tier} overlap is active but no next token exists`);
      }
    }
    
    return {
      healthy: warnings.length === 0,
      warnings
    };
  } catch (error) {
    return {
      healthy: false,
      warnings: [`Token system error: ${error}`]
    };
  }
}
