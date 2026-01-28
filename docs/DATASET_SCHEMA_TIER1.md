# Tier 1 Daily Dataset Schema

This document describes the schema for Tier 1 daily parquet exports.

## Overview

Tier 1 daily exports are the **"Starter — light entry table"**, derived from Tier 3 daily parquets with only essential fields retained. This tier includes **aggregated sentiment** from Twitter but excludes all futures data and sentiment internals.

| Property | Value |
|----------|-------|
| **schema_version** | v7 |
| **tier** | tier1 |
| **granularity** | Daily (one file per UTC day) |
| **source** | Derived from `tier3/daily/` parquets |
| **format** | Apache Parquet with zstd compression |
| **R2 path** | `tier1/daily/{YYYY-MM-DD}/data.parquet` |

---

## Field Policy

### Design Principles

Tier 1 uses an **explicit allowlist** approach with **flattened fields**:
- Fields are extracted from nested Tier 3 structs and flattened to top-level columns
- No nested structs are carried (unlike Tier 2/3)
- This ensures a stable, predictable schema that won't break on dynamic content

### Tier Comparison

| Tier | Approach | Columns | Sentiment | Futures |
|------|----------|---------|-----------|---------|
| **Tier 1** | Explorer | 19 flat fields | Aggregated only | ❌ Excluded |
| **Tier 2** | Analyst | 8 nested columns | Full windows | ❌ Excluded |
| **Tier 3** | Researcher | 12 nested columns | Full windows | ✅ Included |

---

## Field Reference (19 Fields)

### Identity + Timing (6 fields)

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `symbol` | string | top-level | Trading pair (e.g., "BTCUSDT") |
| `snapshot_ts` | string | top-level | Observation timestamp (ISO 8601) |
| `meta_added_ts` | string | meta.added_ts | When entry was added to archive |
| `meta_expires_ts` | string | meta.expires_ts | When entry expires |
| `meta_duration_sec` | double | meta.duration_sec | Cycle duration in seconds |
| `meta_archive_schema_version` | int64 | meta.archive_schema_version | Schema version (7) |

### Core Spot Snapshot (4 fields)

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `spot_mid` | double | spot_raw.mid | Mid price |
| `spot_spread_bps` | double | spot_raw.spread_bps | Spread in basis points |
| `spot_range_pct_24h` | double | spot_raw.range_pct_24h | 24-hour price range % |
| `spot_ticker24_chg` | double | spot_raw.ticker24_chg | 24-hour price change |

### Minimal Derived (2 fields)

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `derived_liq_global_pct` | double | derived.liq_global_pct | Global liquidity percentile |
| `derived_spread_bps` | double | derived.spread_bps | Derived spread in basis points |

### Minimal Scoring (1 field)

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `score_final` | double | scores.final | A composite quality score (0-100) derived from weighted individual factor scores. Key factors include **Price Action** (Momentum, Volatility), **Liquidity Health** (Spread Efficiency, Depth), and **Order Flow** (Taker Buy/Sell Pressure). This metric acts as a quality filter: higher scores (≥60) indicate tradeable, liquid assets with strong market interest, while lower scores filter out predominantly illiquid or noise-heavy pairs. |

### Aggregated Sentiment (6 fields)

These fields are extracted from `twitter_sentiment_windows.last_cycle`, providing aggregated sentiment without exposing any internals.

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `sentiment_posts_total` | int64 | last_cycle.posts_total | Total posts in window |
| `sentiment_posts_pos` | int64 | last_cycle.posts_pos | Positive posts count |
| `sentiment_posts_neu` | int64 | last_cycle.posts_neu | Neutral posts count |
| `sentiment_posts_neg` | int64 | last_cycle.posts_neg | Negative posts count |
| `sentiment_mean_score` | double | last_cycle.hybrid_decision_stats.mean_score | Mean sentiment score |
| `sentiment_is_silent` | bool | last_cycle.sentiment_activity.is_silent | Is symbol silent (no recent posts) |

**Note:** All sentiment fields may be null if Twitter sentiment was not available for an entry. Other `sentiment_activity` fields (recent_posts_count, has_recent_activity, hours_since_latest_tweet) are excluded as they have limited utility for aggregated exports.

---

## Excluded Fields

Tier 1 explicitly **excludes** the following to maintain a minimal, clean schema:

### Futures Data
- `futures_raw` — All futures market data
- `flags.futures_data_ok` — Futures availability flag

### Sentiment Internals
All internal sentiment diagnostics are excluded:
- `decision_sources` — Model decision sources
- `primary_conf_mean`, `referee_conf_mean` — Confidence means
- `top_terms` — Top terms from posts
- `category_counts` — Sentiment category counts
- `tag_counts`, `cashtag_counts`, `mention_counts` — Social counts
- `url_domain_counts` — URL domain counts
- `media_count` — Media attachment counts
- `author_stats`, `content_stats` — Post statistics
- `platform_engagement` — Engagement metrics
- `lexicon_sentiment`, `ai_sentiment` — Raw model outputs

### Time-Series Arrays
- `spot_prices` — Intra-cycle price samples (high volume)

### Other Excluded
- `flags` — Boolean debug flags (entire struct)
- `diag` — Diagnostics (entire struct)
- `twitter_sentiment_windows` — Full dynamic-key struct (causes schema issues)
- `norm`, `labels` — Intentionally dropped in v7

---

## Manifest Schema

Each daily export includes a `manifest.json` with full metadata.

### Example Manifest

