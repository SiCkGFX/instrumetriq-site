#!/usr/bin/env python3
"""
V7 Field Path Inspector
Scans real v7 archive entries and outputs verified field paths.
This is the ground truth for what fields actually exist.
"""

import json
import gzip
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Set
from collections import defaultdict
from dataclasses import dataclass, asdict


@dataclass
class FieldPathInventory:
    """Inventory of discovered field paths in v7 entries."""
    total_entries_scanned: int
    
    # Meta fields
    meta_sample_count: int = 0
    meta_duration_sec: int = 0
    
    # Spot raw fields
    spot_raw_spread_bps: int = 0
    spot_raw_mid: int = 0
    
    # Spot prices array
    has_spot_prices_array: int = 0
    
    # Twitter sentiment windows
    twitter_sentiment_windows_exists: int = 0
    twitter_last_cycle_exists: int = 0
    twitter_last_cycle_posts_total: int = 0
    
    # Sentiment scoring fields (nested in last_cycle)
    twitter_last_cycle_hybrid_mean_score: int = 0
    twitter_last_cycle_mean_score: int = 0
    twitter_last_cycle_lexicon_mean_score: int = 0
    twitter_last_cycle_ai_mean_score: int = 0
    
    # Decision confidence fields
    twitter_last_cycle_primary_confidence: int = 0
    twitter_last_cycle_referee_confidence: int = 0
    twitter_last_cycle_decision_source: int = 0
    twitter_last_cycle_primary_decision: int = 0
    twitter_last_cycle_referee_decision: int = 0
    
    # Derived fields
    derived_liq_global_pct: int = 0
    derived_liq_self_pct: int = 0
    derived_depth_spread_bps: int = 0
    
    # Activity flags
    is_silent: int = 0


