#!/usr/bin/env python3
"""
Field Coverage Inspection Tool (Phase 1A)

PURPOSE:
    This script exists because previous attempts ASSUMED field names and paths
    without verifying them against real data. This led to wasted time, incorrect
    artifacts, and circular debugging.

    This inspection tool:
    - Reads REAL archive entries from the sample file
    - Dynamically DISCOVERS actual field paths (no assumptions)
    - Counts presence/absence for each discovered field
    - Produces a canonical coverage map for future artifact builders

CRITICAL RULES:
    - NO assumptions about field names
    - NO guessing at nesting structures
    - NO hardcoded paths without verification
    - Reports ACTUAL structure as found in data

    If sentiment fields are not found, the inspection logic must be wrong,
    not the data. Re-check traversal logic before concluding data is missing.

INPUTS:
    - data/samples/cryptobot_latest_head200.jsonl (real v7 entries)

OUTPUTS:
    - data/field_coverage_report.json (machine-readable)
    - data/field_coverage_report.md (human-readable, temporary)
"""

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Set


def discover_paths(obj: Any, prefix: str = "") -> Set[str]:
    """
    Recursively discover all field paths in a JSON object.
    
    Returns a set of fully-qualified paths (e.g., "meta.version", "scores.final")
    """
    paths = set()
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            current_path = f"{prefix}.{key}" if prefix else key
            paths.add(current_path)
            
            # Recurse into nested structures
            if isinstance(value, dict):
                paths.update(discover_paths(value, current_path))
            elif isinstance(value, list) and len(value) > 0:
                # Inspect first element of lists
                paths.update(discover_paths(value[0], current_path))
    
    return paths


def get_field_value(obj: Dict, path: str) -> tuple[bool, Any]:
    """
    Navigate to a field using dot-separated path.
    
    Returns:
        (exists: bool, value: Any)
    """
    parts = path.split(".")
    current = obj
    
    for part in parts:
        if not isinstance(current, dict):
            return False, None
        if part not in current:
            return False, None
        current = current[part]
    
    return True, current


def categorize_path(path: str) -> str:
    """
    Categorize a field path into logical groups.
    """
    if path.startswith("spot_prices"):
        return "spot_prices"
    elif path.startswith("futures_raw"):
        return "futures_raw"
    elif path.startswith("spot_raw"):
        return "spot_raw"
    elif path.startswith("meta"):
        return "meta"
    elif path.startswith("derived"):
        return "derived"
    elif path.startswith("norm"):
        return "norm"
    elif path.startswith("scores"):
        return "scores"
    elif path.startswith("flags"):
        return "flags"
    elif path.startswith("diag"):
        return "diag"
    elif path.startswith("labels"):
        return "labels"
    elif path.startswith("twitter_sentiment_windows.last_cycle"):
        return "sentiment_last_cycle"
    elif path.startswith("twitter_sentiment_windows.last_2_cycles"):
        return "sentiment_last_2_cycles"
    elif path.startswith("twitter_sentiment_windows"):
        return "sentiment_windows"
    elif path.startswith("twitter_sentiment_meta"):
        return "sentiment_meta"
    else:
        return "other"


