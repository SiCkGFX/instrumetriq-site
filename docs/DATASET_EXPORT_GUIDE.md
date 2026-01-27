# Dataset Export Guide

This guide covers the tiered dataset export system for Instrumetriq archives.

## Overview

The archive data is exported in multiple tiers, each serving different use cases. **All tiers are now daily exports**, built in sequence each night.

| Tier | Granularity | Schema | Primary Use Case |
|------|-------------|--------|------------------|
| **Tier 1** | Daily | 19 flattened fields | Starter table with aggregated sentiment (no futures) |
| **Tier 2** | Daily | 8 nested columns | Research, reduced column footprint |
| **Tier 3** | Daily | 12 nested columns | Full historical data, ML training |

### Daily Build Schedule

All tiers build daily at these UTC times:

| Tier | Cron Time | Script |
|------|-----------|--------|
| Tier 3 | 00:10 UTC | `export_tier3_daily.py` |
| Tier 2 | 00:20 UTC | `build_tier2_daily.py` |
| Tier 1 | 00:30 UTC | `build_tier1_daily.py` |

---

## Tier 3: Daily Parquet Export

Tier 3 exports produce daily Parquet files containing all archive entries for a UTC day.

### Partition Semantics

Daily partitions are built from the **archive folder day (UTC)**, not from `meta.added_ts` timestamps. Each export includes all entries from hour files `00.jsonl.gz` through `23.jsonl.gz` in the corresponding `YYYYMMDD/` archive folder.

### Usage

#### Automatic (Cron)

The standard operational pattern runs via cron at **00:10 UTC**, exporting the previous day:

```bash
# Cron entry (runs at 00:10 UTC daily)
10 0 * * * cd /srv/instrumetriq && python3 scripts/export_tier3_daily.py --upload >> /var/log/tier3_daily.log 2>&1
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

## Tier 2: Daily Parquet Export

Tier 2 provides daily exports derived from Tier 3 with reduced column footprint, optimized for research and analysis.

### Design Principles

1. **Derived from Tier 3**: Reads from R2 `tier3/daily/` inputs
2. **Column Reduction**: Excludes high-volume/low-utility columns to reduce size
3. **Daily Cadence**: Builds daily, same as Tier 3

### Column Policy (8 columns)

**Included columns:**
- `symbol` - Ticker symbol
- `snapshot_ts` - Observation timestamp
- `meta` - Entry metadata
- `spot_raw` - Spot market data
- `derived` - Calculated metrics
- `scores` - Scoring results
- `twitter_sentiment_meta` - Twitter metadata
- `twitter_sentiment_last_cycle` - Sentiment from last 2-hour cycle (selected fields only)

**Excluded columns:**
- `futures_raw` - Full futures data block, available in Tier 3
- `spot_prices` - Time-series arrays, high volume
- `flags` - Boolean flags block, debugging only
- `diag` - Diagnostics block, internal use

### Usage

#### Automatic (Cron)

Runs daily at 00:20 UTC (after Tier 3 completes):

```bash
# Cron entry
20 0 * * * cd /srv/instrumetriq && python3 scripts/build_tier2_daily.py --upload >> /var/log/tier2_daily.log 2>&1
```

With no `--date` argument, the script automatically builds yesterday's data.

#### Manual Export

```bash
# Dry-run for specific date
python3 scripts/build_tier2_daily.py --date 2026-01-18 --dry-run

# Build and upload
python3 scripts/build_tier2_daily.py --date 2026-01-18 --upload

# Build date range
python3 scripts/build_tier2_daily.py --from-date 2026-01-15 --to-date 2026-01-18 --upload

# Force overwrite existing
python3 scripts/build_tier2_daily.py --date 2026-01-18 --upload --force
```

#### CLI Options

| Option | Description |
|--------|-------------|
| `--date YYYY-MM-DD` | Date to build (default: yesterday UTC) |
| `--from-date YYYY-MM-DD` | Start date for range |
| `--to-date YYYY-MM-DD` | End date for range |
| `--dry-run` | Local build only, no R2 upload |
| `--upload` | Upload results to R2 |
| `--force` | Overwrite existing files |

### Output Structure

```
output/tier2_daily/
└── YYYY-MM-DD/
    ├── data.parquet    # Zstd-compressed parquet
    └── manifest.json   # Build metadata
