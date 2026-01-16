# Tier 1 Weekly Dataset Schema

This document describes the schema for Tier 1 weekly parquet exports.

## Overview

Tier 1 weekly exports are the **"Starter — light entry table"**, derived from Tier 3 daily parquets with only essential fields retained. This tier includes **aggregated sentiment** from Twitter but excludes all futures data and sentiment internals.

| Property | Value |
|----------|-------|
| **schema_version** | v7 |
| **tier** | tier1 |
| **window** | 7 consecutive UTC days (Mon–Sun) |
| **source** | Derived from `tier3/daily/` parquets |
| **format** | Apache Parquet with zstd compression |
| **R2 path** | `tier1/weekly/{end-day}/dataset_entries_7d.parquet` |

### Weekly Window Definition

A Tier 1 weekly export covers 7 consecutive UTC days (Monday through Sunday):
- **Window:** `end_day - 6` (Monday) to `end_day` (Sunday)
- **Example:** `--end-day 2026-01-04` covers 2025-12-29 (Mon) through 2026-01-04 (Sun)

### Partial Week Support

Tier 1 can be built from **5 or more** of the 7 expected days (configurable via `--min-days`).
- Missing days are explicitly recorded in the manifest
- Partial Tier 3 days (those with < 24 hours coverage) are also tracked
- Use the `source_coverage` block in manifest to understand data gaps

---

## Field Policy

### Design Principles

Tier 1 uses an **explicit allowlist** approach with **flattened fields**:
- Fields are extracted from nested Tier 3 structs and flattened to top-level columns
- No nested structs are carried (unlike Tier 2/3)
- This ensures a stable, predictable schema that won't break on dynamic content

### Tier Comparison

| Tier | Approach | Fields | Sentiment | Futures |
|------|----------|--------|-----------|---------|
| **Tier 1** | Flattened allowlist | 22 | Aggregated only | ❌ Excluded |
| **Tier 2** | Struct exclusion | 7 structs | Meta only | ❌ Excluded |
| **Tier 3** | Full archive | 12 structs | Full windows | ✅ Included |

---

## Field Reference (22 Fields)

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
| `score_final` | double | scores.final | Final composite score |

### Aggregated Sentiment (9 fields)

These fields are extracted from `twitter_sentiment_windows.last_cycle`, providing aggregated sentiment without exposing any internals.

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `sentiment_posts_total` | int64 | last_cycle.posts_total | Total posts in window |
| `sentiment_posts_pos` | int64 | last_cycle.posts_pos | Positive posts count |
| `sentiment_posts_neu` | int64 | last_cycle.posts_neu | Neutral posts count |
| `sentiment_posts_neg` | int64 | last_cycle.posts_neg | Negative posts count |
| `sentiment_mean_score` | double | last_cycle.hybrid_decision_stats.mean_score | Mean sentiment score |
| `sentiment_is_silent` | bool | last_cycle.sentiment_activity.is_silent | Is symbol silent (no recent posts) |
| `sentiment_recent_posts_count` | int64 | last_cycle.sentiment_activity.recent_posts_count | Recent posts count |
| `sentiment_has_recent_activity` | bool | last_cycle.sentiment_activity.has_recent_activity | Has recent activity |
| `sentiment_hours_since_latest_tweet` | double | last_cycle.sentiment_activity.hours_since_latest_tweet | Hours since latest tweet |

**Note:** All sentiment fields may be null if Twitter sentiment was not available for an entry.

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

Each weekly export includes a `manifest.json` with full metadata.

### Example Manifest

