/**
 * Token Validation Utility
 * 
 * Validates tier access tokens against the token state stored in R2.
 * Supports overlap window where both current and next tokens are valid.
 * 
 * Token state is stored in R2 at config/tier_tokens.json so both VPS
 * (for generation) and Cloudflare Pages (for validation) can access it.
 */

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
 * Load token state from R2 using the DATASETS bucket binding.
 * Cached for performance, reloaded on demand if state changes.
 */
let cachedState: TokenState | null = null;
let lastLoadTime = 0;
const CACHE_TTL = 60000; // 60 seconds

async function loadTokenState(runtime?: any): Promise<TokenState> {
  const now = Date.now();
  
  // Use cache if still fresh
  if (cachedState && (now - lastLoadTime) < CACHE_TTL) {
    console.log('[tokenValidator] Using cached token state');
    return cachedState;
  }
  
  try {
    console.log('[tokenValidator] Loading token state from R2');
    console.log('[tokenValidator] runtime:', !!runtime);
    console.log('[tokenValidator] runtime.env:', !!runtime?.env);
    console.log('[tokenValidator] runtime.env keys:', runtime?.env ? Object.keys(runtime.env) : 'N/A');
    console.log('[tokenValidator] DATASETS binding:', !!runtime?.env?.DATASETS);
    console.log('[tokenValidator] DATASETS type:', typeof runtime?.env?.DATASETS);
    
    // Get R2 bucket from Cloudflare Pages binding
    const bucket = runtime?.env?.DATASETS;
    if (!bucket) {
      const detail = !runtime ? 'runtime is undefined' : 
                     !runtime.env ? 'runtime.env is undefined' :
                     'DATASETS binding is undefined';
      throw new Error(`R2 bucket binding (DATASETS) not available: ${detail}`);
    }
    
    console.log('[tokenValidator] Fetching from R2:', TOKEN_STATE_KEY);
    // Fetch token state from R2
    const object = await bucket.get(TOKEN_STATE_KEY);
    if (!object) {
      throw new Error(`Token state file not found in R2: ${TOKEN_STATE_KEY}`);
    }
    
    console.log('[tokenValidator] Parsing token state');
    const text = await object.text();
    const state = JSON.parse(text) as TokenState;
    
    // Update cache
    cachedState = state;
    lastLoadTime = now;
    
    console.log('[tokenValidator] Token state loaded successfully');
    return state;
  } catch (error) {
    console.error('[tokenValidator] Failed to load token state:', error);
    throw new Error(`Token validation unavailable: ${error instanceof Error ? error.message : String(error)}`);
  }
}

/**
 * LEGACY: Load token state using AWS SDK for local development.
 * This is a fallback when R2 binding is not available (local dev only).
 */
async function loadTokenStateViaSDK(runtime?: any): Promise<TokenState> {
  try {
    const { S3Client, GetObjectCommand } = await import('@aws-sdk/client-s3');
    
    const endpoint = process.env.R2_ENDPOINT;
    const accessKeyId = process.env.R2_ACCESS_KEY_ID;
    const secretAccessKey = process.env.R2_SECRET_ACCESS_KEY;
    const bucketName = process.env.R2_BUCKET;
    
    if (!endpoint || !accessKeyId || !secretAccessKey || !bucketName) {
      throw new Error('R2 credentials not configured for local development');
    }
    
    const client = new S3Client({
      region: 'auto',
      endpoint,
      credentials: {
        accessKeyId,
        secretAccessKey,
      },
    });
    
    const command = new GetObjectCommand({
      Bucket: bucketName,
      Key: TOKEN_STATE_KEY,
    });
    
    const response = await client.send(command);
    if (!response.Body) {
      throw new Error('Empty response from R2');
    }
    
    const text = await response.Body.transformToString();
    const state = JSON.parse(text) as TokenState;
    
    // Update cache
    cachedState = state;
    lastLoadTime = Date.now();
    
    return state;
  } catch (error) {
    console.error('[tokenValidator] Failed to load token state via SDK:', error);
    throw new Error(`Token validation unavailable: ${error instanceof Error ? error.message : String(error)}`);
  }
}

/**
 * Validate a token for a specific tier.
 * 
 * @param token - The token to validate (43-character base64url string)
 * @param tier - The tier to validate against ('tier1', 'tier2', 'tier3')
 * @param runtime - Optional Astro runtime context (Astro.locals.runtime) for Cloudflare env access
 * @returns ValidationResult with valid flag and optional reason
 */
export async function validateToken(token: string, tier: string, runtime?: any): Promise<ValidationResult> {
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
  
  // Load state (try R2 binding first, fallback to SDK for local dev)
  let state: TokenState;
  try {
    if (runtime?.env?.DATASETS) {
      // Use R2 binding (Cloudflare Pages production)
      state = await loadTokenState(runtime);
    } else {
      // Use SDK (local development)
      state = await loadTokenStateViaSDK(runtime);
    }
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
 * @param runtime - Optional Astro runtime context
 * @returns Metadata about the tier's token state
 */
export async function getTierInfo(tier: string, runtime?: any) {
  const state = runtime?.env?.DATASETS 
    ? await loadTokenState(runtime)
    : await loadTokenStateViaSDK(runtime);
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
 * 
 * @param runtime - Optional Astro runtime context
 */
export async function checkTokenHealth(runtime?: any): Promise<{ healthy: boolean; warnings: string[] }> {
  const warnings: string[] = [];
  
  try {
    const state = runtime?.env?.DATASETS 
      ? await loadTokenState(runtime)
      : await loadTokenStateViaSDK(runtime);
    
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
