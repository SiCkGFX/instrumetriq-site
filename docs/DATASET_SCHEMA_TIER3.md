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

## Nested Field Reference

### meta

| Field | Type | Description |
|-------|------|-------------|
| `added_ts` | string | ISO timestamp when entry was added to archive |
| `archive_schema_version` | int64 | Schema version (currently 7) |
| `duration_sec` | double | Monitoring duration in seconds |
| `expired_ts` | string | When entry was marked expired |
| `expires_ts` | string | When entry is scheduled to expire |
| `futures_api_base` | string | Futures API base URL used |
| `last_sample_ts` | string | Timestamp of last price sample |
| `normalization_version` | string | Version of normalization logic |
| `pairbonus_version` | string | Version of pair bonus logic |
| `sample_count` | int64 | Number of price samples collected |
| `schema_version` | int64 | Entry schema version |
| `scoring_version` | string | Version of scoring logic |
| `session_id` | string | Unique session identifier |
| `source` | string | Data source identifier |
| `total_samples` | int64 | Total samples in monitoring window |
| `universe_page` | int64 | Universe pagination page |
| `universe_page_size` | int64 | Universe page size |
| `universe_snapshot_id` | string | Universe snapshot identifier |
| `universe_snapshot_lag_sec` | double | Lag from universe snapshot |
| `universe_snapshot_ts` | string | Universe snapshot timestamp |

### spot_raw

| Field | Type | Description |
|-------|------|-------------|
| `ask` | double | Best ask price |
| `avg_impact_pct` | double | Average price impact percentage |
| `bid` | double | Best bid price |
| `depth_10bps_quote` | double | Order book depth at 10 bps |
| `depth_25bps_quote` | double | Order book depth at 25 bps |
| `depth_5bps_quote` | double | Order book depth at 5 bps |
| `depth_ask_qty_quote` | double | Ask-side depth in quote currency |
| `depth_bid_qty_quote` | double | Bid-side depth in quote currency |
| `last` | double | Last traded price |
| `liq_eff_raw` | double | Raw liquidity efficiency |
| `liq_qv_usd` | double | Quote volume liquidity in USD |
| `micro_premium_pct` | double | Micro premium percentage |
| `mid` | double | Mid price |
| `obi_5` | double | Order book imbalance at 5 levels |
| `range_pct_24h` | double | 24-hour price range percentage |
| `spread_bps` | double | Bid-ask spread in basis points |
| `spread_eff_raw` | double | Raw effective spread |
| `taker_buy_ratio_5m` | double | Taker buy ratio over 5 minutes |
| `ticker24_chg` | double | 24-hour ticker price change |

### futures_raw

| Field | Type | Description |
|-------|------|-------------|
| `age_sec` | int64 | Age of futures data in seconds |
| `basis_now_bps` | double | Current basis in basis points |
| `contract` | string | Futures contract name |
| `funding_24h_mean` | double | 24-hour mean funding rate |
| `funding_now` | double | Current funding rate |
| `last_updated_ts` | string | Last update timestamp |
| `open_interest` | double | Open interest value |
| `open_interest_1h_delta_pct` | double | 1-hour OI change percentage |
| `top_long_short_accounts_1h` | double | Top trader long/short account ratio |
| `top_long_short_positions_1h` | double | Top trader long/short position ratio |

### derived

| Field | Type | Description |
|-------|------|-------------|
| `depth_imbalance` | double | Order book depth imbalance |
| `depth_skew` | double | Depth skew metric |
| `depth_spread_bps` | double | Depth-adjusted spread |
| `depth_weighted` | double | Weighted depth metric |
| `flow` | double | Flow metric |
| `liq_global_pct` | double | Global liquidity percentile |
| `liq_self_pct` | double | Self liquidity percentile |
| `spread_bps` | double | Derived spread in basis points |
| `spread_pct` | double | Spread as percentage |

### scores

| Field | Type | Description |
|-------|------|-------------|
| `compression_score` | double | Compression algorithm score |
| `depth` | double | Depth score component |
| `final` | double | Final composite score |
| `flow` | double | Flow score component |
| `liq` | double | Liquidity score component |
| `liq_eff_score` | double | Liquidity efficiency score |
| `microstruct` | double | Microstructure score |
| `mom` | double | Momentum score component |
| `spread` | double | Spread score component |
| `spread_eff_score` | double | Spread efficiency score |
| `str` | double | Strength score component |
| `taker` | double | Taker activity score |
| `vol` | double | Volatility score component |

