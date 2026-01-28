#!/usr/bin/env python3
"""
Rebuild History Script
Batches the rebuild of Tier 1, 2, and 3 daily files for a date range.
"""
import sys
import subprocess
from datetime import date, timedelta

START_DATE = date(2025, 12, 12) # Start of data
END_DATE = date(2026, 1, 27)    # Today (ish)

def daterange(start_date, end_date):
    for n in range(int((end_date - start_date).days) + 1):
        yield start_date + timedelta(n)

def run_cmd(cmd):
    print(f">> {cmd}")
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        print(f"[ERROR] Command failed: {cmd}")
        # We don't exit, we try to continue? use --force to overwrite
        # sys.exit(1)

def main():
    print("--- REBUILDING HISTORY ---")
    print(f"Range: {START_DATE} to {END_DATE}")
    print("This will overwrite R2 files with the new naming convention.")
    
    # 1. Rebuild Tier 3 (The Base)
    # We can do this in batches or day by day.
    # The script supports range: --from-date --to-date
    
    start_str = START_DATE.strftime("%Y-%m-%d")
    end_str = END_DATE.strftime("%Y-%m-%d")

    # Tier 3
    run_cmd(f"python3 scripts/build_tier3_daily.py --from-date {start_str} --to-date {end_str} --upload --force")

    # Tier 2 (Depends on T3)
    run_cmd(f"python3 scripts/build_tier2_daily.py --from-date {start_str} --to-date {end_str} --upload --force")

    # Tier 1 (Depends on T3)
    run_cmd(f"python3 scripts/build_tier1_daily.py --from-date {start_str} --to-date {end_str} --upload --force")

    print("\n--- DAILY REBUILD COMPLETE ---")
    print("Now building Monthly bundles...")

    # Monthly Bundles
    # Dec 2025
    run_cmd("python3 scripts/build_monthly_bundle.py --tier tier3 --month 2025-12 --upload --force")
    run_cmd("python3 scripts/build_monthly_bundle.py --tier tier2 --month 2025-12 --upload --force")
    run_cmd("python3 scripts/build_monthly_bundle.py --tier tier1 --month 2025-12 --upload --force")

    # Jan 2026 (Partial)
    run_cmd("python3 scripts/build_monthly_bundle.py --tier tier3 --month 2026-01 --upload --force")
    run_cmd("python3 scripts/build_monthly_bundle.py --tier tier2 --month 2026-01 --upload --force")
    run_cmd("python3 scripts/build_monthly_bundle.py --tier tier1 --month 2026-01 --upload --force")

if __name__ == "__main__":
    main()
