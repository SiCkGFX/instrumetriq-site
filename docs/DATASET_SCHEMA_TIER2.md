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

### Weekly Window Definition

A Tier 2 weekly export covers 7 consecutive UTC days ending on `end_day`:
- **Window:** `end_day - 6` to `end_day` (inclusive)
- **Example:** `--end-day 2026-01-15` covers 2026-01-09 through 2026-01-15

### Partial Week Support

Tier 2 can be built from **5 or more** of the 7 expected days (configurable via `--min-days`).
- Missing days are explicitly recorded in the manifest
- Partial Tier 3 days (those with < 24 hours coverage) are also tracked
- Use the `source_coverage` block in manifest to understand data gaps

---

## Column Policy

### Included Columns (8)

| Column | Type | Description |
|--------|------|-------------|
| `symbol` | string | Ticker symbol (e.g., "BTCUSDT") |
| `snapshot_ts` | string | Observation timestamp |
| `meta` | struct | Entry metadata |
| `spot_raw` | struct | Spot market data |
| `derived` | struct | Calculated metrics |
| `scores` | struct | Scoring results |
| `twitter_sentiment_windows` | struct | Twitter sentiment aggregates (with MAP conversion) |
| `twitter_sentiment_meta` | struct | Twitter sentiment metadata |

### Excluded Columns (6)

| Column | Reason for Exclusion |
|--------|---------------------|
| `futures_raw` | Large block, available in Tier 3 |
| `spot_prices` | Time-series arrays, high volume |
| `flags` | Boolean flags, debugging only |
| `diag` | Diagnostics, internal use |
| `norm` | Intentionally dropped in v7 |
| `labels` | Intentionally dropped in v7 |

### Sentiment Schema Transformation

`twitter_sentiment_windows` contains dynamic-key struct fields where keys are actual hashtag/handle/domain names. These vary between days, causing schema incompatibility during weekly concatenation.

**Tier 2 transforms these fields to MAP<string, int64>:**

| Original Path | Original Type | Tier 2 Type |
|--------------|---------------|-------------|
| `last_cycle.tag_counts` | struct<#BTC: int, #ETH: int, ...> | map<string, int64> |
| `last_cycle.cashtag_counts` | struct<$BTC: int, $ETH: int, ...> | map<string, int64> |
| `last_cycle.mention_counts` | struct<@user1: int, @user2: int, ...> | map<string, int64> |
| `last_cycle.url_domain_counts` | struct<twitter.com: int, x.com: int, ...> | map<string, int64> |
| `last_2_cycles.*` | (same pattern) | map<string, int64> |

**Why MAP?** MAP columns have a fixed schema (`map<string, int64>`) regardless of which keys appear, enabling `pa.concat_tables()` across days with different hashtag/handle sets.

**Tier 3 retains the original struct format** for maximum fidelity. Use Tier 3 if you need the original nested structure.

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

### twitter_sentiment_windows

Contains sentiment aggregates for time windows. In Tier 2, dynamic-key fields are converted to MAP<string, int64>.

| Field | Type | Description |
|-------|------|-------------|
| `last_cycle` | struct | Sentiment data from the most recent cycle |
| `last_2_cycles` | struct | Sentiment data from the last 2 cycles combined |

**last_cycle / last_2_cycles sub-fields:**

| Field | Tier 2 Type | Description |
|-------|-------------|-------------|
| `tweet_count` | int64 | Number of tweets analyzed |
| `unique_users` | int64 | Number of unique users |
| `retweet_count` | int64 | Total retweets |
| `like_count` | int64 | Total likes |
| `reply_count` | int64 | Total replies |
| `sentiment_mean` | double | Mean sentiment score |
| `sentiment_std` | double | Sentiment standard deviation |
| `tag_counts` | map<string, int64> | Hashtag frequency counts |
| `cashtag_counts` | map<string, int64> | Cashtag frequency counts |
| `mention_counts` | map<string, int64> | @mention frequency counts |
| `url_domain_counts` | map<string, int64> | URL domain frequency counts |

**Querying MAP columns:**

