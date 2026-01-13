#!/usr/bin/env python3
"""
Archive Sample Sync Script

Extracts the most recent N entries from the CryptoBot archive and writes them
to a normalized sample file for use by artifact builders.

Usage:
    python scripts/sync_archive_sample.py --n 200
    python scripts/sync_archive_sample.py --n 500 --archive-path /custom/path
"""

import json
import gzip
import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional


# Default paths
DEFAULT_ARCHIVE_BASE = Path("../cryptobot/data/archive")
OUTPUT_SAMPLE = Path("data/samples/cryptobot_latest_tail200.jsonl")
OUTPUT_META = Path("data/samples/cryptobot_latest_tail200.meta.json")


def find_latest_archive_folder(archive_base: Path) -> Path:
    """Find the most recent date folder in the archive."""
    date_folders = [
        d for d in archive_base.iterdir() 
        if d.is_dir() and d.name.isdigit() and len(d.name) == 8
    ]
    
    if not date_folders:
        print(f"[ERROR] No date folders found in {archive_base}", file=sys.stderr)
        sys.exit(1)
    
    latest = sorted(date_folders, key=lambda x: x.name, reverse=True)[0]
    print(f"[INFO] Latest archive folder: {latest.name}")
    return latest


def get_archive_files(folder: Path) -> List[Tuple[Path, float]]:
    """Get all archive files (.jsonl, .jsonl.gz) sorted by modification time (newest first)."""
    files = []
    
    for ext in ['*.jsonl', '*.jsonl.gz']:
        for f in folder.glob(ext):
            mtime = f.stat().st_mtime
            files.append((f, mtime))
    
    # Sort by modification time, newest first
    files.sort(key=lambda x: x[1], reverse=True)
    
    if not files:
        print(f"[ERROR] No .jsonl or .jsonl.gz files found in {folder}", file=sys.stderr)
        sys.exit(1)
    
    print(f"[INFO] Found {len(files)} archive files")
    for f, mtime in files[:5]:  # Show first 5
        dt = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
        print(f"  - {f.name} (modified: {dt})")
    
    return files  # Return list of (Path, mtime) tuples


def read_entries_from_file(filepath: Path, limit: Optional[int] = None) -> List[Dict]:
    """Read entries from a .jsonl or .jsonl.gz file."""
    entries = []
    
    try:
        if filepath.suffix == '.gz':
            opener = gzip.open
        else:
            opener = open
        
        with opener(filepath, 'rt', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    entries.append(entry)
                    if limit and len(entries) >= limit:
                        break
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"[WARN] Error reading {filepath.name}: {e}", file=sys.stderr)
        return []
    
    return entries


def extract_tail_entries(archive_files: List[Tuple[Path, float]], n: int) -> Tuple[List[Dict], List[str]]:
    """Extract the most recent N entries across archive files."""
    all_entries = []
    source_files = []
    
    for filepath, _ in archive_files:
        if len(all_entries) >= n:
            break
        
        print(f"[INFO] Reading {filepath.name}...")
        entries = read_entries_from_file(filepath)
        
        if entries:
            source_files.append(str(filepath))
            all_entries.extend(entries)
            print(f"  → Loaded {len(entries)} entries (total: {len(all_entries)})")
    
    # Take the last N entries (most recent)
    tail_entries = all_entries[-n:] if len(all_entries) > n else all_entries
    
    print(f"[INFO] Extracted {len(tail_entries)} tail entries from {len(source_files)} files")
    return tail_entries, source_files


def write_sample_file(entries: List[Dict], output_path: Path):
    """Write entries to normalized JSONL (ASCII-only, LF line endings)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='ascii', newline='\n') as f:
        for entry in entries:
            json.dump(entry, f, ensure_ascii=True)
            f.write('\n')
    
    print(f"[INFO] Wrote {len(entries)} entries to {output_path}")


def write_meta_file(meta: Dict, output_path: Path):
    """Write metadata JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='ascii', newline='\n') as f:
        json.dump(meta, f, ensure_ascii=True, indent=2)
    
    print(f"[INFO] Wrote metadata to {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Sync archive sample from CryptoBot data')
    parser.add_argument('--n', type=int, default=200, help='Number of entries to extract (default: 200)')
    parser.add_argument('--archive-path', type=Path, default=DEFAULT_ARCHIVE_BASE, 
                        help='Path to archive base directory')
    args = parser.parse_args()
    
    print("=" * 60)
    print("Archive Sample Sync")
    print("=" * 60)
    print()
    
    # Validate archive path
    if not args.archive_path.exists():
        print(f"[ERROR] Archive path does not exist: {args.archive_path}", file=sys.stderr)
        sys.exit(1)
    
    # Find latest archive folder
    latest_folder = find_latest_archive_folder(args.archive_path)
    
    # Get archive files
    archive_files = get_archive_files(latest_folder)
    
    # Extract tail entries
    tail_entries, source_files = extract_tail_entries(archive_files, args.n)
    
    if len(tail_entries) == 0:
        print("[ERROR] No entries extracted", file=sys.stderr)
        sys.exit(1)
    
    # Write sample file
    write_sample_file(tail_entries, OUTPUT_SAMPLE)
    
    # Write metadata
    meta = {
        "extracted_at_utc": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "source_archive_folder": str(latest_folder),
        "source_files": source_files,
        "requested_count": args.n,
        "actual_count": len(tail_entries),
        "sample_file": str(OUTPUT_SAMPLE)
    }
    write_meta_file(meta, OUTPUT_META)
    
    print()
    print("[SUCCESS] Archive sample synced")
    print(f"  Entries: {len(tail_entries)}")
    print(f"  Sample: {OUTPUT_SAMPLE}")
    print(f"  Meta: {OUTPUT_META}")


if __name__ == "__main__":
    main()
