# Dataset Export Guide

This guide covers the tiered dataset export system for Instrumetriq archives.

## Overview

The archive data is exported in multiple tiers, each serving different use cases:

| Tier | Granularity | Update Frequency | Primary Use Case |
|------|-------------|------------------|------------------|
| Tier 1 | Real-time | Continuous | Live dashboards, alerts |
| **Tier 2** | Weekly | Once per week | Research, reduced column footprint |
| **Tier 3** | Daily | Once per day | Historical research, ML training |

---

## Tier 3: Daily Parquet Export

Tier 3 exports produce daily Parquet files containing all archive entries for a UTC day.

### Partition Semantics

Daily partitions are built from the **archive folder day (UTC)**, not from `meta.added_ts` timestamps. Each export includes all entries from hour files `00.jsonl.gz` through `23.jsonl.gz` in the corresponding `YYYYMMDD/` archive folder.

### Usage

#### Automatic (Cron)

The standard operational pattern runs via cron at **00:05 UTC**, exporting the previous day:

```bash
# Cron entry (runs at 00:05 UTC daily)
5 0 * * * cd /srv/instrumetriq && python3 scripts/export_tier3_daily.py --upload >> /var/log/tier3_export.log 2>&1
```

With no `--date` argument, the script automatically selects **yesterday UTC**.

#### Manual Export

```bash
# Dry-run for yesterday (default)
python3 scripts/export_tier3_daily.py --dry-run

# Dry-run for a specific date
python3 scripts/export_tier3_daily.py --date 2026-01-15 --dry-run

# Export and upload to R2
python3 scripts/export_tier3_daily.py --date 2026-01-15 --upload

# Export multiple dates
python3 scripts/export_tier3_daily.py --date 2026-01-13 --date 2026-01-14 --date 2026-01-15 --upload
```

#### CLI Options

| Option | Description |
|--------|-------------|
| `--date YYYY-MM-DD` | Date to export (repeatable). Defaults to yesterday UTC. |
| `--dry-run` | Write local files only, skip R2 upload |
| `--upload` | Upload to R2 after local export |
| `--allow-incomplete` | Bypass completeness guards (for recovery) |

#### Completeness Guards

The exporter enforces two safety checks:

1. **Today Guard**: Refuses to export today's UTC date (day is incomplete)
2. **24-Hour Guard**: Requires all 24 hour files (00–23) to exist

Both guards can be bypassed with `--allow-incomplete` for manual recovery scenarios.

### Output Structure

```
output/tier3_daily/
└── YYYY-MM-DD/
    ├── data.parquet      # Zstd-compressed parquet
    └── manifest.json     # Export metadata
```

### R2 Structure

```
instrumetriq-datasets/
└── tier3/
    └── daily/
        └── YYYY-MM-DD/
            ├── data.parquet
            └── manifest.json
```

### Verification

```bash
# Verify a local export
python3 scripts/verify_tier3_parquet.py --local output/tier3_daily/2026-01-15 --date 2026-01-15

# Verify from R2
python3 scripts/verify_tier3_parquet.py --r2 --date 2026-01-15

# Verify multiple dates
python3 scripts/verify_tier3_parquet.py --r2 --date 2026-01-13 --date 2026-01-14 --date 2026-01-15
```

The verifier checks:
- File presence and size
- Manifest integrity (SHA256, row count, hours completeness)
- Parquet readability
- Required columns present
- Row content sanity (sampling)
- Futures block validity
- Null ratios within expected bounds

### Schema Reference

See [DATASET_SCHEMA_TIER3.md](DATASET_SCHEMA_TIER3.md) for:
- Column schema and types
- Dropped columns
- NULL semantics
- Manifest field descriptions

---

## Tier 2: Weekly Parquet Export

Tier 2 provides weekly aggregations derived from Tier 3 daily inputs, optimized for research and analysis with reduced column footprint.

### Design Principles

1. **Derived from Tier 3**: No direct archive access; reads from R2 `tier3/daily/` inputs
2. **Column Reduction**: Excludes high-volume/low-utility columns to reduce size
3. **Weekly Cadence**: Builds complete 7-day windows (Mon–Sun)

### Column Policy

