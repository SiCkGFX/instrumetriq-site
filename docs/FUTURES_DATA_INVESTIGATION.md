# Futures Data Investigation

## Issue Report
User reported that most sample coins show "Futures data OK = false" in the Research page Entry Deep Dive section.

## Investigation Findings

### Path Configuration Issue (FIXED)
**Problem:** `scripts/sync_from_archive.py` had hardcoded Windows path: `D:/Sentiment-Data/CryptoBot/data/archive`  
**Solution:** Changed to relative path: `../cryptobot/data/archive` (sibling repo on VPS at `/srv/cryptobot`)  
**Impact:** Script now accesses live CryptoBot archive instead of stale Windows samples

### Field Mapping Verification
**Field path:** `flags.futures_data_ok` (boolean)  
**Schema source:** `/srv/cryptobot/SYSTEM_INVESTIGATION_SAMPLES.json` + `/srv/instrumetriq/data/schema/ARCHIVE_ENTRY_FULL_SCHEMA.txt`  
**Related field:** `futures_raw` (object or null)

The field mapping is **correct**. The website reads `entry.flags.futures_data_ok` which is the authoritative field name in the v7 CryptoBot archive schema.

### Data Availability Analysis (LIVE CRYPTOBOT ARCHIVE)
After fixing the path and syncing from the actual CryptoBot archive:
- `/srv/cryptobot/data/archive/20260113/` (latest): 0/247 entries with `futures_data_ok=true`
- `/srv/cryptobot/data/archive/20260112/12.jsonl.gz`: 0/130 entries with `futures_data_ok=true`
- `data/samples/cryptobot_latest_tail200.jsonl` (re-synced): 0/200 entries with `futures_data_ok=true`

**Even the SYSTEM_INVESTIGATION_SAMPLES.json** (CryptoBot's own schema documentation) shows `"futures_data_ok": false` and `"futures_raw": null`.

**Correlation verified:** When `flags.futures_data_ok=false`, the `futures_raw` field is `null`.

### Root Cause
This is **NOT a field mapping bug** in the website or sample generation. This is a **CryptoBot data collection issue**. The live archive legitimately contains no futures data. Possible reasons:

1. **Binance Futures API outage:** Extended downtime or rate limiting
2. **CryptoBot configuration:** Futures collection disabled or not configured for VPS environment
3. **API credentials:** Futures endpoint may require different/additional API keys
4. **Symbol filtering:** CryptoBot may be filtering symbols that don't have active futures markets
5. **Data pipeline failure:** Futures fetching component failing silently

**Action required:** Investigate CryptoBot's futures data collection pipeline in `/srv/cryptobot` repo.

### Current Behavior
The website **correctly displays** `futures_data_ok: false` for these entries because that's the true state in the source data.

## Public Sample Generation

### Script Location
- `scripts/sync_from_archive.py` - Syncs latest entries from CryptoBot archive
- `scripts/generate_public_samples.py` - Builds public artifacts

### Archive Path Configuration
**Old (broken):** `D:/Sentiment-Data/CryptoBot/data/archive` (Windows path, inaccessible on VPS)  
**New (fixed):** `../cryptobot/data/archive` (relative path to sibling repo at `/srv/cryptobot`)

### How It Works
1. **Sync step:** `sync_from_archive.py` reads from `/srv/cryptobot/data/archive/YYYYMMDD/*.jsonl.gz`
   - Finds latest date folder (e.g., `20260113`)
   - Extracts most recent N entries (default: 200)
   - Writes: `data/samples/cryptobot_latest_tail200.jsonl`

2. **Generate step:** `generate_public_samples.py` reads `data/samples/cryptobot_latest_tail200.jsonl`
   - Selects: 100 entries using date-based deterministic rotation
   - Outputs:
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

To refresh with latest CryptoBot archive data:

```bash
cd /srv/instrumetriq

# 1. Sync latest entries from CryptoBot archive
python3 scripts/sync_from_archive.py --n 200

# 2. Regenerate public artifacts
python3 scripts/generate_public_samples.py

# 3. Verify distribution
python3 -c "
import json
with open('public/data/sample_entries_v7.json') as f:
    data = json.load(f)
    entries = data['entries']
    futures_ok = sum(1 for e in entries if e.get('flags', {}).get('futures_data_ok'))
    print(f'Futures OK: {futures_ok}/{len(entries)} entries')
    print(f'Generated at: {data.get(\"generated_at_utc\")}')
"

# 4. Commit and deploy
git add data/samples/cryptobot_latest_tail200.jsonl
git add public/data/sample_entries_v7.json public/data/sample_entries_spots_v7.json
git commit -m "Update public samples from latest CryptoBot archive"
git push
```

## Schema Source of Truth

**CryptoBot schema:** `/srv/cryptobot/SYSTEM_INVESTIGATION_SAMPLES.json`  
**Local mirror:** `/srv/instrumetriq/data/schema/ARCHIVE_ENTRY_FULL_SCHEMA.txt`  
**Field name:** `flags.futures_data_ok` (boolean)  
**Related fields:**
- `flags.futures_stale` (boolean) - indicates stale/outdated futures data
- `futures_raw` (object or null) - raw Binance futures API response

**Validation:** Inspected live CryptoBot archive at `/srv/cryptobot/data/archive/`. Field names and structure confirmed across 450+ entries.

---

**Investigation Date:** 2026-01-13  
**Status:** CryptoBot data collection issue - futures pipeline not populating `futures_raw`  
**Action Required:** Investigate CryptoBot's Binance futures API integration in `/srv/cryptobot`