```

### R2 Structure

```
instrumetriq-datasets/
└── tier2/
    └── daily/
        └── YYYY-MM-DD/
            ├── data.parquet
            └── manifest.json
```

### Manifest Schema

```json
{
  "schema_version": "v7",
  "tier": "tier2",
  "tier_description": "Research — reduced column footprint with sentiment last_cycle",
  "date_utc": "2026-01-18",
  "source_tier3": "tier3/daily/2026-01-18/data.parquet",
  "row_count": 2615,
  "build_ts_utc": "2026-01-19T00:20:05.123456+00:00",
  "parquet_sha256": "...",
  "parquet_size_bytes": 912345,
  "column_policy": {
    "columns": ["symbol", "snapshot_ts", "meta", "spot_raw", "derived", "scores", "twitter_sentiment_meta", "twitter_sentiment_last_cycle"],
    "excluded_from_tier3": ["futures_raw", "spot_prices", "flags", "diag"],
    "sentiment_source": "twitter_sentiment_windows.last_cycle"
  }
}
```

### Prerequisites

1. Tier 3 daily parquet for the date must exist in R2
2. R2 credentials configured (see Environment Setup)
3. Required packages: `duckdb`, `boto3`

### Troubleshooting

**"Tier 3 source not found"**
→ Run `export_tier3_daily.py` for the missing date first

---

## Tier 1: Daily Parquet Export (Starter)

Tier 1 is the **"Starter — light entry table"** with aggregated sentiment. It extracts and flattens specific fields from Tier 3 structs into a stable, predictable schema.

### Field Policy (19 flattened fields)

**Approach:** Explicit allowlist with flattened fields (no nested structs)

| Category | Fields |
|----------|--------|
| Identity + Timing (6) | `symbol`, `snapshot_ts`, `meta_added_ts`, `meta_expires_ts`, `meta_duration_sec`, `meta_archive_schema_version` |
| Core Spot (4) | `spot_mid`, `spot_spread_bps`, `spot_range_pct_24h`, `spot_ticker24_chg` |
| Minimal Derived (2) | `derived_liq_global_pct`, `derived_spread_bps` |
| Minimal Scoring (1) | `score_final` |
| Aggregated Sentiment (6) | `sentiment_posts_total`, `sentiment_posts_pos`, `sentiment_posts_neu`, `sentiment_posts_neg`, `sentiment_mean_score`, `sentiment_is_silent` |

**Key exclusions:**
- All futures data (`futures_raw`, `flags.futures_data_ok`)
- All sentiment internals (decision_sources, conf_mean, top_terms, category_counts, etc.)
- Time-series arrays (`spot_prices`)
- Full nested structs (fields are flattened instead)

**Sentiment source:** `twitter_sentiment_windows.last_cycle` — aggregated sentiment only, no internals.

### Usage

#### Automatic (Cron)

Runs daily at 00:30 UTC (after Tier 2 completes):

```bash
# Cron entry
30 0 * * * cd /srv/instrumetriq && python3 scripts/build_tier1_daily.py --upload >> /var/log/tier1_daily.log 2>&1
```

#### Manual Export

```bash
# Dry-run for specific date
python3 scripts/build_tier1_daily.py --date 2026-01-18 --dry-run

# Build and upload
python3 scripts/build_tier1_daily.py --date 2026-01-18 --upload

# Build date range
python3 scripts/build_tier1_daily.py --from-date 2026-01-15 --to-date 2026-01-18 --upload
```

### R2 Structure

```
instrumetriq-datasets/
└── tier1/
    └── daily/
        └── YYYY-MM-DD/
            ├── data.parquet
            └── manifest.json
```

### Tier Comparison

| Tier | Approach | Columns | Sentiment | Futures |
|------|----------|---------|-----------|----------|
| **Tier 1** | Flattened allowlist | 19 flat fields | Aggregated only | ❌ Excluded |
| **Tier 2** | Struct exclusion | 8 nested columns | Full last_cycle | ❌ Excluded |
| **Tier 3** | Institutional | 12 nested columns | Full windows | ✅ Included |

See [DATASET_SCHEMA_TIER1.md](DATASET_SCHEMA_TIER1.md) for full schema documentation.

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
