#!/usr/bin/env python3
"""
Public Sample Entries Builder

Generates public preview artifacts (JSON and JSONL) from archive sample data.
Splits spot_prices into separate file to keep dataset/index.html under Cloudflare's 25 MiB limit.
Uses date-based deterministic rotation to vary the preview over time.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

# Configuration
SAMPLE_DATA_FILE = Path("data/samples/cryptobot_latest_tail200.jsonl")
OUTPUT_JSON = Path("public/data/sample_entries_v7.json")
OUTPUT_SPOTS_JSON = Path("public/data/sample_entries_spots_v7.json")
OUTPUT_JSONL = Path("public/data/sample_entries_v7.jsonl")
ENTRY_COUNT = 100  # Number of entries to include in public preview


def load_all_entries(sample_file: Path) -> list:
    """
    Load all entries from JSONL sample file.
    
    Args:
        sample_file: Path to JSONL file
    
    Returns:
        List of parsed entry dictionaries
    """
    entries = []
    try:
        with open(sample_file, 'r', encoding='utf-8') as f:
            for line in f:
                entry = json.loads(line)
                entries.append(entry)
        print(f"[INFO] Loaded {len(entries)} entries from {sample_file}")
        return entries
    except FileNotFoundError:
        print(f"[ERROR] Sample file not found: {sample_file}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON in {sample_file}: {e}", file=sys.stderr)
        sys.exit(1)


def select_entries_for_date(all_entries: list, limit: int, date: datetime) -> list:
    """
    Select entries deterministically based on date.
    Uses date-based offset to rotate through entries over time.
    
    Args:
        all_entries: Full list of entries
        limit: Number of entries to select
        date: Date to use for offset calculation (UTC)
    
    Returns:
        List of selected entries
    """
    if len(all_entries) <= limit:
        return all_entries
    
    # Calculate offset from date: YYYYMMDD % total_entries
    date_int = int(date.strftime("%Y%m%d"))
    offset = date_int % len(all_entries)
    
    # Select entries with wrap-around
    selected = []
    for i in range(limit):
        idx = (offset + i) % len(all_entries)
        selected.append(all_entries[idx])
    
    print(f"[INFO] Date-based offset: {offset} (from {date.strftime('%Y-%m-%d')})")
    print(f"[INFO] Selected entries [{offset}:{offset+limit}) with wrap-around")
    
    return selected


def build_json_artifact(entries: list, generation_date: datetime) -> dict:
    """
    Build the JSON artifact structure WITHOUT spot_prices.
    
    Args:
        entries: List of full v7 entry dictionaries
        generation_date: Date used for generation (UTC)
    
    Returns:
        Complete artifact dictionary with spot_prices removed from entries
    """
    # Remove spot_prices from each entry to reduce size
    entries_without_spots = []
    for entry in entries:
        entry_copy = entry.copy()
        if 'spot_prices' in entry_copy:
            del entry_copy['spot_prices']
        entries_without_spots.append(entry_copy)
    
    return {
        "generated_at_utc": generation_date.isoformat().replace('+00:00', 'Z'),
        "schema_version": "v7",
        "entry_count": len(entries_without_spots),
        "source": SAMPLE_DATA_FILE.name,
        "note": "Public preview entries. Spot prices in separate file (sample_entries_spots_v7.json).",
        "entries": entries_without_spots
    }


def build_spots_artifact(entries: list, generation_date: datetime) -> dict:
    """
    Build the spots artifact containing only spot_prices arrays.
    
    Args:
        entries: List of full v7 entry dictionaries
        generation_date: Date used for generation (UTC)
    
    Returns:
        Artifact dictionary with spot_prices arrays keyed by symbol
    """
    spots = []
    for entry in entries:
        spots.append({
            "symbol": entry.get("symbol"),
            "spot_prices": entry.get("spot_prices", [])
        })
    
    return {
        "generated_at_utc": generation_date.isoformat().replace('+00:00', 'Z'),
        "schema_version": "v7",
        "entry_count": len(spots),
        "note": "Spot prices for public preview entries. Load lazily to reduce page size.",
        "spots": spots
    }


def write_json_artifact(artifact: dict, output_path: Path):
    """
    Write JSON artifact to file with ASCII-only encoding.
    
    Args:
        artifact: Complete artifact dictionary
        output_path: Destination file path
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='ascii') as f:
        json.dump(artifact, f, ensure_ascii=True, indent=2)
    
    print(f"[INFO] JSON artifact written to {output_path}")


def write_jsonl_artifact(entries: list, output_path: Path):
    """
    Write JSONL artifact to file with ASCII-only encoding.
    Excludes spot_prices to keep file size manageable for downloads.
    
    Args:
        entries: List of entry dictionaries
        output_path: Destination file path
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='ascii') as f:
        for entry in entries:
            # Remove spot_prices for download file
            entry_copy = entry.copy()
            if 'spot_prices' in entry_copy:
                del entry_copy['spot_prices']
            json.dump(entry_copy, f, ensure_ascii=True)
            f.write('\n')
    
    print(f"[INFO] JSONL artifact written to {output_path}")


def main():
    """Main entry point."""
    print("=" * 60)
    print("Public Sample Entries Builder")
    print("=" * 60)
    print()
    
    # Get current date for deterministic rotation
    generation_date = datetime.now(timezone.utc)
    print(f"[INFO] Generation date: {generation_date.strftime('%Y-%m-%d')}")
    
    # Load all entries
    all_entries = load_all_entries(SAMPLE_DATA_FILE)
    
    if len(all_entries) == 0:
        print("[ERROR] No entries loaded", file=sys.stderr)
        sys.exit(1)
    
    # Select entries based on date
    selected_entries = select_entries_for_date(all_entries, ENTRY_COUNT, generation_date)
    
    # Build JSON artifact (without spot_prices)
    artifact = build_json_artifact(selected_entries, generation_date)
    
    # Build spots artifact (only spot_prices)
    spots_artifact = build_spots_artifact(selected_entries, generation_date)
    
    # Write JSON output (without spot_prices)
    write_json_artifact(artifact, OUTPUT_JSON)
    
    # Write spots JSON output
    write_json_artifact(spots_artifact, OUTPUT_SPOTS_JSON)
    
    # Write JSONL output (without spot_prices for download size)
    write_jsonl_artifact(selected_entries, OUTPUT_JSONL)
    
    print()
    print("[SUCCESS] Public sample entries generated")
    print(f"  Entry count: {len(selected_entries)}")
    print(f"  JSON (no spots): {OUTPUT_JSON}")
    print(f"  Spots JSON: {OUTPUT_SPOTS_JSON}")
    print(f"  JSONL (no spots): {OUTPUT_JSONL}")


if __name__ == "__main__":
    main()
