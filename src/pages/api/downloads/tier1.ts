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
import { S3Client, GetObjectCommand } from '@aws-sdk/client-s3';
import { validateToken } from '@/lib/tokenValidator';
import { generateBundleUrls } from '@/lib/signedUrlGenerator';

// Force server-side rendering (Cloudflare Function)
export const prerender = false;

const TIER = 'tier1';
const INDEX_KEY = 'config/download_index_tier1.json';

export const GET: APIRoute = async ({ request, locals }) => {
  try {
    // Extract token from query parameters
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
    
    // Validate token
    const validation = await validateToken(token, TIER, locals.runtime);
    if (!validation.valid) {
      return new Response(JSON.stringify({
        success: false,
        error: validation.reason || 'Invalid token'
      }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    // Load download index from R2
    let indexData;
    try {
      const runtime = locals.runtime as any;
      const client = new S3Client({
        region: 'auto',
        endpoint: runtime?.env?.R2_ENDPOINT || process.env.R2_ENDPOINT,
        credentials: {
          accessKeyId: runtime?.env?.R2_ACCESS_KEY_ID || process.env.R2_ACCESS_KEY_ID || '',
          secretAccessKey: runtime?.env?.R2_SECRET_ACCESS_KEY || process.env.R2_SECRET_ACCESS_KEY || '',
        },
      });
      
      const command = new GetObjectCommand({
        Bucket: runtime?.env?.R2_BUCKET || process.env.R2_BUCKET || 'instrumetriq-datasets',
        Key: INDEX_KEY,
      });
      
      const response = await client.send(command);
      const body = await response.Body?.transformToString();
      
      if (!body) {
        throw new Error('Empty response from R2');
      }
      
      indexData = JSON.parse(body);
    } catch (error) {
      console.error('[API /downloads/tier1] Failed to load index from R2:', error);
      return new Response(JSON.stringify({
        success: false,
        error: 'Download index unavailable'
      }), {
        status: 503,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    // Generate signed URLs for daily files
    const dailyWithUrls = await Promise.all(
      indexData.daily.map(async (item: any) => {
        const { dataUrl, manifestUrl } = await generateBundleUrls(
          item.r2_key,
          item.manifest_key
        );
        
        return {
          date: item.date,
          size_bytes: item.size_bytes,
          download_url: dataUrl,
          manifest_url: manifestUrl
        };
      })
    );
    
    // Generate signed URLs for MTD if it exists
    let mtdWithUrls = null;
    if (indexData.mtd) {
      const { dataUrl, manifestUrl } = await generateBundleUrls(
        indexData.mtd.r2_key,
        indexData.mtd.manifest_key
      );
      
      mtdWithUrls = {
        month: indexData.mtd.month,
        days_included: indexData.mtd.days_included,
        size_bytes: indexData.mtd.size_bytes,
        download_url: dataUrl,
        manifest_url: manifestUrl
      };
    }
    
    // Return successful response
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
    console.error('[API /downloads/tier1] Unexpected error:', error);
    
    return new Response(JSON.stringify({
      success: false,
      error: 'Internal server error'
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
};
