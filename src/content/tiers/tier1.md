---
title: "Tier 1 Schema"
tierNumber: 1
planName: "Explorer"
shortDescription: "Flat, analysis-ready daily table with aggregated X (Twitter) sentiment."
priceUsdMonthly: 5
updatedAt: 2026-01-23
---

Tier 1 is the smallest export: a flat table derived from Tier 3, designed to be easy to load and stable to join across days.

## Summary

- **Format:** Apache Parquet (zstd)
- **Granularity:** daily partitions (UTC)
- **Schema version:** v7
- **Shape:** 19 flat columns (no nested structs)
- **Sentiment scope:** aggregated X (Twitter) fields only (no sentiment internals)
- **Futures:** excluded

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
| `symbol` | string | Trading pair (e.g., "BTCUSDC") |
| `snapshot_ts` | string | Observation timestamp (ISO 8601, UTC) |
| `meta_added_ts` | string | When the archive entry was recorded |
| `meta_expires_ts` | string | Entry expiration time |
| `meta_duration_sec` | double | Observation duration (seconds) |
| `meta_archive_schema_version` | int64 | Schema version (7) |

### Spot Market (4)

| Field | Type | Description |
|------|------|-------------|
| `spot_mid` | double | Mid price |
| `spot_spread_bps` | double | Bid/ask spread (basis points) |
| `spot_range_pct_24h` | double | 24h price range (%) |
| `spot_ticker24_chg` | double | 24h price change |

### Derived Metrics (2)

| Field | Type | Description |
|------|------|-------------|
| `derived_liq_global_pct` | double | Global liquidity percentile |
| `derived_spread_bps` | double | Derived spread (basis points) |

### Scoring (1)

| Field | Type | Description |
|------|------|-------------|
| `score_final` | double | Final composite liquidity score |

### X (Twitter) Sentiment (6)

These are aggregated counts/summaries sourced from the preceding scrape cycle.

| Field | Type | Description |
|------|------|-------------|
| `sentiment_posts_total` | int64 | Total posts in the sentiment window |
| `sentiment_posts_pos` | int64 | Positive post count |
| `sentiment_posts_neu` | int64 | Neutral post count |
| `sentiment_posts_neg` | int64 | Negative post count |
| `sentiment_mean_score` | double | Mean sentiment score |
| `sentiment_is_silent` | bool | No recent posts for this symbol |

## Notes

- Tier 1 is intended for research and analysis. It is not real-time data and is not presented as a trading signal.
- Sentiment fields can be NULL when X (Twitter) data was unavailable.
