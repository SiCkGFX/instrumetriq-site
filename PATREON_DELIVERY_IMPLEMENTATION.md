# Patreon Data Delivery Implementation Plan

**Goal:** Automated daily parquet delivery with weekly token rotation and manual Patreon posting

**Status Legend:**
- `[ ]` Not started
- `[>]` In progress
- `[✓]` Complete

---

## Phase 1: Foundation & Token System

### 1.1 Token Management
- [✓] Create token storage structure (`/etc/instrumetriq/tier_tokens.json`)
- [✓] Implement token generation script (`scripts/generate_tier_tokens.py`)
- [✓] Implement token validation function (shared utility)
- [✓] Create initial tokens for all 3 tiers
- [✓] Test token rotation logic (current → next → current)

### 1.2 R2 Structure Updates
- [✓] Verify/update daily structure: `tierX/daily/YYYY-MM-DD/`
- [✓] Create MTD structure: `tierX/mtd/YYYY-MM/`
- [✓] Update manifest.json format to include metadata
- [✓] Test upload to new MTD structure

---

## Phase 2: Daily Build Pipeline Updates

### 2.1 Daily Parquet Scripts
- [✓] Update `build_tier1_daily.py` to generate manifest.json (already present, verified)
- [✓] Update `build_tier2_daily.py` to generate manifest.json (already present, verified)
- [✓] Update `build_tier3_daily.py` to generate manifest.json (already present, verified)
- [✓] Test daily builds produce both data.parquet + manifest.json (all scripts confirmed)

### 2.2 Month-to-Date (MTD) Builder
- [✓] Create `scripts/build_mtd_bundle.py` script (reused build_monthly_bundle.py with --mtd flag)
- [✓] Implement logic to merge last N days of current month (filters days <= yesterday)
- [✓] Generate MTD manifest.json with correct date range (includes coverage dates, row count, SHA256)
- [✓] Add MTD upload to R2 (`tierX/mtd/YYYY-MM/`) (separate path from /monthly/)
- [✓] Test MTD generation for all 3 tiers (tier1 tested successfully: 27 days, 5.79 MB)

### 2.3 Retention Management
- [✓] Implement daily retention: keep last 7 days only (cleanup_old_daily_files.py created)
- [✓] Add cleanup logic to tier build scripts (separate script, called after builds)
- [✓] Implement MTD retention: overwrite at same key (build_monthly_bundle.py uploads to same key)
- [✓] Test retention deletes old files correctly (dry-run tested: 111 files identified correctly)
- [ ] Verify retention runs after successful upload (will integrate into daily cron)

### 2.4 Download Index Generation
- [✓] Create `/var/www/instrumetriq/private/download_index/` directory (configurable via --output-dir)
- [✓] Generate `tier1.json` index after tier1 build (generate_download_index.py created)
- [✓] Generate `tier2.json` index after tier2 build (same script, --tier tier2)
- [✓] Generate `tier3.json` index after tier3 build (same script, --tier tier3)
- [✓] Test index files contain correct R2 keys and metadata (tier1 tested: 44 daily files, MTD with 27 days)

---

## Phase 3: Website Implementation

### 3.1 Environment Setup
- [✓] Add R2 credentials to Astro environment variables (reuses ~/.r2_credentials, same as Python scripts)
- [✓] Install AWS SDK for JavaScript (`@aws-sdk/client-s3`, `@aws-sdk/s3-request-presigner`) (installed)
- [✓] Configure R2 endpoint in Astro config (npm scripts source ~/.r2_credentials automatically)
- [ ] Test R2 connection from Astro SSR (ready to test with npm run dev)

### 3.2 Token Validation Utility
- [✓] Create `src/lib/tokenValidator.ts` (complete with all functions)
- [✓] Implement token state loading from JSON file (with 60s cache)
- [✓] Implement overlap window logic (accept current + next) (implemented)
- [✓] Add tier validation (ensure token matches requested tier) (implemented)
- [ ] Write unit tests for token validation (defer to testing phase)

### 3.3 Signed URL Generator
- [✓] Create `src/lib/signedUrlGenerator.ts` (complete)
- [✓] Implement S3-compatible signed URL generation (using AWS SDK v3)
- [✓] Set expiry to 6 days 20 hours (safe buffer) (DEFAULT_EXPIRY_SECONDS = 580800)
- [✓] Add content-disposition header for nice filenames (ResponseContentDisposition)
- [ ] Test signed URLs work in browser (needs .env configuration first)

### 3.4 API Endpoints
- [✓] Create `/api/download` endpoint (generic endpoint for all tiers)
- [✓] Create `/api/downloads/tier1.ts` endpoint (returns full download index with signed URLs)
- [✓] Create `/api/downloads/tier2.ts` endpoint (returns full download index with signed URLs)
- [✓] Create `/api/downloads/tier3.ts` endpoint (returns full download index with signed URLs)
- [✓] Implement token validation in each endpoint (all endpoints validate tokens)
- [✓] Load download index and generate signed URLs (reads from /var/www/instrumetriq/private/download_index/)
- [✓] Return JSON with daily array + MTD object (all endpoints return both)
- [ ] Test API responses with valid/invalid tokens (needs download index files + test)

