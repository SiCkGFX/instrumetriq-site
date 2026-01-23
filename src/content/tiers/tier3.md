---
title: "Tier 3 Schema"
tierNumber: 3
planName: "Full Archive"
shortDescription: "Full nested daily export including spot microstructure, futures blocks, and complete sentiment windows."
priceUsdMonthly: 35
updatedAt: 2026-01-23
---

Tier 3 is the full daily export: a nested schema designed to preserve the archive entry structure while remaining efficient to query in Parquet.

## Summary

- **Format:** Apache Parquet (zstd)
- **Granularity:** daily partitions (UTC)
- **Schema version:** v7
- **Shape:** 12 top-level columns (nested structs + time-series list)
- **Sentiment scope:** complete sentiment windows captured from X (Twitter)
- **Futures:** included where available

## R2 Layout

```
tier3/daily/
└── YYYY-MM-DD/
    ├── data.parquet
    └── manifest.json
```

## Top-Level Columns (12)

| Column | Type | Description |
|--------|------|-------------|
| `symbol` | string | Trading pair (e.g., "BTCUSDC") |
| `snapshot_ts` | string | Observation timestamp (ISO 8601, UTC) |
| `meta` | struct | Entry metadata |
| `spot_raw` | struct | Raw spot market snapshot |
| `futures_raw` | struct | Futures contract snapshot (NULL if unavailable) |
| `derived` | struct | Calculated metrics |
| `scores` | struct | Scoring results |
| `flags` | struct | Operational flags |
| `diag` | struct | Diagnostics |
| `twitter_sentiment_windows` | struct | Sentiment windows (e.g., `last_cycle`, `last_2_cycles`) |
| `twitter_sentiment_meta` | struct | X (Twitter) capture metadata |
| `spot_prices` | list<struct> | Intra-session spot samples (~10s interval) |

## Scoring Logic

The `scores.final` field is a composite quality score (0-100) derived from weighted individual factor scores. Key factors include **Price Action** (Momentum, Volatility), **Liquidity Health** (Spread Efficiency, Depth), and **Order Flow** (Taker Buy/Sell Pressure). This metric acts as a quality filter: higher scores (≥60) indicate tradeable, liquid assets with strong market interest, while lower scores filter out predominantly illiquid or noise-heavy pairs. Source: `base_scorer.py`.

## How to interpret NULLs

- `futures_raw = NULL` typically means the symbol has no futures contract or futures data was not available at capture time.
- NULL in optional blocks indicates “not available for this entry”, not corruption.

## Partition semantics (UTC)

Daily partitions are built from the archive day folder (UTC). The partition is determined by the archive folder name, not by `meta.added_ts` inside each record.

## Notes

- Tier 3 is intended for research and analysis. It is not real-time data and is not presented as a trading signal.
- Sentiment scope is X (Twitter)-only.