```json
{
  "schema_version": "v7",
  "tier": "tier1",
  "tier_description": "Starter — light entry table with aggregated sentiment (no futures, no sentiment internals)",
  "window": {
    "window_basis": "previous_week_utc",
    "week_start_day": "2025-12-22",
    "week_end_day": "2025-12-28",
    "days_expected": ["2025-12-22", "2025-12-23", ...],
    "days_included": ["2025-12-22", "2025-12-23", ...]
  },
  "build_ts_utc": "2026-01-16T12:01:02.113608+00:00",
  "source_inputs": [
    "tier3/daily/2025-12-22/data.parquet",
    ...
  ],
  "row_count": 17635,
  "source_coverage": {
    "days_expected": ["2025-12-22", ...],
    "days_present": ["2025-12-22", ...],
    "days_missing": [],
    "per_day": {
      "2025-12-22": {
        "hours_found": 24,
        "hours_expected": 24,
        "is_partial": false,
        "missing_hours": []
      }
    },
    "present_days_count": 7,
    "missing_days_count": 0,
    "partial_days_count": 0,
    "min_days_threshold_used": 5,
    "coverage_note": "This weekly export is derived from 7/7 daily partitions."
  },
  "field_policy": {
    "approach": "explicit_allowlist_flattened",
    "total_fields": 22,
    "fields": ["symbol", "snapshot_ts", "meta_added_ts", ...],
    "field_categories": {
      "identity_timing": ["symbol", "snapshot_ts", ...],
      "spot_snapshot": ["spot_mid", "spot_spread_bps", ...],
      "derived_metrics": ["derived_liq_global_pct", "derived_spread_bps"],
      "scores": ["score_final"],
      "sentiment_aggregated": ["sentiment_posts_total", ...]
    },
    "sentiment_source": "twitter_sentiment_windows.last_cycle",
    "sentiment_note": "Sentiment fields are aggregated-only from last_cycle. No internals (decision_sources, conf_mean, top_terms, etc.) are included.",
    "exclusions": [
      "futures_raw (all futures data)",
      "flags.futures_data_ok (futures existence flag)",
      "spot_prices (time-series arrays)",
      "twitter_sentiment_windows (full struct)",
      "All sentiment internals: decision_sources, primary_conf_mean, ..."
    ]
  },
  "parquet_sha256": "...",
  "parquet_size_bytes": 1463922
}
```

### window Block

| Field | Description |
|-------|-------------|
| `window_basis` | How end_day was determined: `"previous_week_utc"` (cron) or `"end_day"` (manual) |
| `week_start_day` | First day of the 7-day window (Monday) |
| `week_end_day` | Last day of the 7-day window (Sunday) |
| `days_expected` | List of 7 days in the window |
| `days_included` | Days that were actually included in the build |

### source_coverage Block

| Field | Description |
|-------|-------------|
| `days_expected` | List of 7 days in the window |
| `days_present` | Tier 3 days that exist and were included |
| `days_missing` | Tier 3 days that were not found in R2 |
| `per_day` | Coverage metadata for each present day (hours_found, is_partial, missing_hours) |
| `present_days_count` | Count of included days |
| `missing_days_count` | Count of missing days |
| `partial_days_count` | Count of partial days (< 24 hours coverage) |
| `min_days_threshold_used` | Minimum days required for build |
| `coverage_note` | Human-readable summary |

### field_policy Block

| Field | Description |
|-------|-------------|
| `approach` | `"explicit_allowlist_flattened"` — fields are flattened, not nested |
| `total_fields` | Count of fields in output (22) |
| `fields` | Ordered list of all field names |
| `field_categories` | Fields grouped by category |
| `sentiment_source` | Source path for sentiment fields |
| `sentiment_note` | Clarification that sentiment is aggregated-only |
| `exclusions` | List of excluded fields/structs with reasons |

---

## Usage Examples

### Build Previous Week (Cron Mode)

```bash
# Monday 00:05 UTC cron
python3 scripts/build_tier1_weekly.py --previous-week --upload
```

### Manual Build

```bash
# Dry-run for specific week
python3 scripts/build_tier1_weekly.py --end-day 2026-01-04 --dry-run

# Build and upload
python3 scripts/build_tier1_weekly.py --end-day 2026-01-04 --upload

# Force overwrite existing
python3 scripts/build_tier1_weekly.py --end-day 2026-01-04 --upload --force
```

### Reading Tier 1 Parquet

```python
import pyarrow.parquet as pq

# Read full table
table = pq.read_table("tier1_weekly/2025-12-28/dataset_entries_7d.parquet")

# Read specific columns
table = pq.read_table(
    "tier1_weekly/2025-12-28/dataset_entries_7d.parquet",
    columns=["symbol", "snapshot_ts", "score_final", "sentiment_mean_score"]
)

# Convert to pandas
df = table.to_pandas()
```

### Cron Schedule

```bash
# Monday 00:05 UTC — build previous Mon-Sun week
5 0 * * 1 cd /srv/instrumetriq && python3 scripts/build_tier1_weekly.py --previous-week --upload >> /var/log/tier1_weekly.log 2>&1
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