```json
{
  "schema_version": "v7",
  "tier": "tier1",
  "tier_description": "Starter — light entry table with aggregated sentiment (no futures, no sentiment internals)",
  "date_utc": "2026-01-18",
  "source_tier3": "tier3/daily/2026-01-18/data.parquet",
  "source_tier3_size_bytes": 51596288,
  "row_count": 2615,
  "build_ts_utc": "2026-01-19T00:30:05.123456+00:00",
  "parquet_sha256": "...",
  "parquet_size_bytes": 191395,
  "field_policy": {
    "approach": "explicit_allowlist_flattened",
    "total_fields": 19,
    "fields": ["symbol", "snapshot_ts", "meta_added_ts", "meta_expires_ts", "meta_duration_sec", "meta_archive_schema_version", "spot_mid", "spot_spread_bps", "spot_range_pct_24h", "spot_ticker24_chg", "derived_liq_global_pct", "derived_spread_bps", "score_final", "sentiment_posts_total", "sentiment_posts_pos", "sentiment_posts_neu", "sentiment_posts_neg", "sentiment_mean_score", "sentiment_is_silent"],
    "field_categories": {
      "identity_timing": ["symbol", "snapshot_ts", "meta_added_ts", "meta_expires_ts", "meta_duration_sec", "meta_archive_schema_version"],
      "spot_snapshot": ["spot_mid", "spot_spread_bps", "spot_range_pct_24h", "spot_ticker24_chg"],
      "derived_metrics": ["derived_liq_global_pct", "derived_spread_bps"],
      "scores": ["score_final"],
      "sentiment_aggregated": ["sentiment_posts_total", "sentiment_posts_pos", "sentiment_posts_neu", "sentiment_posts_neg", "sentiment_mean_score", "sentiment_is_silent"]
    },
    "sentiment_source": "twitter_sentiment_windows.last_cycle",
    "sentiment_note": "Sentiment fields are aggregated-only from last_cycle. No internals included.",
    "exclusions": [
      "futures_raw (all futures data)",
      "flags.futures_data_ok (futures existence flag)",
      "spot_prices (time-series arrays)",
      "twitter_sentiment_windows (full struct)",
      "All sentiment internals: decision_sources, conf_mean, top_terms, category_counts, etc."
    ]
  }
}
```

### field_policy Block

| Field | Description |
|-------|-------------|
| `approach` | `"explicit_allowlist_flattened"` — fields are flattened, not nested |
| `total_fields` | Count of fields in output (19) |
| `fields` | Ordered list of all field names |
| `field_categories` | Fields grouped by category |
| `sentiment_source` | Source path for sentiment fields |
| `sentiment_note` | Clarification that sentiment is aggregated-only |
| `exclusions` | List of excluded fields/structs with reasons |

---

## Usage Examples

### Daily Build (Cron Mode)

```bash
# Daily 00:30 UTC cron - builds yesterday
30 0 * * * cd /srv/instrumetriq && python3 scripts/build_tier1_daily.py --upload >> /var/log/tier1_daily.log 2>&1
```

### Manual Build

```bash
# Dry-run for specific date
python3 scripts/build_tier1_daily.py --date 2026-01-18 --dry-run

# Build and upload
python3 scripts/build_tier1_daily.py --date 2026-01-18 --upload

# Build date range
python3 scripts/build_tier1_daily.py --from-date 2026-01-15 --to-date 2026-01-18 --upload

# Force overwrite existing
python3 scripts/build_tier1_daily.py --date 2026-01-18 --upload --force
```

### Reading Tier 1 Parquet

```python
import pyarrow.parquet as pq

# Read full table
table = pq.read_table("tier1/daily/2026-01-18/data.parquet")

# Read specific columns
table = pq.read_table(
    "tier1/daily/2026-01-18/data.parquet",
    columns=["symbol", "snapshot_ts", "score_final", "sentiment_mean_score"]
)

# Convert to pandas
df = table.to_pandas()
```

---

## Field Type Reference

| Type | Description |
|------|-------------|
| `string` | UTF-8 string |
| `int64` | 64-bit signed integer |
| `double` | 64-bit floating point |
| `bool` | Boolean (true/false) |

All fields except identity/timing may contain nulls where data was unavailable.

---

## Verification

Tier 1 exports can be verified for correctness and completeness.

### Verification Checks

| Check | Description |
|-------|-------------|
| **1. Presence + Integrity** | Parquet/manifest exist, SHA256 matches |
| **2. Schema Validation** | 19 required columns with correct types |
| **3. Data Quality** | Row counts, distinct symbols, null ratios |

### Validation Rules

**FAIL conditions:**
- SHA256 mismatch between parquet and manifest
- Missing required columns (any of 19)
- Row count mismatch between parquet and manifest
- Critical columns >99.5% null (symbol, snapshot_ts, spot_mid, score_final)
- Negative sentiment_posts_total values

**WARN conditions:**
- Missing days (< 7)
- Partial days (< 24 hours coverage)
- Column type mismatches (loose type check)
- Expected columns >95% null (meta_duration_sec, spot_spread_bps)
- Unexpected extra columns

### Output Artifacts

After verification, the following artifacts are created:

| Artifact | Description |
|----------|-------------|
| `output/verify_tier1_report.md` | Human-readable verification report |
| `output/verify_tier1/{end-day}/manifest.json` | Downloaded manifest copy |
| `output/verify_tier1/{end-day}/schema.txt` | PyArrow schema pretty print |
| `output/verify_tier1/{end-day}/stats.json` | Machine-readable summary |

### Example Report

The verification report includes:
- Summary table with status, days coverage, row count, file size
- Source coverage details (per-day hours)
- Schema listing with types
- Data quality stats (numeric ranges, null ratios)
- Warnings and errors list

