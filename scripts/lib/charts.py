"""
Chart generator for instrumetriq-site.
Creates clean, static SVG charts from daily statistics.
"""

import math
import sys
from pathlib import Path
from typing import List, Dict

# Graceful matplotlib import with clear error message
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
except ImportError:
    print("[ERROR] matplotlib is required for chart generation")
    print("")
    print("Install script dependencies with:")
    print("  pip install -r scripts/requirements.txt")
    print("")
    print("Or skip chart generation with:")
    print("  npm run publish -- --no-charts")
    sys.exit(1)


def create_snapshots_per_day_chart(daily_stats: List[Dict], output_path: Path):
    """
    Generate snapshots_per_day.svg chart.
    X axis: date, Y axis: usable_entries added that day
    """
    if not daily_stats:
        print("[WARN] No data for snapshots_per_day chart")
        return
    
    dates = [d["date"] for d in daily_stats]
    usable = [d["usable"] for d in daily_stats]
    
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(dates, usable, marker='o', linewidth=2, markersize=4)
    
    ax.set_xlabel("Date", fontsize=11)
    ax.set_ylabel("Usable Snapshots", fontsize=11)
    ax.set_title("Usable Snapshots per Day", fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    # Rotate x-axis labels for readability
    plt.xticks(rotation=45, ha='right')
    
    # Tight layout to prevent label cutoff
    plt.tight_layout()
    
    # Save as SVG
    plt.savefig(output_path, format='svg', dpi=100)
    plt.close()
    
    print(f"  Generated: {output_path.name}")


def create_usable_rate_per_day_chart(daily_stats: List[Dict], output_path: Path):
    """
    Generate usable_rate_per_day.svg chart.
    X axis: date, Y axis: usable / v7_seen (percentage)
    """
    if not daily_stats:
        print("[WARN] No data for usable_rate_per_day chart")
        return
    
    dates = [d["date"] for d in daily_stats]
    rates = []
    
    for d in daily_stats:
        if d["v7_seen"] > 0:
            rate = (d["usable"] / d["v7_seen"]) * 100
        else:
            rate = 0.0
        rates.append(rate)
    
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(dates, rates, marker='o', linewidth=2, markersize=4, color='#2ca02c')
    
    ax.set_xlabel("Date", fontsize=11)
    ax.set_ylabel("Usable Rate (%)", fontsize=11)
    ax.set_title("Usable Rate per Day (v7)", fontsize=13, fontweight='bold')
    ax.set_ylim(0, 105)  # 0-100% with slight padding
    ax.grid(True, alpha=0.3)
    
    # Rotate x-axis labels
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    
    plt.savefig(output_path, format='svg', dpi=100)
    plt.close()
    
    print(f"  Generated: {output_path.name}")


def create_total_usable_over_time_chart(daily_stats: List[Dict], output_path: Path):
    """
    Generate total_usable_over_time.svg chart.
    X axis: date, Y axis: cumulative usable_entries
    
    Expects daily_stats to have 'cumulative_usable' field.
    """
    if not daily_stats:
        print("[WARN] No data for total_usable_over_time chart")
        return
    
    dates = [d["date"] for d in daily_stats]
    cumulative = [d.get("cumulative_usable", 0) for d in daily_stats]
    
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(dates, cumulative, marker='o', linewidth=2, markersize=4, color='#ff7f0e')
    
    ax.set_xlabel("Date", fontsize=11)
    ax.set_ylabel("Total Usable Snapshots", fontsize=11)
    ax.set_title("Cumulative Usable Snapshots Over Time", fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    # Rotate x-axis labels
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    
    plt.savefig(output_path, format='svg', dpi=100)
    plt.close()
    
    print(f"  Generated: {output_path.name}")


def generate_all_charts(daily_stats: List[Dict], output_dir: Path):
    """
    Generate all three charts into output_dir.
    
    Args:
        daily_stats: List of daily statistics with cumulative_usable field
        output_dir: Path to public/charts/ directory
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("\nGenerating charts...")
    
    # Chart 1: Snapshots per day
    create_snapshots_per_day_chart(
        daily_stats,
        output_dir / "snapshots_per_day.svg"
    )
    
    # Chart 2: Usable rate per day
    create_usable_rate_per_day_chart(
        daily_stats,
        output_dir / "usable_rate_per_day.svg"
    )
    
    # Chart 3: Total usable over time
    create_total_usable_over_time_chart(
        daily_stats,
        output_dir / "total_usable_over_time.svg"
    )
    
    print(f"{OK_MARK} All charts generated")


# ============================================================================
# INSIGHT CHARTS (Phase 4.2)
# ============================================================================

def create_spread_bps_hist(samples: List[float], output_path: Path, metadata: Dict):
    """Generate spread_bps histogram."""
    if not samples:
        print("[WARN] No spread_bps samples for chart")
        return
    
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(samples, bins=50, edgecolor='black', alpha=0.7)
    
    ax.set_xlabel("Spread (bps)", fontsize=11)
    ax.set_ylabel("Frequency", fontsize=11)
    
    # Title with subtitle
    title = "Bid-Ask Spread Distribution"
    ax.set_title(title, fontsize=13, fontweight='bold', pad=20)
    
    # Subtitle with metadata
    subtitle = (f"Population: All usable v7 snapshots across all symbols | "
                f"N={metadata['sample_size']:,} | "
                f"Date range: {metadata['first_day']}..{metadata['last_day']} UTC")
    fig.text(0.5, 0.92, subtitle, ha='center', fontsize=8, color='gray')
    
    # Footnote
    footnote = "One sample = one snapshot entry."
    fig.text(0.5, 0.02, footnote, ha='center', fontsize=7, style='italic', color='gray')
    
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout(rect=[0, 0.04, 1, 0.94])
    plt.savefig(output_path, format='svg', dpi=100)
    plt.close()
    
    print(f"  Generated: {output_path.name}")


def create_liq_qv_usd_hist(samples: List[float], output_path: Path, metadata: Dict):
    """Generate liq_qv_usd histogram with log scale."""
    if not samples:
        print("[WARN] No liq_qv_usd samples for chart")
        return
    
    # Filter out zeros for log scale
    log_samples = [math.log10(s) for s in samples if s > 0]
    
    if not log_samples:
        print("[WARN] No positive liq_qv_usd values for log chart")
        return
    
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(log_samples, bins=50, edgecolor='black', alpha=0.7, color='#2ca02c')
    
    ax.set_xlabel("Liquidity Quote Volume (log10 USD)", fontsize=11)
    ax.set_ylabel("Frequency", fontsize=11)
    
    title = "Liquidity Distribution (log scale)"
    ax.set_title(title, fontsize=13, fontweight='bold', pad=20)
    
    subtitle = (f"Population: All usable v7 snapshots across all symbols | "
                f"N={metadata['sample_size']:,} | "
                f"Date range: {metadata['first_day']}..{metadata['last_day']} UTC")
    fig.text(0.5, 0.92, subtitle, ha='center', fontsize=8, color='gray')
    
    footnote = "One sample = one snapshot entry."
    fig.text(0.5, 0.02, footnote, ha='center', fontsize=7, style='italic', color='gray')
    
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout(rect=[0, 0.04, 1, 0.94])
    plt.savefig(output_path, format='svg', dpi=100)
    plt.close()
    
    print(f"  Generated: {output_path.name}")


def create_spread_vs_liq_scatter(spread_samples: List[float], liq_samples: List[float], output_path: Path, metadata: Dict):
    """Generate spread vs liquidity scatter plot (hexbin for density)."""
    if not spread_samples or not liq_samples:
        print("[WARN] Insufficient samples for spread_vs_liq chart")
        return
    
    # Match sample counts
    n = min(len(spread_samples), len(liq_samples))
    spread = spread_samples[:n]
    liq = [math.log10(l) if l > 0 else 0 for l in liq_samples[:n]]
    
    fig, ax = plt.subplots(figsize=(10, 7))
    
    # Use hexbin for density visualization
    hb = ax.hexbin(liq, spread, gridsize=30, cmap='Blues', mincnt=1)
    
    ax.set_xlabel("Liquidity Quote Volume (log10 USD)", fontsize=11)
    ax.set_ylabel("Spread (bps)", fontsize=11)
    
    title = "Spread vs Liquidity Relationship"
    ax.set_title(title, fontsize=13, fontweight='bold', pad=20)
    
    subtitle = (f"Population: All usable v7 snapshots across all symbols | "
                f"N={metadata['sample_size']:,} | "
                f"Date range: {metadata['first_day']}..{metadata['last_day']} UTC")
    fig.text(0.5, 0.92, subtitle, ha='center', fontsize=8, color='gray')
    
    footnote = "One sample = one snapshot entry."
    fig.text(0.5, 0.02, footnote, ha='center', fontsize=7, style='italic', color='gray')
    
    # Add colorbar
    cb = plt.colorbar(hb, ax=ax)
    cb.set_label("Count", fontsize=10)
    
    plt.tight_layout(rect=[0, 0.04, 1, 0.94])
    plt.savefig(output_path, format='svg', dpi=100)
    plt.close()
    
    print(f"  Generated: {output_path.name}")


def create_tweets_last_cycle_hist(samples: List[int], output_path: Path, metadata: Dict):
    """Generate tweets_last_cycle histogram."""
    if not samples:
        print("[WARN] No tweets_last_cycle samples for chart")
        return
    
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(samples, bins=50, edgecolor='black', alpha=0.7, color='#ff7f0e')
    
    ax.set_xlabel("Tweet Count (last_cycle posts_total)", fontsize=11)
    ax.set_ylabel("Frequency", fontsize=11)
    
    title = "Tweet Volume Distribution (Single Cycle)"
    ax.set_title(title, fontsize=13, fontweight='bold', pad=20)
    
    subtitle = (f"Population: All usable v7 snapshots across all symbols | "
                f"N={metadata['sample_size']:,} | "
                f"Date range: {metadata['first_day']}..{metadata['last_day']} UTC")
    fig.text(0.5, 0.92, subtitle, ha='center', fontsize=8, color='gray')
    
    footnote = "One sample = one snapshot entry. Tweet counts from twitter_sentiment_windows.last_cycle.posts_total."
    fig.text(0.5, 0.02, footnote, ha='center', fontsize=7, style='italic', color='gray')
    
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout(rect=[0, 0.04, 1, 0.94])
    plt.savefig(output_path, format='svg', dpi=100)
    plt.close()
    
    print(f"  Generated: {output_path.name}")


def create_tweets_last_2_cycles_hist(samples: List[int], output_path: Path, metadata: Dict):
    """Generate tweets_last_2_cycles histogram."""
    if not samples:
        print("[WARN] No tweets_last_2_cycles samples for chart")
        return
    
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(samples, bins=50, edgecolor='black', alpha=0.7, color='#9467bd')
    
    ax.set_xlabel("Tweet Count (last_2_cycles posts_total)", fontsize=11)
    ax.set_ylabel("Frequency", fontsize=11)
    
    title = "Tweet Volume Distribution (Double Cycle)"
    ax.set_title(title, fontsize=13, fontweight='bold', pad=20)
    
    subtitle = (f"Population: All usable v7 snapshots across all symbols | "
                f"N={metadata['sample_size']:,} | "
                f"Date range: {metadata['first_day']}..{metadata['last_day']} UTC")
    fig.text(0.5, 0.92, subtitle, ha='center', fontsize=8, color='gray')
    
    footnote = "One sample = one snapshot entry. Tweet counts from twitter_sentiment_windows.last_2_cycles.posts_total."
    fig.text(0.5, 0.02, footnote, ha='center', fontsize=7, style='italic', color='gray')
    
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout(rect=[0, 0.04, 1, 0.94])
    plt.savefig(output_path, format='svg', dpi=100)
    plt.close()
    
    print(f"  Generated: {output_path.name}")


def create_tweets_volume_over_time(daily_stats: List[Dict], output_path: Path, metadata: Dict):
    """Generate tweet volume time series (median and p90)."""
    if not daily_stats:
        print("[WARN] No daily tweet stats for time series chart")
        return
    
    dates = [s["date"] for s in daily_stats]
    medians = [s["median"] for s in daily_stats]
    p90s = [s["p90"] for s in daily_stats]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(dates, medians, marker='o', linewidth=2, markersize=4, label='Median', color='#1f77b4')
    ax.plot(dates, p90s, marker='s', linewidth=2, markersize=4, label='P90', color='#ff7f0e')
    
    ax.set_xlabel("UTC Date (archive day)", fontsize=11)
    ax.set_ylabel("Tweet Count (last_cycle posts_total)", fontsize=11)
    
    title = "Tweet Volume Over Time"
    ax.set_title(title, fontsize=13, fontweight='bold', pad=20)
    
    subtitle = (f"Population: All usable v7 snapshots across all symbols | "
                f"N={metadata['sample_size']:,} | "
                f"Date range: {metadata['first_day']}..{metadata['last_day']} UTC")
    fig.text(0.5, 0.92, subtitle, ha='center', fontsize=8, color='gray')
    
    footnote = "One sample = one snapshot entry. Tweet counts from twitter_sentiment_windows.last_cycle.posts_total."
    fig.text(0.5, 0.02, footnote, ha='center', fontsize=7, style='italic', color='gray')
    
    ax.legend(loc='best', fontsize=10)
    ax.grid(True, alpha=0.3)
    
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout(rect=[0, 0.04, 1, 0.94])
    
    plt.savefig(output_path, format='svg', dpi=100)
    plt.close()
    
    print(f"  Generated: {output_path.name}")


def create_abs_return_hist(samples: List[float], output_path: Path, metadata: Dict):
    """Generate absolute return histogram."""
    if not samples:
        print("[WARN] No abs_return samples for chart")
        return
    
    # Convert to percentage
    pct_samples = [s * 100 for s in samples]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(pct_samples, bins=50, edgecolor='black', alpha=0.7, color='#d62728')
    
    ax.set_xlabel("Absolute Return (%)", fontsize=11)
    ax.set_ylabel("Frequency", fontsize=11)
    
    title = "Absolute Return Distribution"
    ax.set_title(title, fontsize=13, fontweight='bold', pad=20)
    
    subtitle = (f"Population: All usable v7 snapshots across all symbols | "
                f"N={metadata['sample_size']:,} | "
                f"Date range: {metadata['first_day']}..{metadata['last_day']} UTC")
    fig.text(0.5, 0.92, subtitle, ha='center', fontsize=8, color='gray')
    
    footnote = "One sample = one snapshot entry. Computed from spot_prices window (first to last mid)."
    fig.text(0.5, 0.02, footnote, ha='center', fontsize=7, style='italic', color='gray')
    
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout(rect=[0, 0.04, 1, 0.94])
    plt.savefig(output_path, format='svg', dpi=100)
    plt.close()
    
    print(f"  Generated: {output_path.name}")


# ============================================================================
# TOP 20 SYMBOL CHARTS (Phase 4.2 FIX)
# ============================================================================

def create_tweets_last_cycle_top20_symbols(symbol_stats: List[Dict], output_path: Path, metadata: Dict):
    """Generate top 20 symbols by tweet volume bar chart."""
    if not symbol_stats:
        print("[WARN] No symbol stats for tweets_last_cycle_top20")
        return
    
    symbols = [s["symbol"] for s in symbol_stats]
    medians = [s["median"] for s in symbol_stats]
    
    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.barh(symbols, medians, color='#ff7f0e', alpha=0.8)
    
    ax.set_xlabel("Median Tweet Count (last_cycle posts_total)", fontsize=11)
    ax.set_ylabel("Symbol", fontsize=11)
    ax.invert_yaxis()  # Highest at top
    
    title = "Top 20 Symbols by Tweet Volume"
    ax.set_title(title, fontsize=13, fontweight='bold', pad=20)
    
    subtitle = (f"Top 20 by sample count (min {metadata.get('min_samples', 30)} snapshots per symbol) | "
                f"Date range: {metadata['first_day']}..{metadata['last_day']} UTC")
    fig.text(0.5, 0.94, subtitle, ha='center', fontsize=8, color='gray')
    
    footnote = "Median across usable snapshots per symbol. Tweet counts from twitter_sentiment_windows.last_cycle.posts_total."
    fig.text(0.5, 0.02, footnote, ha='center', fontsize=7, style='italic', color='gray')
    
    ax.grid(True, alpha=0.3, axis='x')
    
    plt.tight_layout(rect=[0, 0.04, 1, 0.96])
    plt.savefig(output_path, format='svg', dpi=100)
    plt.close()
    
    print(f"  Generated: {output_path.name}")


def create_spread_bps_top20_symbols(symbol_stats: List[Dict], output_path: Path, metadata: Dict):
    """Generate top 20 symbols by spread bar chart."""
    if not symbol_stats:
        print("[WARN] No symbol stats for spread_bps_top20")
        return
    
    symbols = [s["symbol"] for s in symbol_stats]
    medians = [s["median"] for s in symbol_stats]
    
    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.barh(symbols, medians, color='#1f77b4', alpha=0.8)
    
    ax.set_xlabel("Median Spread (bps)", fontsize=11)
    ax.set_ylabel("Symbol", fontsize=11)
    ax.invert_yaxis()  # Highest at top
    
    title = "Top 20 Symbols by Bid-Ask Spread"
    ax.set_title(title, fontsize=13, fontweight='bold', pad=20)
    
    subtitle = (f"Top 20 by sample count (min {metadata.get('min_samples', 30)} snapshots per symbol) | "
                f"Date range: {metadata['first_day']}..{metadata['last_day']} UTC")
    fig.text(0.5, 0.94, subtitle, ha='center', fontsize=8, color='gray')
    
    footnote = "Median across usable snapshots per symbol."
    fig.text(0.5, 0.02, footnote, ha='center', fontsize=7, style='italic', color='gray')
    
    ax.grid(True, alpha=0.3, axis='x')
    
    plt.tight_layout(rect=[0, 0.04, 1, 0.96])
    plt.savefig(output_path, format='svg', dpi=100)
    plt.close()
    
    print(f"  Generated: {output_path.name}")


def create_liq_qv_usd_top20_symbols(symbol_stats: List[Dict], output_path: Path, metadata: Dict):
    """Generate top 20 symbols by liquidity bar chart (log scale labels)."""
    if not symbol_stats:
        print("[WARN] No symbol stats for liq_qv_usd_top20")
        return
    
    symbols = [s["symbol"] for s in symbol_stats]
    medians = [s["median"] for s in symbol_stats]
    
    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.barh(symbols, medians, color='#2ca02c', alpha=0.8)
    
    ax.set_xlabel("Median Liquidity Quote Value (USD)", fontsize=11)
    ax.set_ylabel("Symbol", fontsize=11)
    ax.set_xscale('log')  # Log scale for liquidity
    ax.invert_yaxis()  # Highest at top
    
    title = "Top 20 Symbols by Liquidity"
    ax.set_title(title, fontsize=13, fontweight='bold', pad=20)
    
    subtitle = (f"Top 20 by sample count (min {metadata.get('min_samples', 30)} snapshots per symbol) | "
                f"Date range: {metadata['first_day']}..{metadata['last_day']} UTC")
    fig.text(0.5, 0.94, subtitle, ha='center', fontsize=8, color='gray')
    
    footnote = "Median across usable snapshots per symbol. X-axis on log scale."
    fig.text(0.5, 0.02, footnote, ha='center', fontsize=7, style='italic', color='gray')
    
    ax.grid(True, alpha=0.3, axis='x')
    
    plt.tight_layout(rect=[0, 0.04, 1, 0.96])
    plt.savefig(output_path, format='svg', dpi=100)
    plt.close()
    
    print(f"  Generated: {output_path.name}")


def generate_insight_charts(aggregator, output_dir: Path, metadata: Dict):
    """
    Generate all insight charts from aggregator.
    
    Args:
        aggregator: InsightsAggregator with collected samples
        output_dir: Path to public/charts/insights/ directory
        metadata: Dict with first_day, last_day, sample_size
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("\nGenerating insight charts...")
    
    # Import here to avoid circular dependency
    import math
    
    # Market microstructure
    create_spread_bps_hist(
        aggregator.spread_bps_samples,
        output_dir / "spread_bps_hist.svg",
        metadata
    )
    
    create_liq_qv_usd_hist(
        aggregator.liq_qv_usd_samples,
        output_dir / "liq_qv_usd_hist.svg",
        metadata
    )
    
    create_spread_vs_liq_scatter(
        aggregator.spread_bps_samples,
        aggregator.liq_qv_usd_samples,
        output_dir / "spread_vs_liq_scatter.svg",
        metadata
    )
    
    # Tweet volume
    create_tweets_last_cycle_hist(
        aggregator.tweets_last_cycle_samples,
        output_dir / "tweets_last_cycle_hist.svg",
        metadata
    )
    
    create_tweets_last_2_cycles_hist(
        aggregator.tweets_last_2_cycles_samples,
        output_dir / "tweets_last_2_cycles_hist.svg",
        metadata
    )
    
    # Tweet volume time series
    daily_tweet_stats = aggregator.get_daily_tweet_stats()
    create_tweets_volume_over_time(
        daily_tweet_stats,
        output_dir / "tweets_volume_over_time.svg",
        metadata
    )
    
    # Return distribution
    create_abs_return_hist(
        aggregator.abs_return_samples,
        output_dir / "abs_return_over_window_hist.svg",
        metadata
    )
    
    # Top 20 symbol breakdown charts
    min_samples = 30
    metadata_with_min = {**metadata, "min_samples": min_samples}
    
    tweets_top20 = aggregator.get_top_symbols("tweets_lc", min_samples=min_samples)
    create_tweets_last_cycle_top20_symbols(
        tweets_top20,
        output_dir / "tweets_last_cycle_top20_symbols.svg",
        metadata_with_min
    )
    
    spread_top20 = aggregator.get_top_symbols("spread_bps", min_samples=min_samples)
    create_spread_bps_top20_symbols(
        spread_top20,
        output_dir / "spread_bps_top20_symbols.svg",
        metadata_with_min
    )
    
    liq_top20 = aggregator.get_top_symbols("liq_qv_usd", min_samples=min_samples)
    create_liq_qv_usd_top20_symbols(
        liq_top20,
        output_dir / "liq_qv_usd_top20_symbols.svg",
        metadata_with_min
    )
    
    print(f"{OK_MARK} All insight charts generated (10 total)")


def write_chart_manifest(aggregator, output_dir: Path, metadata: Dict):
    """
    Write chart_manifest.json with metadata for all insight charts.
    
    Args:
        aggregator: InsightsAggregator with collected samples
        output_dir: Path to public/charts/insights/ directory
        metadata: Dict with first_day, last_day, sample_size
    """
    import json
    
    manifest = {
        "generated_at": metadata.get("generated_at", ""),
        "date_range_utc": {
            "first_day": metadata["first_day"],
            "last_day": metadata["last_day"]
        },
        "total_usable_snapshots": metadata["sample_size"],
        "charts": [
            {
                "id": "spread_bps_hist",
                "file": "spread_bps_hist.svg",
                "title": "Bid-Ask Spread Distribution",
                "description": "Distribution of bid-ask spreads across all usable snapshots, showing market microstructure characteristics.",
                "population": "All usable v7 snapshots across all symbols",
                "sample_size": len(aggregator.spread_bps_samples),
                "fields": ["spot_raw.spread_bps"],
                "aggregation": "histogram",
                "notes": ["One sample = one snapshot entry", "Spread measured in basis points"]
            },
            {
                "id": "liq_qv_usd_hist",
                "file": "liq_qv_usd_hist.svg",
                "title": "Liquidity Distribution (log scale)",
                "description": "Distribution of liquidity quote values on log scale, showing market depth characteristics.",
                "population": "All usable v7 snapshots across all symbols",
                "sample_size": len(aggregator.liq_qv_usd_samples),
                "fields": ["spot_raw.liq_qv_usd"],
                "aggregation": "histogram",
                "notes": ["One sample = one snapshot entry", "Log10 scale for clarity"]
            },
            {
                "id": "spread_vs_liq_scatter",
                "file": "spread_vs_liq_scatter.svg",
                "title": "Spread vs Liquidity Relationship",
                "description": "Hexbin density plot showing relationship between spread and liquidity across snapshots.",
                "population": "All usable v7 snapshots across all symbols",
                "sample_size": min(len(aggregator.spread_bps_samples), len(aggregator.liq_qv_usd_samples)),
                "fields": ["spot_raw.spread_bps", "spot_raw.liq_qv_usd"],
                "aggregation": "hexbin",
                "notes": ["One sample = one snapshot entry", "Log scale on liquidity axis"]
            },
            {
                "id": "tweets_last_cycle_hist",
                "file": "tweets_last_cycle_hist.svg",
                "title": "Tweet Volume Distribution (Single Cycle)",
                "description": "Distribution of tweet counts per snapshot for single cycle window, showing social media activity levels.",
                "population": "All usable v7 snapshots across all symbols",
                "sample_size": len(aggregator.tweets_last_cycle_samples),
                "fields": ["twitter_sentiment_windows.last_cycle.posts_total"],
                "aggregation": "histogram",
                "notes": ["One sample = one snapshot entry", "Counts aggregated per snapshot"]
            },
            {
                "id": "tweets_last_2_cycles_hist",
                "file": "tweets_last_2_cycles_hist.svg",
                "title": "Tweet Volume Distribution (Double Cycle)",
                "description": "Distribution of tweet counts per snapshot for double cycle window, showing extended social media activity.",
                "population": "All usable v7 snapshots across all symbols",
                "sample_size": len(aggregator.tweets_last_2_cycles_samples),
                "fields": ["twitter_sentiment_windows.last_2_cycles.posts_total"],
                "aggregation": "histogram",
                "notes": ["One sample = one snapshot entry", "Counts aggregated per snapshot"]
            },
            {
                "id": "tweets_volume_over_time",
                "file": "tweets_volume_over_time.svg",
                "title": "Tweet Volume Over Time",
                "description": "Time series showing median and 90th percentile tweet volumes per day, revealing temporal patterns.",
                "population": "All usable v7 snapshots across all symbols",
                "sample_size": metadata["sample_size"],
                "fields": ["twitter_sentiment_windows.last_cycle.posts_total"],
                "aggregation": "time_series",
                "notes": ["Aggregated by archive day", "Median and P90 computed per day"]
            },
            {
                "id": "abs_return_hist",
                "file": "abs_return_over_window_hist.svg",
                "title": "Absolute Return Distribution",
                "description": "Distribution of absolute returns computed from spot price windows, showing price movement characteristics.",
                "population": "All usable v7 snapshots across all symbols",
                "sample_size": len(aggregator.abs_return_samples),
                "fields": ["spot_prices"],
                "aggregation": "histogram",
                "notes": ["One sample = one snapshot entry", "Computed from first to last mid price"]
            },
            {
                "id": "tweets_last_cycle_top20_symbols",
                "file": "tweets_last_cycle_top20_symbols.svg",
                "title": "Top 20 Symbols by Tweet Volume",
                "description": "Top 20 symbols ranked by sample count, showing median tweet volume per symbol for most-sampled assets.",
                "population": "Symbols with >= 30 usable snapshots",
                "sample_size": sum(len(aggregator.per_symbol.get(s, {}).get("tweets_lc", [])) for s in aggregator.per_symbol),
                "fields": ["twitter_sentiment_windows.last_cycle.posts_total", "symbol"],
                "aggregation": "bar_chart",
                "notes": ["Median per symbol", "Top 20 by sample count for stability"]
            },
            {
                "id": "spread_bps_top20_symbols",
                "file": "spread_bps_top20_symbols.svg",
                "title": "Top 20 Symbols by Bid-Ask Spread",
                "description": "Top 20 symbols ranked by sample count, showing median spread per symbol for most-sampled assets.",
                "population": "Symbols with >= 30 usable snapshots",
                "sample_size": sum(len(aggregator.per_symbol.get(s, {}).get("spread_bps", [])) for s in aggregator.per_symbol),
                "fields": ["spot_raw.spread_bps", "symbol"],
                "aggregation": "bar_chart",
                "notes": ["Median per symbol", "Top 20 by sample count for stability"]
            },
            {
                "id": "liq_qv_usd_top20_symbols",
                "file": "liq_qv_usd_top20_symbols.svg",
                "title": "Top 20 Symbols by Liquidity",
                "description": "Top 20 symbols ranked by sample count, showing median liquidity per symbol for most-sampled assets.",
                "population": "Symbols with >= 30 usable snapshots",
                "sample_size": sum(len(aggregator.per_symbol.get(s, {}).get("liq_qv_usd", [])) for s in aggregator.per_symbol),
                "fields": ["spot_raw.liq_qv_usd", "symbol"],
                "aggregation": "bar_chart",
                "notes": ["Median per symbol", "Top 20 by sample count for stability", "X-axis on log scale"]
            }
        ]
    }
    
    manifest_path = output_dir / "chart_manifest.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"  Generated: chart_manifest.json")


# Import status symbol for consistency
OK_MARK = "[OK]"
