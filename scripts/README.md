# Scripts Directory

This directory contains build scripts and utilities for the Instrumetriq website.

## Overview

All scripts follow the pattern: **`action_target.extension`**
- `generate_*` = Creates JSON artifacts for the website
- `sync_*` = Pulls data from external sources
- `deploy_*` = Deployment operations
- `lint_*` = Code quality checks
- `inspect_*` = Debugging/analysis tools

## Core Scripts (Active Use)

### Website Artifact Generators

These scripts generate JSON files under `public/data/` that are loaded by the website:

#### `generate_research_artifacts.py`
**Purpose:** Generates Phase 2A behavioral summaries for `/research` page  
**Outputs:**
- `public/data/activity_regimes.json` - Tweet volume bins with market metrics
- `public/data/sampling_density.json` - Price sampling statistics
- `public/data/session_lifecycle.json` - Monitoring window durations

**Usage:**
```bash
python scripts/generate_research_artifacts.py --archive-path /srv/cryptobot/data/archive
```

**When to run:** After archive updates, before deploying research page changes

---

#### `generate_archive_stats.py`
**Purpose:** Computes full archive scale metrics for dataset page cassette  
**Outputs:**
- `public/data/archive_stats.json` - Total entries, date range, freshness

**Usage:**
```bash
python scripts/generate_archive_stats.py --archive-path /srv/cryptobot/data/archive
```

**When to run:** Daily or after major archive updates

---

#### `generate_coverage_table.py`
**Purpose:** Builds field coverage table for "What We Collect" section  
**Outputs:**
- `public/data/coverage_table.json` - Field availability and examples

**Usage:**
```bash
python scripts/generate_coverage_table.py
```

**When to run:** After schema changes or when coverage_report updates

---

#### `generate_dataset_overview.py`
**Purpose:** Creates surface-level dataset overview for `/dataset` page  
**Outputs:**
- `public/data/dataset_overview.json` - Scale, freshness, preview row

**Usage:**
```bash
python scripts/generate_dataset_overview.py
```

**When to run:** After sample data updates

---

#### `generate_public_samples.py`
**Purpose:** Generates public preview entries with deterministic rotation  
**Outputs:**
- `public/data/sample_entries_v7.json` - 100 entry preview (no spot_prices)
- `public/data/sample_entries_spots_v7.json` - Spot prices (separate for size limit)
- `public/data/sample_entries_v7.jsonl` - JSONL format

**Usage:**
```bash
python scripts/generate_public_samples.py
```

**When to run:** Daily for rotating preview

---

### Data Sync Scripts

#### `sync_from_archive.py`
**Purpose:** Extracts most recent N entries from CryptoBot archive  
**Outputs:**
- `data/samples/cryptobot_latest_tail200.jsonl` - Sample for artifact builders
- `data/samples/cryptobot_latest_tail200.meta.json` - Metadata

**Usage:**
```bash
python scripts/sync_from_archive.py --n 200 --archive-path /srv/cryptobot/data/archive
```

**When to run:** Before running artifact generators

---

### Deployment Scripts

#### `deploy_to_cloudflare.py`
**Purpose:** Deploys site to Cloudflare Pages via Wrangler CLI  
**Usage:**
```bash
python scripts/deploy_to_cloudflare.py
# or via npm:
npm run publish
```

**When to run:** After successful build and artifact generation

---

### Quality Assurance Scripts

#### `lint_wording.mjs`
**Purpose:** Validates copy against `docs/WORDING_RULES.md` SSOT  
**Usage:**
```bash
node scripts/lint_wording.mjs
# or via npm:
npm run lint:wording
```

**When to run:** Automatically runs before `npm run build`

---

## Configuration Modules

#### `r2_config.py`
**Purpose:** Centralized loader for Cloudflare R2 credentials from environment variables  
**Provides:**
- `get_r2_config()` - Returns R2Config with endpoint, access_key_id, secret_access_key, bucket
- `get_cloudflare_api_token()` - Returns optional Cloudflare API token

