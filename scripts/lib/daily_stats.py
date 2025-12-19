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
    """Check if entry is v7 (schema_version >= 7)."""
    meta = entry.get("meta", {})
    schema_version = meta.get("schema_version", 0)
    return schema_version >= 7


def is_usable_entry(entry: dict) -> bool:
    """
    Check if entry meets 'usable' criteria from status contract.
    
    Requirements (matching CryptoBot exporter logic):
    - v7 entry (schema_version >= 7)
    - spot_prices array has >= 700 samples
    - spot_raw dict has core pricing fields
    """
    # Must be v7
    if not is_v7_entry(entry):
        return False
    
    # Check spot_prices count
    spot_prices = entry.get("spot_prices", [])
    if len(spot_prices) < 700:
        return False
    
    # Check spot_raw has essential fields
    spot_raw = entry.get("spot_raw", {})
    required_fields = ["mid", "bid", "ask", "last"]
    if not all(field in spot_raw for field in required_fields):
        return False
    
    return True


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
                            
                            # Check if usable
                            if is_usable_entry(entry):
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
