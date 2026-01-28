OPTION A IMPLEMENTATION PLAN (Instrumetriq)
Goal: Patreon members-only “tier link” + website token gate + signed R2 URLs + automated daily publishing + automated retention.
No Discord/Telegram. No user accounts. No email collection. No Patreon API posting.

======================================================================
0) DEFINITIONS / TARGET BEHAVIOR
======================================================================

Per tier (tier1 / tier2 / tier3):
- Provide:
  A) Daily parquet for previous ended UTC day
  B) Month-to-date (MTD) parquet for current UTC month (aggregated 1st..yesterday)
- Access method:
  - Patreon hosts a MEMBERS-ONLY pinned post per tier containing the tier URL with a token:
      https://instrumetriq.com/downloads/tier2?t=<TOKEN>
  - The website validates the token.
  - If valid, it shows a download page with signed R2 URLs for:
      - Last 7 daily files
      - Current MTD file
- Retention (as requested):
  - Daily: keep last 7 days (delete day 8 on publish)
  - MTD: overwrite daily (or delete yesterday’s MTD and upload today’s MTD)

Important note:
- Signed URLs can be valid for 7 days, but if you delete a parquet object earlier than 7 days, the URL won’t work (object no longer exists).
- Therefore retention MUST be >= the signed URL validity window.
  - You requested both “signed URLs last 7 days” and “daily parquets rotate removing the 7-day old parquet”.
  - That is compatible if you keep EXACTLY 7 days of objects and generate URLs that last <=7 days.
  - Practical recommendation: set signed URLs to 7 days minus a safety buffer (e.g. 6 days 20 hours) to avoid edge cases.

======================================================================
1) R2: BUCKET LAYOUT + OBJECT NAMING
======================================================================

Bucket: instrumetriq-datasets (public access disabled, keep private)

Per tier daily layout (already matches your current approach):
- tier1/daily/YYYY-MM-DD/data.parquet
- tier1/daily/YYYY-MM-DD/manifest.json
(similarly tier2, tier3)
This aligns with the documented structure. :contentReference[oaicite:0]{index=0} :contentReference[oaicite:1]{index=1} :contentReference[oaicite:2]{index=2}

Per tier month-to-date layout:
- tier1/mtd/YYYY-MM/data.parquet
- tier1/mtd/YYYY-MM/manifest.json
(or use tier1/monthly/YYYY-MM/..., but keep it consistent)

Manifest.json should include:
- tier number/name
- coverage start/end dates (UTC)
- build timestamp (UTC)
- schema version (v7)
- row counts (optional)
- parquet object key and size/hash (optional)

======================================================================
2) R2: SIGNED URL STRATEGY
======================================================================

You do NOT expose raw R2 object URLs.
Website generates time-limited signed URLs (S3-compatible signing) for:
- Each daily parquet in the “last 7 days” list
- The current MTD parquet

Signed URL parameters:
- HTTP method: GET
- Expiry: ~7 days (minus safety buffer)
- Response headers: optionally set content-disposition filename so users get nice file names

Security property:
- Even if someone copies a signed URL, it expires automatically.
- The tier token gate protects the “menu” (download page). The signed URL protects the object access window.

======================================================================
3) WEBSITE: WHAT YOU ADD
======================================================================

Add three public routes (stable URLs):
- /downloads/tier1
- /downloads/tier2
- /downloads/tier3

Each route requires query param:
- ?t=<token>

If token invalid:
- show 403-style page:
  - “Access denied. Please open the latest link from your Patreon tier post.”

If token valid:
- render a page with:
  - “Last updated: <UTC timestamp>”
  - “Daily files (last 7 UTC days):”
      [2026-02-13] Download
      [2026-02-14] Download
      ...
  - “Month-to-date (YYYY-MM):”
      [YYYY-MM MTD] Download

The page should not embed R2 credentials.
It should fetch signed URLs from the server (not generated client-side).

