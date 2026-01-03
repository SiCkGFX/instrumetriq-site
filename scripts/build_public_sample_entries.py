#!/usr/bin/env python3
"""
Public Sample Entries Builder

Generates public preview artifacts (JSON and JSONL) from archive sample data.
Provides a limited, non-exhaustive extract for website visitors to browse.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

# Configuration
SAMPLE_DATA_FILE = Path("data/samples/cryptobot_latest_head200.jsonl")
OUTPUT_JSON = Path("public/data/sample_entries_v7.json")
OUTPUT_JSONL = Path("public/data/sample_entries_v7.jsonl")
ENTRY_COUNT = 100  # Number of entries to include in public preview


def load_sample_entries(sample_file: Path, limit: int) -> list:
    """
    Load entries from JSONL sample file.
    
    Args:
        sample_file: Path to JSONL file
        limit: Maximum number of entries to load
    
    Returns:
        List of parsed entry dictionaries
    """
    entries = []
    try:
        with open(sample_file, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i >= limit:
                    break
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


def build_json_artifact(entries: list) -> dict:
    """
    Build the JSON artifact structure.
    
    Args:
        entries: List of full v7 entry dictionaries
    
    Returns:
        Complete artifact dictionary
    """
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "schema_version": "v7",
        "entry_count": len(entries),
        "source": SAMPLE_DATA_FILE.name,
        "note": "Public preview extract. Non-exhaustive. Not suitable for training.",
        "entries": entries
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
    
    Args:
        entries: List of entry dictionaries
        output_path: Destination file path
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='ascii') as f:
        for entry in entries:
            json.dump(entry, f, ensure_ascii=True)
            f.write('\n')
    
    print(f"[INFO] JSONL artifact written to {output_path}")


def main():
    """Main entry point."""
    print("=" * 60)
    print("Public Sample Entries Builder")
    print("=" * 60)
    print()
    
    # Load entries (deterministic: first N entries)
    entries = load_sample_entries(SAMPLE_DATA_FILE, ENTRY_COUNT)
    
    if len(entries) == 0:
        print("[ERROR] No entries loaded", file=sys.stderr)
        sys.exit(1)
    
    # Build JSON artifact
    artifact = build_json_artifact(entries)
    
    # Write JSON output
    write_json_artifact(artifact, OUTPUT_JSON)
    
    # Write JSONL output (same entries, same order)
    write_jsonl_artifact(entries, OUTPUT_JSONL)
    
    print()
    print("[SUCCESS] Public sample entries generated")
    print(f"  Entry count: {len(entries)}")
    print(f"  JSON: {OUTPUT_JSON}")
    print(f"  JSONL: {OUTPUT_JSONL}")


if __name__ == "__main__":
    main()
