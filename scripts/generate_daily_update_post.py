#!/usr/bin/env python3
"""
Generate Daily Update Post for Instrumetriq Site

This script creates a new markdown post in `src/content/updates/` based on
the daily data refresh stats. It is intended to be run as part of the
daily_site_refresh.sh pipeline.
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime, timezone

# Paths
SITE_ROOT = Path("/srv/instrumetriq")
STATS_FILE = SITE_ROOT / "public/data/archive_stats.json"
UPDATES_DIR = SITE_ROOT / "src/content/updates"

def main():
    if not STATS_FILE.exists():
        print(f"[ERROR] Stats file not found: {STATS_FILE}")
        sys.exit(1)

    try:
        with open(STATS_FILE, "r") as f:
            stats = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse stats file: {e}")
        sys.exit(1)

    # Use the generation date from stats, or current UTC date
    if "generated_at_utc" in stats:
        gen_dt = datetime.fromisoformat(stats["generated_at_utc"].replace("Z", "+00:00"))
        log_date = gen_dt.strftime("%Y-%m-%d")
    else:
        log_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    filename = f"{log_date}.md"
    file_path = UPDATES_DIR / filename

    if file_path.exists():
        print(f"[INFO] Update post {filename} already exists. Skipping.")
        return

    # Calculate some deltas could be cool later, but for now just raw stats
    total_entries = stats.get("total_entries_all_time", 0)
    total_days = stats.get("total_days", 0)
    last_entry = stats.get("last_entry_ts_utc", "N/A")

    # Content Template
    content = f"""---
title: "Daily Dataset Update - {log_date}"
date: {log_date}
description: "Dataset status snapshot for {log_date}"
author: "System"
---

## Dataset Status Update

**Last Updated:** {stats.get('generated_at_utc', datetime.now(timezone.utc).isoformat())}

**Archive Window:** {stats.get('first_day_utc')} to {stats.get('last_day_utc')}

## Counts

- **Total Entries Archived:** {total_entries:,}
- **Total Days:** {total_days}
- **Last Entry Timestamp:** {last_entry}

***

*This is an automated report generated during the daily site refresh.*
"""

    with open(file_path, "w") as f:
        f.write(content)

    print(f"[SUCCESS] Generated new update post: {file_path}")

if __name__ == "__main__":
    main()
