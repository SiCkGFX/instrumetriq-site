#!/usr/bin/env python3
"""
Generate Sentiment Time Series for Sample Symbols

Extracts all archive entries for the 100 sample symbols and creates a per-symbol
time series of sentiment scores and post counts.

Output: public/data/sample_symbols_sentiment_timeseries.json
"""

import json
import gzip
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional


def load_sample_symbols(sample_json_path: Path) -> List[str]:
    """Load the list of symbols from the public sample entries file."""
    try:
        with open(sample_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            symbols = [entry['symbol'] for entry in data.get('entries', [])]
            print(f"[INFO] Loaded {len(symbols)} sample symbols")
            return symbols
    except Exception as e:
        print(f"[ERROR] Failed to load sample symbols: {e}", file=sys.stderr)
        sys.exit(1)


def extract_sentiment_data(entry: dict) -> Optional[dict]:
    """
    Extract sentiment and post count from an entry.
    
    Returns dict with:
    - ts: timestamp (ISO8601)
    - mean_sent: hybrid sentiment mean score (-1 to +1)
    - posts: total posts counted
    - is_silent: whether entry was marked as silent
    """
    # Get timestamp
    ts = entry.get('meta', {}).get('added_ts')
    if not ts:
        return None
    
    # Try to get sentiment from last_2_cycles first, fallback to last_cycle
    windows = entry.get('twitter_sentiment_windows', {})
    
    sentiment_data = None
    posts_total = None
    is_silent = None
    
    # Priority: last_2_cycles > last_cycle
    if 'last_2_cycles' in windows:
        window = windows['last_2_cycles']
        sentiment_data = window.get('hybrid_decision_stats', {}).get('mean_score')
        posts_total = window.get('posts_total')
        activity = window.get('sentiment_activity', {})
        is_silent = activity.get('is_silent')
    
    if sentiment_data is None and 'last_cycle' in windows:
        window = windows['last_cycle']
        sentiment_data = window.get('hybrid_decision_stats', {}).get('mean_score')
        posts_total = window.get('posts_total')
        activity = window.get('sentiment_activity', {})
        is_silent = activity.get('is_silent')
    
    # Only include entries with sentiment data
    if sentiment_data is None:
        return None
    
    result = {
        'ts': ts,
        'mean_sent': round(sentiment_data, 4)
    }
    
    if posts_total is not None:
        result['posts'] = posts_total
    
    if is_silent is not None:
        result['is_silent'] = is_silent
    
    return result


def scan_archive_for_symbols(archive_path: Path, target_symbols: set) -> Dict[str, List[dict]]:
    """
    Scan the archive and extract all entries for the target symbols.
    
    Returns a dict mapping symbol -> list of time series points.
    """
    print(f"[INFO] Scanning archive: {archive_path}")
    
    series_by_symbol = {symbol: [] for symbol in target_symbols}
    total_entries_scanned = 0
    total_entries_matched = 0
    
    # Find all date folders
    date_folders = sorted([
        d for d in archive_path.iterdir() 
        if d.is_dir() and d.name.isdigit() and len(d.name) == 8
    ])
    
    if not date_folders:
        print(f"[ERROR] No date folders found in {archive_path}", file=sys.stderr)
        sys.exit(1)
    
    print(f"[INFO] Found {len(date_folders)} date folders")
    
    for date_folder in date_folders:
        print(f"[INFO] Processing {date_folder.name}...")
        
        # Find all .jsonl.gz files in this folder
        archive_files = list(date_folder.glob('*.jsonl.gz'))
        
        for archive_file in archive_files:
            try:
                with gzip.open(archive_file, 'rt', encoding='utf-8') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        
                        total_entries_scanned += 1
                        
                        try:
                            entry = json.loads(line)
                            symbol = entry.get('symbol')
                            
                            if symbol in target_symbols:
                                sentiment_point = extract_sentiment_data(entry)
                                if sentiment_point:
                                    series_by_symbol[symbol].append(sentiment_point)
                                    total_entries_matched += 1
                        
                        except json.JSONDecodeError:
                            continue
            
            except Exception as e:
                print(f"[WARN] Error reading {archive_file.name}: {e}", file=sys.stderr)
                continue
    
    print(f"[INFO] Scanned {total_entries_scanned} total entries")
    print(f"[INFO] Matched {total_entries_matched} entries for sample symbols")
    
    # Sort each symbol's series by timestamp
    for symbol in series_by_symbol:
        series_by_symbol[symbol].sort(key=lambda x: x['ts'])
        if series_by_symbol[symbol]:
            print(f"  {symbol}: {len(series_by_symbol[symbol])} entries")
    
    return series_by_symbol


def write_timeseries_artifact(series_by_symbol: Dict[str, List[dict]], output_path: Path):
    """Write the time series artifact to JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    total_entries = sum(len(series) for series in series_by_symbol.values())
    
    artifact = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "symbols_count": len(series_by_symbol),
            "total_entries": total_entries,
            "note": "Per-symbol sentiment time series extracted from archive. Each point is one entry."
        },
        "series_by_symbol": series_by_symbol
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(artifact, f, ensure_ascii=True, indent=2)
    
    print(f"[INFO] Wrote timeseries artifact to {output_path}")
    
    # Report file size
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"[INFO] File size: {size_mb:.2f} MB")
    
    if size_mb > 20:
        print(f"[WARN] File size exceeds 20MB, may be too large for client-side fetch", file=sys.stderr)


def main():
    print("=" * 70)
    print("Sentiment Time Series Generator")
    print("=" * 70)
    print()
    
    # Paths
    sample_json = Path("public/data/sample_entries_v7.json")
    archive_path = Path("/srv/cryptobot/data/archive")
    output_path = Path("public/data/sample_symbols_sentiment_timeseries.json")
    
    # Check if archive exists
    if not archive_path.exists():
        print(f"[ERROR] Archive path does not exist: {archive_path}", file=sys.stderr)
        print("[INFO] Trying alternative path: D:/Sentiment-Data/CryptoBot/data/archive")
        archive_path = Path("D:/Sentiment-Data/CryptoBot/data/archive")
        if not archive_path.exists():
            print(f"[ERROR] Archive path does not exist: {archive_path}", file=sys.stderr)
            sys.exit(1)
    
    # Load sample symbols
    symbols = load_sample_symbols(sample_json)
    target_symbols = set(symbols)
    
    # Scan archive
    series_by_symbol = scan_archive_for_symbols(archive_path, target_symbols)
    
    # Write artifact
    write_timeseries_artifact(series_by_symbol, output_path)
    
    print()
    print("[SUCCESS] Sentiment time series generated")
    print(f"  Symbols: {len(series_by_symbol)}")
    print(f"  Total entries: {sum(len(s) for s in series_by_symbol.values())}")
    print(f"  Output: {output_path}")


if __name__ == "__main__":
    main()
