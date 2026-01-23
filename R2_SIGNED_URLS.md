# R2 Signed URLs for Patreon Access Control

This document describes how to generate time-limited signed URLs for Cloudflare R2, enabling secure data distribution to Patreon subscribers.

---

## Why Signed URLs?

Raw R2 URLs can be bookmarked and reused indefinitely. Signed URLs solve this by:

- **Expiring after a set duration** (e.g., 7 days, 30 days)
- **Preventing permanent access** after unsubscribing
- **Allowing controlled distribution** via Patreon posts

---

## Option 1: boto3 Script (Simple Monthly Refresh)

Generate signed URLs locally and post them to Patreon each month.

### Setup

1. Create R2 API credentials:
   - Cloudflare Dashboard → R2 → Manage R2 API Tokens
   - Create a token with **Object Read** permission for your bucket
   - Save the Access Key ID and Secret Access Key

2. Install boto3:
   ```bash
   pip install boto3
   ```

3. Configure environment variables:
   ```bash
   export R2_ACCOUNT_ID="your-account-id"
   export R2_ACCESS_KEY_ID="your-access-key"
   export R2_SECRET_ACCESS_KEY="your-secret-key"
   export R2_BUCKET_NAME="instrumetriq-data"
   ```

### Example Script

```python
#!/usr/bin/env python3
"""Generate signed URLs for R2 tier data."""

import boto3
import os
from datetime import datetime

# Configuration
ACCOUNT_ID = os.environ['R2_ACCOUNT_ID']
ACCESS_KEY = os.environ['R2_ACCESS_KEY_ID']
SECRET_KEY = os.environ['R2_SECRET_ACCESS_KEY']
BUCKET = os.environ.get('R2_BUCKET_NAME', 'instrumetriq-data')

# Expiry in seconds (30 days)
EXPIRY_SECONDS = 30 * 24 * 60 * 60

# Initialize R2 client
r2 = boto3.client(
    's3',
    endpoint_url=f'https://{ACCOUNT_ID}.r2.cloudflarestorage.com',
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    region_name='auto'
)

def generate_signed_url(key: str, expires_in: int = EXPIRY_SECONDS) -> str:
    """Generate a presigned URL for an R2 object."""
    return r2.generate_presigned_url(
        'get_object',
        Params={'Bucket': BUCKET, 'Key': key},
        ExpiresIn=expires_in
    )

def list_tier_files(tier: str) -> list[str]:
    """List all files in a tier prefix."""
    paginator = r2.get_paginator('list_objects_v2')
    keys = []
    for page in paginator.paginate(Bucket=BUCKET, Prefix=f'{tier}/'):
        for obj in page.get('Contents', []):
            keys.append(obj['Key'])
    return keys

def generate_tier_urls(tier: str):
    """Generate signed URLs for all files in a tier."""
    print(f"\n=== {tier.upper()} ===")
    print(f"Expiry: {EXPIRY_SECONDS // 86400} days from now")
    print()
    
    keys = list_tier_files(tier)
    for key in sorted(keys):
        if key.endswith('.parquet') or key.endswith('.jsonl.gz'):
            url = generate_signed_url(key)
            print(f"{key}")
            print(f"  {url}")
            print()

if __name__ == '__main__':
    import sys
    
    tiers = sys.argv[1:] if len(sys.argv) > 1 else ['tier1', 'tier2', 'tier3']
    
    print(f"Generated: {datetime.utcnow().isoformat()}Z")
    for tier in tiers:
        generate_tier_urls(tier)
```

### Usage

```bash
# Generate URLs for all tiers
python scripts/generate_signed_urls.py

# Generate URLs for specific tier
python scripts/generate_signed_urls.py tier1

# Redirect to file for Patreon post
python scripts/generate_signed_urls.py tier1 > /tmp/tier1_links.txt
```

### Workflow

1. Run the script at the start of each month
2. Copy the output into a **Patreon-only post** for each tier
3. When subscribers access the post, they get working links
4. After 30 days, links expire—new month, new links
5. Unsubscribed users lose access to new posts, old links expire naturally

---

## Option 2: Cloudflare Worker (On-Demand Signing)

More secure: validates Patreon membership in real-time before generating short-lived URLs.

### Architecture

```
User → Worker → Patreon OAuth → (verified?) → Generate 1-hour signed URL → User downloads
```

### Worker Code (Conceptual)

```javascript
// wrangler.toml binds R2_BUCKET and secrets for R2 credentials

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    
    // Validate Patreon access token from header or cookie
    const patreonToken = request.headers.get('Authorization')?.replace('Bearer ', '');
    if (!patreonToken) {
      return new Response('Unauthorized', { status: 401 });
    }
    
    // Verify membership with Patreon API
    const membership = await verifyPatreonMembership(patreonToken, env);
    if (!membership.active) {
      return new Response('Subscription required', { status: 403 });
    }
    
    // Check tier access
    const requestedTier = url.searchParams.get('tier');
    if (!hasAccessToTier(membership.tier, requestedTier)) {
      return new Response('Tier not included in your subscription', { status: 403 });
    }
    
    // Generate short-lived signed URL (1 hour)
    const objectKey = url.searchParams.get('key');
    const signedUrl = await generateSignedUrl(env, objectKey, 3600);
    
    // Return redirect or JSON with URL
    return Response.redirect(signedUrl, 302);
  }
};

async function verifyPatreonMembership(token, env) {
  const response = await fetch('https://www.patreon.com/api/oauth2/v2/identity?include=memberships', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  const data = await response.json();
  // Parse membership tier from response
  // Return { active: boolean, tier: 'explorer' | 'researcher' | 'full_archive' }
}

async function generateSignedUrl(env, key, expiresIn) {
  // Use @aws-sdk/client-s3 or manual signing
  // R2 is S3-compatible, so standard presigning works
}
```

### Pros & Cons

| Aspect | Option 1 (boto3) | Option 2 (Worker) |
|--------|------------------|-------------------|
| **Setup complexity** | Low | Medium-High |
| **Security** | Good (30-day window) | Excellent (real-time) |
| **Maintenance** | Monthly manual step | Automatic |
| **URL sharing risk** | Medium (30 days) | Low (1 hour) |
| **Patreon integration** | Via posts | Via OAuth |
| **Cost** | Free | Worker requests (low) |

---

## Recommendation

**Start with Option 1** for simplicity:
1. Generate 30-day signed URLs monthly
2. Post to Patreon as tier-locked content
3. Monitor for abuse (unlikely at small scale)

**Upgrade to Option 2** if:
- You have many subscribers and want real-time control
- You observe URL sharing abuse
- You want a seamless "click to download" UX without copy-pasting URLs

---

## Next Steps

1. [ ] Create R2 API token with Object Read permission
2. [ ] Add credentials to environment or secrets manager
3. [ ] Create `scripts/generate_signed_urls.py` based on example above
4. [ ] Test with a single file before full rollout
5. [ ] Set up Patreon tiers matching Explorer/Researcher/Full Archive
6. [ ] Post first batch of signed URLs to Patreon

---

## References

- [Cloudflare R2 Documentation](https://developers.cloudflare.com/r2/)
- [R2 Presigned URLs](https://developers.cloudflare.com/r2/api/s3/presigned-urls/)
- [Patreon API](https://docs.patreon.com/)
- [boto3 generate_presigned_url](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html)