Implementation detail:
- Use a server-side endpoint per tier that returns JSON:
  - /api/downloads/tier1?t=...
  - /api/downloads/tier2?t=...
  - /api/downloads/tier3?t=...
Response JSON includes:
- daily: [{date, filename, signed_url, expires_at}]
- mtd: {month, filename, signed_url, expires_at}
- metadata: {tier, generated_at_utc, coverage_notes}

The HTML page calls the API and renders the list.

======================================================================
4) TOKEN GATING (THE CORE OF OPTION A)
======================================================================

Per tier you maintain token state with overlap:
- current_token: token that is active now
- next_token: token that will become active at next rotation
- overlap window: 1 day (announce next_token before current_token expires)

Token rules:
- On normal days:
  - accept current_token only
- On “announcement day” (the day before rotation):
  - accept BOTH current_token and next_token
- On rotation moment:
  - drop old current_token
  - promote next_token -> current_token
  - generate a fresh next_token for the next cycle (optional)

Where token state lives:
- simplest: JSON file on VPS (not in git), e.g. /etc/instrumetriq/tier_tokens.json
- or environment variables (less ergonomic for overlap)
- or Cloudflare KV / D1 (optional; not required)

Token format:
- random 32+ bytes (base64url or hex)
- never guessable

No patron identity stored. No emails stored.

======================================================================
5) DAILY PIPELINE (PARQUETS + RETENTION)
======================================================================

Assumptions:
- Your VPS cron produces and uploads the daily parquet for “previous ended UTC day”
- Tier build times vary (00:10..00:30 UTC depending on tier)

Daily job per tier (or one job orchestrating tiers in order):
Step A: Build daily parquet for YESTERDAY (UTC)
- Produce data.parquet + manifest.json locally
- Upload to:
    tierX/daily/YYYY-MM-DD/data.parquet
    tierX/daily/YYYY-MM-DD/manifest.json

Step B: Build MTD parquet for CURRENT month up to YESTERDAY
- Produce data.parquet + manifest.json locally
- Upload to:
    tierX/mtd/YYYY-MM/data.parquet
    tierX/mtd/YYYY-MM/manifest.json
This overwrites the previous day’s MTD object at the same key (or you delete then upload).

Step C: Enforce retention (as requested)
- Daily retention:
  - List daily prefixes for tierX/daily/
  - Keep newest 7 day-folders (YYYY-MM-DD)
  - Delete day-folder objects older than the newest 7 (data.parquet + manifest.json)
- MTD retention:
  - If you overwrite at the same key, nothing else required.
  - If you version MTD by day, delete yesterday’s MTD version and keep only latest.

Step D: Update website “index JSON” (optional but recommended)
- Write a small “availability index” per tier (server-side) that records:
  - which 7 daily dates exist
  - which MTD month exists
  - their R2 object keys
This index lets the website quickly produce signed URLs without listing R2 every request.

======================================================================
6) WEBSITE “AVAILABILITY INDEX” (RECOMMENDED FOR SPEED + SIMPLICITY)
======================================================================

On VPS after uploads:
- Generate a file per tier, e.g.:
    /var/www/instrumetriq/private/download_index/tier1.json
containing:
- daily_keys: [ "tier1/daily/2026-02-13/data.parquet", ... (7) ]
- mtd_key: "tier1/mtd/2026-02/data.parquet"
- generated_at_utc: "..."

The website API endpoint:
- validates token
- reads tier index JSON
- signs each key (7 daily + 1 mtd)
- returns signed URLs to the client

This avoids:
- listing R2 on every user page load
- mismatches between “what exists” and “what you want to show”

======================================================================
7) WEEKLY TOKEN ROTATION SCHEDULE WITH 1-DAY ADVANCE NOTICE
======================================================================

Pick a weekly rotation anchor:
Example: Rotation happens Monday 00:00 UTC.
Announcement day is Sunday 00:00 UTC (24h overlap).

