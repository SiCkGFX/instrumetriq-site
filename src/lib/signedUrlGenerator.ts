/**
 * Signed URL Generator
 * 
 * Generates time-limited signed URLs for R2 object downloads.
 * Uses Cloudflare R2 native binding in production (Cloudflare Pages).
 * Falls back to AWS SDK with credentials for local development.
 */

import { S3Client, GetObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';

// R2 Configuration from environment variables (for local dev only)
const R2_ENDPOINT = import.meta.env.R2_ENDPOINT || process.env.R2_ENDPOINT;
const R2_ACCESS_KEY_ID = import.meta.env.R2_ACCESS_KEY_ID || process.env.R2_ACCESS_KEY_ID;
const R2_SECRET_ACCESS_KEY = import.meta.env.R2_SECRET_ACCESS_KEY || process.env.R2_SECRET_ACCESS_KEY;
const R2_BUCKET = import.meta.env.R2_BUCKET || process.env.R2_BUCKET;

// Default expiry: 6 days 20 hours (580800 seconds)
// This provides a safe buffer before the 7-day maximum
const DEFAULT_EXPIRY_SECONDS = 6 * 24 * 60 * 60 + 20 * 60 * 60; // 580800

/**
 * Initialize R2 client (S3-compatible)
 * Uses local credentials for development.
 */
function getR2Client(): S3Client {
  if (!R2_ENDPOINT || !R2_ACCESS_KEY_ID || !R2_SECRET_ACCESS_KEY) {
    throw new Error('R2 credentials not configured for local development. Ensure ~/.r2_credentials is sourced.');
  }
  
  // R2_ENDPOINT is already a full URL from ~/.r2_credentials
  return new S3Client({
    region: 'auto',
    endpoint: R2_ENDPOINT,
    credentials: {
      accessKeyId: R2_ACCESS_KEY_ID,
      secretAccessKey: R2_SECRET_ACCESS_KEY,
    },
  });
}

/**
 * Generate a signed URL for downloading an R2 object.
 * 
 * @param key - The R2 object key (e.g., 'tier1/daily/2026-01/2026-01-27/data.parquet')
 * @param expirySeconds - How long the URL should be valid (default: 6 days 20 hours)
 * @param filename - Optional custom filename for download (sets Content-Disposition header)
 * @returns Signed URL string
 */
export async function generateSignedUrl(
  key: string,
  expirySeconds: number = DEFAULT_EXPIRY_SECONDS,
  filename?: string
): Promise<string> {
  if (!R2_BUCKET) {
    throw new Error('R2_BUCKET not configured');
  }
  
  const client = getR2Client();
  
  // Build command with optional content-disposition for nice filenames
  const params: any = {
    Bucket: R2_BUCKET,
    Key: key,
  };
  
  // Set content-disposition if filename provided
  // This makes browsers download with the specified filename
  if (filename) {
    params.ResponseContentDisposition = `attachment; filename="${filename}"`;
  }
  
  const command = new GetObjectCommand(params);
  
  try {
    const signedUrl = await getSignedUrl(client, command, {
      expiresIn: expirySeconds,
    });
    
    return signedUrl;
  } catch (error) {
    console.error('[SignedUrlGenerator] Failed to generate signed URL:', error);
    throw new Error(`Failed to generate signed URL: ${error}`);
  }
}

/**
 * Generate a signed URL with a friendly filename.
 * Extracts date and tier from key to construct descriptive filename.
 * 
 * @param key - The R2 object key
 * @param expirySeconds - How long the URL should be valid
 * @returns Signed URL with content-disposition header
 */
export async function generateSignedUrlWithFilename(
  key: string,
  expirySeconds: number = DEFAULT_EXPIRY_SECONDS
): Promise<string> {
  // Extract filename from key (last part after /)
  const parts = key.split('/');
  const originalFilename = parts[parts.length - 1];
  
  return generateSignedUrl(key, expirySeconds, originalFilename);
}

/**
 * Generate signed URLs for both parquet and manifest files.
 * Returns both URLs in an object for convenience.
 * 
 * @param dataKey - The R2 key for the data parquet file
 * @param manifestKey - The R2 key for the manifest.json file
 * @param expirySeconds - How long the URLs should be valid
 * @returns Object with { dataUrl, manifestUrl }
 */
export async function generateBundleUrls(
  dataKey: string,
  manifestKey: string,
  expirySeconds: number = DEFAULT_EXPIRY_SECONDS
): Promise<{ dataUrl: string; manifestUrl: string }> {
  const [dataUrl, manifestUrl] = await Promise.all([
    generateSignedUrlWithFilename(dataKey, expirySeconds),
    generateSignedUrlWithFilename(manifestKey, expirySeconds),
  ]);
  
  return { dataUrl, manifestUrl };
}

/**
 * Validate R2 configuration at startup.
 * Throws error if configuration is invalid.
 */
export function validateR2Config(): void {
  const required = [
    { name: 'R2_ENDPOINT', value: R2_ENDPOINT },
    { name: 'R2_ACCESS_KEY_ID', value: R2_ACCESS_KEY_ID },
    { name: 'R2_SECRET_ACCESS_KEY', value: R2_SECRET_ACCESS_KEY },
    { name: 'R2_BUCKET', value: R2_BUCKET },
  ];
  
  const missing = required.filter(item => !item.value).map(item => item.name);
  
  if (missing.length > 0) {
    throw new Error(`Missing R2 configuration: ${missing.join(', ')}. Ensure ~/.r2_credentials is sourced.`);
  }
}
