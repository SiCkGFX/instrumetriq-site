#!/usr/bin/env python3
"""
Generate dataset_overview.json for Dataset page surface-level overview.

Output:
- public/data/dataset_overview.json
  Structure:
    - generated_at_utc: ISO timestamp
    - scale: entries_scanned, distinct_symbols, date_range_utc, last_entry_ts_utc
    - freshness: archive_sample_source, notes
    - preview_row: redacted sample (symbol + 3-4 metrics, no timestamps/authors/text/ids)
    - non_claims_block: 4+ descriptive bullet points
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

# SSOT for sample data location
SAMPLE_DATA_FILE = Path(__file__).parent.parent / 'data' / 'samples' / 'cryptobot_latest_head200.jsonl'
OUTPUT_FILE = Path(__file__).parent.parent / 'public' / 'data' / 'dataset_overview.json'


def load_sample_entries():
    """Load entries from sample JSONL file."""
    if not SAMPLE_DATA_FILE.exists():
        raise FileNotFoundError(f"Sample data not found: {SAMPLE_DATA_FILE}")
    
    entries = []
    with open(SAMPLE_DATA_FILE, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entries.append(entry)
            except json.JSONDecodeError as e:
                print(f"Warning: Skipping invalid JSON at line {line_num}: {e}", file=sys.stderr)
    
    return entries


def extract_scale_metrics(entries):
    """Extract scale metrics from entries."""
    symbols = set(e.get('symbol') for e in entries if e.get('symbol'))
    
    # Extract dates from snapshot_ts
    dates = []
    last_entry_ts = None
    for e in entries:
        ts_str = e.get('snapshot_ts')
        if ts_str:
            try:
                # Parse ISO format timestamp
                # Could be: "2026-01-01T17:54:42.435Z" or "2026-01-01T17:54:42.435+00:00"
                if ts_str.endswith('Z'):
                    dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                else:
                    dt = datetime.fromisoformat(ts_str)
                dates.append(dt.date())
                if last_entry_ts is None or dt > last_entry_ts:
                    last_entry_ts = dt
            except Exception:
                pass
    
    date_range_utc = "Unknown"
    if dates:
        min_date = min(dates)
        max_date = max(dates)
        if min_date == max_date:
            date_range_utc = min_date.isoformat()
        else:
            date_range_utc = f"{min_date.isoformat()} to {max_date.isoformat()}"
    
    last_entry_ts_utc = last_entry_ts.isoformat().replace('+00:00', 'Z') if last_entry_ts else None
    
    return {
        "entries_scanned": len(entries),
        "distinct_symbols": len(symbols),
        "date_range_utc": date_range_utc,
        "last_entry_ts_utc": last_entry_ts_utc
    }


def extract_preview_row(entries):
    """
    Extract ONE redacted preview row from sample data.
    
    Redacted: no timestamps, no author names, no tweet text, no IDs.
    Include: symbol, spread_bps, liq_global_pct, posts_total, optionally mean_score.
    """
    if not entries:
        return None
    
    # Pick first entry with required fields
    for e in entries:
        symbol = e.get('symbol')
        spread_bps = e.get('derived', {}).get('spread_bps')
        liq_global_pct = e.get('derived', {}).get('liq_global_pct')
        posts_total = e.get('twitter_sentiment_windows', {}).get('last_2_cycles', {}).get('posts_total')
        
        if symbol and spread_bps is not None and liq_global_pct is not None and posts_total is not None:
            # Build preview row
            row = {
                "symbol": symbol,
                "spread_bps": round(spread_bps, 2),
                "liq_global_pct": round(liq_global_pct, 2),
                "posts_total": posts_total
            }
            
            # Optional: mean_score if available
            mean_score = e.get('twitter_sentiment_windows', {}).get('last_2_cycles', {}).get('hybrid_decision_stats', {}).get('mean_score')
            if mean_score is not None:
                row["mean_score"] = round(mean_score, 4)
            
            return row
    
    return None


def generate_non_claims_block():
    """Generate non-claims disclaimers (4+ bullet points)."""
    return [
        "This dataset is descriptive only. It documents observed patterns in market snapshots and social sentiment, but makes no claims about predictive value.",
        "No correlation between sentiment and forward returns is implied or claimed. Aggregations may change as methodology evolves.",
        "Data is not real-time. Snapshots reflect monitoring windows from the past, provided for transparency and research purposes.",
        "All metrics are derived from algorithmic processing. Human interpretation or trading decisions based on this data carry inherent risks."
    ]


def build_dataset_overview():
    """Build dataset_overview.json artifact."""
    print("Loading sample entries...")
    entries = load_sample_entries()
    print(f"Loaded {len(entries)} entries from {SAMPLE_DATA_FILE}")
    
    # Extract metrics
    scale = extract_scale_metrics(entries)
    preview_row = extract_preview_row(entries)
    
    # Freshness info
    freshness = {
        "archive_sample_source": str(SAMPLE_DATA_FILE.name),
        "notes": "This sample represents the first 200 entries from the latest archive snapshot. Full dataset may differ."
    }
    
    # Non-claims block
    non_claims_block = generate_non_claims_block()
    
    # Build artifact
    artifact = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "scale": scale,
        "freshness": freshness,
        "preview_row": preview_row,
        "non_claims_block": non_claims_block
    }
    
    # Write artifact
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(artifact, f, indent=2, ensure_ascii=True)
    
    print(f"✓ Generated: {OUTPUT_FILE}")
    print(f"  - Entries scanned: {scale['entries_scanned']}")
    print(f"  - Distinct symbols: {scale['distinct_symbols']}")
    print(f"  - Date range: {scale['date_range_utc']}")
    if preview_row:
        print(f"  - Preview row: {preview_row['symbol']} ({len(preview_row)} fields)")
    print(f"  - Non-claims: {len(non_claims_block)} items")


if __name__ == '__main__':
    try:
        build_dataset_overview()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