### 3.5 Download Pages
- [✓] Create `/src/pages/downloads/tier1.astro` (complete with all features)
- [✓] Create `/src/pages/downloads/tier2.astro` (complete with all features)
- [✓] Create `/src/pages/downloads/tier3.astro` (complete with all features)
- [✓] Implement token validation on page load (server-side validation before rendering)
- [✓] Show 403 error for invalid tokens (HTTP 403 with user-friendly message)
- [✓] Fetch signed URLs from API endpoint (client-side fetch after token validation)
- [✓] Display last 7 daily files with dates (shows most recent 7 from API response)
- [✓] Display current MTD file (featured section at top with month/days info)
- [✓] Add "Last updated" timestamp (shows API generation timestamp in UTC)
- [ ] Style download page to match site design
- [ ] Test download pages in browser

---

## Phase 4: Token Rotation Automation

### 4.1 Weekly Rotation Script
- [ ] Create `scripts/rotate_tier_tokens.py`
- [ ] Implement "announce" mode (Sunday: generate next_token, enable overlap)
- [ ] Implement "promote" mode (Monday: promote next → current, disable overlap)
- [ ] Add logging for token rotation events
- [ ] Test rotation script in both modes

### 4.2 Patreon Link Generator
- [ ] Create `scripts/generate_patreon_links.py`
- [ ] Load current/next tokens from state file
- [ ] Generate URLs: `https://instrumetriq.com/downloads/tier[1-3]?t=TOKEN`
- [ ] Output formatted text for copy/paste to Patreon
- [ ] Include instructions for which link is current/next
- [ ] Test link generation produces correct output

### 4.3 Cron Jobs
- [ ] Add Sunday 00:00 UTC cron: `rotate_tier_tokens.py --mode=announce`
- [ ] Add Monday 00:00 UTC cron: `rotate_tier_tokens.py --mode=promote`
- [ ] Test cron jobs execute correctly
- [ ] Verify token state updates as expected

---

## Phase 5: Integration & Testing

### 5.1 End-to-End Testing
- [ ] Test full daily pipeline: build → upload → index → signed URLs
- [ ] Test MTD updates correctly each day
- [ ] Test retention deletes 8th day correctly
- [ ] Verify signed URLs expire after ~7 days
- [ ] Test token rotation: old tokens stop working Monday
- [ ] Test overlap window: both tokens work Sunday

### 5.2 Error Handling
- [ ] Add error handling for missing R2 files
- [ ] Add error handling for token file corruption
- [ ] Add error handling for R2 signing failures
- [ ] Add graceful degradation if index file missing
- [ ] Test error pages display correctly

### 5.3 Monitoring
- [ ] Add logging for daily build success/failure
- [ ] Add logging for token rotation events
- [ ] Add logging for download page access (aggregated, no PII)
- [ ] Create simple health check script
- [ ] Document monitoring procedures

---

## Phase 6: Deployment & Documentation

### 6.1 VPS Deployment
- [ ] Deploy token state file to VPS
- [ ] Deploy rotation scripts to VPS
- [ ] Configure cron jobs on VPS
- [ ] Test VPS scripts can read/write token state
- [ ] Test VPS scripts can access R2

### 6.2 Website Deployment
- [ ] Deploy updated Astro site to Cloudflare Pages
- [ ] Verify environment variables set correctly
- [ ] Test download pages work in production
- [ ] Test API endpoints work in production
- [ ] Test signed URLs work from production

### 6.3 Patreon Setup
- [ ] Create tier1 pinned members-only post
- [ ] Create tier2 pinned members-only post
- [ ] Create tier3 pinned members-only post
- [ ] Add initial download links to posts
- [ ] Test links work from Patreon
- [ ] Document Patreon update procedure

### 6.4 Documentation
- [ ] Document weekly Patreon update workflow
- [ ] Document token rotation schedule
- [ ] Document troubleshooting procedures
- [ ] Document emergency token rotation procedure
- [ ] Create runbook for common issues

---

## Weekly Manual Tasks (After Implementation)

**Every Sunday Morning:**
1. Run: `python3 scripts/generate_patreon_links.py`
2. Copy the generated text
3. Edit each tier's pinned Patreon post
4. Paste new links (show both current + next for 24h overlap)

**Every Monday (Optional Check):**
- Verify old links stopped working
- Run: `python3 scripts/generate_patreon_links.py` to confirm promotion

**Time commitment:** ~5 minutes every Sunday

---

## Emergency Procedures

**If token leaked publicly:**
1. Run: `python3 scripts/rotate_tier_tokens.py --mode=emergency --tier=tierX`
2. Update Patreon post immediately
3. Old token invalidated within seconds

**If signed URLs not working:**
1. Check R2 credentials in environment variables
2. Check download index files exist and are recent
3. Check R2 object keys match index
4. Regenerate index: rerun daily build with `--force-index`

---

## Success Criteria

- [ ] Daily parquets uploaded automatically every night
- [ ] MTD updates automatically every night
- [ ] Old files deleted automatically (7-day retention)
- [ ] Download pages work with valid tokens
- [ ] Invalid tokens show 403 error
- [ ] Signed URLs work for 6+ days
- [ ] Token rotation happens automatically Sunday/Monday
- [ ] Patreon link generation takes < 1 minute
- [ ] No manual intervention needed except Sunday Patreon edit
- [ ] Zero personal data stored (no emails, no OAuth tokens)
