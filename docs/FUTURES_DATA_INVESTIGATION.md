# Futures Data Investigation

## Issue Report
User reported that most sample coins show "Futures data OK = false" in the Research page Entry Deep Dive section.

## Investigation Findings

### Field Mapping Verification
**Field path:** `flags.futures_data_ok` (boolean)  
**Schema source:** `/srv/instrumetriq/data/schema/ARCHIVE_ENTRY_FULL_SCHEMA.txt`  
**Related field:** `futures_raw` (object or null)

The field mapping is **correct**. The website reads `entry.flags.futures_data_ok` which is the authoritative field name in the v7 CryptoBot archive schema.

### Data Availability Analysis
Analyzed sample data files:
- `data/samples/cryptobot_latest_tail200.jsonl`: 0/200 entries with `futures_data_ok=true`
- `data/samples/cryptobot_latest_head200.jsonl`: 0/200 entries with `futures_data_ok=true`
- `data/samples/cryptobot_latest.jsonl.gz` (first 50): 0/50 entries with `futures_data_ok=true`

**Correlation verified:** When `flags.futures_data_ok=false`, the `futures_raw` field is `null`.

### Root Cause
This is **NOT a field mapping bug** in the website or public sample generation scripts. The sample data legitimately contains no futures data. Possible reasons:

1. **Timing:** Samples were captured when Binance Futures API was unavailable/down
2. **Configuration:** CryptoBot system wasn't configured to fetch futures data at the time
3. **Symbol coverage:** Selected symbols genuinely don't have active futures markets on Binance
4. **Data pipeline:** Futures data collection was disabled or failed during this sample period

### Current Behavior
The website **correctly displays** `futures_data_ok: false` for these entries because that's the true state in the source data.

## Public Sample Generation

### Script Location
`scripts/generate_public_samples.py`

### How It Works
1. Reads: `data/samples/cryptobot_latest_tail200.jsonl` (200 entries)
2. Selects: 100 entries using date-based deterministic rotation
3. Outputs:
   - `public/data/sample_entries_v7.json` (entries without spot_prices)
   - `public/data/sample_entries_spots_v7.json` (spot_prices arrays)
   - `public/data/sample_entries_v7.jsonl` (JSONL format for downloads)

**Important:** The script does **NOT modify** entry fields. It copies them as-is, only removing `spot_prices` from the main artifact to reduce size.

### Field Passthrough
The following fields are preserved exactly as they appear in source data:
- `flags.futures_data_ok`
- `flags.futures_stale`
- `futures_raw`
- All other v7 schema fields

## Regenerating Public Artifacts

If you have access to CryptoBot archive data with futures coverage:

```bash
# 1. Replace sample source file with better data
# (must have entries where futures_data_ok=true)
cp /path/to/better/cryptobot_sample.jsonl data/samples/cryptobot_latest_tail200.jsonl

# 2. Regenerate public artifacts
cd /srv/instrumetriq
python3 scripts/generate_public_samples.py

# 3. Verify distribution
python3 -c "
import json
with open('public/data/sample_entries_v7.json') as f:
    data = json.load(f)
    entries = data['entries']
    futures_ok = sum(1 for e in entries if e.get('flags', {}).get('futures_data_ok'))
    print(f'Futures OK: {futures_ok}/{len(entries)} entries')
"

# 4. Commit and deploy
git add public/data/sample_entries_v7.json public/data/sample_entries_spots_v7.json
git commit -m "Update public samples with futures data coverage"
git push
```

## Website Implementation

### Research Page Display
File: `src/pages/research.astro`  
Line: ~745 (Context section rendering)

```typescript
const futuresOk = entry.flags?.futures_data_ok !== undefined 
  ? entry.flags.futures_data_ok 
  : null;
```

Renders as:
```html
<div class="context-item">
  <span class="context-label">Futures data OK</span>
  <span class="context-value">${futuresOk !== null ? futuresOk : 'N/A'}</span>
</div>
```

**This is correct.** No changes needed unless the v7 schema changes.

## Recommendations

To improve futures data coverage in public samples:

1. **Capture new samples** when futures APIs are stable and available
2. **Filter during generation:** Modify `generate_public_samples.py` to prefer entries with `futures_data_ok=true` if multiple snapshots are available
3. **Mix sources:** Use samples from different time periods to ensure diversity
4. **Document expectations:** Add note on Dataset page that futures coverage varies by capture time

## Schema Source of Truth

**Primary:** `/srv/instrumetriq/data/schema/ARCHIVE_ENTRY_FULL_SCHEMA.txt`  
**Field name:** `flags.futures_data_ok` (boolean)  
**Related fields:**
- `flags.futures_stale` (boolean) - indicates stale/outdated futures data
- `futures_raw` (object or null) - raw Binance futures API response

**Validation:** Inspected 450+ real v7 entries across multiple sample files. Field names and structure confirmed.

---

**Investigation Date:** 2026-01-13  
**Status:** Data collection issue, not a mapping bug  
**Action Required:** Replace sample data source if better futures coverage is needed
