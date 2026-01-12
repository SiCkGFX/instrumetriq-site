#!/usr/bin/env python3
"""
Build Phase 2A Descriptive Behavior Artifacts

Creates 3 website-safe JSON artifacts showing dataset behavior:
- activity_regimes.json: Tweet volume bins with descriptive stats
- sampling_density.json: Sampling resolution quality metrics
- session_lifecycle.json: Monitoring window lifecycle patterns

Rules:
- Use ONLY paths from field_coverage_report.json (Phase 1A SSOT)
- NO predictive claims or correlations
- Deterministic output (except timestamp)
- ASCII-only JSON
"""

import gzip
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def get_nested_value(obj: Dict[str, Any], path: str) -> Any:
    """Safely navigate nested dict using dot-separated path."""
    parts = path.split('.')
    current = obj
    for part in parts:
        if not isinstance(current, dict):
            return None
        if part not in current:
            return None
        current = current[part]
    return current


def find_path_in_ssot(coverage: Dict[str, Any], *candidates: str) -> Optional[str]:
    """Find first matching path from candidates that exists in SSOT."""
    all_paths = set()
    for group, fields in coverage.get('field_groups', {}).items():
        all_paths.update(fields.keys())
    
    for path in candidates:
        if path in all_paths:
            return path
    return None


def extract_numeric_values(entries: List[Dict], path: str) -> List[float]:
    """Extract all valid numeric values from entries for a given path."""
    values = []
    for entry in entries:
        val = get_nested_value(entry, path)
        if val is not None and isinstance(val, (int, float)):
            if not math.isnan(val) and not math.isinf(val):
                values.append(val)
    return values


def compute_percentiles(values: List[float]) -> Dict[str, Optional[float]]:
    """Compute p10, median, p90, min, max."""
    if not values:
        return {'median': None, 'p10': None, 'p90': None, 'min': None, 'max': None}
    
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    
    return {
        'median': statistics.median(sorted_vals),
        'p10': sorted_vals[int(n * 0.1)],
        'p90': sorted_vals[int(n * 0.9)],
        'min': min(sorted_vals),
        'max': max(sorted_vals)
    }


def build_activity_regimes(entries: List[Dict], coverage: Dict[str, Any]) -> Dict[str, Any]:
    """Build activity_regimes.json artifact."""
    print("\n[BUILD] activity_regimes.json")
    
    # Find posts_total path
    posts_path = find_path_in_ssot(
        coverage,
        'twitter_sentiment_windows.last_2_cycles.posts_total',
        'twitter_sentiment_windows.last_cycle.posts_total'
    )
    
    if not posts_path:
        print("  ERROR: No posts_total path found in SSOT")
        return {
            'error': 'No posts_total field available',
            'unavailable_reason': 'Required field not in field_coverage_report.json'
        }
    
    print(f"  Using posts_total: {posts_path}")
    
    # Find liquidity/spread paths
    spread_path = find_path_in_ssot(coverage, 'derived.spread_bps')
    liq_global_path = find_path_in_ssot(coverage, 'derived.liq_global_pct')
    liq_self_path = find_path_in_ssot(coverage, 'derived.liq_self_pct')
    
    # Define bins
    bins = [
        {'name': '0_posts', 'min': 0, 'max': 0},
        {'name': '1-2_posts', 'min': 1, 'max': 2},
        {'name': '3-9_posts', 'min': 3, 'max': 9},
        {'name': '10-24_posts', 'min': 10, 'max': 24},
        {'name': '25-49_posts', 'min': 25, 'max': 49},
        {'name': '50+_posts', 'min': 50, 'max': float('inf')}
    ]
    
    # Initialize bins
    bin_data = defaultdict(lambda: {
        'posts_values': [],
        'spread_values': [],
        'liq_global_values': [],
        'liq_self_values': []
    })
    
    # Bin entries
    for entry in entries:
        posts = get_nested_value(entry, posts_path)
        if posts is None or not isinstance(posts, (int, float)):
            continue
        
        # Find bin
        bin_name = None
        for b in bins:
            if b['min'] <= posts <= b['max']:
                bin_name = b['name']
                break
        
        if not bin_name:
            continue
        
        bin_data[bin_name]['posts_values'].append(posts)
        
        # Collect other metrics
        if spread_path:
            spread = get_nested_value(entry, spread_path)
            if spread is not None and isinstance(spread, (int, float)):
                bin_data[bin_name]['spread_values'].append(spread)
        
        if liq_global_path:
            liq_g = get_nested_value(entry, liq_global_path)
            if liq_g is not None and isinstance(liq_g, (int, float)):
                bin_data[bin_name]['liq_global_values'].append(liq_g)
        
        if liq_self_path:
            liq_s = get_nested_value(entry, liq_self_path)
            if liq_s is not None and isinstance(liq_s, (int, float)):
                bin_data[bin_name]['liq_self_values'].append(liq_s)
    
    # Compute stats per bin
    total_entries = sum(len(bd['posts_values']) for bd in bin_data.values())
    
    regime_rows = []
    for b in bins:
        bd = bin_data[b['name']]
        n = len(bd['posts_values'])
        
        if n == 0:
            continue
        
        regime_rows.append({
            'bin': b['name'],
            'posts_range': f"{b['min']}-{b['max']}" if b['max'] != float('inf') else f"{b['min']}+",
            'n_entries': n,
            'share_pct': round(n / total_entries * 100, 1) if total_entries > 0 else 0,
            'median_spread_bps': round(statistics.median(bd['spread_values']), 1) if bd['spread_values'] else None,
            'median_liq_global_pct': round(statistics.median(bd['liq_global_values']), 1) if bd['liq_global_values'] else None,
            'median_liq_self_pct': round(statistics.median(bd['liq_self_values']), 1) if bd['liq_self_values'] else None
        })
    
    print(f"  Generated {len(regime_rows)} regime bins")
    
    # Build artifact
    artifact = {
        'generated_at_utc': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'entries_scanned': len(entries),
        'total_binned': total_entries,
        'source': {
            'sample_file': 'data/samples/cryptobot_latest_head200.jsonl',
            'ssot_file': 'data/field_coverage_report.json'
        },
        'fields_used': {
            'posts_total': posts_path,
            'spread_bps': spread_path if spread_path else None,
            'liq_global_pct': liq_global_path if liq_global_path else None,
            'liq_self_pct': liq_self_path if liq_self_path else None
        },
        'unavailable_fields': [],
        'regimes': regime_rows
    }
    
    # Note unavailable fields
    if not spread_path:
        artifact['unavailable_fields'].append({
            'field': 'spread_bps',
            'reason': 'Path not found in field_coverage_report.json'
        })
    if not liq_global_path:
        artifact['unavailable_fields'].append({
            'field': 'liq_global_pct',
            'reason': 'Path not found in field_coverage_report.json'
        })
    if not liq_self_path:
        artifact['unavailable_fields'].append({
            'field': 'liq_self_pct',
            'reason': 'Path not found in field_coverage_report.json'
        })
    
    return artifact