**Environment Variables Required:** (set via `~/.r2_credentials` on VPS)
- `R2_ENDPOINT` - S3-compatible endpoint URL
- `R2_ACCESS_KEY_ID` - Access key for R2
- `R2_SECRET_ACCESS_KEY` - Secret key for R2
- `R2_BUCKET` - Target bucket name
- `CLOUDFLARE_API_TOKEN` (optional) - For Cloudflare API calls

**Usage:**
```python
from r2_config import get_r2_config

config = get_r2_config()
# Use config.endpoint, config.access_key_id, etc.
```

**Validation:**
```bash
python3 scripts/r2_config.py  # Validates all required vars are set
```

---

#### `init_r2_structure.py`
**Purpose:** Initializes the R2 bucket folder/prefix structure for dataset tiers  
**Creates:**
```
tier1/daily/.keep
tier2/daily/.keep
tier3/daily/.keep
tier3/full/.keep
```

**Usage:**
```bash
python3 scripts/init_r2_structure.py
```

**Notes:**
- Idempotent (safe to re-run)
- Creates zero-byte `.keep` files to materialize prefixes
- Requires R2 credentials in environment

---

## Utility Scripts (As Needed)

#### `inspect_field_coverage.py`
**Purpose:** Phase 1A inspection tool - discovers actual field paths in archive data  
**Outputs:**
- `data/field_coverage_report.json` - Machine-readable coverage map
- `data/field_coverage_report.md` - Human-readable report

**Usage:**
```bash
python scripts/inspect_field_coverage.py
```

**When to run:** When schema changes or debugging field availability

---

## R2 Dataset Export Scripts

### `export_tier3_daily.py`
**Purpose:** Exports daily archive data to Parquet and uploads to Cloudflare R2  
**Outputs:**
- Local: `output/tier3_daily/{date}/data.parquet` - Zstd-compressed Parquet
- Local: `output/tier3_daily/{date}/manifest.json` - Export metadata
- R2: `tier3/daily/{date}/data.parquet` - Authoritative daily dataset
- R2: `tier3/daily/{date}/manifest.json` - Manifest with SHA256

**Usage:**
```bash
# Self-test (validates entry parsing and schema)
python3 scripts/export_tier3_daily.py --self-test

# Dry run (exports locally, no R2 upload)
python3 scripts/export_tier3_daily.py --date 2026-01-14

# Full export with R2 upload
python3 scripts/export_tier3_daily.py --date 2026-01-14 --upload

# Export yesterday's data
python3 scripts/export_tier3_daily.py --yesterday --upload

# Export partial day with custom minimum hours
python3 scripts/export_tier3_daily.py --date 2026-01-14 --min-hours 18 --upload
```

**Features:**
- Loads all available hour files for a UTC day from archive
- Validates schema version (currently v7)
- Converts nested JSON to Parquet with zstd compression
- Generates manifest with SHA256 checksums and coverage metadata
- Supports partial-day exports (default: requires 20/24 hours minimum)
- Uploads to R2 `tier3/daily/{date}/` prefix

**Partial-Day Support:**
- By default, requires at least 20 of 24 hour files (`--min-hours 20`)
- Missing hours are recorded in manifest (`missing_hours`, `coverage_ratio`, `is_partial`)
- `rows_by_hour` shows entry distribution across hours
- Use `--min-hours 24` to require complete days (strict mode)

**Requirements:**
- pyarrow (for Parquet export)
- boto3 (for R2 upload)
- R2 credentials in environment (see `r2_config.py`)

**When to run:** Daily after archive rotation (e.g., 02:00 UTC for previous day)

---

### `build_tier1_weekly.py`
**Purpose:** Derives Tier 1 weekly parquets from Tier 3 daily inputs in R2 (most minimal dataset)  
**Outputs:**
- Local: `output/tier1_weekly/{end-date}/dataset_entries_7d.parquet` - Zstd-compressed
- Local: `output/tier1_weekly/{end-date}/manifest.json` - Build metadata
- R2: `tier1/weekly/{end-date}/dataset_entries_7d.parquet` - Weekly dataset
- R2: `tier1/weekly/{end-date}/manifest.json` - Manifest with SHA256