def scan_v7_entries(archive_path: Path, sample_limit: int = 200) -> FieldPathInventory:
    """
    Scan v7 entries and count field availability.
    Returns exact counts for each field path.
    """
    print("=" * 70)
    print("V7 Field Path Inspector")
    print("=" * 70)
    print(f"Archive: {archive_path}")
    print(f"Sample limit: {sample_limit}")
    print()
    
    inventory = FieldPathInventory(total_entries_scanned=0)
    entries_scanned = 0
    
    # Find day directories
    day_dirs = sorted(archive_path.glob("202512*"))
    if not day_dirs:
        print(f"[ERROR] No archive directories found in {archive_path}")
        sys.exit(1)
    
    print(f"[INFO] Found {len(day_dirs)} day directories")
    print("[INFO] Scanning entries...")
    print()
    
    # Sample entries to print structure
    sample_entries = []
    
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
                            meta = entry.get("meta", {})
                            
                            # Only v7
                            if meta.get("schema_version") != 7:
                                continue
                            
                            entries_scanned += 1
                            
                            # Store first few for detailed inspection
                            if len(sample_entries) < 3:
                                sample_entries.append(entry)
                            
                            # Count meta fields
                            if "sample_count" in meta:
                                inventory.meta_sample_count += 1
                            if "duration_sec" in meta:
                                inventory.meta_duration_sec += 1
                            
                            # Count spot_raw fields
                            spot_raw = entry.get("spot_raw", {})
                            if "spread_bps" in spot_raw:
                                inventory.spot_raw_spread_bps += 1
                            if "mid" in spot_raw:
                                inventory.spot_raw_mid += 1
                            
                            # Count spot_prices array
                            spot_prices = entry.get("spot_prices", [])
                            if spot_prices:
                                inventory.has_spot_prices_array += 1
                            
                            # Count twitter sentiment windows
                            tsw = entry.get("twitter_sentiment_windows", {})
                            if tsw:
                                inventory.twitter_sentiment_windows_exists += 1
                            
                            last_cycle = tsw.get("last_cycle", {})
                            if last_cycle:
                                inventory.twitter_last_cycle_exists += 1
                                
                                # Count posts_total
                                if "posts_total" in last_cycle:
                                    inventory.twitter_last_cycle_posts_total += 1
                                
                                # Count sentiment scoring fields
                                if "hybrid_mean_score" in last_cycle:
                                    inventory.twitter_last_cycle_hybrid_mean_score += 1
                                if "mean_score" in last_cycle:
                                    inventory.twitter_last_cycle_mean_score += 1
                                if "lexicon_mean_score" in last_cycle:
                                    inventory.twitter_last_cycle_lexicon_mean_score += 1
                                if "ai_mean_score" in last_cycle:
                                    inventory.twitter_last_cycle_ai_mean_score += 1
                                
                                # Count decision confidence fields
                                if "primary_confidence" in last_cycle:
                                    inventory.twitter_last_cycle_primary_confidence += 1
                                if "referee_confidence" in last_cycle:
                                    inventory.twitter_last_cycle_referee_confidence += 1
                                if "decision_source" in last_cycle:
                                    inventory.twitter_last_cycle_decision_source += 1
                                if "primary_decision" in last_cycle:
                                    inventory.twitter_last_cycle_primary_decision += 1
                                if "referee_decision" in last_cycle:
                                    inventory.twitter_last_cycle_referee_decision += 1
                            
                            # Count derived fields
                            derived = entry.get("derived", {})
                            if "liq_global_pct" in derived:
                                inventory.derived_liq_global_pct += 1
                            if "liq_self_pct" in derived:
                                inventory.derived_liq_self_pct += 1
                            if "depth_spread_bps" in derived:
                                inventory.derived_depth_spread_bps += 1
                            
                            # Count activity flags
                            flags = entry.get("flags", {})
                            if "is_silent" in flags:
                                inventory.is_silent += 1
                            
                            if entries_scanned >= sample_limit:
                                break
                        
                        except json.JSONDecodeError:
                            continue
                
                if entries_scanned >= sample_limit:
                    break
            
            except Exception as e:
                print(f"[WARN] Error reading {gz_file}: {e}")
                continue
        
        if entries_scanned >= sample_limit:
            break
    
    inventory.total_entries_scanned = entries_scanned
    
    if entries_scanned == 0:
        print("[ERROR] No v7 entries found!")
        sys.exit(1)
    
    # Print sample entry structure
    if sample_entries:
        print("=" * 70)
        print("SAMPLE ENTRY STRUCTURE")
        print("=" * 70)
        entry = sample_entries[0]
        print(f"Top-level keys: {list(entry.keys())}")
        print()
        
        print("twitter_sentiment_windows structure:")
        tsw = entry.get("twitter_sentiment_windows", {})
        if tsw:
            print(f"  Keys: {list(tsw.keys())}")
            last_cycle = tsw.get("last_cycle", {})
            if last_cycle:
                print(f"  last_cycle keys: {list(last_cycle.keys())}")
                
                # Show nested structure
                nested = last_cycle.get("nested", {})
                if nested:
                    print(f"  last_cycle.nested keys: {list(nested.keys())}")
                    for key, val in nested.items():
                        if isinstance(val, dict):
                            print(f"    nested.{key} (dict): {list(val.keys())}")
        else:
            print("  [NOT FOUND]")
        print()
    
    return inventory


