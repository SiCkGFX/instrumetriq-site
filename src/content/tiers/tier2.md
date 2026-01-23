---
title: "Tier 2 Schema"
tierNumber: 2
planName: "Researcher"
shortDescription: "Structured daily export with nested market microstructure and rich X (Twitter) sentiment."
priceUsdMonthly: 15
updatedAt: 2026-01-23
---

Tier 2 is a professional-grade daily dataset designed for research and analysis workflows. It offers deep visibility into spot market microstructure and granular sentiment metrics using a structured, nested schema.

## Key characteristics

- **Structured schema** — 8 top-level nested columns preserving data richness
- **Market Microstructure** — Spot price, spread, depth, and imbalance metrics
- **Rich Sentiment** — Detailed breakdown of sentiment sources, engagement, and decision stats
- **Daily granularity** — one parquet file per UTC day

## Overview

| Property | Value |
|----------|-------|
| **Format** | Apache Parquet (zstd compressed) |
| **Granularity** | Daily (one file per UTC day) |
| **Schema Version** | v7 |
| **Columns** | 8 top-level nested columns |

## R2 Layout

```
tier2/daily/
└── YYYY-MM-DD/
    ├── data.parquet
    └── manifest.json
```

## Top-Level Columns (8)

| Column | Type | Description |
|--------|------|-------------|
| `symbol` | string | Trading pair (e.g., "BTCUSDC") |
| `snapshot_ts` | string | Observation timestamp (ISO 8601, UTC) |
| `meta` | struct | Entry metadata |
| `spot_raw` | struct | Spot market snapshot |
| `derived` | struct | Calculated metrics |
| `scores` | struct | Scoring results |
| `twitter_sentiment_meta` | struct | X (Twitter) capture metadata |
| `twitter_sentiment_last_cycle` | struct | Stable selection of sentiment fields |

## Data Scope

Tier 2 provides a focused view on **Spot Market** and **Social Sentiment**. It includes the `spot_raw` structure for order book analysis and a stable, high-value subset of `twitter_sentiment` for advanced social signals.

## `twitter_sentiment_last_cycle` (selected fields)

This struct is extracted from `twitter_sentiment_windows.last_cycle` with a stable selection of fields.

| Field | Type | Description |
|-------|------|-------------|
| `ai_sentiment` | struct | AI model sentiment stats |
| `author_stats` | struct | Author stats (e.g., follower distributions) |
| `bucket_has_valid_sentiment` | bool | Bucket has valid sentiment |
| `bucket_min_posts_for_score` | int64 | Minimum posts required |
| `bucket_status` | string | Bucket status indicator |
| `category_counts` | struct | Counts per sentiment category |
| `hybrid_decision_stats` | struct | Decision source ratios + mean score |
| `platform_engagement` | struct | Likes/retweets/replies/views aggregates |
| `posts_neg` | int64 | Negative posts count |
| `posts_neu` | int64 | Neutral posts count |
| `posts_pos` | int64 | Positive posts count |
| `posts_total` | int64 | Total posts count |
| `sentiment_activity` | struct | Activity metrics (e.g., silent, recency) |

## Scoring Logic

The `scores.final` field is a composite quality score (0-100) derived from weighted individual factor scores. Key factors include **Price Action** (Momentum, Volatility), **Liquidity Health** (Spread Efficiency, Depth), and **Order Flow** (Taker Buy/Sell Pressure). This metric acts as a quality filter: higher scores (≥60) indicate tradeable, liquid assets with strong market interest, while lower scores filter out predominantly illiquid or noise-heavy pairs. Source: `base_scorer.py`.

## Notes

- Some high-cardinality dynamic-key fields (hashtags, mentions, domains) are excluded from Tier 2 to keep the schema stable across days.
- Tier 2 is intended for research and analysis. It is not real-time data and is not presented as a trading signal.
