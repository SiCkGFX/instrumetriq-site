#!/usr/bin/env python3
"""
Build Coverage Table for "What We Collect" Section (Phase 1B-fix)

Reads field_coverage_report.json and generates a website-safe coverage table.
NO 0% rows. NO "Not available yet" messages. All examples are REAL computed values.

Examples are computed deterministically from sample entries:
- Numeric fields: median value
- Counts: median count
- Ranges: p10-p90
"""

import json
import math
import statistics
from datetime import datetime
from pathlib import Path


def get_nested_value(obj, path):
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


def find_best_path(coverage_lookup, *candidates):
    """Find first matching path from candidates that exists in coverage."""
    for path in candidates:
        if path in coverage_lookup:
            return path
    return None


def extract_numeric_values(entries, path):
    """Extract all valid numeric values from entries for a given path."""
    values = []
    for entry in entries:
        val = get_nested_value(entry, path)
        if val is not None:
            # Handle numeric types
            if isinstance(val, (int, float)):
                # Skip NaN and Inf
                if not math.isnan(val) and not math.isinf(val):
                    values.append(val)
    return values


def compute_median(entries, path):
    """Compute median of numeric values."""
    values = extract_numeric_values(entries, path)
    return statistics.median(values) if values else None


def compute_percentile(values, p):
    """Compute percentile p (0-100) from sorted values."""
    if not values:
        return None
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * p / 100.0)
    idx = min(idx, len(sorted_vals) - 1)
    return sorted_vals[idx]


def compute_p10_p90(entries, path):
    """Compute p10-p90 range."""
    values = extract_numeric_values(entries, path)
    if not values:
        return None, None
    p10 = compute_percentile(values, 10)
    p90 = compute_percentile(values, 90)
    return p10, p90


def count_array_lengths(entries, path):
    """Count lengths of arrays at path, return median length."""
    lengths = []
    for entry in entries:
        val = get_nested_value(entry, path)
        if val is not None and isinstance(val, list):
            lengths.append(len(val))
    return statistics.median(lengths) if lengths else None


def count_zero_values(entries, path):
    """Count how many entries have value == 0 at path."""
    total = 0
    zeros = 0
    for entry in entries:
        val = get_nested_value(entry, path)
        if val is not None and isinstance(val, (int, float)):
            total += 1
            if val == 0:
                zeros += 1
    return (zeros / total * 100.0) if total > 0 else None