def print_inventory_report(inventory: FieldPathInventory) -> None:
    """Print human-readable inventory report."""
    print("=" * 70)
    print("FIELD PATH INVENTORY REPORT")
    print("=" * 70)
    print(f"Total v7 entries scanned: {inventory.total_entries_scanned}")
    print()
    
    def rate(count: int) -> str:
        """Format availability rate."""
        pct = (count / inventory.total_entries_scanned * 100) if inventory.total_entries_scanned > 0 else 0
        status = "[VERIFIED]" if pct >= 90 else "[SPARSE]" if pct > 0 else "[MISSING]"
        return f"{status} {count:5d} / {inventory.total_entries_scanned:5d} ({pct:5.1f}%)"
    
    print("META FIELDS:")
    print(f"  meta.sample_count                : {rate(inventory.meta_sample_count)}")
    print(f"  meta.duration_sec                : {rate(inventory.meta_duration_sec)}")
    print()
    
    print("MARKET MICROSTRUCTURE:")
    print(f"  spot_raw.spread_bps              : {rate(inventory.spot_raw_spread_bps)}")
    print(f"  spot_raw.mid                     : {rate(inventory.spot_raw_mid)}")
    print(f"  spot_prices (array)              : {rate(inventory.has_spot_prices_array)}")
    print()
    
    print("SENTIMENT WINDOWS:")
    print(f"  twitter_sentiment_windows        : {rate(inventory.twitter_sentiment_windows_exists)}")
    print(f"  twitter_sentiment_windows.last_cycle : {rate(inventory.twitter_last_cycle_exists)}")
    print(f"  last_cycle.posts_total           : {rate(inventory.twitter_last_cycle_posts_total)}")
    print()
    
    print("SENTIMENT SCORING (in last_cycle):")
    print(f"  hybrid_mean_score                : {rate(inventory.twitter_last_cycle_hybrid_mean_score)}")
    print(f"  mean_score                       : {rate(inventory.twitter_last_cycle_mean_score)}")
    print(f"  lexicon_mean_score               : {rate(inventory.twitter_last_cycle_lexicon_mean_score)}")
    print(f"  ai_mean_score                    : {rate(inventory.twitter_last_cycle_ai_mean_score)}")
    print()
    
    print("DECISION CONFIDENCE (in last_cycle):")
    print(f"  primary_confidence               : {rate(inventory.twitter_last_cycle_primary_confidence)}")
    print(f"  referee_confidence               : {rate(inventory.twitter_last_cycle_referee_confidence)}")
    print(f"  decision_source                  : {rate(inventory.twitter_last_cycle_decision_source)}")
    print(f"  primary_decision                 : {rate(inventory.twitter_last_cycle_primary_decision)}")
    print(f"  referee_decision                 : {rate(inventory.twitter_last_cycle_referee_decision)}")
    print()
    
    print("DERIVED FIELDS:")
    print(f"  derived.liq_global_pct           : {rate(inventory.derived_liq_global_pct)}")
    print(f"  derived.liq_self_pct             : {rate(inventory.derived_liq_self_pct)}")
    print(f"  derived.depth_spread_bps         : {rate(inventory.derived_depth_spread_bps)}")
    print()
    
    print("ACTIVITY FLAGS:")
    print(f"  flags.is_silent                  : {rate(inventory.is_silent)}")
    print()


def save_inventory_json(inventory: FieldPathInventory, output_path: Path) -> None:
    """Save inventory as JSON for programmatic use."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(asdict(inventory), f, indent=2, ensure_ascii=True)
    
    print(f"[OK] Saved inventory to: {output_path}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Inspect v7 field paths")
    parser.add_argument("--sample", type=int, default=200, help="Number of entries to sample")
    parser.add_argument("--output", type=str, help="Save inventory JSON to this path")
    args = parser.parse_args()
    
    # Determine archive path
    archive_base = os.getenv("ARCHIVE_BASE_PATH", "D:/Sentiment-Data/CryptoBot/data/archive")
    archive_path = Path(archive_base)
    
    if not archive_path.exists():
        print(f"[ERROR] Archive not found: {archive_path}")
        sys.exit(1)
    
    # Scan entries
    inventory = scan_v7_entries(archive_path, sample_limit=args.sample)
    
    # Print report
    print_inventory_report(inventory)
    
    # Save JSON if requested
    if args.output:
        save_inventory_json(inventory, Path(args.output))
    
    print()
    print("[SUCCESS] Field path inspection complete")


if __name__ == "__main__":
    main()