def main():
    # Locate sample file
    instrumetriq_root = Path(__file__).resolve().parent.parent
    sample_file = instrumetriq_root / "data" / "samples" / "cryptobot_latest_head200.jsonl"
    
    if not sample_file.exists():
        print(f"ERROR: Sample file not found: {sample_file}", file=sys.stderr)
        print("Run: npm run sync-sample", file=sys.stderr)
        return 1
    
    print("=" * 70)
    print("Field Coverage Inspection (Phase 1A)")
    print("=" * 70)
    print(f"Source: {sample_file.name}")
    print()
    
    # Load all entries
    entries = []
    with open(sample_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                entry = json.loads(line)
                entries.append(entry)
            except json.JSONDecodeError as e:
                print(f"WARNING: Line {line_num} invalid JSON: {e}", file=sys.stderr)
    
    print(f"[INFO] Loaded {len(entries)} entries")
    
    if len(entries) == 0:
        print("ERROR: No entries loaded", file=sys.stderr)
        return 1
    
    print()
    
    # Discover all unique paths across all entries
    print("[DISCOVERY] Scanning all entries for field paths...")
    all_paths = set()
    for entry in entries:
        all_paths.update(discover_paths(entry))
    
    print(f"[DISCOVERY] Found {len(all_paths)} unique field paths")
    print()
    
    # Count presence for each path
    print("[COUNTING] Checking presence across all entries...")
    path_counts = {}
    for path in sorted(all_paths):
        present = 0
        for entry in entries:
            exists, _ = get_field_value(entry, path)
            if exists:
                present += 1
        
        path_counts[path] = {
            "present": present,
            "missing": len(entries) - present
        }
    
    print(f"[COUNTING] Counted presence for {len(path_counts)} paths")
    print()
    
    # Organize by category
    categorized = defaultdict(dict)
    for path, counts in sorted(path_counts.items()):
        category = categorize_path(path)
        categorized[category][path] = counts
    
    # Build JSON output
    output_data = {
        "source": sample_file.name,
        "entries_scanned": len(entries),
        "unique_paths_discovered": len(all_paths),
        "field_groups": dict(categorized)
    }
    
    # Write JSON output
    json_output = instrumetriq_root / "data" / "field_coverage_report.json"
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=True)
    
    print(f"[OUTPUT] Wrote JSON: {json_output}")
    
    # Build Markdown output
    md_lines = [
        "# Field Coverage Report (Phase 1A)",
        "",
        f"**Source:** `{sample_file.name}`",
        f"**Entries Scanned:** {len(entries)}",
        f"**Unique Paths Discovered:** {len(all_paths)}",
        "",
        "---",
        "",
        "## Field Groups",
        ""
    ]
    
    for category in sorted(categorized.keys()):
        paths = categorized[category]
        md_lines.append(f"### {category}")
        md_lines.append("")
        md_lines.append("| Field Path | Present | Missing | Rate |")
        md_lines.append("|------------|---------|---------|------|")
        
        for path in sorted(paths.keys()):
            counts = paths[path]
            rate = counts["present"] / len(entries) * 100
            md_lines.append(
                f"| `{path}` | {counts['present']} | {counts['missing']} | {rate:.1f}% |"
            )
        
        md_lines.append("")
    
    md_lines.extend([
        "---",
        "",
        "## Notes",
        "",
        "- This report was generated by dynamically traversing real archive entries",
        "- NO assumptions were made about field names or structure",
        "- Paths reflect ACTUAL nesting as found in the data",
        "- If sentiment scoring fields appear missing, re-check inspection logic",
        "",
        "## Usage",
        "",
        "This coverage report is the **canonical reference** for all future artifact builders.",
        "",
        "Before writing aggregation code:",
        "1. Check this report for field availability",
        "2. Use exact paths as listed (no renaming)",
        "3. Only use fields with >= 90% present rate",
        "4. Document unavailable fields with exact paths from this report",
        ""
    ])
    
    md_output = instrumetriq_root / "data" / "field_coverage_report.md"
    with open(md_output, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_lines))
    
    print(f"[OUTPUT] Wrote Markdown: {md_output}")
    print()
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Entries scanned:       {len(entries)}")
    print(f"Unique paths found:    {len(all_paths)}")
    print(f"Field groups:          {len(categorized)}")
    print()
    
    # Highlight key groups
    for key_group in ["sentiment_last_cycle", "sentiment_last_2_cycles", "sentiment_meta"]:
        if key_group in categorized:
            count = len(categorized[key_group])
            print(f"{key_group:25} {count} paths")
    
    print()
    print("=" * 70)
    print("DONE")
    print("=" * 70)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