def main():
    instrumetriq_root = Path(__file__).resolve().parent.parent
    coverage_file = instrumetriq_root / 'data' / 'field_coverage_report.json'
    sample_file = instrumetriq_root / 'data' / 'samples' / 'cryptobot_latest_head200.jsonl'
    output_file = instrumetriq_root / 'public' / 'data' / 'coverage_table.json'
    
    print("=" * 70)
    print("Building Coverage Table (Phase 1B)")
    print("=" * 70)
    print()
    
    # Load coverage report
    print("[LOAD] field_coverage_report.json...")
    with open(coverage_file, 'r', encoding='utf-8') as f:
        coverage = json.load(f)
    
    entries_scanned = coverage['entries_scanned']
    
    # Build coverage lookup
    coverage_lookup = {}
    for group, fields in coverage['field_groups'].items():
        for path, data in fields.items():
            pct = (data['present'] / entries_scanned) * 100
            coverage_lookup[path] = {
                'present': data['present'],
                'missing': data['missing'],
                'present_pct': pct
            }
    
    print(f"[INFO] Loaded {len(coverage_lookup)} field paths")
    print()
    
    # Load sample entries for examples
    print("[LOAD] cryptobot_latest_head200.jsonl...")
    entries = []
    with open(sample_file, 'r', encoding='utf-8') as f:
        for line in f:
            entries.append(json.loads(line))
    print(f"[INFO] Loaded {len(entries)} sample entries")
    print()
    
    # Define feature groups with candidate paths
    print("[BUILD] Evaluating feature groups...")
    rows = []
    
    # 1. Market Microstructure
    print("  [1] market_microstructure...")
    spread_bps_path = find_best_path(coverage_lookup, 'derived.spread_bps')
    depth_imb_path = find_best_path(coverage_lookup, 'derived.depth_imbalance')
    
    checks_micro = []
    if spread_bps_path and coverage_lookup[spread_bps_path]['present_pct'] > 0:
        median_spread = compute_median(entries, spread_bps_path)
        checks_micro.append({
            'label': 'Spread (bps)',
            'path': spread_bps_path,
            'present_pct': round(coverage_lookup[spread_bps_path]['present_pct'], 1),
            'example': f"{median_spread:.1f}" if median_spread else "0.0",
            'notes': 'Median bid-ask spread in basis points'
        })
    
    if depth_imb_path and coverage_lookup[depth_imb_path]['present_pct'] > 0:
        median_imb = compute_median(entries, depth_imb_path)
        checks_micro.append({
            'label': 'Depth imbalance',
            'path': depth_imb_path,
            'present_pct': round(coverage_lookup[depth_imb_path]['present_pct'], 1),
            'example': f"{median_imb:.3f}" if median_imb else "0.0",
            'notes': 'Median bid/ask volume ratio'
        })
    
    if checks_micro:
        rows.append({
            'group': 'market_microstructure',
            'label': 'Market Microstructure',
            'present_pct': round(min(c['present_pct'] for c in checks_micro), 1),
            'checks': checks_micro
        })
    
    # 2. Liquidity
    print("  [2] liquidity...")
    liq_global_path = find_best_path(coverage_lookup, 'derived.liq_global_pct')
    liq_self_path = find_best_path(coverage_lookup, 'derived.liq_self_pct')
    
    checks_liq = []
    if liq_global_path and coverage_lookup[liq_global_path]['present_pct'] > 0:
        median_global = compute_median(entries, liq_global_path)
        checks_liq.append({
            'label': 'Global liquidity %',
            'path': liq_global_path,
            'present_pct': round(coverage_lookup[liq_global_path]['present_pct'], 1),
            'example': f"{median_global:.1f}" if median_global else "0.0",
            'notes': 'Median liquidity vs global market'
        })
    
    if liq_self_path and coverage_lookup[liq_self_path]['present_pct'] > 0:
        median_self = compute_median(entries, liq_self_path)
        checks_liq.append({
            'label': 'Self liquidity %',
            'path': liq_self_path,
            'present_pct': round(coverage_lookup[liq_self_path]['present_pct'], 1),
            'example': f"{median_self:.1f}" if median_self else "0.0",
            'notes': 'Median liquidity vs own history'
        })
    
    if checks_liq:
        rows.append({
            'group': 'liquidity',
            'label': 'Liquidity Metrics',
            'present_pct': round(min(c['present_pct'] for c in checks_liq), 1),
            'checks': checks_liq
        })
    
    # 3. Order Book Depth
    print("  [3] order_book_depth...")
    depth_weighted_path = find_best_path(coverage_lookup, 'derived.depth_weighted')
    depth_skew_path = find_best_path(coverage_lookup, 'derived.depth_skew')
    
    checks_depth = []
    if depth_weighted_path and coverage_lookup[depth_weighted_path]['present_pct'] > 0:
        median_weighted = compute_median(entries, depth_weighted_path)
        checks_depth.append({
            'label': 'Weighted depth',
            'path': depth_weighted_path,
            'present_pct': round(coverage_lookup[depth_weighted_path]['present_pct'], 1),
            'example': f"{median_weighted:.2f}" if median_weighted else "0.0",
            'notes': 'Median volume-weighted depth'
        })
    
    if depth_skew_path and coverage_lookup[depth_skew_path]['present_pct'] > 0:
        median_skew = compute_median(entries, depth_skew_path)
        checks_depth.append({
            'label': 'Depth skew',
            'path': depth_skew_path,
            'present_pct': round(coverage_lookup[depth_skew_path]['present_pct'], 1),
            'example': f"{median_skew:.3f}" if median_skew else "0.0",
            'notes': 'Median bid vs ask asymmetry'
        })
    
    if checks_depth:
        rows.append({
            'group': 'order_book_depth',
            'label': 'Order Book Depth',
            'present_pct': round(min(c['present_pct'] for c in checks_depth), 1),
            'checks': checks_depth
        })
    
    # 4. Spot Prices
    print("  [4] spot_prices...")
    spot_prices_path = find_best_path(coverage_lookup, 'spot_prices')
    
    checks_spot = []
    if spot_prices_path and coverage_lookup[spot_prices_path]['present_pct'] > 0:
        # Count median array length for spot_prices
        median_count = count_array_lengths(entries, spot_prices_path)
        checks_spot.append({
            'label': 'Spot price samples',
            'path': spot_prices_path,
            'present_pct': round(coverage_lookup[spot_prices_path]['present_pct'], 1),
            'example': f"{int(median_count)}" if median_count else "0",
            'notes': 'Median OHLCV snapshots per session'
        })
    
    if checks_spot:
        rows.append({
            'group': 'spot_prices',
            'label': 'Spot Prices',
            'present_pct': round(min(c['present_pct'] for c in checks_spot), 1),
            'checks': checks_spot
        })
    
    # 5. Sampling Density (skip if 0%)
    print("  [5] sampling_density...")
    # This may not exist in current v7, so it might be empty
    
    # 6. Sentiment (Last Cycle)
    print("  [6] sentiment_last_cycle...")
    posts_total_last_path = find_best_path(coverage_lookup, 'twitter_sentiment_windows.last_cycle.posts_total')
    lex_score_path = find_best_path(coverage_lookup, 'twitter_sentiment_windows.last_cycle.lexicon_sentiment.score')
    hybrid_posts_scored_path = find_best_path(coverage_lookup, 'twitter_sentiment_windows.last_cycle.hybrid_decision_stats.posts_scored')
    
    checks_sent_last = []
    if posts_total_last_path and coverage_lookup[posts_total_last_path]['present_pct'] > 0:
        median_posts = compute_median(entries, posts_total_last_path)
        checks_sent_last.append({
            'label': 'Posts per cycle',
            'path': posts_total_last_path,
            'present_pct': round(coverage_lookup[posts_total_last_path]['present_pct'], 1),
            'example': f"{int(median_posts)}" if median_posts else "0",
            'notes': 'Median tweet volume per window'
        })
    
    if lex_score_path and coverage_lookup[lex_score_path]['present_pct'] >= 70:
        p10, p90 = compute_p10_p90(entries, lex_score_path)
        if p10 is not None and p90 is not None:
            checks_sent_last.append({
                'label': 'Lexicon score range',
                'path': lex_score_path,
                'present_pct': round(coverage_lookup[lex_score_path]['present_pct'], 1),
                'example': f"{p10:.2f} to {p90:.2f}",
                'notes': 'p10-p90 sentiment score range'
            })
    
    if hybrid_posts_scored_path and coverage_lookup[hybrid_posts_scored_path]['present_pct'] >= 70:
        median_scored = compute_median(entries, hybrid_posts_scored_path)
        checks_sent_last.append({
            'label': 'Posts scored',
            'path': hybrid_posts_scored_path,
            'present_pct': round(coverage_lookup[hybrid_posts_scored_path]['present_pct'], 1),
            'example': f"{int(median_scored)}" if median_scored else "0",
            'notes': 'Median posts with sentiment scores'
        })
    
    if checks_sent_last:
        rows.append({
            'group': 'sentiment_last_cycle',
            'label': 'Sentiment (Last Cycle)',
            'present_pct': round(min(c['present_pct'] for c in checks_sent_last), 1),
            'checks': checks_sent_last
        })
    
    # 7. Sentiment (Last 2 Cycles)
    print("  [7] sentiment_last_2_cycles...")
    posts_total_2_path = find_best_path(coverage_lookup, 'twitter_sentiment_windows.last_2_cycles.posts_total')
    lex_score_2_path = find_best_path(coverage_lookup, 'twitter_sentiment_windows.last_2_cycles.lexicon_sentiment.score')
    hybrid_posts_scored_2_path = find_best_path(coverage_lookup, 'twitter_sentiment_windows.last_2_cycles.hybrid_decision_stats.posts_scored')
    
    checks_sent_2 = []
    if posts_total_2_path and coverage_lookup[posts_total_2_path]['present_pct'] > 0:
        median_posts_2 = compute_median(entries, posts_total_2_path)
        checks_sent_2.append({
            'label': 'Posts (2-cycle)',
            'path': posts_total_2_path,
            'present_pct': round(coverage_lookup[posts_total_2_path]['present_pct'], 1),
            'example': f"{int(median_posts_2)}" if median_posts_2 else "0",
            'notes': 'Median tweets over 2 cycles'
        })
    
    if lex_score_2_path and coverage_lookup[lex_score_2_path]['present_pct'] >= 70:
        median_score_2 = compute_median(entries, lex_score_2_path)
        checks_sent_2.append({
            'label': 'Lexicon score (2-cycle)',
            'path': lex_score_2_path,
            'present_pct': round(coverage_lookup[lex_score_2_path]['present_pct'], 1),
            'example': f"{median_score_2:.3f}" if median_score_2 else "0.0",
            'notes': 'Median sentiment over 2 cycles'
        })
    
    if hybrid_posts_scored_2_path and coverage_lookup[hybrid_posts_scored_2_path]['present_pct'] >= 70:
        median_scored_2 = compute_median(entries, hybrid_posts_scored_2_path)
        checks_sent_2.append({
            'label': 'Posts scored (2-cycle)',
            'path': hybrid_posts_scored_2_path,
            'present_pct': round(coverage_lookup[hybrid_posts_scored_2_path]['present_pct'], 1),
            'example': f"{int(median_scored_2)}" if median_scored_2 else "0",
            'notes': 'Median scored posts over 2 cycles'
        })
    
    if checks_sent_2:
        rows.append({
            'group': 'sentiment_last_2_cycles',
            'label': 'Sentiment (Last 2 Cycles)',
            'present_pct': round(min(c['present_pct'] for c in checks_sent_2), 1),
            'checks': checks_sent_2
        })
    
    # 8. Activity vs Silence
    print("  [8] activity_vs_silence...")
    posts_for_silence_path = find_best_path(coverage_lookup, 'twitter_sentiment_windows.last_cycle.posts_total')
    
    checks_activity = []
    if posts_for_silence_path and coverage_lookup[posts_for_silence_path]['present_pct'] > 0:
        # Calculate % of entries with posts_total == 0 (silence)
        silence_pct = count_zero_values(entries, posts_for_silence_path)
        checks_activity.append({
            'label': 'Silence rate',
            'path': posts_for_silence_path,
            'present_pct': round(coverage_lookup[posts_for_silence_path]['present_pct'], 1),
            'example': f"{silence_pct:.1f}%" if silence_pct is not None else "0.0%",
            'notes': 'Percent of periods with zero posts'
        })
    
    if checks_activity:
        rows.append({
            'group': 'activity_vs_silence',
            'label': 'Activity vs Silence',
            'present_pct': round(min(c['present_pct'] for c in checks_activity), 1),
            'checks': checks_activity
        })
    
    # 9. Engagement and Authors
    print("  [9] engagement_and_authors...")
    distinct_authors_path = find_best_path(coverage_lookup, 'twitter_sentiment_windows.last_cycle.author_stats.distinct_authors_total')
    followers_path = find_best_path(coverage_lookup, 'twitter_sentiment_windows.last_cycle.author_stats.followers_count_mean')
    
    checks_engagement = []
    if distinct_authors_path and coverage_lookup[distinct_authors_path]['present_pct'] >= 70:
        median_authors = compute_median(entries, distinct_authors_path)
        checks_engagement.append({
            'label': 'Distinct authors',
            'path': distinct_authors_path,
            'present_pct': round(coverage_lookup[distinct_authors_path]['present_pct'], 1),
            'example': f"{int(median_authors)}" if median_authors else "0",
            'notes': 'Median unique posters per cycle'
        })
    
    if followers_path and coverage_lookup[followers_path]['present_pct'] >= 70:
        median_followers = compute_median(entries, followers_path)
        if median_followers and median_followers >= 1000:
            checks_engagement.append({
                'label': 'Follower reach',
                'path': followers_path,
                'present_pct': round(coverage_lookup[followers_path]['present_pct'], 1),
                'example': f"{int(median_followers/1000)}K",
                'notes': 'Median follower count (thousands)'
            })
        elif median_followers:
            checks_engagement.append({
                'label': 'Follower reach',
                'path': followers_path,
                'present_pct': round(coverage_lookup[followers_path]['present_pct'], 1),
                'example': f"{int(median_followers)}",
                'notes': 'Median follower count'
            })
    
    if checks_engagement:
        rows.append({
            'group': 'engagement_and_authors',
            'label': 'Engagement & Authors',
            'present_pct': round(min(c['present_pct'] for c in checks_engagement), 1),
            'checks': checks_engagement
        })
    
    print()
    print(f"[INFO] Generated {len(rows)} feature group rows")
    print()
    
    # Build output
    output = {
        'generated_at_utc': datetime.utcnow().isoformat() + 'Z',
        'entries_scanned': entries_scanned,
        'rows': rows
    }
    
    # Write output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='ascii') as f:
        json.dump(output, f, indent=2, ensure_ascii=True)
    
    print(f"[OUTPUT] {output_file}")
    print()
    
    # Summary
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    for row in rows:
        print(f"{row['label']:35} {row['present_pct']:5.1f}% ({len(row['checks'])} checks)")
    
    print()
    print("=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == '__main__':
    main()
