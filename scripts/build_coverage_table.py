#!/usr/bin/env python3
"""
Build Coverage Table for "What We Collect" Section (Phase 1B)

Reads field_coverage_report.json and generates a website-safe coverage table.
NO 0% rows. NO "Not available yet" messages. All examples populated.
"""

import json
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


def calculate_median_value(entries, path):
    """Calculate median value for a numeric field."""
    values = []
    for entry in entries:
        val = get_nested_value(entry, path)
        if val is not None and isinstance(val, (int, float)):
            values.append(val)
    
    if len(values) == 0:
        return None
    return statistics.median(values)


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
    flow_path = find_best_path(coverage_lookup, 'derived.flow')
    
    checks_micro = []
    if spread_bps_path and coverage_lookup[spread_bps_path]['present_pct'] > 0:
        median_spread = calculate_median_value(entries, spread_bps_path)
        checks_micro.append({
            'label': 'Spread (bps)',
            'path': spread_bps_path,
            'present_pct': round(coverage_lookup[spread_bps_path]['present_pct'], 1),
            'example': f"{median_spread:.1f} bps" if median_spread else "varies",
            'notes': 'Bid-ask spread in basis points'
        })
    
    if depth_imb_path and coverage_lookup[depth_imb_path]['present_pct'] > 0:
        checks_micro.append({
            'label': 'Depth imbalance',
            'path': depth_imb_path,
            'present_pct': round(coverage_lookup[depth_imb_path]['present_pct'], 1),
            'example': 'bid/ask volume ratio',
            'notes': 'Order book depth asymmetry'
        })
    
    if flow_path and coverage_lookup[flow_path]['present_pct'] > 0:
        checks_micro.append({
            'label': 'Flow indicators',
            'path': flow_path,
            'present_pct': round(coverage_lookup[flow_path]['present_pct'], 1),
            'example': 'momentum metrics',
            'notes': 'Trade flow and momentum signals'
        })
    
    if checks_micro:
        rows.append({
            'group': 'market_microstructure',
            'label': 'Market Microstructure',
            'present_pct': round(sum(c['present_pct'] for c in checks_micro) / len(checks_micro), 1),
            'checks': checks_micro
        })
    
    # 2. Liquidity
    print("  [2] liquidity...")
    liq_global_path = find_best_path(coverage_lookup, 'derived.liq_global_pct')
    liq_self_path = find_best_path(coverage_lookup, 'derived.liq_self_pct')
    
    checks_liq = []
    if liq_global_path and coverage_lookup[liq_global_path]['present_pct'] > 0:
        checks_liq.append({
            'label': 'Global liquidity %',
            'path': liq_global_path,
            'present_pct': round(coverage_lookup[liq_global_path]['present_pct'], 1),
            'example': 'cross-market comparison',
            'notes': 'Liquidity relative to global market'
        })
    
    if liq_self_path and coverage_lookup[liq_self_path]['present_pct'] > 0:
        checks_liq.append({
            'label': 'Self liquidity %',
            'path': liq_self_path,
            'present_pct': round(coverage_lookup[liq_self_path]['present_pct'], 1),
            'example': 'symbol-specific depth',
            'notes': 'Liquidity relative to own history'
        })
    
    if checks_liq:
        rows.append({
            'group': 'liquidity',
            'label': 'Liquidity Metrics',
            'present_pct': round(sum(c['present_pct'] for c in checks_liq) / len(checks_liq), 1),
            'checks': checks_liq
        })
    
    # 3. Order Book Depth
    print("  [3] order_book_depth...")
    depth_weighted_path = find_best_path(coverage_lookup, 'derived.depth_weighted')
    depth_skew_path = find_best_path(coverage_lookup, 'derived.depth_skew')
    
    checks_depth = []
    if depth_weighted_path and coverage_lookup[depth_weighted_path]['present_pct'] > 0:
        checks_depth.append({
            'label': 'Weighted depth',
            'path': depth_weighted_path,
            'present_pct': round(coverage_lookup[depth_weighted_path]['present_pct'], 1),
            'example': 'volume-weighted book',
            'notes': 'Depth across price levels'
        })
    
    if depth_skew_path and coverage_lookup[depth_skew_path]['present_pct'] > 0:
        checks_depth.append({
            'label': 'Depth skew',
            'path': depth_skew_path,
            'present_pct': round(coverage_lookup[depth_skew_path]['present_pct'], 1),
            'example': 'bid vs ask asymmetry',
            'notes': 'Order book balance'
        })
    
    if checks_depth:
        rows.append({
            'group': 'order_book_depth',
            'label': 'Order Book Depth',
            'present_pct': round(sum(c['present_pct'] for c in checks_depth) / len(checks_depth), 1),
            'checks': checks_depth
        })
    
    # 4. Spot Prices
    print("  [4] spot_prices...")
    # Check if spot_prices data exists
    spot_prices_path = find_best_path(coverage_lookup, 'spot_prices')
    checks_spot = []
    
    if spot_prices_path and coverage_lookup[spot_prices_path]['present_pct'] > 0:
        checks_spot.append({
            'label': 'Spot prices',
            'path': spot_prices_path,
            'present_pct': round(coverage_lookup[spot_prices_path]['present_pct'], 1),
            'example': 'OHLCV snapshots',
            'notes': 'Current and recent prices'
        })
    
    if checks_spot:
        rows.append({
            'group': 'spot_prices',
            'label': 'Spot Prices',
            'present_pct': round(sum(c['present_pct'] for c in checks_spot) / len(checks_spot), 1),
            'checks': checks_spot
        })
    
    # 5. Sampling Density
    print("  [5] sampling_density...")
    # Look for meta.sampling or similar fields
    checks_sampling = []
    # This may not exist in current v7, so it might be empty
    
    # 6. Sentiment (Last Cycle)
    print("  [6] sentiment_last_cycle...")
    ai_sent_path = find_best_path(coverage_lookup, 'twitter_sentiment_windows.last_cycle.ai_sentiment')
    lex_sent_path = find_best_path(coverage_lookup, 'twitter_sentiment_windows.last_cycle.lexicon_sentiment')
    hybrid_path = find_best_path(coverage_lookup, 'twitter_sentiment_windows.last_cycle.hybrid_decision_stats')
    
    checks_sent_last = []
    if ai_sent_path and coverage_lookup[ai_sent_path]['present_pct'] > 0:
        checks_sent_last.append({
            'label': 'AI sentiment',
            'path': ai_sent_path,
            'present_pct': round(coverage_lookup[ai_sent_path]['present_pct'], 1),
            'example': 'transformer-based scoring',
            'notes': 'ML model sentiment classification'
        })
    
    if lex_sent_path and coverage_lookup[lex_sent_path]['present_pct'] > 0:
        checks_sent_last.append({
            'label': 'Lexicon sentiment',
            'path': lex_sent_path,
            'present_pct': round(coverage_lookup[lex_sent_path]['present_pct'], 1),
            'example': 'dictionary-based scoring',
            'notes': 'Keyword-based sentiment'
        })
    
    if hybrid_path and coverage_lookup[hybrid_path]['present_pct'] > 0:
        checks_sent_last.append({
            'label': 'Hybrid decisions',
            'path': hybrid_path,
            'present_pct': round(coverage_lookup[hybrid_path]['present_pct'], 1),
            'example': 'referee-arbitrated scoring',
            'notes': 'Combined sentiment logic'
        })
    
    if checks_sent_last:
        rows.append({
            'group': 'sentiment_last_cycle',
            'label': 'Sentiment (Last Cycle)',
            'present_pct': round(sum(c['present_pct'] for c in checks_sent_last) / len(checks_sent_last), 1),
            'checks': checks_sent_last
        })
    
    # 7. Sentiment (Last 2 Cycles)
    print("  [7] sentiment_last_2_cycles...")
    ai_sent2_path = find_best_path(coverage_lookup, 'twitter_sentiment_windows.last_2_cycles.ai_sentiment')
    lex_sent2_path = find_best_path(coverage_lookup, 'twitter_sentiment_windows.last_2_cycles.lexicon_sentiment')
    hybrid2_path = find_best_path(coverage_lookup, 'twitter_sentiment_windows.last_2_cycles.hybrid_decision_stats')
    
    checks_sent_2 = []
    if ai_sent2_path and coverage_lookup[ai_sent2_path]['present_pct'] > 0:
        checks_sent_2.append({
            'label': 'AI sentiment (2-cycle)',
            'path': ai_sent2_path,
            'present_pct': round(coverage_lookup[ai_sent2_path]['present_pct'], 1),
            'example': 'extended window scoring',
            'notes': 'ML sentiment over 2 cycles'
        })
    
    if lex_sent2_path and coverage_lookup[lex_sent2_path]['present_pct'] > 0:
        checks_sent_2.append({
            'label': 'Lexicon sentiment (2-cycle)',
            'path': lex_sent2_path,
            'present_pct': round(coverage_lookup[lex_sent2_path]['present_pct'], 1),
            'example': 'extended window scoring',
            'notes': 'Lexicon sentiment over 2 cycles'
        })
    
    if hybrid2_path and coverage_lookup[hybrid2_path]['present_pct'] > 0:
        checks_sent_2.append({
            'label': 'Hybrid decisions (2-cycle)',
            'path': hybrid2_path,
            'present_pct': round(coverage_lookup[hybrid2_path]['present_pct'], 1),
            'example': 'extended window decisions',
            'notes': 'Combined logic over 2 cycles'
        })
    
    if checks_sent_2:
        rows.append({
            'group': 'sentiment_last_2_cycles',
            'label': 'Sentiment (Last 2 Cycles)',
            'present_pct': round(sum(c['present_pct'] for c in checks_sent_2) / len(checks_sent_2), 1),
            'checks': checks_sent_2
        })
    
    # 8. Activity vs Silence
    print("  [8] activity_vs_silence...")
    posts_total_path = find_best_path(coverage_lookup, 'twitter_sentiment_windows.last_cycle.posts_total')
    bucket_status_path = find_best_path(coverage_lookup, 'twitter_sentiment_windows.last_cycle.bucket_status')
    
    checks_activity = []
    if posts_total_path and coverage_lookup[posts_total_path]['present_pct'] > 0:
        median_posts = calculate_median_value(entries, posts_total_path)
        checks_activity.append({
            'label': 'Posts per cycle',
            'path': posts_total_path,
            'present_pct': round(coverage_lookup[posts_total_path]['present_pct'], 1),
            'example': f"{int(median_posts)} posts" if median_posts else "varies by symbol",
            'notes': 'Tweet volume per time window'
        })
    
    if bucket_status_path and coverage_lookup[bucket_status_path]['present_pct'] > 0:
        checks_activity.append({
            'label': 'Silence detection',
            'path': bucket_status_path,
            'present_pct': round(coverage_lookup[bucket_status_path]['present_pct'], 1),
            'example': 'active/silent classification',
            'notes': 'Detects periods with no posts'
        })
    
    if checks_activity:
        rows.append({
            'group': 'activity_vs_silence',
            'label': 'Activity vs Silence',
            'present_pct': round(sum(c['present_pct'] for c in checks_activity) / len(checks_activity), 1),
            'checks': checks_activity
        })
    
    # 9. Engagement and Authors
    print("  [9] engagement_and_authors...")
    author_stats_path = find_best_path(coverage_lookup, 'twitter_sentiment_windows.last_cycle.author_stats')
    distinct_authors_path = find_best_path(coverage_lookup, 'twitter_sentiment_windows.last_cycle.author_stats.distinct_authors_total')
    followers_path = find_best_path(coverage_lookup, 'twitter_sentiment_windows.last_cycle.author_stats.followers_count_mean')
    
    checks_engagement = []
    if distinct_authors_path and coverage_lookup[distinct_authors_path]['present_pct'] > 0:
        checks_engagement.append({
            'label': 'Distinct authors',
            'path': distinct_authors_path,
            'present_pct': round(coverage_lookup[distinct_authors_path]['present_pct'], 1),
            'example': 'unique users per cycle',
            'notes': 'Number of unique posters'
        })
    
    if followers_path and coverage_lookup[followers_path]['present_pct'] > 0:
        checks_engagement.append({
            'label': 'Follower reach',
            'path': followers_path,
            'present_pct': round(coverage_lookup[followers_path]['present_pct'], 1),
            'example': 'audience size metrics',
            'notes': 'Average follower counts'
        })
    
    if checks_engagement:
        rows.append({
            'group': 'engagement_and_authors',
            'label': 'Engagement & Authors',
            'present_pct': round(sum(c['present_pct'] for c in checks_engagement) / len(checks_engagement), 1),
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