```python
import pyarrow.parquet as pq

table = pq.read_table("dataset_entries_7d.parquet")

# Access MAP data for a row
row = table.slice(0, 1).to_pydict()
tag_counts = row['twitter_sentiment_windows'][0]['last_cycle']['tag_counts']
# Returns: [('BTC', 42), ('ETH', 17), ...]  (list of key-value tuples)
```

---

## Manifest Schema

Each weekly export includes a `manifest.json` with:

```json
{
  "schema_version": "v7",
  "tier": "tier2",
  "window": {
    "window_basis": "previous_week_utc",
    "week_start_day": "2025-12-22",
    "week_end_day": "2025-12-28",
    "days_expected": ["2025-12-22", "2025-12-23", ...],
    "days_included": ["2025-12-22", "2025-12-23", ...]
  },
  "build_ts_utc": "2026-01-16T08:14:05.789519+00:00",
  "source_inputs": [
    "tier3/daily/2025-12-22/data.parquet",
    ...
  ],
  "row_count": 17635,
  "source_coverage": {
    "days_expected": ["2025-12-22", ...],
    "days_present": ["2025-12-22", ...],
    "days_missing": [],
    "per_day": {
      "2025-12-22": {
        "hours_found": 24,
        "hours_expected": 24,
        "is_partial": false,
        "missing_hours": []
      }
    },
    "present_days_count": 7,
    "missing_days_count": 0,
    "partial_days_count": 0,
    "min_days_threshold_used": 5,
    "coverage_note": "This weekly export is derived from 7/7 daily partitions."
  },
  "column_policy": {
    "included_top_level_columns": [...],
    "excluded_top_level_columns": [...],
    "explicit_exclusions": [...]
  },
  "sentiment_shape": {
    "note": "Dynamic-key fields converted to MAP<string, int64> for stable schema",
    "transformed_fields": [
      "twitter_sentiment_windows.last_cycle.tag_counts",
      "twitter_sentiment_windows.last_cycle.cashtag_counts",
      "twitter_sentiment_windows.last_cycle.mention_counts",
      "twitter_sentiment_windows.last_cycle.url_domain_counts",
      "twitter_sentiment_windows.last_2_cycles.tag_counts",
      "twitter_sentiment_windows.last_2_cycles.cashtag_counts",
      "twitter_sentiment_windows.last_2_cycles.mention_counts",
      "twitter_sentiment_windows.last_2_cycles.url_domain_counts"
    ],
    "original_type": "struct<key1: int64, key2: int64, ...> (keys vary per day)",
    "tier2_type": "map<string, int64>",
    "reason": "Struct field names differ between days causing schema incompatibility"
  },
  "parquet_sha256": "...",
  "parquet_size_bytes": 5339067
}
```

### window Block

The `window` block describes the weekly range:

| Field | Description |
|-------|-------------|
| `window_basis` | How end_day was determined: `"previous_week_utc"` (cron mode) or `"end_day"` (manual) |
| `week_start_day` | First day of the 7-day window (Monday) |
| `week_end_day` | Last day of the 7-day window (Sunday) |
| `days_expected` | List of 7 days in the window |
| `days_included` | Days that were actually included in the build |

**Window basis modes:**
- `previous_week_utc`: Used with `--previous-week` flag; computes end_day as most recent Sunday UTC
- `end_day`: Used with `--end-day YYYY-MM-DD` flag; uses explicit date provided

### source_coverage Block

The `source_coverage` block documents data completeness:

| Field | Description |
|-------|-------------|
| `days_expected` | List of 7 days in the window |
| `days_present` | Tier 3 days that exist and were included |
| `days_missing` | Tier 3 days that were not found in R2 |
| `per_day` | Coverage metadata for each present day |
| `present_days_count` | Count of included days (e.g., 6) |
| `missing_days_count` | Count of missing days (e.g., 1) |
| `partial_days_count` | Count of partial days (< 24 hours coverage) |
| `min_days_threshold_used` | Minimum days required for build |
| `coverage_note` | Human-readable summary |

**Gaps reflect pipeline uptime**, not missing market data. If the archival pipeline was offline, those days will be missing from Tier 3 and therefore from Tier 2.

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
