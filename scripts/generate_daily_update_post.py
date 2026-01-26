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
TIER3_DIR = SITE_ROOT / "output/tier3_daily"
UPDATES_DIR = SITE_ROOT / "src/content/updates"
COVERAGE_FILE = SITE_ROOT / "public/data/coverage_table.json"

def load_json(path):
    if not path.exists():
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] Failed to load {path}: {e}")
        return {}

def main():
    if not STATS_FILE.exists():
        print(f"[ERROR] Stats file not found: {STATS_FILE}")
        sys.exit(1)

    # 1. Determine "Yesterday" (Target Date)
    # The cron runs at 03:00 UTC on Day X, but we want to report on Day X-1 (Yesterday)
    # because that is the completed Tier 3 day.
    today_utc = datetime.now(timezone.utc)
    from datetime import timedelta
    yesterday_utc = today_utc - timedelta(days=1)
    target_date = yesterday_utc.strftime("%Y-%m-%d")

    # 2. Check for Tier 3 Manifest
    manifest_path = TIER3_DIR / target_date / "manifest.json"
    if not manifest_path.exists():
        print(f"[WARN] Tier 3 manifest for {target_date} not found at {manifest_path}")
        print("Skipping post generation (waiting for Tier 3 build).")
        return

    manifest = load_json(manifest_path)
    stats = load_json(STATS_FILE)
    coverage = load_json(COVERAGE_FILE) # Keeping coverage as it is general V7 validation

    # 3. Prevent Duplicates
    filename = f"{target_date}.md"
    file_path = UPDATES_DIR / filename
    if file_path.exists():
        print(f"[INFO] Update post {filename} already exists. Skipping.")
        return

    # 4. Extract Metrics
    row_count = manifest.get("row_count", 0)
    hours_found = manifest.get("hours_found", 0)
    hours_expected = manifest.get("hours_expected", 24)
    is_partial = manifest.get("is_partial", False)
    
    # Hourly Stats
    rows_by_hour = manifest.get("rows_by_hour", {})
    if rows_by_hour:
        peak_hour = max(rows_by_hour, key=rows_by_hour.get)
        peak_count = rows_by_hour[peak_hour]
        min_hour = min(rows_by_hour, key=rows_by_hour.get)
        min_count = rows_by_hour[min_hour]
    else:
        peak_hour, peak_count, min_hour, min_count = ("N/A", 0, "N/A", 0)

    # Coverage Highlights (General)
    cov_map = {row["group"]: row.get("present_pct", 0) for row in coverage.get("rows", [])}
    
    # 5. Build Content
    status_emoji = "✅" if (hours_found == hours_expected and not is_partial) else "⚠️"
    status_text = "Complete (24h)" if (hours_found == hours_expected and not is_partial) else f"Partial ({hours_found}/{hours_expected}h)"

    content = f"""---
title: "Daily Dataset Update - {target_date}"
date: {target_date}
description: "Validated Tier 3 archive statistics for {target_date}"
author: "System"
---

## 📊 Daily Production Stats
*Finalized metrics for the full 24-hour UTC cycle.*

| Metric | Value |
| :--- | :--- |
| **Status** | {status_emoji} {status_text} |
| **Total Snapshots** | `{row_count:,}` |
| **Peak Volume** | {peak_count} (at {peak_hour}:00 UTC) |
| **Low Volume** | {min_count} (at {min_hour}:00 UTC) |
| **Schema Version** | v{manifest.get('schema_versions', ['?'])[0]} |

## 🛡️ Validation & Coverage
*Field availability percentages from the daily validation batch:*

- **Market Microstructure:** {cov_map.get("market_microstructure", 0)}%
- **Liquidity Metrics:** {cov_map.get("liquidity", 0)}%
- **Sentiment (Last Cycle):** {cov_map.get("sentiment_last_cycle", 0)}%

## 📂 Archive Metadata
- **Partition:** `tier3/daily/{target_date}`
- **Format:** Parquet (Snappy/Zstd)
- **Manifest SHA:** `{manifest.get('parquet_sha256', 'N/A')[:8]}...`

***
*This report is generated automatically after the daily Tier 3 build verification.*
"""

    with open(file_path, "w") as f:
        f.write(content)

    print(f"[SUCCESS] Generated new update post: {file_path}")

if __name__ == "__main__":
    main()
