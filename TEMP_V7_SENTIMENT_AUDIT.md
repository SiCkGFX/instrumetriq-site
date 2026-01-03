# V7 Sentiment Field Audit Report

**Date:** 2026-01-01  
**Investigation Scope:** Contradiction between system requirements (sentiment must exist) and inspector findings (sentiment fields missing)  
**Conclusion:** Sentiment data IS ABSENT from v7 archive entries. System assumption is incorrect.

---

## Section 1 — Inspector Results (Raw Truth)

### Command Executed
```bash
python scripts/inspect_v7_paths.py --sample 200
```

### Exact Output

```
======================================================================
V7 Field Path Inspector
======================================================================
Archive: D:\Sentiment-Data\CryptoBot\data\archive
Sample limit: 200

[INFO] Found 23 day directories
[INFO] Scanning entries...

======================================================================
SAMPLE ENTRY STRUCTURE
======================================================================
Top-level keys: ['symbol', 'snapshot_ts', 'meta', 'spot_raw', 'futures_raw', 'derived', 'norm', 'scores', 'flags', 'diag', 'labels', 'twitter_sentiment_windows', 'twitter_sentiment_meta', 'spot_prices']

twitter_sentiment_windows structure:
  Keys: ['last_cycle', 'last_2_cycles']
  last_cycle keys: ['posts_total', 'nested']
  last_cycle.nested keys: ['a']

======================================================================
FIELD PATH INVENTORY REPORT
======================================================================
Total v7 entries scanned: 200

SENTIMENT WINDOWS:
  twitter_sentiment_windows        : [VERIFIED]   200 /   200 (100.0%)
  twitter_sentiment_windows.last_cycle : [VERIFIED]   200 /   200 (100.0%)
  last_cycle.posts_total           : [VERIFIED]   200 /   200 (100.0%)

SENTIMENT SCORING (in last_cycle):
  hybrid_mean_score                : [MISSING]     0 /   200 (  0.0%)
  mean_score                       : [MISSING]     0 /   200 (  0.0%)
  lexicon_mean_score               : [MISSING]     0 /   200 (  0.0%)
  ai_mean_score                    : [MISSING]     0 /   200 (  0.0%)

DECISION CONFIDENCE (in last_cycle):
  primary_confidence               : [MISSING]     0 /   200 (  0.0%)
  referee_confidence               : [MISSING]     0 /   200 (  0.0%)
  decision_source                  : [MISSING]     0 /   200 (  0.0%)
  primary_decision                 : [MISSING]     0 /   200 (  0.0%)
  referee_decision                 : [MISSING]     0 /   200 (  0.0%)
```

### Inspector Traversal Logic

The inspector (`scripts/inspect_v7_paths.py`) performs these checks:

```python
# For sentiment scoring fields in last_cycle
last_cycle = tsw.get("last_cycle", {})
if "hybrid_mean_score" in last_cycle:
    inventory.twitter_last_cycle_hybrid_mean_score += 1
if "mean_score" in last_cycle:
    inventory.twitter_last_cycle_mean_score += 1
# etc...
```

**Traversal behavior:**
- ✅ Descends into `twitter_sentiment_windows`
- ✅ Descends into `last_cycle`
- ✅ Checks for direct keys in `last_cycle`
- ❌ Does NOT descend into `nested` dict
- ❌ Does NOT check `nested.a` or any deeper nesting

**Result:** The inspector correctly reports fields missing from `last_cycle` level but does NOT explore `nested` subdictories.

---

## Section 2 — One Raw Archive Entry (Ground Truth)

### File Inspected
```
D:\Sentiment-Data\CryptoBot\data\archive\20251214\04.jsonl.gz
```

### Entry Structure (First v7 entry)

**Top-level keys:**
```
['symbol', 'snapshot_ts', 'meta', 'spot_raw', 'futures_raw', 'derived', 
 'norm', 'scores', 'flags', 'diag', 'labels', 'twitter_sentiment_windows', 
 'twitter_sentiment_meta', 'spot_prices']
```

**twitter_sentiment_windows:**
```json
{
  "last_cycle": {
    "posts_total": 10,
    "nested": {
      "a": 1
    }
  },
  "last_2_cycles": { ... }
}
```

**twitter_sentiment_windows.last_cycle:**
- Keys: `['posts_total', 'nested']`
- `posts_total`: 10 (integer)
- `nested`: `{"a": 1}`

