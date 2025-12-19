"""
Daily statistics aggregator for CryptoBot archive.
Scans day folders, computes v7_seen and usable entries per day.
"""

import gzip
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


def is_v7_entry(entry: dict) -> bool:
    """Check if entry is v7 (schema_version == 7)."""
    meta = entry.get("meta", {})
    schema_version = meta.get("schema_version", 0)
    return schema_version == 7


def is_usable_v7_entry(entry: dict, min_spot_samples: int = 700) -> tuple[bool, str]:
    """
    Check if entry meets 'usable' criteria from status contract.
    
    Requirements (aligned with status.json contract):
    - meta.schema_version == 7
    - spot_prices is list with len >= min_spot_samples (default 700)
    - spot_raw is dict with non-null required keys: mid, bid, ask, spread_bps
    - twitter_sentiment_windows is dict with required windows (last_cycle OR last_2_cycles)
    
    Returns:
        (is_usable: bool, reason: str)
    """
    # Must be v7
    meta = entry.get("meta", {})
    schema_version = meta.get("schema_version", 0)
    if schema_version != 7:
        return (False, f"schema_version={schema_version}, expected 7")
    
    # Check spot_prices is list and has enough samples
    spot_prices = entry.get("spot_prices")
    if not isinstance(spot_prices, list):
        return (False, "spot_prices not a list")
    if len(spot_prices) < min_spot_samples:
        return (False, f"spot_prices={len(spot_prices)}, required>={min_spot_samples}")
    
    # Check spot_raw has required fields with non-null values
    spot_raw = entry.get("spot_raw")
    if not isinstance(spot_raw, dict):
        return (False, "spot_raw not a dict")
    
    required_spot_fields = ["mid", "bid", "ask", "spread_bps"]
    for field in required_spot_fields:
        if field not in spot_raw:
            return (False, f"spot_raw missing '{field}'")
        if spot_raw[field] is None:
            return (False, f"spot_raw '{field}' is null")
    
    # Check twitter_sentiment_windows has required windows
    tsw = entry.get("twitter_sentiment_windows")
    if not isinstance(tsw, dict):
        return (False, "twitter_sentiment_windows not a dict")
    
    # Must have at least one of the required windows
    if "last_cycle" not in tsw and "last_2_cycles" not in tsw:
        return (False, "twitter_sentiment_windows missing required windows")
    
    return (True, "OK")


def scan_day_folder(day_folder: Path) -> Dict[str, int]:
    """
    Scan a single day folder (YYYYMMDD/*.jsonl.gz).
    Returns: {"v7_seen": int, "usable": int}
    """
    v7_seen = 0
    usable = 0
    
    # Find all .jsonl.gz files in this day
    jsonl_files = list(day_folder.glob("*.jsonl.gz"))
    
    for jsonl_file in jsonl_files:
        try:
            with gzip.open(jsonl_file, 'rt', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        entry = json.loads(line)
                        
                        # Count v7 entries
                        if is_v7_entry(entry):
                            v7_seen += 1
                            
                            # Check if usable (using aligned gate)
                            is_usable, reason = is_usable_v7_entry(entry)
                            if is_usable:
                                usable += 1
                    
                    except json.JSONDecodeError:
                        # Skip malformed lines
                        continue
        
        except Exception as e:
            # Skip files that can't be read
            print(f"  Warning: Could not read {jsonl_file.name}: {e}")
            continue
    
    return {"v7_seen": v7_seen, "usable": usable}


def compute_daily_stats(archive_path: Path) -> List[Dict]:
    """
    Compute daily statistics across all day folders in archive.
    
    Returns list of dicts:
    [
        {
            "date": "2025-12-19",
            "v7_seen": 1,
            "usable": 1
        },
        ...
    ]
    Sorted by date ascending.
    """
    if not archive_path.exists():
        print(f"[WARN] Archive path does not exist: {archive_path}")
        return []
    
    stats = []
    
    # Find all day folders (YYYYMMDD format)
    day_folders = sorted([d for d in archive_path.iterdir() 
                         if d.is_dir() and d.name.isdigit() and len(d.name) == 8])
    
    print(f"Found {len(day_folders)} day folders in archive")
    
    for day_folder in day_folders:
        day_str = day_folder.name  # YYYYMMDD
        
        # Parse date
        try:
            date_obj = datetime.strptime(day_str, "%Y%m%d")
            date_iso = date_obj.strftime("%Y-%m-%d")
        except ValueError:
            print(f"  Warning: Invalid day folder name: {day_str}")
            continue
        
        # Scan this day
        day_stats = scan_day_folder(day_folder)
        
        # Only include days with data
        if day_stats["v7_seen"] > 0:
            stats.append({
                "date": date_iso,
                "v7_seen": day_stats["v7_seen"],
                "usable": day_stats["usable"]
            })
            print(f"  {date_iso}: v7_seen={day_stats['v7_seen']}, usable={day_stats['usable']}")
    
    return stats


def compute_cumulative_usable(daily_stats: List[Dict]) -> List[Dict]:
    """
    Add cumulative usable count to each day's stats.
    Returns new list with 'cumulative_usable' field added.
    """
    cumulative = 0
    result = []
    
    for day in daily_stats:
        cumulative += day["usable"]
        result.append({
            **day,
            "cumulative_usable": cumulative
        })
    
    return result