def build_sampling_density(entries: List[Dict], coverage: Dict[str, Any]) -> Dict[str, Any]:
    """Build sampling_density.json artifact."""
    print("\n[BUILD] sampling_density.json")
    
    # Find sample_count path
    sample_count_path = find_path_in_ssot(
        coverage,
        'meta.sample_count',
        'meta.samples',
        'sampling.count'
    )
    
    # Find spot_prices path
    spot_prices_path = find_path_in_ssot(coverage, 'spot_prices')
    
    sample_counts = []
    spot_lengths = []
    
    # Collect sample counts
    if sample_count_path:
        print(f"  Using sample_count: {sample_count_path}")
        sample_counts = extract_numeric_values(entries, sample_count_path)
    else:
        print("  WARNING: No sample_count path found")
    
    # Collect spot_prices lengths
    if spot_prices_path:
        print(f"  Using spot_prices: {spot_prices_path}")
        for entry in entries:
            spots = get_nested_value(entry, spot_prices_path)
            if spots is not None and isinstance(spots, list):
                spot_lengths.append(len(spots))
    else:
        print("  WARNING: No spot_prices path found")
    
    # Compute stats
    sample_stats = compute_percentiles(sample_counts) if sample_counts else {
        'median': None, 'p10': None, 'p90': None, 'min': None, 'max': None
    }
    
    spot_stats = compute_percentiles(spot_lengths) if spot_lengths else {
        'median': None, 'p10': None, 'p90': None, 'min': None, 'max': None
    }
    
    # Build histogram for sample_count
    histogram = []
    if sample_counts:
        buckets = [
            {'label': '<600', 'min': 0, 'max': 599},
            {'label': '600-699', 'min': 600, 'max': 699},
            {'label': '700-749', 'min': 700, 'max': 749},
            {'label': '750-799', 'min': 750, 'max': 799},
            {'label': '800-899', 'min': 800, 'max': 899},
            {'label': '900+', 'min': 900, 'max': float('inf')}
        ]
        
        for bucket in buckets:
            count = sum(1 for v in sample_counts if bucket['min'] <= v <= bucket['max'])
            histogram.append({
                'bucket': bucket['label'],
                'count': count,
                'share_pct': round(count / len(sample_counts) * 100, 1) if sample_counts else 0
            })
    
    print(f"  Sample count values: {len(sample_counts)}")
    print(f"  Spot price lengths: {len(spot_lengths)}")
    
    # Build artifact
    artifact = {
        'generated_at_utc': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'entries_scanned': len(entries),
        'source': {
            'sample_file': 'data/samples/cryptobot_latest_head200.jsonl',
            'ssot_file': 'data/field_coverage_report.json'
        },
        'fields_used': {
            'sample_count': sample_count_path if sample_count_path else None,
            'spot_prices': spot_prices_path if spot_prices_path else None
        },
        'sample_count_stats': {
            'n_entries': len(sample_counts),
            'median': round(sample_stats['median'], 1) if sample_stats['median'] else None,
            'p10': round(sample_stats['p10'], 1) if sample_stats['p10'] else None,
            'p90': round(sample_stats['p90'], 1) if sample_stats['p90'] else None,
            'min': round(sample_stats['min'], 1) if sample_stats['min'] else None,
            'max': round(sample_stats['max'], 1) if sample_stats['max'] else None
        },
        'sample_count_histogram': histogram if histogram else None,
        'spot_prices_len_stats': {
            'n_entries': len(spot_lengths),
            'median': int(spot_stats['median']) if spot_stats['median'] else None,
            'p10': int(spot_stats['p10']) if spot_stats['p10'] else None,
            'p90': int(spot_stats['p90']) if spot_stats['p90'] else None,
            'min': int(spot_stats['min']) if spot_stats['min'] else None,
            'max': int(spot_stats['max']) if spot_stats['max'] else None
        },
        'unavailable_fields': []
    }
    
    # Note unavailable fields
    if not sample_count_path:
        artifact['unavailable_fields'].append({
            'field': 'sample_count',
            'reason': 'No meta.sample_count or similar path found in SSOT'
        })
    if not spot_prices_path:
        artifact['unavailable_fields'].append({
            'field': 'spot_prices',
            'reason': 'Path not found in field_coverage_report.json'
        })
    
    return artifact


