# Canonical Field Selection Map (Phase 1B)

**This file is the single source of truth for all future dataset artifacts.**

## Purpose

This document defines which fields from the v7 archive entries will be used in dataset artifacts, and which will be excluded. Every decision is based on:

1. **Availability** - Presence rate across entries
2. **Semantic value** - Usefulness for dataset-level insights
3. **Reliability** - Data quality and completeness

## Selection Rules

**Primary threshold:** >= 90% presence rate

**Exceptions allowed when:**
- Field is critical for sentiment analysis (e.g., confidence scores at 73.5%)
- Field provides essential context (e.g., author engagement metrics at 73.5%)
- Explicit justification documented in canonical_fields.json

**Always excluded:**
- Granular entity-level data (individual mentions, cashtags, tags, author names)
- Fields below 70% availability without critical justification
- Top-level container fields with no direct value

## Why Availability Matters

Dataset artifacts must be **reliable and consistent**. If a field is present in only 50% of entries:
- Aggregations become misleading
- Comparisons across time periods fail
- Users cannot trust the data

By requiring >= 90% availability (or explicit justification for >= 70%), we ensure artifacts reflect the actual data quality.

## Why Some High-Availability Fields Are Excluded

Even if a field appears in 100% of entries, it may be excluded because:

1. **Too granular** - Individual user mentions don't inform dataset-level patterns
2. **No semantic value** - Top-level containers are organizational, not data
3. **Redundant** - Multiple representations of the same concept
4. **Out of scope** - Not relevant for current artifact goals

---

## Field Groups

### 1. Market Microstructure

**Included (26 fields):**
- Spot market data (bid/ask, volume, orderbook depth)
- Futures market data (funding rate, open interest, liquidations)
- Derived metrics (spread, depth imbalance, flow indicators)
- Normalized metrics (volume normalization, price normalization)

**Purpose:** Provide market context for sentiment-price relationships.

**Excluded (2 fields):**
- Top-level container fields (spot_raw, futures_raw)

---

### 2. Liquidity

**Included (3 fields):**
- `derived.liq_global_pct` - Global liquidity percentage
- `derived.liq_self_pct` - Self liquidity percentage
- Related liquidity metrics

**Purpose:** Market depth and liquidity analysis.

**Excluded:** None (all liquidity fields pass threshold).

---

### 3. Spot Prices

**Included:** 0 fields (all excluded due to path structure)

**Excluded (6 fields):**
- Top-level container and redundant price fields
- Price data available through spot_raw with better structure

**Note:** Price data IS available via market_microstructure group.

---

### 4. Sampling Density

**Included:** 0 fields in this release

**Purpose:** Future artifact for collection frequency and gaps.

---

### 5. Sentiment (Last Cycle)

**Included (32 fields):**

**Core scoring:**
- `twitter_sentiment_windows.last_cycle.ai_sentiment.*` (100%)
- `twitter_sentiment_windows.last_cycle.lexicon_sentiment.*` (100%)
- `twitter_sentiment_windows.last_cycle.hybrid_decision_stats.*` (100% container, 73.5% nested stats)

**Activity tracking:**
- `posts_total`, `bucket_status`, `bucket_has_valid_sentiment`
- `bucket_min_posts_for_score`

**Decision metadata:**
- Confidence scores (primary_conf_mean, referee_conf_mean)
- Decision sources (primary_default, referee_override, etc.)
- Sentiment ratios (pos_ratio, neg_ratio, neu_ratio)

**Excluded (175 fields):**
- Granular mention counts (individual @usernames)
- Granular cashtag counts (individual $SYMBOLS)
- Granular tag counts (individual #hashtags)
- Granular author names

**Rationale:** Entity-level data is too granular for dataset-level artifacts. We aggregate sentiment at the window level, not the entity level.

---

### 6. Sentiment (Last 2 Cycles)

**Included (31 fields):**

Same structure as last_cycle:
- AI sentiment scoring (100%)
- Lexicon sentiment scoring (100%)
- Hybrid decision stats (79.6% for nested fields)
- Activity tracking
- Decision metadata

**Excluded (260 fields):**
- Same granular entity-level data as last_cycle

**Purpose:** Extended time window for sentiment trend analysis.

---

### 7. Author Stats

**Included (13 fields):**

From both last_cycle and last_2_cycles:
- `distinct_authors_total` (73.5%)
- `distinct_authors_verified` (73.5%)
- `distinct_authors_blue` (73.5%)
- `followers_count_*` (mean, median, max, sum)

**Purpose:** Engagement quality and reach metrics.

**Justification for <90%:** Author stats are critical for understanding sentiment signal quality. 73.5% availability is acceptable given their importance.

**Excluded:** None (all author stats fields are useful).

---

### 8. Activity vs Silence

**Included (5 fields):**
- `posts_total` from both windows (100%)
- `bucket_status` (100%)
- `bucket_has_valid_sentiment` (100%)

**Purpose:** Detect silence periods and activity patterns.

**Excluded:** None.

---

### 9. Sentiment Metadata

**Included (18 fields):**
- Data source identifiers
- Capture timestamps
- Bucket metadata (is_silent flag)
- API key tracking

**Purpose:** Provenance and data quality tracking.

**Excluded (1 field):**
- Top-level container field

---

### 10. Data Quality

**Included (10 fields):**
- Diagnostic fields (build_duration_ms, builder_version)
- Quality flags (futures_data_ok, spot_data_ok, etc.)
- Fallback indicators (mom_fallback, vol_fallback, spread_fallback)

**Purpose:** Data quality assessment and filtering.

**Excluded:** None (all pass threshold).

---

### 11. Entry Metadata

**Included (20 fields):**
- Symbol, snapshot timestamp
- Schema version
- Cycle tracking
- Collection metadata

**Purpose:** Entry provenance and dataset structure.

**Excluded:** None (all pass threshold).

---

### 12. Scores & Labels

**Included (12 fields):**
- Aggregated scores (scores.final, etc.)
- Classification labels (market regime, volatility state)

**Purpose:** High-level entry classification.

**Excluded:** None (all pass threshold).

---

## Usage Guidelines

### For Artifact Builders

1. Load `canonical_fields.json` at the start of your script
2. Use ONLY fields listed in the `included` arrays
3. Do NOT hardcode field paths
4. If you need a field not in the canonical map, stop and justify its addition

### For Reviewers

1. Check that artifact scripts import canonical_fields.json
2. Verify no hardcoded field paths exist
3. Ensure all field paths match the canonical map exactly

### For Future Phases

- Phase 1C will reference this map for aggregation logic
- Website artifacts will use this map to determine what to display
- Any field additions require updating this map and re-verifying

---

## Change Log

**2026-01-02 (Phase 1B):**
- Initial canonical field selection
- 170 fields included, 454 excluded
- 12 field groups defined
- Selection based on 147-entry sample from 2026-01-01
