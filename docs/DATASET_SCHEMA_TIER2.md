# Tier 2 Daily Dataset Schema

This document describes the schema for Tier 2 daily parquet exports.

## Overview

Tier 2 daily exports are derived from Tier 3 daily parquets with a reduced column footprint optimized for research and analysis. Tier 2 includes rich sentiment data from `twitter_sentiment_windows.last_cycle`.

| Property | Value |
|----------|-------|
| **schema_version** | v7 |
| **tier** | tier2 |
| **granularity** | Daily (one file per UTC day) |
| **source** | Derived from `tier3/daily/` parquets |
| **format** | Apache Parquet with zstd compression |
| **R2 path** | `tier2/daily/{YYYY-MM-DD}/data.parquet` |

---

## Column Policy

### Included Columns (8)

| Column | Type | Description |
|--------|------|-------------|
| `symbol` | string | Ticker symbol (e.g., "BTCUSDT") |
| `snapshot_ts` | string | Observation timestamp |
| `meta` | struct | Entry metadata |
| `spot_raw` | struct | Spot market data |
| `derived` | struct | Calculated metrics |
| `scores` | struct | Scoring results |
| `twitter_sentiment_meta` | struct | Twitter sentiment metadata |
| `twitter_sentiment_last_cycle` | struct | Sentiment from last 2-hour cycle (selected fields only) |

### Excluded Columns (6)

| Column | Reason for Exclusion |
|--------|---------------------|
| `futures_raw` | Large block, available in Tier 3 |
| `spot_prices` | Time-series arrays, high volume |
| `flags` | Boolean flags, debugging only |
| `diag` | Diagnostics, internal use |
| `norm` | Intentionally dropped in v7 |
| `labels` | Intentionally dropped in v7 |

### twitter_sentiment_last_cycle Structure

The `twitter_sentiment_last_cycle` column is extracted from `twitter_sentiment_windows.last_cycle` with **13 selected fields** (stable schema):

| Field | Type | Description |
|-------|------|-------------|
| `ai_sentiment` | struct | AI model sentiment scores and stats |
| `author_stats` | struct | Author follower counts and distinct author counts |
| `bucket_has_valid_sentiment` | bool | Whether bucket has valid sentiment |
| `bucket_min_posts_for_score` | int64 | Minimum posts required for scoring |
| `bucket_status` | string | Bucket status indicator |
| `category_counts` | struct | Counts per sentiment category (emoji_pos, fud_fear, etc.) |
| `hybrid_decision_stats` | struct | Combined decision sources and ratios |
| `platform_engagement` | struct | Likes, retweets, replies, views stats |
| `posts_neg` | int64 | Negative posts count |
| `posts_neu` | int64 | Neutral posts count |
| `posts_pos` | int64 | Positive posts count |
| `posts_total` | int64 | Total posts count |
| `sentiment_activity` | struct | Activity metrics (is_silent, hours_since_latest_tweet) |

**Note:** This column is named `twitter_sentiment_last_cycle` (not `twitter_sentiment_windows`) because it only contains the `last_cycle` data, not `last_2_cycles`.

### Excluded Sentiment Fields

The following fields from `twitter_sentiment_windows.last_cycle` are **excluded** from Tier 2:

| Field | Reason for Exclusion |
|-------|---------------------|
| `content_stats` | Detailed content type breakdown, low utility |
| `lexicon_sentiment` | Lexicon-based sentiment (AI sentiment preferred) |
| `media_count` | Media attachment count, low utility |
| `top_terms` | Top terms per category, high cardinality |

### Excluded Dynamic-Key Fields

The following **dynamic-key fields** are excluded from Tier 2 due to schema instability:

| Field | Reason for Exclusion |
|-------|---------------------|
| `tag_counts` | 3,600+ unique hashtag keys per day |
| `cashtag_counts` | 2,300+ unique cashtag keys per day |
| `mention_counts` | 10,000+ unique mention keys per day |
| `url_domain_counts` | 1,500+ unique domain keys per day |

