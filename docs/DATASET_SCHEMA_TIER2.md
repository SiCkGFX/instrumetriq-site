# Tier 2 Weekly Dataset Schema

This document describes the schema for Tier 2 weekly parquet exports.

## Overview

Tier 2 weekly exports are derived from Tier 3 daily parquets with a reduced column footprint optimized for research and analysis.

| Property | Value |
|----------|-------|
| **schema_version** | v7 |
| **tier** | tier2 |
| **window** | 7 consecutive UTC days |
| **source** | Derived from `tier3/daily/` parquets |
| **format** | Apache Parquet with zstd compression |
| **R2 path** | `tier2/weekly/{end-day}/dataset_entries_7d.parquet` |

---

## Column Policy

### Included Columns (7)

| Column | Type | Description |
|--------|------|-------------|
| `symbol` | string | Ticker symbol (e.g., "BTCUSDT") |
| `snapshot_ts` | string | Observation timestamp |
| `meta` | struct | Entry metadata |
| `spot_raw` | struct | Spot market data |
| `derived` | struct | Calculated metrics |
| `scores` | struct | Scoring results |
| `twitter_sentiment_meta` | struct | Twitter sentiment metadata |

### Excluded Columns (7)

| Column | Reason for Exclusion |
|--------|---------------------|
| `futures_raw` | Large block, available in Tier 3 |
| `spot_prices` | Time-series arrays, high volume |
| `flags` | Boolean flags, debugging only |
| `diag` | Diagnostics, internal use |
| `twitter_sentiment_windows` | Dynamic-key structs cause schema mismatch |
| `norm` | Intentionally dropped in v7 |
| `labels` | Intentionally dropped in v7 |

**Note:** `twitter_sentiment_windows` contains structs like `tag_counts`, `mention_counts`, and `url_domain_counts` where keys are actual hashtag/handle/domain names. These vary between days, causing schema incompatibility during weekly concatenation. The essential sentiment metadata is preserved in `twitter_sentiment_meta`.

---

## Nested Struct Fields

### meta

Key fields within the `meta` struct:

| Field | Type | Description |
|-------|------|-------------|
| `added_ts` | string | ISO timestamp when entry was added |
| `expires_ts` | string | ISO timestamp when entry expires |
| `duration_sec` | double | Cycle duration in seconds |
| `archive_schema_version` | int64 | Schema version (currently 7) |
| `source` | string | Data source identifier |
| `session_id` | string | Unique session identifier |

### spot_raw

Key fields within the `spot_raw` struct:

| Field | Type | Description |
|-------|------|-------------|
| `mid` | double | Mid price |
| `bid` | double | Best bid price |
| `ask` | double | Best ask price |
| `spread_bps` | double | Spread in basis points |
| `last` | double | Last traded price |

### derived

Key fields within the `derived` struct:

| Field | Type | Description |
|-------|------|-------------|
| `spread_bps` | double | Calculated spread in basis points |
| `depth_imbalance` | double | Order book depth imbalance |
| `flow` | double | Flow metric |

### scores

Key fields within the `scores` struct:

| Field | Type | Description |
|-------|------|-------------|
| `final` | double | Final composite score |
| `spread` | double | Spread component score |
| `depth` | double | Depth component score |
| `liq` | double | Liquidity component score |

### twitter_sentiment_meta

Key fields within the `twitter_sentiment_meta` struct:

| Field | Type | Description |
|-------|------|-------------|
| `source` | string | Data source (e.g., "twscrape_snapshot") |
| `captured_at_utc` | string | ISO timestamp of capture |
| `bucket_meta` | struct | Nested metadata about the sentiment bucket |

---

## Manifest Schema

Each weekly export includes a `manifest.json` with:

```json
{
  "schema_version": "v7",
  "tier": "tier2",
  "window": {
    "start_day": "2025-12-22",
    "end_day": "2025-12-28",
    "days_included": ["2025-12-22", "2025-12-23", ...]
  },
  "build_ts_utc": "2026-01-16T08:14:05.789519+00:00",
  "source_inputs": [
    "tier3/daily/2025-12-22/data.parquet",
    ...
  ],
  "row_count": 17635,
  "column_policy": {
    "included_top_level_columns": [...],
    "excluded_top_level_columns": [...],
    "explicit_exclusions": [...]
  },
  "parquet_sha256": "...",
  "parquet_size_bytes": 5339067
}
```

---

## Verification

Use the verification script to validate Tier 2 exports:

```bash
# Verify most recent week from R2
python3 scripts/verify_tier2_weekly.py

# Verify specific week
python3 scripts/verify_tier2_weekly.py --end-day 2025-12-28

# Verify local files
python3 scripts/verify_tier2_weekly.py --local output/tier2_weekly/2025-12-28
```

**Report location:** `output/verify_tier2_report.md`

**Artifacts generated:**
- `output/verify_tier2/{end-day}/manifest.json` - Downloaded manifest copy
- `output/verify_tier2/{end-day}/schema.txt` - PyArrow schema pretty print
- `output/verify_tier2/{end-day}/stats.json` - Machine-readable summary

---

## Related Documentation

- [DATASET_EXPORT_GUIDE.md](DATASET_EXPORT_GUIDE.md) - Export workflow and usage
- [scripts/README.md](../scripts/README.md) - Script reference