### flags

| Field | Type | Description |
|-------|------|-------------|
| `compression_enabled` | bool | Whether compression is enabled |
| `futures_contract_check_failed` | bool | Futures contract check failed |
| `futures_contract_exists` | bool | Futures contract exists for symbol |
| `futures_data_ok` | bool | Futures data is valid |
| `futures_stale` | bool | Futures data is stale |
| `mom_fallback` | bool | Momentum used fallback |
| `pair_bonus_applied` | double | Pair bonus value applied |
| `spot_data_ok` | bool | Spot data is valid |
| `spread_fallback` | bool | Spread used fallback |
| `twitter_data_ok` | bool | Twitter sentiment data is valid |
| `vol_fallback` | bool | Volatility used fallback |

### diag

| Field | Type | Description |
|-------|------|-------------|
| `admission_validated` | bool | Entry passed admission validation |
| `admission_validation_ts` | string | Validation timestamp |
| `build_duration_ms` | double | Build duration in milliseconds |
| `builder_version` | string | Builder version string |

### twitter_sentiment_meta

| Field | Type | Description |
|-------|------|-------------|
| `bucket_meta` | struct | Nested metadata about the sentiment bucket |
| `captured_at_utc` | string | ISO timestamp of capture |
| `key_used` | string | API key identifier used |
| `source` | string | Data source (e.g., "twscrape_snapshot") |

### twitter_sentiment_windows

Contains two cycle windows: `last_cycle` and `last_2_cycles`. Each contains:

| Field | Type | Description |
|-------|------|-------------|
| `ai_sentiment` | struct | AI model sentiment scores and stats |
| `author_stats` | struct | Author follower counts and distinct authors |
| `bucket_has_valid_sentiment` | bool | Whether bucket has valid sentiment |
| `bucket_min_posts_for_score` | int64 | Minimum posts required for scoring |
| `bucket_status` | string | Bucket status indicator |
| `cashtag_counts` | struct | Cashtag mention counts (dynamic keys) |
| `category_counts` | struct | Counts per sentiment category |
| `content_stats` | struct | Content type statistics |
| `cycle_end_utc` | string | Cycle end timestamp (last_2_cycles only) |
| `cycle_start_utc` | string | Cycle start timestamp (last_2_cycles only) |
| `from_cycle_id` | int64 | Starting cycle ID (last_2_cycles only) |
| `hybrid_decision_stats` | struct | Combined decision source stats |
| `lexicon_sentiment` | struct | Lexicon-based sentiment score |
| `media_count` | int64 | Media attachment count |
| `mention_counts` | struct | @mention counts (dynamic keys) |
| `platform_engagement` | struct | Likes, retweets, replies, views |
| `posts_neg` | int64 | Negative posts count |
| `posts_neu` | int64 | Neutral posts count |
| `posts_pos` | int64 | Positive posts count |
| `posts_total` | int64 | Total posts count |
| `sentiment_activity` | struct | Activity metrics (is_silent, hours_since_latest_tweet) |
| `tag_counts` | struct | Hashtag counts (dynamic keys) |
| `to_cycle_id` | int64 | Ending cycle ID (last_2_cycles only) |
| `top_terms` | struct | Top sentiment-triggering terms |
| `url_domain_counts` | struct | URL domain counts (dynamic keys) |
| `window_cycles` | int64 | Number of cycles in window (last_2_cycles only) |

**Note:** Fields marked "dynamic keys" contain thousands of unique keys (hashtags, mentions, domains) that vary between entries. These fields have high cardinality and may cause schema compatibility issues when merging across days.

### spot_prices (list element)

| Field | Type | Description |
|-------|------|-------------|
| `ask` | double | Ask price at sample time |
| `bid` | double | Bid price at sample time |
| `mid` | double | Mid price at sample time |
| `spread_bps` | double | Spread in basis points |
| `ts` | string | ISO timestamp of sample |

---

## Related Documentation

- [DATASET_EXPORT_GUIDE.md](DATASET_EXPORT_GUIDE.md) - Export workflow and usage
- [DATASET_SCHEMA_TIER2.md](DATASET_SCHEMA_TIER2.md) - Tier 2 daily schema
- [DATASET_SCHEMA_TIER1.md](DATASET_SCHEMA_TIER1.md) - Tier 1 daily schema
