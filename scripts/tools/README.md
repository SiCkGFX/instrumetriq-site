# Scripts Tools

Utilities for working with CryptoBot archive data.

## sync_cryptobot_sample.py

Syncs the newest `*.jsonl.gz` from CryptoBot archive into instrumetriq for local inspection.

**Usage:**

```bash
# Auto-detect CryptoBot repo (assumes sibling directory)
python scripts/tools/sync_cryptobot_sample.py

# Explicit path
python scripts/tools/sync_cryptobot_sample.py --cryptobot-root "D:\Sentiment-Data\CryptoBot"

# Via npm
npm run sync-sample
```

**Outputs:**

- `data/samples/cryptobot_latest.jsonl.gz` - Latest archive file (deterministic name)
- `data/samples/cryptobot_YYYYMMDD_HHMM.jsonl.gz` - Timestamped copy
- `data/samples/cryptobot_latest_head200.jsonl` - First 200 lines (decompressed, for fast inspection)

**Testing:**

```bash
python scripts/tools/sync_cryptobot_sample.py --cryptobot-root "D:\Sentiment-Data\CryptoBot"
```

Verify:
1. Three files created in `data/samples/`
2. Head file contains valid JSONL (one JSON object per line)
3. No errors printed

**Use Cases:**

- Quick schema verification before writing aggregation code
- Local inspection without accessing full archive
- Fast field path discovery for new artifact builders
