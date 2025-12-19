"""
Chart generator for instrumetriq-site.
Creates clean, static SVG charts from daily statistics.
"""

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


# Import status symbol for consistency
OK_MARK = "[OK]"
