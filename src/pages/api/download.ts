/**
 * API Endpoint: Download File
 * 
 * POST /api/download
 * 
 * Validates tier access token and returns signed R2 URL for downloading a specific file.
 * 
 * Request Body:
 * {
 *   "token": "abc...xyz",  // 43-character tier access token
 *   "tier": "tier1",       // tier1, tier2, or tier3
 *   "file_key": "tier1/daily/2026-01/2026-01-27/instrumetriq_tier1_daily_2026-01-27.parquet"
 * }
 * 
 * Response (success):
 * {
 *   "success": true,
 *   "signed_url": "https://...",
 *   "expires_in_seconds": 580800
 * }
 * 
 * Response (error):
 * {
 *   "success": false,
 *   "error": "Invalid token for this tier"
 * }
 */

import type { APIRoute } from 'astro';
import { validateToken } from '@/lib/tokenValidator';
import { generateSignedUrlWithFilename } from '@/lib/signedUrlGenerator';

export const POST: APIRoute = async ({ request }) => {
  try {
    // Parse request body
    const body = await request.json();
    const { token, tier, file_key } = body;
    
    // Validate required fields
    if (!token || !tier || !file_key) {
      return new Response(JSON.stringify({
        success: false,
        error: 'Missing required fields: token, tier, file_key'
      }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    // Validate token
    const validation = validateToken(token, tier);
    if (!validation.valid) {
      return new Response(JSON.stringify({
        success: false,
        error: validation.reason || 'Invalid token'
      }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    // Verify file_key matches requested tier (security check)
    if (!file_key.startsWith(`${tier}/`)) {
      return new Response(JSON.stringify({
        success: false,
        error: 'File key does not match requested tier'
      }), {
        status: 403,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    // Generate signed URL
    try {
      const signedUrl = await generateSignedUrlWithFilename(file_key);
      
      return new Response(JSON.stringify({
        success: true,
        signed_url: signedUrl,
        expires_in_seconds: 580800 // 6 days 20 hours
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });
    } catch (error) {
      console.error('[API /download] Failed to generate signed URL:', error);
      
      return new Response(JSON.stringify({
        success: false,
        error: 'Failed to generate download URL'
      }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      });
    }
  } catch (error) {
    console.error('[API /download] Request processing error:', error);
    
    return new Response(JSON.stringify({
      success: false,
      error: 'Invalid request format'
    }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }
};