def build_session_lifecycle(entries: List[Dict], coverage: Dict[str, Any]) -> Dict[str, Any]:
    """Build session_lifecycle.json artifact."""
    print("\n[BUILD] session_lifecycle.json")
    
    # Find timestamp paths
    added_path = find_path_in_ssot(
        coverage,
        'meta.added_ts',
        'meta.created_at',
        'timestamps.added'
    )
    
    expires_path = find_path_in_ssot(
        coverage,
        'meta.expires_ts',
        'meta.expires_at',
        'timestamps.expires'
    )
    
    print(f"  Added timestamp: {added_path if added_path else 'NOT FOUND'}")
    print(f"  Expires timestamp: {expires_path if expires_path else 'NOT FOUND'}")
    
    durations = []
    admission_hours = defaultdict(int)
    
    # Compute durations if both timestamps available
    if added_path and expires_path:
        from dateutil import parser as date_parser
        
        for entry in entries:
            added_str = get_nested_value(entry, added_path)
            expires_str = get_nested_value(entry, expires_path)
            
            if added_str and expires_str:
                try:
                    added_dt = date_parser.isoparse(str(added_str))
                    expires_dt = date_parser.isoparse(str(expires_str))
                    
                    duration_sec = (expires_dt - added_dt).total_seconds()
                    if duration_sec > 0:
                        durations.append(duration_sec)
                    
                    # Track admission hour in UTC
                    # If timestamp has timezone info, convert to UTC; if naive, assume UTC
                    if added_dt.tzinfo is not None:
                        added_utc = added_dt.astimezone(timezone.utc)
                    else:
                        # Naive timestamp: assume UTC
                        added_utc = added_dt.replace(tzinfo=timezone.utc)
                    
                    admission_hours[added_utc.hour] += 1
                except:
                    pass
    
    # Compute stats
    duration_stats = compute_percentiles(durations) if durations else {
        'median': None, 'p10': None, 'p90': None, 'min': None, 'max': None
    }
    
    # Build hour distribution
    hour_dist = [
        {'hour': h, 'count': admission_hours[h]}
        for h in range(24)
    ] if admission_hours else None
    
    print(f"  Durations computed: {len(durations)}")
    print(f"  Admission hours tracked: {sum(admission_hours.values())}")
    
    # Check for highly concentrated admission hours
    total_admissions = sum(admission_hours.values())
    max_hour_count = max(admission_hours.values()) if admission_hours else 0
    has_concentration_bias = (max_hour_count / total_admissions >= 0.90) if total_admissions > 0 else False
    
    if has_concentration_bias:
        print(f"  NOTE: Admission hours are highly concentrated ({max_hour_count}/{total_admissions} = {max_hour_count/total_admissions:.1%})")
    
    # Build artifact
    artifact = {
        'generated_at_utc': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'entries_scanned': len(entries),
        'source': {
            'sample_file': 'data/samples/cryptobot_latest_head200.jsonl',
            'ssot_file': 'data/field_coverage_report.json'
        },
        'definition': {
            'session': 'One admitted watchlist window from added_ts to expires_ts',
            'typical_duration': '~2 hours per monitoring window'
        },
        'fields_used': {
            'added_ts': added_path if added_path else None,
            'expires_ts': expires_path if expires_path else None
        },
        'duration_stats': {
            'n_entries_with_duration': len(durations),
            'duration_sec': {
                'median': int(duration_stats['median']) if duration_stats['median'] else None,
                'p10': int(duration_stats['p10']) if duration_stats['p10'] else None,
                'p90': int(duration_stats['p90']) if duration_stats['p90'] else None,
                'min': int(duration_stats['min']) if duration_stats['min'] else None,
                'max': int(duration_stats['max']) if duration_stats['max'] else None
            }
        },
        'admission_hour_distribution': hour_dist,
        'unavailable_fields': []
    }
    
    # Add concentration note if detected
    if has_concentration_bias:
        artifact['note_sample_bias'] = 'Admission hours are highly concentrated in this sample; this may reflect the sample window rather than global behavior.'
    
    # Note unavailable fields
    if not added_path:
        artifact['unavailable_fields'].append({
            'field': 'added_ts',
            'reason': 'No meta.added_ts or similar timestamp path found in SSOT'
        })
    if not expires_path:
        artifact['unavailable_fields'].append({
            'field': 'expires_ts',
            'reason': 'No meta.expires_ts or similar timestamp path found in SSOT'
        })
    
    return artifact


