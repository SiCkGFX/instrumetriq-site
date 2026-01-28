# R2 Signed URLs (Patreon Integration)

This strategy prevents "subscribe-and-dash" behavior. By using **Signed URLs** instead of public links, you ensure that:
1.  **Access is Temporary:** Links expire after 7 days (default). Old posts effectively "lock" themselves.
2.  **Access is Revocable:** Unsubscribed users lose access to *future* posts, and their access to *past* posts expires naturally.

## 1. Prerequisites

Ensure you have your R2 credentials configured on your VPS/machine.

1.  **Install Dependencies:**
    ```bash
    pip install boto3 pyarrow
    ```

2.  **Verify Credentials:**
    The scripts look for `~/.r2_credentials` or environment variables:
    ```bash
    export R2_ENDPOINT="https://<ACCOUNT_ID>.r2.cloudflarestorage.com"
    export R2_ACCESS_KEY_ID="<ACCESS_KEY>"
    export R2_SECRET_ACCESS_KEY="<SECRET_KEY>"
    export R2_BUCKET="instrumetriq-data"
    ```

---

## 2. Daily Workflow (Standard)

Every day, post the new data "slice".

### Step 1: Run the generator
```bash
# Generates links for Yesterday (defaults to latest available day)
python3 scripts/generate_patreon_links.py
```

### Step 2: Create the Daily Post
*   **Title:** `Daily Data: 2026-01-26`
*   **Body:** "Here is today's data slice. Downloads expire in 7 days."
*   **Attach:** The links generated above.

---

## 3. Monthly Workflow (The Archives)

To give new subscribers access to past data without giving away the farm, we bundle data into **Monthly Parquet Files**.

### Step 1: Build the Bundle (Once per month)
On the 1st/2nd of a new month (e.g., Feb 1st), build the bundle for the previous month (Jan).

```bash
# Build & Upload for all tiers
python3 scripts/build_monthly_bundle.py --tier tier1 --month 2026-01 --upload
python3 scripts/build_monthly_bundle.py --tier tier2 --month 2026-01 --upload
python3 scripts/build_monthly_bundle.py --tier tier3 --month 2026-01 --upload
```
*   This downloads all daily files from R2, merges them, and uploads a single file: `tier3/monthly/2026-01/data.parquet`.

### Step 2: Generate Links for the Archive
```bash
python3 scripts/generate_patreon_links.py --month 2026-01
```

### Step 3: Update the "Pinned Post"
Maintain a **single Pinned Post** on Patreon titled "📚 Data Archives (2025-2026)".
*   Edit this post to add the new month's link.
*   **Note:** These links expire in 7 days.
*   **Strategy:** You don't need to keep valid links up 24/7. When a new user asks for archives, or once a week, simple re-run the generator and update the pinned post.
*   *Alternatively: Just send the archive link via DM to new annual subscribers.*

---

## 4. Advanced & Troubleshooting

**"File not found in R2"**
*   Daily: The nightly build script (`build_tierX_daily.py`) failed. Check logs.
*   Monthly: You forgot to run `build_monthly_bundle.py` first.

**"Bundle contains 0 rows?"**
*   The build script will warn you if it can't find daily files. Ensure the month actually has data in R2.

**"Access Denied" (XML Error)**
*   Incorrect Endpoint formatting. Ensure `R2_ENDPOINT` has NO path suffix (just `https://....com`).
