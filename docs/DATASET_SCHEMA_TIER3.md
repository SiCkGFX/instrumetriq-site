# Tier 3 Dataset Schema

This document describes the Tier 3 daily parquet dataset layout and schema conventions.

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
  - `min_added_ts` / `max_added_ts`: Timestamp range
  - `dropped_columns`: Columns intentionally omitted
  - `null_semantics`: Documentation of NULL meanings

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
