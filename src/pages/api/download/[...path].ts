/**
 * Download Proxy API
 * 
 * Proxies downloads from R2 through the API with token validation.
 * This keeps the R2 bucket private while allowing authenticated downloads.
 * 
 * GET /api/download/tier1/daily/2026-01/2026-01-27/data.parquet?token=xxx
 */

import type { APIRoute } from 'astro';

export const prerender = false;

const TOKEN_STATE_KEY = 'config/tier_tokens.json';

export const GET: APIRoute = async ({ params, request, locals }) => {
  try {
    const path = params.path;
    const url = new URL(request.url);
    const token = url.searchParams.get('token');
    
    if (!path) {
      return new Response('Missing path', { status: 400 });
    }
    
    if (!token) {
      return new Response('Missing token', { status: 400 });
    }
    
    // Determine tier from path (tier1/..., tier2/..., tier3/...)
    const tier = path.split('/')[0];
    if (!['tier1', 'tier2', 'tier3'].includes(tier)) {
      return new Response('Invalid tier in path', { status: 400 });
    }
    
    // Get R2 bucket
    const bucket = (locals.runtime as any)?.env?.DATASETS;
    if (!bucket) {
      return new Response('R2 bucket not available', { status: 500 });
    }
    
    // Validate token
    try {
      const tokenStateObj = await bucket.get(TOKEN_STATE_KEY);
      if (!tokenStateObj) {
        return new Response('Token state not found', { status: 500 });
      }
      
      const tokenState = JSON.parse(await tokenStateObj.text());
      const tierState = tokenState.tiers?.[tier];
      
      let tokenValid = false;
      if (tierState) {
        if (token === tierState.current_token) {
          tokenValid = true;
        } else if (tierState.overlap_active && token === tierState.next_token) {
          tokenValid = true;
        }
      }
      
      if (!tokenValid) {
        return new Response('Invalid or expired token', { status: 401 });
      }
    } catch (e) {
      return new Response(`Token validation error: ${e}`, { status: 500 });
    }
    
    // Fetch file from R2
    const object = await bucket.get(path);
    if (!object) {
      return new Response(`File not found: ${path}`, { status: 404 });
    }
    
    // Determine content type
    let contentType = 'application/octet-stream';
    if (path.endsWith('.parquet')) {
      contentType = 'application/vnd.apache.parquet';
    } else if (path.endsWith('.json')) {
      contentType = 'application/json';
    }
    
    // Get filename for Content-Disposition
    const filename = path.split('/').pop() || 'download';
    
    // Stream the file to the client
    return new Response(object.body, {
      status: 200,
      headers: {
        'Content-Type': contentType,
        'Content-Disposition': `attachment; filename="${filename}"`,
        'Content-Length': object.size.toString(),
        'Cache-Control': 'private, max-age=3600'
      }
    });
    
  } catch (error) {
    return new Response(`Download error: ${error}`, { status: 500 });
  }
};