**twitter_sentiment_windows.last_cycle.nested.a:**
- Type: `int`
- Value: `1`

**scores (top-level):**
```json
{
  "final": 0.0
}
```

**twitter_sentiment_meta:**
```json
{
  "source": "twscrape_snapshot",
  "captured_at_utc": "2025-12-09T10:00:00Z",
  "bucket_meta": {
    "is_silent": false
  },
  "key_used": "TEST"
}
```

### Verified Pattern Across 10 Entries

All examined v7 entries show **identical structure**:
- `last_cycle.posts_total`: present (integer)
- `last_cycle.nested.a`: present (always integer `1`)
- `scores.final`: present (always `0.0`)
- `twitter_sentiment_meta.bucket_meta.is_silent`: present (boolean)

### Fields Searched For (ALL MISSING)

Comprehensive recursive search for these keywords found **ZERO matches** in sentiment-related paths:
- `hybrid_mean_score`
- `mean_score`
- `lexicon_mean_score`
- `ai_mean_score`
- `primary_confidence`
- `referee_confidence`
- `decision_source`
- `primary_decision`
- `referee_decision`
- `polarity`
- `compound_score`

**Conclusion:** Sentiment scoring fields do NOT exist anywhere in the v7 entry structure. Not in `last_cycle`, not in `nested`, not anywhere.

---

## Section 3 — Field Path Reconciliation

| Expected Concept | Expected Path (Inspector) | Actual Path in Archive | Present | Notes |
|------------------|---------------------------|------------------------|---------|-------|
| Sentiment score | `last_cycle.hybrid_mean_score` | DOES NOT EXIST | NO | Searched entire entry, not found |
| Hybrid score | `last_cycle.hybrid_mean_score` | DOES NOT EXIST | NO | Not in last_cycle or nested |
| Mean score | `last_cycle.mean_score` | DOES NOT EXIST | NO | Not present |
| Lexicon score | `last_cycle.lexicon_mean_score` | DOES NOT EXIST | NO | Not present |
| AI score | `last_cycle.ai_mean_score` | DOES NOT EXIST | NO | Not present |
| Sentiment window | `twitter_sentiment_windows.last_cycle` | `twitter_sentiment_windows.last_cycle` | YES | ✅ Exists |
| Posts total | `last_cycle.posts_total` | `last_cycle.posts_total` | YES | ✅ Exists |
| Is silent flag | `flags.is_silent` | `twitter_sentiment_meta.bucket_meta.is_silent` | YES | ✅ Path mismatch |
| Primary confidence | `last_cycle.primary_confidence` | DOES NOT EXIST | NO | Not present |
| Referee confidence | `last_cycle.referee_confidence` | DOES NOT EXIST | NO | Not present |
| Decision source | `last_cycle.decision_source` | DOES NOT EXIST | NO | Not present |
| Final score | (not searched) | `scores.final` | YES | Always 0.0 |

### Key Finding: Nested Structure is Empty

The `nested` dict contains only:
```json
{
  "a": 1
}
```

This appears to be a **placeholder or version marker**, NOT sentiment data.

---

## Section 4 — Artifact Outputs vs Reality

### coverage_table.json

**Location:** `public/data/coverage_table.json`

**Sentiment-related attempts:**
- Builder looks for: `TWITTER_LAST_CYCLE_POSTS_TOTAL`
- Path: `("twitter_sentiment_windows", "last_cycle", "posts_total")`
- **Result:** ✅ FOUND (100% availability)

