#!/usr/bin/env python3
"""
Archive Statistics Builder

Generates archive_stats.json with full archive scale metrics.
Must be run locally (Cloudflare build cannot access local paths).
Output is committed to repo under public/data/.
"""

import json
import gzip
import sys
from pathlib import Path
from datetime import datetime, timezone


# Configuration
DEFAULT_ARCHIVE_PATH = Path(r"D:\Sentiment-Data\CryptoBot\data\archive")
OUTPUT_FILE = Path("public/data/archive_stats.json")


def find_archive_folders(archive_path: Path) -> list:
    """
    Find all YYYYMMDD archive folders.
    
    Args:
        archive_path: Path to archive root directory
    
    Returns:
        List of folder paths sorted by date (oldest first)
    """
    folders = []
    
    if not archive_path.exists():
        print(f"[ERROR] Archive path not found: {archive_path}", file=sys.stderr)
        return folders
    
    for item in archive_path.iterdir():
        if item.is_dir() and item.name.isdigit() and len(item.name) == 8:
            folders.append(item)
    
    folders.sort(key=lambda p: p.name)
    return folders


def count_entries_in_file(filepath: Path) -> int:
    """
    Count entries in a .jsonl or .jsonl.gz file.
    
    Args:
        filepath: Path to JSONL file
    
    Returns:
        Number of entries
    """
    count = 0
    
    try:
        if filepath.suffix == '.gz':
            with gzip.open(filepath, 'rt', encoding='utf-8') as f:
                for _ in f:
                    count += 1
        else:
            with open(filepath, 'r', encoding='utf-8') as f:
                for _ in f:
                    count += 1
    except Exception as e:
        print(f"[WARN] Failed to read {filepath}: {e}", file=sys.stderr)
    
    return count


def get_last_entry_timestamp(filepath: Path) -> str | None:
    """
    Get timestamp from last entry in a JSONL file.
    
    Args:
        filepath: Path to JSONL file
    
    Returns:
        ISO timestamp string or None
    """
    try:
        if filepath.suffix == '.gz':
            with gzip.open(filepath, 'rt', encoding='utf-8') as f:
                lines = f.readlines()
        else:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        
        if lines:
            last_entry = json.loads(lines[-1])
            # Try common timestamp fields
            for field in ['meta.added_ts', 'added_ts', 'timestamp', 'ts']:
                parts = field.split('.')
                value = last_entry
                for part in parts:
                    value = value.get(part) if isinstance(value, dict) else None
                    if value is None:
                        break
                if value:
                    return value
    except Exception as e:
        print(f"[WARN] Failed to extract timestamp from {filepath}: {e}", file=sys.stderr)
    
    return None


def build_archive_stats(archive_path: Path) -> dict:
    """
    Build archive statistics from full archive.
    
    Args:
        archive_path: Path to archive root directory
    
    Returns:
        Dictionary with archive statistics
    """
    folders = find_archive_folders(archive_path)
    
    if not folders:
        print("[ERROR] No archive folders found", file=sys.stderr)
        sys.exit(1)
    
    print(f"[INFO] Found {len(folders)} archive folders")
    print(f"[INFO] Date range: {folders[0].name} to {folders[-1].name}")
    
    total_entries = 0
    last_entry_ts = None
    
    # Count entries in all folders
    for folder in folders:
        folder_entries = 0
        
        # Find all .jsonl and .jsonl.gz files
        jsonl_files = list(folder.glob("*.jsonl")) + list(folder.glob("*.jsonl.gz"))
        jsonl_files.sort(key=lambda p: p.stat().st_mtime)
        
        for filepath in jsonl_files:
            count = count_entries_in_file(filepath)
            folder_entries += count
        
        # Get last entry timestamp from newest file in last folder
        if folder == folders[-1] and jsonl_files:
            last_entry_ts = get_last_entry_timestamp(jsonl_files[-1])
        
        total_entries += folder_entries
        print(f"[INFO] {folder.name}: {folder_entries} entries")
    
    # Parse date strings
    first_day = folders[0].name  # YYYYMMDD
    last_day = folders[-1].name  # YYYYMMDD
    
    # Convert to YYYY-MM-DD format
    first_day_formatted = f"{first_day[:4]}-{first_day[4:6]}-{first_day[6:8]}"
    last_day_formatted = f"{last_day[:4]}-{last_day[4:6]}-{last_day[6:8]}"
    
    return {
        "total_entries_all_time": total_entries,
        "total_days": len(folders),
        "first_day_utc": first_day_formatted,
        "last_day_utc": last_day_formatted,
        "last_entry_ts_utc": last_entry_ts,
        "source_path": str(archive_path),
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    }


def write_stats(stats: dict, output_path: Path):
    """
    Write archive stats to JSON file.
    
    Args:
        stats: Statistics dictionary
        output_path: Output file path
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='ascii') as f:
        json.dump(stats, f, ensure_ascii=True, indent=2)
    
    print(f"[INFO] Archive stats written to {output_path}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Build archive statistics")
    parser.add_argument(
        '--archive-path',
        type=Path,
        default=DEFAULT_ARCHIVE_PATH,
        help=f"Path to archive root (default: {DEFAULT_ARCHIVE_PATH})"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Archive Statistics Builder")
    print("=" * 60)
    print()
    
    # Build stats
    stats = build_archive_stats(args.archive_path)
    
    # Write output
    write_stats(stats, OUTPUT_FILE)
    
    print()
    print("[SUCCESS] Archive statistics generated")
    print(f"  Total entries: {stats['total_entries_all_time']:,}")
    print(f"  Total days: {stats['total_days']}")
    print(f"  Date range: {stats['first_day_utc']} to {stats['last_day_utc']}")
    if stats['last_entry_ts_utc']:
        print(f"  Last entry: {stats['last_entry_ts_utc']}")


if __name__ == "__main__":
    main()
