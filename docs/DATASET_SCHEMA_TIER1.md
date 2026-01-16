# Tier 1 Weekly Dataset Schema

This document describes the schema for Tier 1 weekly parquet exports.

## Overview

Tier 1 weekly exports are the **most minimal dataset**, derived from Tier 3 daily parquets with only core price/liquidity metrics retained. This tier is optimized for lightweight analysis and real-time monitoring use cases.

| Property | Value |
|----------|-------|
| **schema_version** | v7 |
| **tier** | tier1 |
| **window** | 7 consecutive UTC days (Mon–Sun) |
| **source** | Derived from `tier3/daily/` parquets |
| **format** | Apache Parquet with zstd compression |
| **R2 path** | `tier1/weekly/{end-day}/dataset_entries_7d.parquet` |

### Weekly Window Definition

A Tier 1 weekly export covers 7 consecutive UTC days (Monday through Sunday):
- **Window:** `end_day - 6` (Monday) to `end_day` (Sunday)
- **Example:** `--end-day 2026-01-04` covers 2025-12-29 (Mon) through 2026-01-04 (Sun)

### Partial Week Support

Tier 1 can be built from **5 or more** of the 7 expected days (configurable via `--min-days`).
- Missing days are explicitly recorded in the manifest
- Partial Tier 3 days (those with < 24 hours coverage) are also tracked
- Use the `source_coverage` block in manifest to understand data gaps

---

## Column Policy

### Tier Hierarchy

The tier system provides progressively more data:

| Tier | Columns | Use Case |
|------|---------|----------|
| **Tier 1** | 5 columns | Lightweight analysis, real-time monitoring |
| **Tier 2** | 7 columns | Research, reduced column footprint |
| **Tier 3** | 12 columns | Full historical data, ML training |

### Included Columns (5)

| Column | Type | Description |
|--------|------|-------------|
| `symbol` | string | Trading pair (e.g., "BTCUSDT") |
| `snapshot_ts` | string | Observation timestamp |
| `meta` | struct | Entry metadata |
| `spot_raw` | struct | Spot market data |
| `scores` | struct | Scoring results |

### Excluded Columns (9)

| Column | Reason for Exclusion |
|--------|---------------------|
| `derived` | Calculated metrics (can be recomputed from spot_raw) |
| `twitter_sentiment_meta` | Social sentiment metadata (not core price data) |
| `futures_raw` | Futures data (available in Tier 3) |
| `spot_prices` | Time-series arrays, high volume |
| `flags` | Boolean flags, debugging only |
| `diag` | Diagnostics, internal use |
| `twitter_sentiment_windows` | Dynamic-key structs cause schema mismatch |
| `norm` | Intentionally dropped in v7 |
| `labels` | Intentionally dropped in v7 |

**Note:** Tier 1 uses an **explicit allowlist** approach—only the 5 listed columns are included. Tier 2 adds `derived` and `twitter_sentiment_meta` on top of Tier 1.

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

### scores

Key fields within the `scores` struct:

| Field | Type | Description |
|-------|------|-------------|
| `final` | double | Final composite score |
| `spread` | double | Spread component score |
| `depth` | double | Depth component score |
| `liq` | double | Liquidity component score |

---

## Manifest Schema

Each weekly export includes a `manifest.json` with:

```json
{
  "schema_version": "v7",
  "tier": "tier1",
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
    "included_columns": ["symbol", "snapshot_ts", "meta", "spot_raw", "scores"],
    "excluded_columns": ["derived", "twitter_sentiment_meta", ...],
    "policy_note": "Tier 1 is the most minimal dataset, containing only core price/liquidity metrics."
  },
  "parquet_sha256": "...",
  "parquet_size_bytes": 4460657
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

#### per_day Coverage Details

For each included day, the `per_day` object contains:

| Field | Description |
|-------|-------------|
| `hours_found` | Number of hour files found (0-24) |
| `hours_expected` | Expected hours (always 24) |
| `is_partial` | Boolean, true if hours_found < 24 |
| `missing_hours` | List of missing hour strings (e.g., `["03", "04"]`) |
| `row_count` | Number of entries from this day |

**Gaps reflect pipeline uptime**, not missing market data. If the archival pipeline was offline, those hours/days will be missing from Tier 3 and therefore from Tier 1.

---

## Usage

### Building Tier 1 Weekly Exports

```bash
# Cron mode: build previous Mon-Sun week (for Monday 00:05 UTC cron)
python3 scripts/build_tier1_weekly.py --previous-week --upload

# Dry-run to see computed window
python3 scripts/build_tier1_weekly.py --previous-week --dry-run

# Manual/backfill: build specific week ending on a date (Sunday)
python3 scripts/build_tier1_weekly.py --end-day 2025-12-28 --upload

# Build partial week (requires at least 5 days)
python3 scripts/build_tier1_weekly.py --end-day 2026-01-04 --min-days 5 --upload

# Custom output directory
python3 scripts/build_tier1_weekly.py --end-day 2025-12-28 --local-out ./my_output --upload
```

### Cron Schedule

Run Mondays at 00:05 UTC to build the previous complete Mon-Sun week:

```bash
# /etc/cron.d/tier1_weekly
5 0 * * 1 instrum cd /srv/instrumetriq && python3 scripts/build_tier1_weekly.py --previous-week --upload 2>&1 | logger -t tier1_weekly
```

---

## R2 Layout

```
instrumetriq-datasets/
└── tier1/
    └── weekly/
        └── YYYY-MM-DD/           # end_day (Sunday)
            ├── dataset_entries_7d.parquet
            └── manifest.json
```

---

## Related Documentation

- [DATASET_SCHEMA_TIER2.md](DATASET_SCHEMA_TIER2.md) - Tier 2 weekly schema (7 columns)
- [DATASET_SCHEMA_TIER3.md](DATASET_SCHEMA_TIER3.md) - Tier 3 daily schema (12 columns)
- [DATASET_EXPORT_GUIDE.md](DATASET_EXPORT_GUIDE.md) - General export guide
