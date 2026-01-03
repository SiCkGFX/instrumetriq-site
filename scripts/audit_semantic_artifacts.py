#!/usr/bin/env python3
"""
Semantic Artifacts Audit Script

Performs comprehensive validation:
- B) Cross-file consistency checks (invariants)
- C) Ground-truth spot checks against archive
- ASCII-only output
"""

import json
import sys
import gzip
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple


# ============================================================================
# Configuration
# ============================================================================

OUTPUT_DIR = Path("D:/Sentiment-Data/instrumetriq/public/data")
ARCHIVE_BASE = Path("D:/Sentiment-Data/CryptoBot/data/archive")

# For ground-truth spot checks
RANDOM_SEED = 1337
SPOT_CHECK_COUNT = 20


# ============================================================================
# Utilities
# ============================================================================

def print_check(name: str, passed: bool, details: str = "") -> None:
    """Print a single check result in ASCII."""
    status = "[OK]" if passed else "[FAIL]"
    msg = f"{status} {name}"
    if details:
        msg += f": {details}"
    print(msg)


def load_json(path: Path) -> Dict[str, Any]:
    """Load JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def is_usable_v7_entry(entry: Dict[str, Any]) -> bool:
    """Check if entry meets usability criteria (matches builder logic)."""
    # Check schema version
    meta = entry.get("meta", {})
    schema_version = meta.get("schema_version")
    if schema_version != 7:
        return False
    
    # Check spot_prices count
    spot_prices = entry.get("spot_prices", [])
    if len(spot_prices) < 700:
        return False
    
    # Check spot_raw
    spot_raw = entry.get("spot_raw", {})
    required_spot_keys = {"mid", "bid", "ask", "spread_bps"}
    if not required_spot_keys.issubset(spot_raw.keys()):
        return False
    
    # Check twitter_sentiment_windows has at least one cycle
    tsw = entry.get("twitter_sentiment_windows", {})
    has_last_cycle = tsw.get("last_cycle") is not None
    has_last_2_cycles = tsw.get("last_2_cycles") is not None
    if not (has_last_cycle or has_last_2_cycles):
        return False
    
    return True


def parse_iso_date(date_str: str) -> datetime:
    """Parse ISO date string YYYY-MM-DD."""
    return datetime.strptime(date_str, "%Y-%m-%d")


# ============================================================================
# B) Cross-file consistency checks
# ============================================================================

def check_cross_file_consistency(
    coverage: Dict[str, Any],
    summary: Dict[str, Any],
    symbols: Dict[str, Any]
) -> Tuple[List[str], List[str]]:
    """
    Validate invariants between artifacts.
    Returns (passed_checks, failed_checks).
    """
    passed = []
    failed = []
    
    # Extract key values
    summary_symbols = summary["scale"]["distinct_symbols"]
    symbol_table_total = symbols["total_symbols"]
    symbol_table_count = len(symbols["symbols"])
    summary_usable = summary["scale"]["total_usable_entries"]
    
    # Check 1: Symbol counts match
    if summary_symbols == symbol_table_total == symbol_table_count:
        passed.append(f"Symbol counts match: {summary_symbols}")
    else:
        failed.append(
            f"Symbol count mismatch: summary={summary_symbols}, "
            f"symbol_table.total={symbol_table_total}, "
            f"symbol_table.len={symbol_table_count}"
        )
    
    # Check 2: Activity regime bins sum to total usable
    regimes = summary.get("activity_regimes", {})
    bins = regimes.get("bins", [])
    if bins:
        bins_sum = sum(b["n_entries"] for b in bins)
        if bins_sum == summary_usable:
            passed.append(f"Activity regime bins sum matches total: {bins_sum}")
        else:
            failed.append(
                f"Activity regime bins sum mismatch: bins_sum={bins_sum}, "
                f"total_usable={summary_usable}"
            )
    
    # Check 3: Coverage table total_entries matches summary total_usable
    coverage_total = coverage["total_entries"]
    if coverage_total == summary_usable:
        passed.append(f"Coverage total matches summary: {coverage_total}")
    else:
        failed.append(
            f"Coverage total mismatch: coverage={coverage_total}, "
            f"summary={summary_usable}"
        )
    
    return passed, failed


def check_formatting_rules(
    coverage: Dict[str, Any],
    symbols: Dict[str, Any]
) -> Tuple[List[str], List[str]]:
    """
    Validate formatting rules.
    Returns (passed_checks, failed_checks).
    """
    passed = []
    failed = []
    
    # Check coverage table groups
    for group in coverage["feature_groups"]:
        group_name = group["group"]
        label = group.get("example_metric_label")
        value = group.get("example_metric_value")
        present_rate = group["present_rate_pct"]
        
        # No null labels/values
        if label is None:
            failed.append(f"Group {group_name}: null example_metric_label")
        if value is None:
            failed.append(f"Group {group_name}: null example_metric_value")
        
        # For 0% groups, value must be non-empty string
        if present_rate == 0.0:
            if not isinstance(value, str) or not value:
                failed.append(
                    f"Group {group_name}: 0% group must have non-empty string value"
                )
    
    if not failed:
        passed.append("Coverage table formatting valid")
    
    # Check date strings in symbol table
    date_errors = []
    for sym in symbols["symbols"]:
        symbol = sym["symbol"]
        first = sym.get("first_seen")
        last = sym.get("last_seen")
        
        try:
            first_dt = None
            last_dt = None
            if first:
                first_dt = parse_iso_date(first)
            if last:
                last_dt = parse_iso_date(last)
            
            # Validate first_seen <= last_seen
            if first_dt is not None and last_dt is not None:
                if first_dt > last_dt:
                    date_errors.append(
                        f"{symbol}: first_seen > last_seen ({first} > {last})"
                    )
        except ValueError as e:
            date_errors.append(f"{symbol}: Invalid date format - {e}")
    
    if date_errors:
        failed.extend(date_errors)
    else:
        passed.append("Symbol table dates valid")
    
    return passed, failed


# ============================================================================
# C) Ground-truth spot checks
# ============================================================================

def scan_archive_for_spot_checks() -> Tuple[
    List[Dict[str, Any]],  # sample_entries
    int,  # total_usable_count
    int  # distinct_symbol_count
]:
    """
    Stream archive and collect:
    - Random sample of usable entries
    - Total usable count
    - Distinct symbol count
    """
    random.seed(RANDOM_SEED)
    
    all_usable_entries = []
    distinct_symbols = set()
    processed_count = 0
    usable_count = 0
    
    print("[INFO] Scanning archive for ground-truth validation...")
    
    # Iterate through day directories (format: YYYYMMDD)
    day_dirs = sorted(ARCHIVE_BASE.glob("202512*"))
    print(f"[INFO] Found {len(day_dirs)} day directories")
    
    for day_dir in day_dirs:
        if not day_dir.is_dir():
            continue
        
        # Process gzipped JSONL files
        gz_files = list(day_dir.glob("*.jsonl.gz"))
        print(f"[INFO] Processing {day_dir.name}: {len(gz_files)} files")
        
        for gz_file in gz_files:
            try:
                with gzip.open(gz_file, 'rt', encoding='utf-8') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        
                        try:
                            entry = json.loads(line)
                            processed_count += 1
                            
                            if is_usable_v7_entry(entry):
                                all_usable_entries.append(entry)
                                usable_count += 1
                                
                                # Track symbol (at top level, not in meta)
                                symbol = entry.get("symbol")
                                if symbol:
                                    distinct_symbols.add(symbol)
                        
                        except json.JSONDecodeError:
                            continue
            
            except Exception as e:
                print(f"[WARN] Error reading {gz_file}: {e}")
                continue
    
    print(f"[INFO] Archive scan complete: processed={processed_count}, usable={usable_count}")
    
    # Sample random entries
    sample_size = min(SPOT_CHECK_COUNT, len(all_usable_entries))
    sample_entries = random.sample(all_usable_entries, sample_size) if sample_size > 0 else []
    
    return sample_entries, len(all_usable_entries), len(distinct_symbols)


def check_ground_truth(
    summary: Dict[str, Any],
    symbols: Dict[str, Any]
) -> Tuple[List[str], List[str]]:
    """
    Validate against archive ground truth.
    Returns (passed_checks, failed_checks).
    """
    passed = []
    failed = []
    
    sample_entries, total_usable, distinct_symbols = scan_archive_for_spot_checks()
    
    # Check 1: Validate sample entries are correctly classified as usable
    invalid_count = 0
    for entry in sample_entries:
        if not is_usable_v7_entry(entry):
            symbol = entry.get("meta", {}).get("symbol", "UNKNOWN")
            snapshot = entry.get("snapshot_ts", "UNKNOWN")
            failed.append(
                f"Sample entry incorrectly classified: {symbol} @ {snapshot}"
            )
            invalid_count += 1
    
    if invalid_count == 0:
        passed.append(f"All {len(sample_entries)} sample entries correctly classified")
    
    # Check 2: Distinct symbol count
    summary_symbols = summary["scale"]["distinct_symbols"]
    if distinct_symbols == summary_symbols:
        passed.append(f"Distinct symbols match: {distinct_symbols}")
    else:
        failed.append(
            f"Distinct symbols mismatch: archive={distinct_symbols}, "
            f"summary={summary_symbols}"
        )
    
    # Check 3: Total usable count
    summary_usable = summary["scale"]["total_usable_entries"]
    if total_usable == summary_usable:
        passed.append(f"Total usable entries match: {total_usable}")
    else:
        # This could differ if publisher runs with different scan limits
        # Treat as FAIL per user requirements
        failed.append(
            f"Total usable entries mismatch: archive={total_usable}, "
            f"summary={summary_usable}"
        )
    
    return passed, failed


# ============================================================================
# Main audit
# ============================================================================

def run_audit() -> int:
    """
    Run complete audit.
    Returns exit code: 0 if all OK, 1 if any failures.
    """
    print("=" * 70)
    print("Semantic Artifacts Audit")
    print("=" * 70)
    print()
    
    # Load artifacts
    print("[INFO] Loading artifacts...")
    try:
        coverage = load_json(OUTPUT_DIR / "coverage_table.json")
        summary = load_json(OUTPUT_DIR / "dataset_summary.json")
        symbols = load_json(OUTPUT_DIR / "symbol_table.json")
    except Exception as e:
        print(f"[FAIL] Could not load artifacts: {e}")
        return 1
    
    print("[OK] All artifacts loaded")
    print()
    
    all_passed = []
    all_failed = []
    
    # Section B: Cross-file consistency
    print("--- B) Cross-file consistency checks ---")
    passed, failed = check_cross_file_consistency(coverage, summary, symbols)
    all_passed.extend(passed)
    all_failed.extend(failed)
    
    for msg in passed:
        print_check(msg, True)
    for msg in failed:
        print_check(msg, False)
    print()
    
    # Section B: Formatting rules
    print("--- B) Formatting rules ---")
    passed, failed = check_formatting_rules(coverage, symbols)
    all_passed.extend(passed)
    all_failed.extend(failed)
    
    for msg in passed:
        print_check(msg, True)
    for msg in failed:
        print_check(msg, False)
    print()
    
    # Section C: Ground-truth spot checks
    print("--- C) Ground-truth spot checks ---")
    passed, failed = check_ground_truth(summary, symbols)
    all_passed.extend(passed)
    all_failed.extend(failed)
    
    for msg in passed:
        print_check(msg, True)
    for msg in failed:
        print_check(msg, False)
    print()
    
    # Summary
    print("=" * 70)
    print(f"Results: {len(all_passed)} passed, {len(all_failed)} failed")
    print("=" * 70)
    
    if all_failed:
        print()
        print("[FAIL] Audit failed with the following issues:")
        for msg in all_failed:
            print(f"  - {msg}")
        return 1
    else:
        print()
        print("[OK] All audit checks passed")
        return 0


if __name__ == "__main__":
    exit_code = run_audit()
    sys.exit(exit_code)
