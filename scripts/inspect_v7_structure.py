#!/usr/bin/env python3
"""
Ground truth inspection utility for v7 archive entries.
Prints actual field structure to verify paths before using them.
"""

import json
import gzip
import os
from pathlib import Path
from collections import defaultdict


def inspect_v7_entries(archive_base: Path, sample_size: int = 5):
    """Inspect real v7 entries and print their structure."""
    
    print("=" * 70)
    print("V7 Entry Structure Inspector")
    print("=" * 70)
    print()
    
    # Find day directories
    day_dirs = sorted(archive_base.glob("202512*"))
    if not day_dirs:
        print(f"[ERROR] No archive directories found in {archive_base}")
        return
    
    print(f"[INFO] Found {len(day_dirs)} day directories")
    print()
    
    # Collect sample entries
    entries_inspected = 0
    field_stats = defaultdict(int)
    
    for day_dir in day_dirs:
        if not day_dir.is_dir():
            continue
        
        for gz_file in day_dir.glob("*.jsonl.gz"):
            try:
                with gzip.open(gz_file, 'rt', encoding='utf-8') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        
                        try:
                            entry = json.loads(line)
                            
                            # Check if v7
                            meta = entry.get("meta", {})
                            if meta.get("schema_version") != 7:
                                continue
                            
                            entries_inspected += 1
                            
                            if entries_inspected <= sample_size:
                                print(f"--- Entry {entries_inspected} ---")
                                print(f"Top-level keys: {list(entry.keys())}")
                                print()
                                
                                # Meta structure
                                print("meta keys:")
                                for k in sorted(meta.keys()):
                                    print(f"  - {k}: {type(meta[k]).__name__}")
                                print()
                                
                                # Spot raw
                                spot_raw = entry.get("spot_raw", {})
                                print("spot_raw keys:")
                                for k in sorted(spot_raw.keys()):
                                    print(f"  - {k}: {type(spot_raw[k]).__name__}")
                                print()
                                
                                # Twitter sentiment windows
                                tsw = entry.get("twitter_sentiment_windows", {})
                                print("twitter_sentiment_windows keys:")
                                for k in sorted(tsw.keys()):
                                    print(f"  - {k}: {type(tsw[k]).__name__}")
                                print()
                                
                                # Inspect last_cycle structure
                                last_cycle = tsw.get("last_cycle")
                                if last_cycle:
                                    print("twitter_sentiment_windows.last_cycle keys:")
                                    for k in sorted(last_cycle.keys()):
                                        val = last_cycle[k]
                                        if isinstance(val, dict):
                                            print(f"  - {k}: dict with keys {list(val.keys())}")
                                        else:
                                            print(f"  - {k}: {type(val).__name__}")
                                    print()
                                
                                # Check for sentiment scoring fields
                                if last_cycle:
                                    print("Sentiment scoring fields in last_cycle:")
                                    sentiment_keys = [
                                        'hybrid_mean_score', 'mean_score', 'final_score',
                                        'lexicon_mean_score', 'ai_mean_score',
                                        'primary_decision', 'referee_decision',
                                        'primary_confidence', 'referee_confidence',
                                        'decision_source'
                                    ]
                                    for key in sentiment_keys:
                                        if key in last_cycle:
                                            print(f"  [FOUND] {key}: {last_cycle[key]}")
                                        else:
                                            print(f"  [MISSING] {key}")
                                    print()
                            
                            # Track field availability across all entries
                            if "spot_raw" in entry and "spread_bps" in entry["spot_raw"]:
                                field_stats["spot_raw.spread_bps"] += 1
                            
                            if "twitter_sentiment_windows" in entry:
                                tsw = entry["twitter_sentiment_windows"]
                                if "last_cycle" in tsw:
                                    field_stats["twitter_sentiment_windows.last_cycle"] += 1
                                    lc = tsw["last_cycle"]
                                    if "posts_total" in lc:
                                        field_stats["last_cycle.posts_total"] += 1
                                    if "hybrid_mean_score" in lc:
                                        field_stats["last_cycle.hybrid_mean_score"] += 1
                                    if "mean_score" in lc:
                                        field_stats["last_cycle.mean_score"] += 1
                                    if "primary_confidence" in lc:
                                        field_stats["last_cycle.primary_confidence"] += 1
                                    if "referee_confidence" in lc:
                                        field_stats["last_cycle.referee_confidence"] += 1
                                    if "decision_source" in lc:
                                        field_stats["last_cycle.decision_source"] += 1
                            
                            if entries_inspected >= sample_size + 100:
                                break
                        
                        except json.JSONDecodeError:
                            continue
                
                if entries_inspected >= sample_size + 100:
                    break
            
            except Exception as e:
                print(f"[WARN] Error reading {gz_file}: {e}")
                continue
        
        if entries_inspected >= sample_size + 100:
            break
    
    print()
    print("=" * 70)
    print(f"Field Availability Summary (from {entries_inspected} v7 entries)")
    print("=" * 70)
    for field, count in sorted(field_stats.items()):
        pct = (count / entries_inspected * 100) if entries_inspected > 0 else 0
        print(f"{field:50s} : {count:5d} / {entries_inspected:5d} ({pct:5.1f}%)")
    print()


if __name__ == "__main__":
    import sys
    
    archive_base = os.getenv("ARCHIVE_BASE_PATH", "D:/Sentiment-Data/CryptoBot/data/archive")
    archive_path = Path(archive_base)
    
    if not archive_path.exists():
        print(f"[ERROR] Archive not found: {archive_path}")
        sys.exit(1)
    
    inspect_v7_entries(archive_path, sample_size=3)
