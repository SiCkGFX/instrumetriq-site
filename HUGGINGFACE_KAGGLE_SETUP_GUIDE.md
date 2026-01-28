# Hugging Face & Kaggle Setup Guide (Instrumetriq)

This guide defines the strategy and copy for listing **Free Sample** datasets on Hugging Face (HF) and Kaggle.

**Goal:** Drive traffic to the paid Patreon tiers by offering high-quality, non-commercial samples to researchers and students.

**Strategy:** "The Rolling Lag"
- Release a small, static sample (e.g., "Jan 2024").
- Optional: Update it monthly with data that is 3+ months old (keeps listing fresh, but protects premium real-time value).

---

## 1) Asset Prep Checklist

Before creating listings, prepare these assets:

*   **The Data File:** A single file named `instrumetriq_sample_jan2024.parquet`.
    *   *Content:* Tier 1 (Explorer) schema.
    *   *Range:* One full month (e.g., Jan 1 - Jan 31).
*   **Cover Image (Kaggle):**
    *   *Size:* 1136 x 360 px (recommended).
    *   *Style:* Dark background, "Instrumetriq" logo, text "Research Sample: Crypto Sentiment".
    *   *Format:* PNG/JPG.
*   **Starter Notebook code:** Simple Python script to load the parquet and plot `price` vs `sentiment` (crucial for Kaggle visibility).

---

## 2) Hugging Face Setup

Hugging Face is the search engine for AI researchers.

**Repository Name:** `instrumetriq/crypto-sentiment-market-data-sample`

### A. Dataset Card (`README.md`)
Create this file at the root of your HF dataset repository.

```markdown
---
language:
- en
license: cc-by-nc-sa-4.0
task_categories:
- time-series-forecasting
- text-classification
tags:
- crypto
- finance
- sentiment
- twitter
- bitcoin
- market-microstructure
size_categories:
- 10K<n<100K
configs:
- config_name: default
  data_files:
  - split: train
    path: "data/*.parquet"
---

# Crypto Market Structure + X (Twitter) Sentiment (Research Sample)

## Dataset Description

This is a **research-grade sample** from the Instrumetriq pipeline. It aligns high-resolution market microstructure snapshots (Binance) with aggregated social sentiment from X (Twitter).

- **Granularity:** Daily aggregation (source data captured in 2-hour monitoring windows).
- **Scope:** Spot market metrics + AI-scored sentiment.
- **Source:** Instrumetriq Premium Pipeline (Tier 1 Schema).

## Content
Each row represents a 2-hour observation session for a specific coin.

| Column | Description |
|---|---|
| `symbol` | Trading pair (e.g., BTCUSDT) |
| `snapshot_ts` | ISO timestamp of the session start |
| `spot_price` | Mid-price on Binance Spot |
| `sentiment_score` | Mean sentiment score (-1.0 to 1.0) from DistilBERT model |
| `sentiment_volume` | Total social posts analyzed in the window |
| `liquidity_score` | Composite liquidity metric (0-100) |

## Intended Use & Restrictions

**License:** [CC-BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)
- **Allowed:** Academic research, backtesting simulation, student theses.
- **Prohibited:** Commercial trading bots, reselling the data, building paid signals.

## Full Dataset Access

This repository contains a **1-month sample**.
The complete historical archive (2025-Present) with daily updates and institutional-grade depth (Tier 3) is available for subscribers.

👉 **Full Archive & Daily Updates:** [Instrumetriq.com](https://instrumetriq.com)
```

### B. Settings Checklist
1.  **Gated Access:** Go to *Settings* -> *Gated Dataset*.
    *   Enable "Gate dataset".
    *   **Auto-approve:** ON (We want low friction, just tracking).
    *   **User Question:** "What is your intended research use case?"

---

## 3) Kaggle Setup

Kaggle relies on "Usability Scores". You must fill every field to get a "10.0" score and rank in "Trending".

**Dataset Title:** `Crypto Market Sentiment & Microstructure (2025 Sample)`
**Subtitle:** `Daily aligned X (Twitter) Sentiment + Binance Spot Data (Research Sample)`

### A. Metadata (`dataset-metadata.json`)
If uploading via API. If using Web UI, just paste the description.

```json
{
  "title": "Crypto Market Sentiment & Microstructure (2025 Sample)",
  "subtitle": "Daily aligned X (Twitter) Sentiment + Binance Spot Data",
  "id": "instrumetriq/crypto-market-sentiment-sample",
  "licenses": [{"name": "cc-by-nc-sa-4.0"}],
  "keywords": ["finance", "crypto", "bitcoin", "sentiment", "nlp", "trading"],
  "description": "(Paste the README.md content from the Hugging Face section above)"
}
```

### B. "Usability 10.0" Checklist (Critical)
1.  **Tagging:** Add at least 5 tags (Finance, NLP, Time Series, Bitcoin, Twitter).
2.  **Cover Image:** Upload the 1136x360 banner. **Mandatory** for trending.
3.  **Column Descriptions:** In the columns tab, add a 1-sentence description for *every single column*.
    *   *Tip:* Copy these from `docs/DATASET_SCHEMA_TIER1.md`.
4.  **Provenance:** In the "Provenance" field, link to `https://instrumetriq.com`.

### C. The "Starter Notebook" (Traffic Driver)
You **must** upload a simple notebook kernel alongside the dataset. This allows users to "Fork" and start working immediately.

**Title:** `Quickstart: Plotting Sentiment vs Price`
**Code Snippet (Python):**

```python
import pandas as pd
import plotly.express as px

# Load Data
df = pd.read_parquet('/kaggle/input/crypto-market-sentiment-sample/instrumetriq_sample_jan2024.parquet')

# Filter for Bitcoin
btc = df[df['symbol'] == 'BTCUSDT'].sort_values('snapshot_ts')

# Plot
fig = px.line(btc, x='snapshot_ts', y='spot_price', title='BTC Price Action')
fig.show()

fig2 = px.bar(btc, x='snapshot_ts', y='sentiment_score', title='BTC Sentiment (-1 to 1)', color='sentiment_score')
fig2.show()
```

---

## 4) Monthly Maintenance Routine

To stay relevant in search results without creating "real work":

1.  **Calendar:** Set a reminder for the **1st of every month**.
2.  **Action:** Upload *one* new month of data from **3 months ago**.
    *   *Example:* On May 1st, add February data.
3.  **Update Description:** Change "Jan 2024 Sample" to "Jan-Feb 2024 Sample".
4.  **Effect:** This triggers "Recently Updated" flags on both platforms, pushing you back to the top of the "Finance" category.
