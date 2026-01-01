# Quick Reference: Artifact Development Workflow

## Before Writing ANY Aggregation Code

```bash
# Step 1: Sync latest archive sample
npm run sync-sample

# Step 2: Read the schema
cat data/schema/ARCHIVE_ENTRY_FULL_SCHEMA.txt

# Step 3: Inspect actual data
python -c "import json; f = open('data/samples/cryptobot_latest_head200.jsonl', 'r'); entry = json.loads(f.readline()); print(json.dumps(entry, indent=2))"
```

## Field Path Verification Template

```python
import json

field_path = "twitter_sentiment_windows.last_cycle.YOUR_FIELD_HERE"
found = 0
total = 20

with open('data/samples/cryptobot_latest_head200.jsonl', 'r') as f:
    for i, line in enumerate(f):
        if i >= total:
            break
        entry = json.loads(line)
        
        # Navigate path safely
        value = entry.get('twitter_sentiment_windows', {}).get('last_cycle', {}).get('YOUR_FIELD_HERE')
        if value is not None:
            found += 1
            if i == 0:  # Print example from first entry
                print(f"Example value: {value}")

print(f"\nPath present: {found}/{total} entries ({found/total*100:.0f}%)")
print(f"Decision: {'VERIFIED (>=90%)' if found/total >= 0.9 else 'MISSING (<90%)'}")
```

## Decision Logic

- **≥ 90% availability** → Mark as VERIFIED, use in artifacts
- **< 90% availability** → Mark as MISSING, set `available: false` with exact path and count

## Files to Reference

- `data/schema/ARCHIVE_ENTRY_FULL_SCHEMA.txt` - Canonical v7 structure
- `TEMP_V7_SENTIMENT_AUDIT.md` - Investigation results
- `docs/PROJECT_GUIDE.md` - Full workflow documentation
- `.github/copilot-instruction.md` - Mandatory investigation rules

## Current Known Facts (as of 2026-01-01)

**VERIFIED (100%):**
- `twitter_sentiment_windows.last_cycle.posts_total`
- `twitter_sentiment_meta.bucket_meta.is_silent`
- `scores.final` (always 0.0)

**MISSING (0%):**
- All sentiment scoring fields (hybrid_mean_score, mean_score, etc.)
- All decision confidence fields (primary_confidence, referee_confidence, etc.)

## Remember

❌ **DON'T:**
- Assume field names
- Use "maybe this field is called..."
- Write code before inspection
- Claim features exist when they don't

✅ **DO:**
- Sync sample first
- Verify paths in 20+ entries
- Document missing paths with counts
- Show "Not available yet" with exact reasons
