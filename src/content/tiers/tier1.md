---
title: "Tier 1 Schema"
tierNumber: 1
planName: "Explorer"
shortDescription: "Flat, analysis-ready daily table with aggregated X (Twitter) sentiment."
priceUsdMonthly: 5
updatedAt: 2026-01-23
---

This dataset captures **2-hour observation sessions** of cryptocurrency trading pairs on Binance. Each row represents one session where a coin was tracked for market conditions and social sentiment.

## Key characteristics

- **Flat schema** — 19 columns, no nested structs, ready for analysis
- **Essential metrics only** — price, spread, score, sentiment summary
- **X (Twitter) sentiment** — post counts and mean score
- **Daily granularity** — one parquet file per UTC day

## Use cases

- Quick sentiment screening across coins
- Correlation studies between price and social activity
- Lightweight backtesting inputs
- Learning/prototyping with minimal data complexity

## Overview

| Property | Value |
|----------|-------|
| **Format** | Apache Parquet (zstd compressed) |
| **Granularity** | Daily (one file per UTC day) |
| **Schema Version** | v7 |
| **Columns** | 19 flat fields |

## R2 Layout

```
tier1/daily/
└── YYYY-MM-DD/
    ├── data.parquet
    └── manifest.json
```

## Field Reference (19 columns)

### Identity & Timing (6)

| Field | Type | Description |
|------|------|-------------|
| `symbol` | string | The unique trading pair identifier on Binance (e.g., "BTCUSDC"). |
| `snapshot_ts` | string | The ISO 8601 timestamp (UTC) marking the end of the observation window. |
| `meta_added_ts` | string | The timestamp when this record was permanently written to the archive. |
| `meta_expires_ts` | string | The timestamp when this record is considered effectively expired for real-time usage. |
| `meta_duration_sec` | double | The total duration of the data collection window in seconds (standard is 7200s / 2 hours). |
| `meta_archive_schema_version` | int64 | The internal version number of the schema definition (currently v7). |

### Spot Market (4)

| Field | Type | Description |
|------|------|-------------|
| `spot_mid` | double | The mid-market price (average of best bid and best ask) at the moment of the snapshot. |
| `spot_spread_bps` | double | The difference between best bid and best ask prices, expressed in basis points (1 bp = 0.01%). |
| `spot_range_pct_24h` | double | The percentage difference between the 24-hour high and low prices. |
| `spot_ticker24_chg` | double | The absolute price change over the rolling 24-hour window. |

### Derived Metrics (2)

| Field | Type | Description |
|------|------|-------------|
| `derived_liq_global_pct` | double | A percentile rank (0.0–1.0) comparing this asset's liquidity to the entire monitored universe. |
| `derived_spread_bps` | double | A smoothed or adjusted spread metric used for historical consistency. |

### Scoring (1)

| Field | Type | Description |
|------|------|-------------|
| `score_final` | double | A composite score (0–100) aggregating liquidity, volatility, and social presence. Used for ranking. |

### X (Twitter) Sentiment (6)

| Field | Type | Description |
|------|------|-------------|
| `sentiment_posts_total` | int64 | The total count of relevant posts detected during the observation window. |
| `sentiment_posts_pos` | int64 | The number of posts classified as having Positive sentiment by the AI model. |
| `sentiment_posts_neu` | int64 | The number of posts classified as Neutral. |
| `sentiment_posts_neg` | int64 | The number of posts classified as Negative. |
| `sentiment_mean_score` | double | The separate average sentiment intensity score (-1.0 to 1.0) derived from the model's confidence logic. |
| `sentiment_is_silent` | bool | Boolean flag indicating whether the asset had zero social activity in this window. |

## Notes

- Tier 1 is intended for research and analysis. It is not real-time data and is not presented as a trading signal.
- When `sentiment_is_silent` is true, sentiment fields can be NULL.
