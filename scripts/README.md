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

# 3. Build and deploy
npm run build
npm run publish
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
- Standard library only (no external packages required)
- Python 3.8+ recommended

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
├── sync_from_archive.py           # Archive data sync
├── deploy_to_cloudflare.py        # Cloudflare deployment
├── lint_wording.mjs               # Wording compliance
├── inspect_field_coverage.py      # Field inspection tool
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
