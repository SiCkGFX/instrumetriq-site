# Dataset Export Guide

This guide covers the tiered dataset export system for Instrumetriq archives.

## Overview

The archive data is exported in multiple tiers, each serving different use cases:

| Tier | Granularity | Update Frequency | Primary Use Case |
|------|-------------|------------------|------------------|
| Tier 1 | Real-time | Continuous | Live dashboards, alerts |
| Tier 2 | Hourly | Every hour | Intraday analysis |
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

## Tier 2: Hourly Export

*Coming soon.*

Tier 2 will provide hourly granularity for intraday analysis.

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
