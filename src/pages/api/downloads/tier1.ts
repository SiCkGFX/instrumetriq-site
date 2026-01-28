/**
 * API Endpoint: Get Tier 1 Downloads
 * 
 * GET /api/downloads/tier1?token=abc...xyz
 * 
 * Returns all available Tier 1 downloads with signed URLs.
 * Validates token before returning any data.
 * 
 * Response (success):
 * {
 *   "success": true,
 *   "tier": "tier1",
 *   "daily": [
 *     {
 *       "date": "2026-01-27",
 *       "size_bytes": 194596,
 *       "download_url": "https://...",
 *       "manifest_url": "https://..."
 *     },
 *     ...
 *   ],
 *   "mtd": {
 *     "month": "2026-01",
 *     "days_included": 27,
 *     "size_bytes": 6074808,
 *     "download_url": "https://...",
 *     "manifest_url": "https://..."
 *   },
 *   "generated_at": "2026-01-28T12:00:00Z"
 * }
 * 
 * Response (error):
 * {
 *   "success": false,
 *   "error": "Invalid token for this tier"
 * }
 */

import type { APIRoute } from 'astro';

// Force server-side rendering (Cloudflare Function)
export const prerender = false;

const TIER = 'tier1';
const INDEX_KEY = 'config/download_index_tier1.json';
const TOKEN_STATE_KEY = 'config/tier_tokens.json';

export const GET: APIRoute = async ({ request, locals }) => {
  try {
    const url = new URL(request.url);
    const token = url.searchParams.get('token');
    
    if (!token) {
      return new Response(JSON.stringify({
        success: false,
        error: 'Missing token parameter'
      }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    // Get R2 bucket from runtime binding
    const bucket = (locals.runtime as any)?.env?.DATASETS;
    if (!bucket) {
      return new Response(JSON.stringify({
        success: false,
        error: 'R2 bucket binding not available',
        debug: {
          runtimeExists: !!locals.runtime,
          envExists: !!(locals.runtime as any)?.env,
          envKeys: (locals.runtime as any)?.env ? Object.keys((locals.runtime as any).env) : []
        }
      }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    // Step 1: Validate token against R2 token state
    let tokenValid = false;
    try {
      const tokenStateObj = await bucket.get(TOKEN_STATE_KEY);
      if (!tokenStateObj) {
        return new Response(JSON.stringify({
          success: false,
          error: 'Token state not found in R2'
        }), {
          status: 500,
          headers: { 'Content-Type': 'application/json' }
        });
      }
      
      const tokenState = JSON.parse(await tokenStateObj.text());
      const tierState = tokenState.tiers?.[TIER];
      
      if (tierState) {
        if (token === tierState.current_token) {
          tokenValid = true;
        } else if (tierState.overlap_active && token === tierState.next_token) {
          tokenValid = true;
        }
      }
    } catch (e) {
      return new Response(JSON.stringify({
        success: false,
        error: `Token validation error: ${e instanceof Error ? e.message : String(e)}`
      }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    if (!tokenValid) {
      return new Response(JSON.stringify({
        success: false,
        error: 'Invalid or expired token'
      }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    // Step 2: Load download index from R2
    let indexData;
    try {
      const indexObj = await bucket.get(INDEX_KEY);
      if (!indexObj) {
        return new Response(JSON.stringify({
          success: false,
          error: `Download index not found: ${INDEX_KEY}`
        }), {
          status: 500,
          headers: { 'Content-Type': 'application/json' }
        });
      }
      
      indexData = JSON.parse(await indexObj.text());
    } catch (e) {
      return new Response(JSON.stringify({
        success: false,
        error: `Index load error: ${e instanceof Error ? e.message : String(e)}`
      }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    // Step 3: Generate download URLs through our proxy API
    const baseUrl = new URL(request.url).origin;
    
    const dailyWithUrls = (indexData.daily || []).map((item: any) => {
      return {
        date: item.date,
        size_bytes: item.size_bytes,
        download_url: `${baseUrl}/api/download/${item.r2_key}?token=${encodeURIComponent(token)}`,
        manifest_url: `${baseUrl}/api/download/${item.manifest_key}?token=${encodeURIComponent(token)}`
      };
    });
    
    let mtdWithUrls = null;
    if (indexData.mtd) {
      mtdWithUrls = {
        month: indexData.mtd.month,
        days_included: indexData.mtd.days_included,
        size_bytes: indexData.mtd.size_bytes,
        download_url: `${baseUrl}/api/download/${indexData.mtd.r2_key}?token=${encodeURIComponent(token)}`,
        manifest_url: `${baseUrl}/api/download/${indexData.mtd.manifest_key}?token=${encodeURIComponent(token)}`
      };
    }
    
    return new Response(JSON.stringify({
      success: true,
      tier: TIER,
      daily: dailyWithUrls,
      mtd: mtdWithUrls,
      generated_at: new Date().toISOString()
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
    
  } catch (error) {
    return new Response(JSON.stringify({
      success: false,
      error: `Unexpected error: ${error instanceof Error ? error.message : String(error)}`,
      stack: error instanceof Error ? error.stack : undefined
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
};
