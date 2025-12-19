#!/usr/bin/env python3
"""
Publisher script for instrumetriq-site
Runs CryptoBot exporter and generates daily update posts
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Import chart generation modules
sys.path.insert(0, str(Path(__file__).parent))
from lib import daily_stats, charts

# ASCII-only mode for OS-agnostic operation (Windows + Linux safe)
ASCII_MODE = True

# Status symbols (ASCII-safe)
OK_MARK = "[OK]" if ASCII_MODE else "✓"
ERROR_MARK = "[ERROR]" if ASCII_MODE else "❌"
WARN_MARK = "[WARN]" if ASCII_MODE else "⚠️"
RUNNING_MARK = "[>>]" if ASCII_MODE else "🔄"
SUMMARY_MARK = "[SUMMARY]" if ASCII_MODE else "📊"
SUCCESS_MARK = "[SUCCESS]" if ASCII_MODE else "✅"
START_MARK = "[START]" if ASCII_MODE else "🚀"


def get_repo_paths():
    """Determine repository paths relative to instrumetriq-site root."""
    site_root = Path.cwd()
    cryptobot_root = site_root.parent / "CryptoBot"
    cryptobot_exporter = cryptobot_root / "tools" / "export_public_site_assets.py"
    cryptobot_archive = cryptobot_root / "data" / "archive"
    
    return {
        "site_root": site_root,
        "cryptobot_root": cryptobot_root,
        "cryptobot_exporter": cryptobot_exporter,
        "cryptobot_archive": cryptobot_archive,
        "output_dir": site_root / "public" / "data",
        "updates_dir": site_root / "src" / "content" / "updates",
        "charts_dir": site_root / "public" / "charts",
    }


def ensure_directories(paths):
    """Ensure destination folders exist."""
    paths["output_dir"].mkdir(parents=True, exist_ok=True)
    paths["updates_dir"].mkdir(parents=True, exist_ok=True)
    paths["charts_dir"].mkdir(parents=True, exist_ok=True)
    print(f"{OK_MARK} Ensured directories exist:")
    print(f"  - {paths['output_dir']}")
    print(f"  - {paths['updates_dir']}")
    print(f"  - {paths['charts_dir']}")


def run_exporter(paths, scan_limit=None):
    """Run CryptoBot exporter as subprocess."""
    if not paths["cryptobot_exporter"].exists():
        print(f"{ERROR_MARK} CryptoBot exporter not found at {paths['cryptobot_exporter']}")
        sys.exit(1)
    
    if not paths["cryptobot_archive"].exists():
        print(f"{ERROR_MARK} CryptoBot archive not found at {paths['cryptobot_archive']}")
        sys.exit(1)
    
    # Build environment variables
    env = os.environ.copy()
    env["ARCHIVE_BASE_PATH"] = str(paths["cryptobot_archive"])
    env["OUTPUT_DIR"] = str(paths["output_dir"])
    env["PYTHONIOENCODING"] = "utf-8"  # Fix Unicode output issues
    
    if scan_limit:
        env["DATASET_SCAN_LIMIT"] = str(scan_limit)
        print(f"  Using scan limit: {scan_limit}")
    
    print(f"\n{RUNNING_MARK} Running CryptoBot exporter...")
    print(f"  Archive: {paths['cryptobot_archive']}")
    print(f"  Output: {paths['output_dir']}")
    
    # Determine python executable
    python_cmd = sys.executable if sys.executable else "python"
    
    try:
        result = subprocess.run(
            [python_cmd, str(paths["cryptobot_exporter"])],
            env=env,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=True
        )
        print(result.stdout)
        if result.stderr:
            print("Warnings:", result.stderr, file=sys.stderr)
        print(f"{OK_MARK} Exporter completed successfully")
    except subprocess.CalledProcessError as e:
        print(f"{ERROR_MARK} Exporter failed with code {e.returncode}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        sys.exit(1)


def verify_outputs(paths):
    """Verify outputs exist and are valid JSON."""
    status_json = paths["output_dir"] / "status.json"
    history_jsonl = paths["output_dir"] / "status_history.jsonl"
    
    if not status_json.exists():
        print(f"{ERROR_MARK} status.json not found at {status_json}")
        sys.exit(1)
    
    try:
        with open(status_json, 'r') as f:
            data = json.load(f)
        print(f"{OK_MARK} Verified status.json ({len(json.dumps(data))} bytes)")
    except json.JSONDecodeError as e:
        print(f"{ERROR_MARK} status.json is not valid JSON: {e}")
        sys.exit(1)
    
    if not history_jsonl.exists():
        print(f"{WARN_MARK} Warning: status_history.jsonl not found (optional)")
    else:
        print(f"{OK_MARK} Verified status_history.jsonl exists")
    
    return data


def load_previous_history(paths):
    """Load previous history record for delta computation."""
    history_jsonl = paths["output_dir"] / "status_history.jsonl"
    
    if not history_jsonl.exists():
        return None
    
    try:
        with open(history_jsonl, 'r') as f:
            lines = f.readlines()
            if len(lines) >= 2:
                # Second-to-last line is previous
                prev = json.loads(lines[-2])
                return prev
    except (json.JSONDecodeError, IndexError):
        pass
    
    return None


def generate_daily_update(paths, status_data, date_override=None, no_history=False):
    """Generate daily update markdown file."""
    update_date = datetime.fromisoformat(date_override) if date_override else datetime.now(timezone.utc)
    date_str = update_date.strftime("%Y-%m-%d")
    update_file = paths["updates_dir"] / f"{date_str}.md"
    
    # Extract data
    last_updated = status_data.get("last_updated_utc", "N/A")
    archive_window = status_data.get("archive_window", {})
    first_day = archive_window.get("first_day", "N/A")
    last_day = archive_window.get("last_day", "N/A")
    
    counts = status_data.get("counts", {})
    usable_entries = counts.get("usable_entries", 0)
    v7_entries_seen = counts.get("v7_entries_seen", 0)
    total_scanned = counts.get("total_entries_scanned", 0)
    
    usable_v7_pct = (usable_entries / v7_entries_seen * 100) if v7_entries_seen > 0 else 0.0
    
    # Compute deltas if possible
    delta_text = ""
    if not no_history:
        prev = load_previous_history(paths)
        if prev:
            prev_counts = prev.get("counts", {})
            prev_usable = prev_counts.get("usable_entries", 0)
            prev_v7 = prev_counts.get("v7_entries_seen", 0)
            
            delta_usable = usable_entries - prev_usable
            delta_v7 = v7_entries_seen - prev_v7
            
            if delta_usable != 0 or delta_v7 != 0:
                delta_text = f"\n**Change from previous:** +{delta_usable} usable entries, +{delta_v7} v7 entries seen\n"
    
    # Check if file exists
    if update_file.exists():
        print(f"{WARN_MARK} Update file already exists: {update_file}")
        print(f"   Appending refresh timestamp...")
        with open(update_file, 'a', encoding='utf-8') as f:
            f.write(f"\n_Refreshed at {datetime.now(timezone.utc).isoformat()}_\n")
        return update_file
    
    # Generate content
    content = f"""---
