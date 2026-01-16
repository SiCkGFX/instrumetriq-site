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
| `twitter_sentiment_windows` | Dynamic-key structs (10K-17K keys), see note below |
| `norm` | Intentionally dropped in v7 |
| `labels` | Intentionally dropped in v7 |

### Why twitter_sentiment_windows is Excluded

`twitter_sentiment_windows` contains dynamic-key struct fields where keys are actual hashtag/handle/domain names (e.g., `tag_counts: struct<#BTC: 5, #ETH: 3, ...>`). 

**Problem:** These fields have 10,000-17,000 unique keys per day. The keys differ between days, causing schema incompatibility during weekly concatenation. Converting to MAP<string, int64> for stable schema takes 15-30 minutes per weekly build.

**Solution:** Tier 2 excludes `twitter_sentiment_windows` entirely. The essential provenance metadata is still available in `twitter_sentiment_meta`.

**For full sentiment data:** Use Tier 3 daily files (no concatenation needed, original struct format preserved).

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
