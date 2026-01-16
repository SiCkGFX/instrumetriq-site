# Tier 3 Dataset Schema

This document describes the Tier 3 daily parquet dataset layout and schema conventions.

## Partition Semantics

**Daily partitions are built from the archive day folder (UTC) containing hourly files 00–23.**

Each daily export represents all entries written to the archive folder for that UTC day. The partition is determined by the archive folder name (e.g., `20260113/`), not by `meta.added_ts` timestamps within the entries.

This means:
- An entry with `meta.added_ts = 2026-01-12T23:55:00Z` may appear in the `2026-01-13` daily export if it was written to the `20260113/` archive folder
- A partial daily export is allowed if at least 20 of 24 hour files are present (configurable via `--min-hours`)

### Partial-Day Exports

Partial-day exports are allowed when:
- At least **20 of 24** hours are available (the `MIN_HOURS` threshold, configurable via `--min-hours`)
- The pipeline was offline for brief periods but recovered

Partial days are **explicitly marked** in the manifest:
- `is_partial: true` indicates fewer than 24 hours were found
- `missing_hours` lists which hour files were absent
- `coverage_ratio` shows the fraction of hours found (e.g., 0.875 for 21/24)
- `rows_by_hour` shows how many entries came from each hour file

**Gaps reflect pipeline uptime**, not missing market data. If the pipeline was offline for 2 hours, those hours will be missing. This is expected for operational incidents and is recorded honestly rather than hidden.

## R2 Layout

Tier 3 daily exports are stored in Cloudflare R2 with the following structure:

```
instrumetriq-datasets/
└── tier3/
    └── daily/
        └── YYYY-MM-DD/
            ├── data.parquet      # Zstd-compressed parquet file
            └── manifest.json     # Export metadata and checksums
```

### File Descriptions

**data.parquet**
- Contains all archive entries for the UTC day
- Compressed with zstd for optimal size/speed tradeoff
- Schema version 7 (v7) entries with nested structs

**manifest.json**
- Export metadata including:
  - `date_utc`: The UTC date covered
  - `row_count`: Number of entries
  - `parquet_sha256`: SHA256 hash for integrity verification
  - `min_added_ts` / `max_added_ts`: Timestamp range of entries
  - `partition_basis`: "archive_folder_utc_day" (how the day is determined)
  - `archive_day`: The archive folder name (YYYYMMDD)
  - `hours_expected`: 24 (expected hour files)
  - `hours_found`: Actual hour files found
  - `missing_hours`: List of hour strings that were absent (e.g., `["03", "04"]`)
  - `coverage_ratio`: Fraction of hours found (e.g., 0.875 for 21/24)
  - `is_partial`: Boolean, true if hours_found < 24
  - `rows_by_hour`: Object mapping each hour ("00"–"23") to row count
  - `min_hours_threshold`: Minimum hours required for export (default 20)
  - `dropped_columns`: Columns intentionally omitted
  - `null_semantics`: Documentation of NULL meanings
  - `export_version`: Schema version of manifest format (currently "1.3")

## Column Schema

The parquet file contains 12 top-level columns:

| Column | Type | Description |
|--------|------|-------------|
| `symbol` | string | Trading pair (e.g., "BTCUSDT") |
| `snapshot_ts` | string | ISO timestamp of snapshot |
| `meta` | struct | Entry metadata (added_ts, duration_sec, schema_version) |
| `spot_raw` | struct | Raw spot market data (bid, ask, depth) |
| `futures_raw` | struct | Futures contract data (basis, funding, OI) |
| `derived` | struct | Calculated metrics (spread_bps, imbalance) |
| `scores` | struct | Scoring results |
| `flags` | struct | Boolean flags and status indicators |
| `diag` | struct | Diagnostic/debug information |
| `twitter_sentiment_windows` | struct | Twitter sentiment data per time window |
| `twitter_sentiment_meta` | struct | Twitter capture metadata |
| `spot_prices` | list\<struct\> | Time series of spot price samples |

### Dropped Columns

The following columns are intentionally **not included** in Tier 3 exports because they are always empty in v7 schema:

- `norm` - Normalized metrics (unused in v7)
- `labels` - Classification labels (unused in v7)

## How to Interpret NULLs

### futures_raw

A NULL value in `futures_raw` means:
- No futures contract is available for this symbol, OR
- Futures data was unavailable at capture time

This is **not an error**. Symbols without perpetual contracts (e.g., some altcoins) will always have NULL futures.

### Optional Struct Columns

NULL in struct columns like `scores`, `diag` indicates:
- The data block was empty or unavailable
- This is expected for some entries and does not indicate corruption

### Required Non-NULL Columns

The following columns should **never** be NULL:
- `symbol`
- `meta`
- `snapshot_ts`
- `spot_raw`

If these are NULL, it indicates a data quality issue.

## Timestamp Semantics

Entries are organized by **write time** (when the entry was added to the archive), not by monitoring window start time. This means:

- An entry with `meta.added_ts = 2026-01-12T23:55:00Z` may appear in the `2026-01-13` daily file if it was written shortly after midnight UTC
- The `min_added_ts` and `max_added_ts` in the manifest show the actual timestamp range

## Field Dictionary

> **Coming soon:** A detailed field-by-field dictionary documenting every nested field will be added in a future update.

For now, refer to:
- `data/schema/ARCHIVE_ENTRY_FULL_SCHEMA.txt` - V7 schema overview
- `data/canonical_fields.md` - Field coverage report