title: "Daily Dataset Update - {date_str}"
date: {update_date.strftime("%Y-%m-%d")}
description: "Dataset status snapshot for {date_str}"
---

## Dataset Status Update

**Last Updated:** {last_updated}

**Archive Window:** {first_day} to {last_day}

## Counts

- **Usable Entries:** {usable_entries:,}
- **v7 Entries Seen:** {v7_entries_seen:,}
- **Total Entries Scanned:** {total_scanned:,}
- **Usable v7 Percentage:** {usable_v7_pct:.1f}%
{delta_text}
## Notes

Status generated locally from CryptoBot archives; no live API.

All records represent validated v7 snapshots that pass dataset health gates (700+ spot samples).
"""
    
    with open(update_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"{OK_MARK} Generated daily update: {update_file}")
    return update_file


def print_summary(paths, status_data, update_file):
    """Print final summary to console."""
    counts = status_data.get("counts", {})
    usable_entries = counts.get("usable_entries", 0)
    v7_entries_seen = counts.get("v7_entries_seen", 0)
    usable_v7_pct = (usable_entries / v7_entries_seen * 100) if v7_entries_seen > 0 else 0.0
    
    archive_window = status_data.get("archive_window", {})
    window_str = f"{archive_window.get('first_day', 'N/A')} to {archive_window.get('last_day', 'N/A')}"
    
    last_updated = status_data.get("last_updated_utc", "N/A")
    
    print("\n" + "=" * 60)
    print(f"{SUMMARY_MARK} PUBLISH SUMMARY")
    print("=" * 60)
    print(f"Status JSON:      {paths['output_dir'] / 'status.json'}")
    print(f"Update Post:      {update_file}")
    print(f"")
    print(f"Usable Entries:   {usable_entries:,}")
    print(f"v7 Entries Seen:  {v7_entries_seen:,}")
    print(f"Usable v7 %:      {usable_v7_pct:.1f}%")
    print(f"Archive Window:   {window_str}")
    print(f"Last Updated:     {last_updated}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Publish daily dataset status and update posts for instrumetriq-site"
    )
    parser.add_argument(
        "--scan-limit",
        type=int,
        help="Limit number of archive files to scan (for testing)"
    )
    parser.add_argument(
        "--date",
        help="Override date for update post (YYYY-MM-DD format)"
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Skip reading history for delta computation"
    )
    parser.add_argument(
        "--no-charts",
        action="store_true",
        help="Skip chart generation"
    )
    
    args = parser.parse_args()
    
    print(f"{START_MARK} Instrumetriq Site Publisher")
    print("=" * 60)
    
    # Step 1: Determine paths
    paths = get_repo_paths()
    print(f"Site root:        {paths['site_root']}")
    print(f"CryptoBot root:   {paths['cryptobot_root']}")
    
    # Step 2: Ensure directories
    ensure_directories(paths)
    
    # Step 3: Run exporter
    run_exporter(paths, scan_limit=args.scan_limit)
    
    # Step 4: Verify outputs
    status_data = verify_outputs(paths)
    
    # Step 4.5: Generate charts (unless --no-charts or PUBLISH_NO_CHARTS env var)
    skip_charts = args.no_charts or os.environ.get("PUBLISH_NO_CHARTS") == "1"
    if not skip_charts:
        print(f"\n{RUNNING_MARK} Computing daily statistics...")
        daily_data = daily_stats.compute_daily_stats(paths["cryptobot_archive"])
        
        if daily_data:
            # Add cumulative usable count
            daily_data_with_cumulative = daily_stats.compute_cumulative_usable(daily_data)
            
            # Generate charts
            charts.generate_all_charts(daily_data_with_cumulative, paths["charts_dir"])
        else:
            print(f"{WARN_MARK} No daily data found, skipping chart generation")
    else:
        print(f"\n{WARN_MARK} Chart generation skipped")
    
    # Step 5: Generate daily update
    update_file = generate_daily_update(
        paths, 
        status_data, 
        date_override=args.date,
        no_history=args.no_history
    )
    
    # Step 6: Print summary
    print_summary(paths, status_data, update_file)
    
    print(f"\n{SUCCESS_MARK} Publish completed successfully!")
    print("Next steps:")
    print("  1. Review changes: git status")
    print("  2. Build site: npm run build")
    print("  3. Commit: git add . && git commit -m 'Daily dataset update'")
    print("  4. Push: git push")


if __name__ == "__main__":
    main()