**Included columns:**
- `symbol` - Ticker symbol
- `snapshot_ts` - Observation timestamp
- `meta` - Entry metadata
- `spot_raw` - Spot market data
- `derived` - Calculated metrics
- `scores` - Scoring results
- `twitter_sentiment_meta` - Twitter metadata

**Excluded columns:**
- `futures_raw` - Full futures data block
- `spot_prices` - Spot price time-series arrays
- `flags` - Boolean flags block
- `diag` - Diagnostics block
- `twitter_sentiment_windows` - Dynamic-key structs (hashtags, handles, domains vary by day)

### Usage

#### Automatic (Cron)

Run weekly on Mondays at 00:05 UTC:

```bash
# Cron entry
5 0 * * 1 cd /srv/instrumetriq && python3 scripts/build_tier2_weekly.py --upload >> /var/log/tier2_weekly.log 2>&1
```

With no `--end-day` argument, the script automatically calculates yesterday as the end of the 7-day window.

#### Manual Export

```bash
# Dry-run (local output only, no R2 operations)
python3 scripts/build_tier2_weekly.py --end-day 2025-12-28 --dry-run

# Build locally (no upload)
python3 scripts/build_tier2_weekly.py --end-day 2025-12-28

# Build and upload to R2
python3 scripts/build_tier2_weekly.py --end-day 2025-12-28 --upload

# Custom output directory
python3 scripts/build_tier2_weekly.py --end-day 2025-12-28 --output-dir ./custom_output --upload
```

#### CLI Options

| Option | Description |
|--------|-------------|
| `--end-day YYYY-MM-DD` | End date of 7-day window (default: yesterday UTC) |
| `--days N` | Override window size (default: 7) |
| `--output-dir PATH` | Local output directory |
| `--dry-run` | Skip R2 upload, local output only |
| `--upload` | Upload results to R2 |

### Window Logic

Given `--end-day 2025-12-28`:
- Window: 2025-12-22 to 2025-12-28 (7 days)
- Requires: All 7 Tier 3 daily parquets in R2
- Output: `tier2/weekly/2025-12-28/dataset_entries_7d.parquet`

### Output Structure

```
output/tier2_weekly/
└── YYYY-MM-DD/
    ├── dataset_entries_7d.parquet  # Zstd-compressed parquet
    └── manifest.json               # Build metadata
```

### R2 Structure

```
instrumetriq-datasets/
└── tier2/
    └── weekly/
        └── YYYY-MM-DD/
            ├── dataset_entries_7d.parquet
            └── manifest.json
```

### Manifest Schema

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
  "source_inputs": ["tier3/daily/2025-12-22/data.parquet", ...],
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

### Prerequisites

1. All Tier 3 daily inputs for the window must exist in R2
2. R2 credentials configured (see Environment Setup)
3. Required packages: `pyarrow`, `boto3`

### Troubleshooting

**"Missing Tier 3 daily parquets for: [dates]"**
→ Run `export_tier3_daily.py` for the missing dates first

**Schema mismatch errors**
→ Ensure you're using the latest version of `build_tier2_weekly.py`
→ The `twitter_sentiment_windows` column must be excluded (it has dynamic schemas)

---

## Tier 1: Real-time Feed

*Coming soon.*

Tier 1 will provide real-time/streaming access for live dashboards and alerting.

---

## Environment Setup

### R2 Credentials

The export scripts require Cloudflare R2 credentials. Configure via:

```bash
python3 scripts/r2_config.py
```

This stores credentials in `~/.config/instrumetriq/r2_credentials.json`.

### Dependencies

```bash
pip install pyarrow boto3
```

---

## Troubleshooting

### "Cannot export today's date"

The exporter blocks today's UTC date because the day is incomplete. Either:
- Wait until after midnight UTC, or
- Use `--allow-incomplete` for partial exports (not recommended for production)

### "Incomplete day: missing hours"

Some hour files are missing from the archive. Either:
- Wait for the missing hours to be written, or
- Use `--allow-incomplete` to export available data

### Verification warnings about duration_sec

Long `meta.duration_sec` values (>9000s) are flagged as warnings but are not critical. These indicate cycles that ran longer than the typical 2-hour window.

### meta.added_ts outside date range

This is expected behavior. Entries are partitioned by archive folder, not by `meta.added_ts`. An entry timestamped late on day N may be written to day N+1's archive folder.
