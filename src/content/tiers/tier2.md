---
title: "Tier 2 Schema"
tierNumber: 2
planName: "Researcher"
shortDescription: "Reduced Tier 3 export with nested structs and richer X (Twitter) sentiment (no futures)."
priceUsdMonthly: 15
updatedAt: 2026-01-23
---

Tier 2 is a reduced Tier 3 export: it keeps nested structs for market microstructure and scoring, and includes a stable subset of sentiment fields from the preceding scrape cycle.

## Summary

- **Format:** Apache Parquet (zstd)
- **Granularity:** daily partitions (UTC)
- **Schema version:** v7
- **Shape:** 8 top-level columns (nested structs)
- **Sentiment scope:** selected `last_cycle` sentiment fields (stable subset)
- **Futures:** excluded

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
| `twitter_sentiment_last_cycle` | struct | Selected sentiment fields from the preceding scrape cycle |

## Column Exclusions (from Tier 3)

Tier 2 intentionally omits:

- `futures_raw` (available in Tier 3)
- `spot_prices` (high-volume time series)
- `flags`, `diag` (operational/debug blocks)
- `norm`, `labels` (dropped in v7)

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

## Notes

- Some high-cardinality dynamic-key fields (hashtags, mentions, domains) are excluded from Tier 2 to keep the schema stable across days.
- Tier 2 is intended for research and analysis. It is not real-time data and is not presented as a trading signal.
