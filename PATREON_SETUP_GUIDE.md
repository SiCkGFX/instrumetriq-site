# Patreon Setup Guide (Instrumetriq)

This guide is a practical checklist + copy kit for setting up Instrumetriq’s Patreon page and membership tiers.

It is written to comply with:
- Brand: `branding/instrumetriq brand guide.txt`
- Scope: `docs/SSOT_TWITTER_SENTIMENT_PIPELINE.md` (X/Twitter-only)
- Wording guardrails: `docs/WORDING_RULES.md`

---

## 1) Non‑Negotiables (Keep This True)

### Scope truth
- Data sources: **X (Twitter) only** for sentiment. Do not imply other platforms.
- The dataset is **descriptive**. Do not imply prediction, “alpha”, guarantees, or causation.

### Tone rules (Instrumetriq)
- Calm, analytical, slightly austere.
- Evidence-first. Avoid hype.
- Prefer: “measured”, “observed”, “documented”, “descriptive”.
- Avoid: “unlock”, “powerful”, “revolutionary”, “AI-driven alpha”, “guaranteed”.

### Sentiment system wording (safe)
- OK: “custom-trained DistilBERT sentiment model”, “two-model arbitration”, “hybrid sentiment system”.
- Not OK: anything suggesting OpenAI/Anthropic “decision making”, predictions, or multi-platform sentiment.

---

## 2) Patreon Page Setup (What to Fill In)

Patreon’s UI changes over time, but the fields below are stable concepts.

### Page name
- Use: `instrumetriq` (lowercase, matches brand).

### Category / tags
- Use research/education/data/technology-style categories.
- Avoid anything that signals “signals”, “trading calls”, or “pump”.

### Page avatar
- Use the monochrome Instrumetriq wordmark.
- No cyan fill in the logo body. No gradients/shadows.

### Banner
- Dark background (very dark grey, not pure black).
- Minimal: wordmark + short descriptive line.
- Cyan only as a thin divider/indicator if necessary.

### Short tagline (one line)
Suggested options:
- “Crypto market microstructure + X (Twitter) sentiment, published daily.”
- “Measured narrative signals from X (Twitter), aligned to market snapshots.”

### About / Description (copy template)
Pasteable draft:

> Instrumetriq publishes daily research datasets: market microstructure snapshots for crypto trading pairs with aligned X (Twitter) sentiment.
>
> The system scrapes public X (Twitter) posts, scores them with a custom-trained DistilBERT sentiment model (hybrid two-model arbitration), and aggregates results into time windows.
>
> This is descriptive data for research and analysis. It is not real-time data, and it is not trading advice.

### External links
- Link to your site pages:
  - `/access` (pricing + access overview)
  - `/dataset` (schema + coverage)
  - `/research` (research artifacts)
  - `/legal/disclaimer`

### Welcome note (sent on join)
Keep it operational and calm.

Template:

> Thanks for supporting Instrumetriq.
>
> Your membership gives access to daily dataset downloads for your tier.
> New files are published daily.
>
> Notes:
> - Data is descriptive and intended for research.
> - Sentiment is sourced from X (Twitter) only.
> - Sentiment timing: captured in a ~1-hour window prior to the ~2-hour price monitoring session.

---

## 3) Membership Tiers (Recommended Structure)

These tiers mirror the website Access page.

### Tier 1 — Explorer ($5/mo)
**Title:** Explorer

**Short description:** Lightweight sentiment screening.

**Benefits (paste into Patreon):**
- Daily Tier 1 Parquet files (compact)
- 19 flat columns
- Sentiment summary (pos/neu/neg counts)
- Spot price + spread + 24h change
- Final liquidity score

**Best for:** Quick screening, correlation studies, learning.

### Tier 2 — Analyst ($15/mo)
**Title:** Analyst

**Short description:** Full market microstructure + sentiment.

**Benefits:**
- Daily Tier 2 Parquet files
- 8 nested column groups
- Order book depth at multiple levels
- Rich sentiment details (last 1-hour cycle)
- Derived analytics (depth imbalance, flow)

**Best for:** Research, dashboards, analysis workflows.

### Tier 3 — Researcher ($35/mo)
**Title:** Researcher

**Short description:** Complete data for ML and backtesting.

**Benefits:**
- Daily Tier 3 Parquet files
- 12 nested column groups
- 700+ price samples per entry (~10s intervals)
- Futures data (funding rate, open interest)
- Multi-window sentiment (current + trailing)

**Best for:** ML training, backtesting, quantitative research.

---

## 4) “How Access Works” (What to Say)

Keep this simple. Don’t over-explain security details.

Template:

> After subscribing, you’ll receive access to download links for your tier.
> Files are hosted on Cloudflare R2 and published daily.

If you want one extra line (optional):

> Links are refreshed periodically.

---

## 5) Timing Semantics (Professional Wording)

Use this wording consistently across Patreon and the site:

> Each record represents an approximately 2-hour monitoring session for a symbol. Sentiment is captured in a roughly 1-hour window immediately prior to that session and attached at admission to the active watchlist. This introduces a natural lead-time between sentiment observation and subsequent price evolution.

(Still descriptive; does not claim predictive power.)

---

## 6) Pinned Post Template (Public)

Use a calm pinned post to orient visitors.

Template:

Title: “How this dataset is produced (scope + cadence)”

Body:
- Source: X (Twitter) only (public posts)
- Data cadence: published daily
- Output: Parquet (analysis-ready)
- Purpose: descriptive research dataset (not trading advice)
- Where to start: link to `/dataset` for schema and `/research` for artifacts

---

## 7) Pinned Post Template (Members-Only)

Title: “Daily Downloads (Links + Notes)”

Body:
- Today’s date
- Links per tier (Tier 1 / Tier 2 / Tier 3)
- “Known issues” section (only if needed)
- Reminder: descriptive only; no predictive claims

---

## 8) Operational Checklist (Daily Reliability)

### What must happen daily
1. Archive day completes (hour 23 file closes around ~23:55 UTC for live days).
2. Tier builders run (Tier 3 → Tier 2 → Tier 1) and upload to R2.
3. Site refresh runs at 03:00 UTC.
4. Monitor alerts if anything fails.

### Monitoring
- The repo now has a tier build monitor:
  - `scripts/monitor_tier_builds.py`
  - Intended to run via cron every 10 minutes
  - Sends Telegram alerts when a tier is missing (local or R2)

---

## 9) Compliance / Safety Copy (Use Sparingly)

Suggested footer line for tier descriptions or pinned posts:

> Data is provided for research purposes and documents observed patterns. No predictive value, correlation, or trading edge is implied.

---

## 10) Before You Publish (Final Check)

- Re-read the About section and remove any hint of:
  - “signals”, “alpha”, “predict”, “beat the market”, “guaranteed”, “moon”, etc.
- Confirm you only mention **X (Twitter)** (not “social media platforms”).
- Keep the visual design minimal: dark background, restrained cyan.

---

## Notes

- If you need signed / expiring download links for R2, see `R2_SIGNED_URLS.md`.