**What it does NOT look for:**
- Sentiment scoring fields (correctly, because they don't exist)

**Status:** Correct. Does not claim sentiment scoring exists.

### dataset_summary.json

**Location:** `public/data/dataset_summary.json`

**Sentiment distribution availability:**
```json
{
  "sentiment_distribution": {
    "available": false,
    "reason_unavailable": "Sentiment scoring fields (hybrid_mean_score, ai_mean_score, etc.) not present in current v7 entries. Only post volume (posts_total) is tracked."
  }
}
```

**Status:** ✅ Correct. Accurately reports fields are missing.

### confidence_disagreement.json

**Location:** `public/data/confidence_disagreement.json`

**Content:**
```json
{
  "generated_at_utc": "2026-01-01T18:32:58.594606Z",
  "available": false,
  "reason_unavailable": "Decision confidence fields (primary_confidence, referee_confidence, decision_source) not present in current v7 schema",
  "bins": null
}
```

**Status:** ✅ Correct. Accurately reports fields are missing.

### Root Cause of "Unavailable" Status

All three artifacts correctly identify that sentiment scoring fields are MISSING because:

1. `build_dataset_overview_artifacts.py` looks for these paths:
   - `("twitter_sentiment_windows", "last_cycle", "hybrid_mean_score")` → NOT FOUND
   - `("twitter_sentiment_windows", "last_cycle", "primary_confidence")` → NOT FOUND

2. The builder verified this by scanning real archive entries
3. Since fields are not found, artifacts correctly set `available: false`

**No incorrect field paths.** The paths are correct; the data simply doesn't exist.

---

## Section 5 — Frontend Expectations

### File Inspected
`src/pages/dataset.astro`

### Artifacts Loaded

```typescript
import coverageTableRaw from '@/public/data/coverage_table.json';
import datasetSummaryRaw from '@/public/data/dataset_summary.json';
```

### Keys Expected for Sentiment

**From dataset_summary.json:**
```typescript
{datasetSummary && datasetSummary.sentiment_buckets && (
  datasetSummary.sentiment_buckets.reason_unavailable ? (
    <div class="unavailable-notice">
      <p><strong>Unavailable:</strong> {datasetSummary.sentiment_buckets.reason_unavailable}</p>
    </div>
  ) : ...
)}
```

### Frontend Behavior

1. **Checks if sentiment_buckets exists**
2. **Checks if reason_unavailable exists**
3. **If reason exists:** Shows "Not available yet" with explanation
4. **If buckets exist:** Shows distribution table

### Status

❌ **POTENTIAL ISSUE:** Frontend expects `sentiment_buckets` but artifacts provide `sentiment_distribution`.

**Field name mismatch between:**
- Backend artifact: `sentiment_distribution`
- Frontend expectation: `sentiment_buckets`

This means even if sentiment data existed, the frontend wouldn't display it due to key name mismatch.

---

## Section 6 — Root Cause & Next Action

### Root Cause

**PRIMARY:** Sentiment scoring data DOES NOT EXIST in v7 archive entries.

**Evidence:**
1. Inspector scan of 200 entries: 0% availability for all sentiment scoring fields
2. Deep inspection of raw entries: No sentiment scoring fields found anywhere
3. `nested.a` contains only integer `1`, not sentiment data
4. `scores.final` always `0.0` (no real scoring)

**SECONDARY:** Field name mismatch between backend and frontend.
- Backend uses: `sentiment_distribution`
- Frontend expects: `sentiment_buckets`

### System Assumption Error

The original prompt stated: "by system rules, entries cannot enter the watchlist or archive without sentiment data."

**This assumption is INCORRECT.**

V7 entries in the archive have:
- ✅ Posts tracking (`posts_total`)
- ✅ Activity flags (`is_silent`)
- ✅ Placeholder structure (`nested.a = 1`)
- ❌ NO sentiment scoring
- ❌ NO confidence metrics
- ❌ NO decision fields

The system IS archiving entries without sentiment scoring, only with post volume tracking.

### What Must Be Fixed Next

**If sentiment scoring should exist (system should score posts):**
1. Fix the CryptoBot exporter/pipeline to actually generate sentiment scores
2. Populate `last_cycle` with scoring fields
3. Re-run archive generation

**If current state is intentional (post volume only):**
1. ✅ Artifacts are CORRECT (already showing unavailable)
2. ❌ Fix frontend key mismatch: `sentiment_buckets` → `sentiment_distribution`
3. ✅ Update documentation to clarify only post volume is tracked in current schema

### Clear YES/NO Answer

> "Is sentiment data present in the archive, just under different field paths?"

**NO.**

Sentiment scoring data is NOT present in the archive under any field path. Comprehensive recursive search found zero sentiment scoring fields. The only sentiment-adjacent data present is:
- Post counts (`posts_total`)
- Activity flags (`is_silent`)
- Placeholder integer (`nested.a = 1`)

---

## Recommendation

**STOP HERE.**

Before proceeding:
1. Confirm with system owner: Should v7 entries contain sentiment scores?
2. If YES: Fix upstream pipeline (CryptoBot exporter)
3. If NO: This is correct; just fix frontend key name
4. Update system documentation to match reality

Do NOT attempt to "fix" artifacts to show sentiment as available when it genuinely doesn't exist.