**Tier 1 Column Policy (5 columns - most minimal):**
- **Included columns:** `symbol`, `snapshot_ts`, `meta`, `spot_raw`, `scores`
- **Excluded columns:** `derived`, `twitter_sentiment_meta`, `futures_raw`, `spot_prices`, `flags`, `diag`, `twitter_sentiment_windows`

**Tier Hierarchy:**
| Tier | Columns | Description |
|------|---------|-------------|
| Tier 1 | 5 | Core price/liquidity metrics only |
| Tier 2 | 7 | Tier 1 + `derived`, `twitter_sentiment_meta` |
| Tier 3 | 12 | Full archive data |

**Usage:**
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

**Weekly Window Logic:**
- `--previous-week`: Computes end_day as the most recent Sunday (UTC) strictly before today
  - On Monday 00:05 UTC, this yields yesterday (Sunday), covering Mon-Sun
  - Manifest records `window_basis: "previous_week_utc"`
- `--end-day YYYY-MM-DD`: Builds the 7-day window ending on that date
  - Manifest records `window_basis: "end_day"`
- By default, requires **at least 5 of 7** Tier 3 days (`--min-days 5`)
- Missing days and partial days are recorded in manifest `source_coverage` block

**Partial Week Support:**
- If some Tier 3 days are missing from R2, Tier 1 can still be built if >= min-days are present
- The manifest `source_coverage` block explicitly documents:
  - `days_missing`: which days were not found
  - `partial_days_count`: how many included days had < 24 hours
  - `per_day`: coverage metadata for each included day (including `missing_hours`)

**Cron Schedule:**
Run Mondays at 00:05 UTC to build the previous complete Mon-Sun week:
```bash
# /etc/cron.d/tier1_weekly
5 0 * * 1 instrum cd /srv/instrumetriq && python3 scripts/build_tier1_weekly.py --previous-week --upload 2>&1 | logger -t tier1_weekly
```

**Requirements:**
- pyarrow (for Parquet I/O)
- boto3 (for R2 operations)
- R2 credentials in environment (see `r2_config.py`)
- At least 5 of 7 Tier 3 daily inputs must exist in R2 (configurable)

**When to run:** Weekly on Mondays, after Tier 3 daily exports are complete

---

### `build_tier2_weekly.py`
**Purpose:** Derives Tier 2 weekly parquets from Tier 3 daily inputs in R2  
**Outputs:**
- Local: `output/tier2_weekly/{end-date}/dataset_entries_7d.parquet` - Zstd-compressed
- Local: `output/tier2_weekly/{end-date}/manifest.json` - Build metadata
- R2: `tier2/weekly/{end-date}/dataset_entries_7d.parquet` - Weekly dataset
- R2: `tier2/weekly/{end-date}/manifest.json` - Manifest with SHA256

**Tier 2 Column Policy:**
- **Excluded columns:** `futures_raw`, `spot_prices`, `flags`, `diag`, `twitter_sentiment_windows`
- **Included columns:** `symbol`, `snapshot_ts`, `meta`, `spot_raw`, `derived`, `scores`, `twitter_sentiment_meta`

**Note:** `twitter_sentiment_windows` is excluded because it contains dynamic-key structs
(hashtag/handle/domain names as field names) that differ between days, causing schema
incompatibility. The essential metadata is preserved in `twitter_sentiment_meta`.

**Usage:**
```bash
# Cron mode: build previous Mon-Sun week (for Monday 00:05 UTC cron)
python3 scripts/build_tier2_weekly.py --previous-week --upload

# Dry-run to see computed window
python3 scripts/build_tier2_weekly.py --previous-week --dry-run

# Manual/backfill: build specific week ending on a date
python3 scripts/build_tier2_weekly.py --end-day 2025-12-28 --upload

# Build partial week (requires at least 5 days)
python3 scripts/build_tier2_weekly.py --end-day 2026-01-15 --min-days 5 --upload

# Custom output directory
python3 scripts/build_tier2_weekly.py --end-day 2025-12-28 --output-dir ./my_output --upload
```