def main():
    """Build all Phase 2A artifacts."""
    print("=" * 70)
    print("Building Phase 2A Descriptive Behavior Artifacts")
    print("=" * 70)
    
    root = Path(__file__).resolve().parent.parent
    
    # Load SSOT
    print("\n[LOAD] field_coverage_report.json (SSOT)...")
    coverage_file = root / 'data' / 'field_coverage_report.json'
    with open(coverage_file, 'r', encoding='utf-8') as f:
        coverage = json.load(f)
    print(f"  Loaded {coverage['unique_paths_discovered']} paths")
    
    # Load entries from full archive (stream from compressed file)
    print("\n[LOAD] Full archive from CryptoBot...")
    archive_base = Path('/srv/cryptobot/data/archive')
    
    # Find latest archive folder
    date_folders = sorted([d for d in archive_base.iterdir() if d.is_dir() and d.name.isdigit()], reverse=True)
    if not date_folders:
        print("  ERROR: No archive folders found")
        sys.exit(1)
    
    latest_folder = date_folders[0]
    print(f"  Using archive folder: {latest_folder.name}")
    
    # Find all .jsonl.gz files in the latest folder, sorted by modification time (newest first)
    archive_files = sorted(latest_folder.glob('*.jsonl.gz'), key=lambda f: f.stat().st_mtime, reverse=True)
    
    if not archive_files:
        print(f"  ERROR: No .jsonl.gz files found in {latest_folder}")
        sys.exit(1)
    
    print(f"  Found {len(archive_files)} archive file(s)")
    
    # Load all entries from all files
    entries = []
    for archive_file in archive_files:
        print(f"  Reading {archive_file.name}...")
        with gzip.open(archive_file, 'rt', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    
    print(f"  Loaded {len(entries)} total entries from full archive")
    
    # Build artifacts
    output_dir = root / 'public' / 'data'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Activity regimes
    activity = build_activity_regimes(entries, coverage)
    activity['source']['sample_file'] = f'Full archive: {latest_folder.name}'
    activity_file = output_dir / 'activity_regimes.json'
    with open(activity_file, 'w', encoding='ascii') as f:
        json.dump(activity, f, indent=2, ensure_ascii=True)
    print(f"  Wrote: {activity_file}")
    
    # 2. Sampling density
    sampling = build_sampling_density(entries, coverage)
    sampling['source']['sample_file'] = f'Full archive: {latest_folder.name}'
    sampling_file = output_dir / 'sampling_density.json'
    with open(sampling_file, 'w', encoding='ascii') as f:
        json.dump(sampling, f, indent=2, ensure_ascii=True)
    print(f"  Wrote: {sampling_file}")
    
    # 3. Session lifecycle
    lifecycle = build_session_lifecycle(entries, coverage)
    lifecycle['source']['sample_file'] = f'Full archive: {latest_folder.name}'
    lifecycle_file = output_dir / 'session_lifecycle.json'
    with open(lifecycle_file, 'w', encoding='ascii') as f:
        json.dump(lifecycle, f, indent=2, ensure_ascii=True)
    print(f"  Wrote: {lifecycle_file}")
    
    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)
    print(f"Generated 3 artifacts from {len(entries)} entries in {output_dir}")


if __name__ == '__main__':
    main()