These fields have high-cardinality dynamic keys that vary between days, causing schema incompatibility when merging parquet files. They are available in Tier 3 daily exports.

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
| `final` | double | A composite quality score (0-100) derived from weighted individual factor scores. Key factors include **Price Action** (Momentum, Volatility), **Liquidity Health** (Spread Efficiency, Depth), and **Order Flow** (Taker Buy/Sell Pressure). This metric acts as a quality filter: higher scores (≥60) indicate tradeable, liquid assets with strong market interest, while lower scores filter out predominantly illiquid or noise-heavy pairs. Source: `base_scorer.py`. |
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

Each daily export includes a `manifest.json` with:

```json
{
  "schema_version": "v7",
  "tier": "tier2",
  "tier_description": "Research — reduced column footprint with sentiment last_cycle",
  "date_utc": "2026-01-18",
  "source_tier3": "tier3/daily/2026-01-18/data.parquet",
  "source_tier3_size_bytes": 51588086,
  "row_count": 2615,
  "build_ts_utc": "2026-01-19T00:20:33.971078+00:00",
  "parquet_sha256": "...",
  "parquet_size_bytes": 912958,
  "column_policy": {
    "columns": [
      "symbol",
      "snapshot_ts",
      "meta",
      "spot_raw",
      "derived",
      "scores",
      "twitter_sentiment_meta",
      "twitter_sentiment_last_cycle"
    ],
    "excluded_from_tier3": [
      "futures_raw",
      "spot_prices",
      "flags",
      "diag"
    ],
    "sentiment_source": "twitter_sentiment_windows.last_cycle",
    "sentiment_excluded_fields": [
      "top_terms",
      "tag_counts",
      "mention_counts",
      "cashtag_counts",
      "url_domain_counts",
      "lexicon_sentiment",
      "content_stats",
      "media_count"
    ]
  }
}
```

### Manifest Fields

| Field | Description |
|-------|-------------|
| `schema_version` | Archive schema version (v7) |
| `tier` | Tier identifier (tier2) |
| `tier_description` | Human-readable tier description |
| `date_utc` | The UTC date covered |
| `source_tier3` | Path to source Tier 3 parquet |
| `source_tier3_size_bytes` | Size of source Tier 3 file |
| `row_count` | Number of entries in output |
| `build_ts_utc` | Build timestamp |
| `parquet_sha256` | SHA256 hash of parquet file |
| `parquet_size_bytes` | Size of output parquet |
| `column_policy` | Column inclusion/exclusion rules |

### column_policy Block

| Field | Description |
|-------|-------------|
| `columns` | List of 8 included columns |
| `excluded_from_tier3` | Tier 3 columns not included in Tier 2 |
| `sentiment_source` | Source path for sentiment data |
| `sentiment_excluded_fields` | Fields excluded from twitter_sentiment_last_cycle |

---

## Verification

Use the verification script to validate Tier 2 exports:

```bash
# Verify latest date from R2
python3 scripts/verify_tier2_daily.py

# Verify specific date
python3 scripts/verify_tier2_daily.py --date 2026-01-18

# Verify all dates
python3 scripts/verify_tier2_daily.py --all

# Schema-only check (faster)
python3 scripts/verify_tier2_daily.py --date 2026-01-18 --schema-only
```

### Verification Checks

| Check | Description |
|-------|-------------|
| Schema Validation | 8 required columns with correct types |
| Sentiment Fields | 13 required fields in twitter_sentiment_last_cycle |
| Data Quality | Null rates, distinct symbols |

---

## Related Documentation

- [DATASET_EXPORT_GUIDE.md](DATASET_EXPORT_GUIDE.md) - Export workflow and usage
- [DATASET_SCHEMA_TIER3.md](DATASET_SCHEMA_TIER3.md) - Tier 3 daily schema
- [DATASET_SCHEMA_TIER1.md](DATASET_SCHEMA_TIER1.md) - Tier 1 daily schema