Cron schedule (VPS):
- Sunday 00:00 UTC:
  - Generate next_token for each tier
  - Update token state so that BOTH current_token and next_token are accepted
  - (Manual step) You update the Patreon pinned post for each tier to include the “new link”
    - You can edit the post text to show:
      - “Current link (works until Monday): ...?t=current”
      - “New link (starts now, becomes required Monday): ...?t=next”
- Monday 00:00 UTC:
  - Promote next_token -> current_token
  - Invalidate old current_token (now only the new one works)
  - Generate a fresh next_token placeholder for next week (optional)
  - Website immediately stops accepting old bookmarked links

What you must do on Patreon:
- Patreon cannot be auto-posted via API, so you do a manual edit once per week.
- Keep it minimal: same post, edit 2 URLs once weekly. :contentReference[oaicite:3]{index=3}

QoL:
- If you don’t want “two links” visible, you can replace the token in the same link on Sunday.
  - But you explicitly want advance notice and overlap, so show both.

======================================================================
8) WHAT THIS PREVENTS / WHAT IT DOESN’T
======================================================================

Prevents:
- Unsubscribe + keep downloading forever:
  - They can keep using the token they bookmarked only until the next rotation.
  - After Monday 00:00 UTC they lose access.
- “Change 1 to 3” guessing:
  - tier3 requires a different token.

Doesn’t fully prevent:
- A paying user sharing the token publicly during the week.
Mitigation:
- Weekly rotation limits the abuse window to at most 7 days.
- If abuse becomes a problem, rotate more frequently (e.g., twice per week) without changing architecture.

======================================================================
9) REQUIRED CONFIG / SECRETS (WHERE THEY LIVE)
======================================================================

On VPS / server:
- R2 access key / secret (or equivalent credentials) used ONLY server-side to sign URLs
- Token state file (tier tokens)
- Download index files (optional but recommended)

On website:
- Server-side signing code uses the R2 credentials
- API endpoints validate token + generate signed URLs

Nothing stored:
- No patron emails
- No patron names
- No patron IDs
- No OAuth tokens

======================================================================
10) MONITORING / FAILURE MODES (MINIMUM VIABLE)
======================================================================

Daily publishing checks:
- Confirm daily parquet exists for yesterday for each tier
- Confirm MTD exists/updated for current month
- Confirm retention ran (only 7 daily days remain)

Token rotation checks:
- Sunday: ensure next_token generated and overlap enabled
- Monday: ensure old token invalidated
- Log each token change with timestamps (do not log the token itself; log token hash prefix)

User-facing:
- If token invalid, the error page tells them to open the latest Patreon post.

======================================================================
11) DELIVERABLES LIST (WHAT YOU WILL IMPLEMENT)
======================================================================

R2:
- Ensure object keys follow:
  - tierX/daily/YYYY-MM-DD/data.parquet + manifest.json
  - tierX/mtd/YYYY-MM/data.parquet + manifest.json
- Add retention delete step for daily (keep last 7) and MTD overwrite

VPS cron jobs:
- Daily tier build/upload + MTD build/upload + retention delete
- Weekly token rotation:
  - Sunday overlap enable + next token generation
  - Monday promotion + old token invalidate

Website:
- Routes:
  - /downloads/tier1, /downloads/tier2, /downloads/tier3
- API:
  - /api/downloads/tier1?t=...
  - /api/downloads/tier2?t=...
  - /api/downloads/tier3?t=...
- Token validator:
  - checks current + (if overlap active) next token
- Signed URL generator:
  - signs 7 daily + 1 MTD keys from the tier index

Patreon:
- 1 pinned members-only post per tier
- Weekly manual edit:
  - add/replace “New link” on Sunday
  - optionally remove “Old link” on Monday after rotation

======================================================================
12) NOTES ABOUT YOUR CURRENT R2 DIRECTORY SCREENSHOTS
======================================================================

Your current R2 layout already matches the daily folder-per-day pattern (tier1/daily/YYYY-MM-DD/...).
That is the correct foundation for this plan. :contentReference[oaicite:4]{index=4}

======================================================================
END OF PLAN
======================================================================
