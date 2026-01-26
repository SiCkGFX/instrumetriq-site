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
REGIMES_FILE = SITE_ROOT / "public/data/activity_regimes.json"
COVERAGE_FILE = SITE_ROOT / "public/data/coverage_table.json"
UPDATES_DIR = SITE_ROOT / "src/content/updates"

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

    stats = load_json(STATS_FILE)
    regimes = load_json(REGIMES_FILE)
    coverage = load_json(COVERAGE_FILE)

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

    # 1. Archive Stats
    total_entries = stats.get("total_entries_all_time", 0)
    total_days = stats.get("total_days", 0)
    last_entry = stats.get("last_entry_ts_utc", "N/A")
    archive_start = stats.get("first_day_utc", "N/A")
    archive_end = stats.get("last_day_utc", "N/A")

    # 2. Activity Regimes (Get Top 3 by share)
    regime_rows = []
    if "regimes" in regimes:
        sorted_regimes = sorted(regimes["regimes"], key=lambda x: x.get("share_pct", 0), reverse=True)
        for r in sorted_regimes[:4]: # Top 4
            name = r.get("bin", "Unknown").replace("_", " ").title()
            count = r.get("n_entries", 0)
            share = r.get("share_pct", 0.0)
            regime_rows.append(f"| {name} | {count} | {share:.1f}% |")
    
    regime_table = "\n".join(regime_rows) if regime_rows else "| No data available | - | - |"

    # 3. Coverage Highlights
    cov_map = {row["group"]: row.get("present_pct", 0) for row in coverage.get("rows", [])}
    sentiment_cov = cov_map.get("sentiment_last_cycle", 0)
    market_cov = cov_map.get("market_microstructure", 0)
    liquidity_cov = cov_map.get("liquidity", 0)


    # Content Template
    content = f"""---
title: "Daily Dataset Update - {log_date}"
date: {log_date}
description: "Dataset status snapshot for {log_date}"
author: "System"
---

## 📊 Status Snapshot

**Total Archived Entries:** `{total_entries:,}`  
**Archive Window:** `{archive_start}` to `{archive_end}` ({total_days} days)  
**Last Data Entry:** `{last_entry}`

## 📈 Activity Regimes
*Distribution of tweet volume per monitoring window in the latest snapshot:*

| Regime | Count | Share |
|---|---|---|
{regime_table}

## 🛡️ Coverage Metrics
*Field availability percentages in the latest validation batch:*

- **Market Structure:** {market_cov}%
- **Liquidity:** {liquidity_cov}%
- **Sentiment (Last Cycle):** {sentiment_cov}%

***

*This is an automated report generated during the daily site refresh.*
"""

    with open(file_path, "w") as f:
        f.write(content)

    print(f"[SUCCESS] Generated new update post: {file_path}")

if __name__ == "__main__":
    main()