**Weekly Window Logic:**
- `--previous-week`: Computes end_day as the most recent Sunday (UTC) strictly before today
  - On Monday 00:05 UTC, this yields yesterday (Sunday), covering Mon-Sun
  - Manifest records `window_basis: "previous_week_utc"`
- `--end-day YYYY-MM-DD`: Builds the 7-day window ending on that date
  - Manifest records `window_basis: "end_day"`
- By default, requires **at least 5 of 7** Tier 3 days (`--min-days 5`)
- Missing days and partial days are recorded in manifest `source_coverage` block

**Partial Week Support:**
- If some Tier 3 days are missing from R2, Tier 2 can still be built if >= min-days are present
- The manifest `source_coverage` block explicitly documents:
  - `days_missing`: which days were not found
  - `partial_days_count`: how many included days had < 24 hours
  - `per_day`: coverage metadata for each included day (including `missing_hours`)

**Cron Schedule:**
Run Mondays at 00:05 UTC to build the previous complete Mon-Sun week:
```bash
# /etc/cron.d/tier2_weekly
5 0 * * 1 instrum cd /srv/instrumetriq && python3 scripts/build_tier2_weekly.py --previous-week --upload 2>&1 | logger -t tier2_weekly
```

**Requirements:**
- pyarrow (for Parquet I/O)
- boto3 (for R2 operations)
- R2 credentials in environment (see `r2_config.py`)
- At least 5 of 7 Tier 3 daily inputs must exist in R2 (configurable)

**When to run:** Weekly on Mondays, after Tier 3 daily exports are complete

---

### `verify_tier3_parquet.py`
**Purpose:** Validates Tier 3 daily parquet exports for correctness and completeness  
**Outputs:**
- Report: `output/verify_tier3_report.md` - Human-readable verification report
- Artifacts: `output/verify_tier3/{date}/` - Schema, manifest copy, stats

**Usage:**
```bash
# Verify most recent export from R2
python3 scripts/verify_tier3_parquet.py

# Verify specific dates
python3 scripts/verify_tier3_parquet.py --date 2026-01-14 --date 2026-01-15

# Verify local files
python3 scripts/verify_tier3_parquet.py --local output/tier3_daily/2026-01-14
```

**Partial-Day Handling:**
- Reads `min_hours_threshold` from manifest (default: 20 if absent)
- **PASS**: ≥ threshold hours with full coverage (24/24)
- **WARN**: ≥ threshold hours but partial coverage (e.g., 21/24) - proceeds with warning
- **FAIL**: < threshold hours - insufficient data for reliable export

The report shows hours found, coverage ratio, and missing hours for each date.

**When to run:** After Tier 3 exports to validate data integrity

---

### `verify_tier2_weekly.py`
**Purpose:** Validates Tier 2 weekly parquet exports for correctness and completeness  
**Outputs:**
- Report: `output/verify_tier2_report.md` - Human-readable verification report
- Artifacts: `output/verify_tier2/{end-day}/manifest.json` - Downloaded manifest copy
- Artifacts: `output/verify_tier2/{end-day}/schema.txt` - PyArrow schema pretty print
- Artifacts: `output/verify_tier2/{end-day}/stats.json` - Machine-readable summary

**Usage:**
```bash
# Verify most recent week from R2
python3 scripts/verify_tier2_weekly.py

# Verify specific week by end date
python3 scripts/verify_tier2_weekly.py --end-day 2025-12-28

# Verify local files
python3 scripts/verify_tier2_weekly.py --local output/tier2_weekly/2025-12-28
```

