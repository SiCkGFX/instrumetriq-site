#!/usr/bin/env python3
"""
sync_cryptobot_sample.py

Syncs the newest *.jsonl.gz from CryptoBot archive into instrumetriq for local inspection.

Usage:
    python scripts/tools/sync_cryptobot_sample.py --cryptobot-root "D:\\Sentiment-Data\\CryptoBot"
    python scripts/tools/sync_cryptobot_sample.py  # Auto-detects ../CryptoBot

Outputs:
    - data/samples/cryptobot_latest.jsonl.gz (newest archive file)
    - data/samples/cryptobot_YYYYMMDD_HHMM.jsonl.gz (timestamped copy)
    - data/samples/cryptobot_latest_head200.jsonl (first 200 lines decompressed)
"""

import argparse
import gzip
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path


def find_newest_archive_file(archive_root: Path) -> tuple[Path, str]:
    """Find the newest *.jsonl.gz file in the archive directory.
    
    Returns:
        (path_to_file, relative_path_from_archive_root)
    """
    if not archive_root.exists():
        raise FileNotFoundError(f"Archive root does not exist: {archive_root}")
    
    newest_file = None
    newest_mtime = 0
    
    for filepath in archive_root.rglob("*.jsonl.gz"):
        mtime = filepath.stat().st_mtime
        if mtime > newest_mtime:
            newest_mtime = mtime
            newest_file = filepath
    
    if newest_file is None:
        raise FileNotFoundError(f"No *.jsonl.gz files found in {archive_root}")
    
    relative_path = newest_file.relative_to(archive_root)
    return newest_file, str(relative_path)


def extract_head_lines(gzip_path: Path, output_path: Path, num_lines: int = 200) -> int:
    """Extract the first N lines from a gzipped JSONL file.
    
    Returns:
        Number of lines written
    """
    lines_written = 0
    with gzip.open(gzip_path, 'rt', encoding='utf-8') as f_in:
        with open(output_path, 'w', encoding='utf-8') as f_out:
            for i, line in enumerate(f_in):
                if i >= num_lines:
                    break
                f_out.write(line)
                lines_written += 1
    return lines_written


def extract_head_lines_multi(archive_root: Path, output_path: Path, num_lines: int = 200) -> int:
    """Extract the first N lines across multiple archive files if needed.
    
    Starts with the newest file and works backwards until we have N lines.
    
    Returns:
        Number of lines written
    """
    # Find all archive files sorted by modification time (newest first)
    all_files = []
    for filepath in archive_root.rglob("*.jsonl.gz"):
        mtime = filepath.stat().st_mtime
        all_files.append((filepath, mtime))
    
    if not all_files:
        raise FileNotFoundError(f"No *.jsonl.gz files found in {archive_root}")
    
    # Sort by modification time, newest first
    all_files.sort(key=lambda x: x[1], reverse=True)
    
    lines_written = 0
    files_used = []
    
    with open(output_path, 'w', encoding='utf-8') as f_out:
        for filepath, _ in all_files:
            if lines_written >= num_lines:
                break
            
            files_used.append(filepath.name)
            remaining = num_lines - lines_written
            
            with gzip.open(filepath, 'rt', encoding='utf-8') as f_in:
                for i, line in enumerate(f_in):
                    if lines_written >= num_lines:
                        break
                    f_out.write(line)
                    lines_written += 1
            
            print(f"  [READ] {filepath.name} → {lines_written}/{num_lines} lines")
    
    print(f"  [INFO] Used {len(files_used)} archive file(s) to extract {lines_written} lines")
    return lines_written


def main():
    parser = argparse.ArgumentParser(description="Sync newest CryptoBot archive file to instrumetriq")
    parser.add_argument(
        '--cryptobot-root',
        type=str,
        help='Path to CryptoBot repo root (default: auto-detect ../CryptoBot)'
    )
    args = parser.parse_args()
    
    # Determine CryptoBot root
    if args.cryptobot_root:
        cryptobot_root = Path(args.cryptobot_root).resolve()
    else:
        # Auto-detect: assume instrumetriq and cryptobot are siblings
        instrumetriq_root = Path(__file__).resolve().parent.parent.parent
        cryptobot_root = instrumetriq_root.parent / "cryptobot"
    
    archive_root = cryptobot_root / "data" / "archive"
    
    print("=" * 70)
    print("CryptoBot Sample Sync")
    print("=" * 70)
    print(f"CryptoBot root:  {cryptobot_root}")
    print(f"Archive folder:  {archive_root}")
    print()
    
    # Find newest archive file
    try:
        newest_file, relative_path = find_newest_archive_file(archive_root)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    
    print(f"[INFO] Found newest file: {relative_path}")
    print(f"       Full path: {newest_file}")
    print()
    
    # Prepare output paths
    instrumetriq_root = Path(__file__).resolve().parent.parent.parent
    samples_dir = instrumetriq_root / "data" / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    
    output_latest = samples_dir / "cryptobot_latest.jsonl.gz"
    output_timestamped = samples_dir / f"cryptobot_{timestamp}.jsonl.gz"
    output_head = samples_dir / "cryptobot_latest_head200.jsonl"
    
    # Copy compressed file (deterministic name)
    shutil.copy2(newest_file, output_latest)
    print(f"[COPY] {output_latest}")
    
    # Copy compressed file (timestamped name)
    shutil.copy2(newest_file, output_timestamped)
    print(f"[COPY] {output_timestamped}")
    
    # Extract first 200 lines (across multiple files if needed)
    print(f"[EXTRACT] Extracting first 200 lines to {output_head}...")
    lines_written = extract_head_lines_multi(archive_root, output_head, num_lines=200)
    print(f"[EXTRACT] {output_head} ({lines_written} lines)")
    print()
    
    print("=" * 70)
    print("DONE")
    print("=" * 70)
    print(f"Latest archive: {output_latest}")
    print(f"Timestamped:    {output_timestamped}")
    print(f"Head sample:    {output_head} ({lines_written} lines)")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