**Checks performed:**
- Object presence and SHA256 integrity
- Window semantics (7-day window with days_expected/days_included)
- Column policy (required present, excluded absent)
- Data quality stats (row counts, null ratios, duration stats)
- Source coverage validation (new):
  - FAIL if `present_days_count` < `min_days_threshold_used`
  - WARN if `missing_days_count` > 0 or `partial_days_count` > 0
  - Reports per-day coverage details

**When to run:** After Tier 2 builds to validate data integrity

---

## Typical Workflow

### Daily Updates
```bash
# 1. Sync latest archive data
python scripts/sync_from_archive.py --n 200 --archive-path /srv/cryptobot/data/archive

# 2. Regenerate all artifacts
python scripts/generate_research_artifacts.py --archive-path /srv/cryptobot/data/archive
python scripts/generate_archive_stats.py --archive-path /srv/cryptobot/data/archive
python scripts/generate_dataset_overview.py
python scripts/generate_public_samples.py

# 3. Export previous day to R2 (Tier 3 daily Parquet)
python3 scripts/export_tier3_daily.py --yesterday --upload

# 4. Build and deploy
npm run build
npm run publish
```

### Weekly Updates (Tier 1 + Tier 2)
```bash
# Run on Mondays after Tier 3 daily exports complete
# Builds previous Mon-Sun week
python3 scripts/build_tier1_weekly.py --previous-week --upload
python3 scripts/build_tier2_weekly.py --previous-week --upload
```

### Schema Changes
```bash
# 1. Inspect new field structure
python scripts/inspect_field_coverage.py

# 2. Update artifact generators based on findings

# 3. Regenerate coverage table
python scripts/generate_coverage_table.py

# 4. Test and deploy
npm run build
```

---

## Script Dependencies

### Python Scripts
- Python 3.10+ recommended
- Most scripts use standard library only
- R2/export scripts require:
  - `boto3` - AWS S3-compatible client for R2
  - `pyarrow` - Parquet file creation

Install with:
```bash
pip install boto3 pyarrow
```

### JavaScript Scripts
- Node.js 18+ required for `lint_wording.mjs`

---

## Directory Structure

```
scripts/
├── README.md                      # This file
├── generate_research_artifacts.py # Phase 2A artifacts
├── generate_archive_stats.py      # Archive scale metrics
├── generate_coverage_table.py     # Field coverage table
├── generate_dataset_overview.py   # Dataset page overview
├── generate_public_samples.py     # Public preview entries
├── generate_sentiment_timeseries.py # Twitter sentiment timeseries
├── sync_from_archive.py           # Archive data sync
├── deploy_to_cloudflare.py        # Cloudflare deployment
├── lint_wording.mjs               # Wording compliance
├── inspect_field_coverage.py      # Field inspection tool
├── r2_config.py                   # R2 credentials loader
├── init_r2_structure.py           # R2 bucket initialization
├── export_tier3_daily.py          # Tier 3 daily Parquet export
├── verify_tier3_parquet.py        # Tier 3 verification + report
├── build_tier1_weekly.py          # Tier 1 weekly derived from Tier 3 (5 columns)
├── build_tier2_weekly.py          # Tier 2 weekly derived from Tier 3 (7 columns)
├── verify_tier2_weekly.py         # Tier 2 verification + report
└── tools/                         # Helper utilities
    └── sync_cryptobot_sample.py   # CryptoBot-specific sync
```

---

## Notes

- All artifact generators write to `public/data/` (committed to repo)
- Sample data lives in `data/samples/` (not committed)
- Archive path defaults to local Windows path; override with `--archive-path` on VPS
- Scripts are idempotent and can be run multiple times safely
- Artifacts are deterministic (except for timestamps)

---

## Troubleshooting

**"Archive path not found"**
→ Use `--archive-path` flag to specify correct location

**"Sample file not found"**
→ Run `sync_from_archive.py` first to populate sample data

**"Field not in SSOT"**
→ Run `inspect_field_coverage.py` to regenerate field coverage report

**Build artifacts too large**
→ Check artifact sizes in `public/data/` (should all be <10KB except samples)
