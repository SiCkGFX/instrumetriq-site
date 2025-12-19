"""
Insights statistics aggregator for CryptoBot archive.
Computes distributional metrics for dataset characterization.
Uses reservoir sampling to keep memory bounded.
"""

import gzip
import json
import math
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def get_tweets_last_cycle(entry: dict) -> Optional[int]:
    """
    Get tweet count from last_cycle window.
    
    Field path: entry["twitter_sentiment_windows"]["last_cycle"]["posts_total"]
    
    Returns:
        int if found and valid, None otherwise
    """
    try:
        tsw = entry.get("twitter_sentiment_windows", {})
        last_cycle = tsw.get("last_cycle", {})
        posts_total = last_cycle.get("posts_total")
        
        if posts_total is not None and isinstance(posts_total, (int, float)):
            return int(posts_total)
        return None
    except (KeyError, TypeError, ValueError):
        return None


def get_tweets_last_2_cycles(entry: dict) -> Optional[int]:
    """
    Get tweet count from last_2_cycles window.
    
    Field path: entry["twitter_sentiment_windows"]["last_2_cycles"]["posts_total"]
    
    Returns:
        int if found and valid, None otherwise
    """
    try:
        tsw = entry.get("twitter_sentiment_windows", {})
        last_2_cycles = tsw.get("last_2_cycles", {})
        posts_total = last_2_cycles.get("posts_total")
        
        if posts_total is not None and isinstance(posts_total, (int, float)):
            return int(posts_total)
        return None
    except (KeyError, TypeError, ValueError):
        return None


def is_valid_number(value) -> bool:
    """Check if value is a valid finite number."""
    if value is None:
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def reservoir_sample(item, reservoir: list, k: int, n: int) -> int:
    """
    Reservoir sampling algorithm to maintain bounded sample size.
    
    Args:
        item: Item to potentially add
        reservoir: Current reservoir (modified in place)
        k: Max reservoir size
        n: Current item count (1-indexed)
    
    Returns:
        Updated n (incremented)
    """
    if len(reservoir) < k:
        reservoir.append(item)
    else:
        # Random replacement with probability k/n
        j = random.randint(0, n - 1)
        if j < k:
            reservoir[j] = item
    return n + 1


def compute_abs_return(spot_prices: list) -> Optional[float]:
    """
    Compute absolute return over spot_prices window.
    
    spot_prices is a list of dict objects with keys: ts, mid, bid, ask, spread_bps
    We use 'mid' for price calculation.
    
    Returns:
        abs((last_mid - first_mid) / first_mid) if valid, None otherwise
    """
    if not isinstance(spot_prices, list) or len(spot_prices) < 2:
        return None
    
    try:
        first_sample = spot_prices[0]
        last_sample = spot_prices[-1]
        
        # Extract mid price from dict
        if isinstance(first_sample, dict):
            first = first_sample.get("mid")
        else:
            first = first_sample
        
        if isinstance(last_sample, dict):
            last = last_sample.get("mid")
        else:
            last = last_sample
        
        if not is_valid_number(first) or not is_valid_number(last):
            return None
        
        first = float(first)
        last = float(last)
        
        if first <= 0:
            return None
        
        return abs((last - first) / first)
    except (TypeError, ValueError, ZeroDivisionError, KeyError):
        return None


class InsightsAggregator:
    """Aggregates insight metrics using reservoir sampling."""
    
    def __init__(self, max_samples: int = 200_000):
        self.max_samples = max_samples
        
        # Reservoir samples
        self.spread_bps_samples = []
        self.liq_qv_usd_samples = []
        self.abs_return_samples = []
        self.tweets_last_cycle_samples = []
        self.tweets_last_2_cycles_samples = []
        
        # Counters for sampling
        self.n_spread = 0
        self.n_liq = 0
        self.n_return = 0
        self.n_tweets_lc = 0
        self.n_tweets_l2c = 0
        
        # Missing data tracking
        self.missing_spread = 0
        self.missing_liq = 0
        self.missing_return = 0
        self.missing_tweets_lc = 0
        self.missing_tweets_l2c = 0
        
        # Per-day tweet volume (for time series)
        self.daily_tweets = {}  # date -> list of last_cycle tweet counts
        
        # Per-symbol aggregation (for top-20 charts)
        self.per_symbol = {}  # symbol -> {tweets_lc: [], spread_bps: [], liq_qv_usd: []}
        
        # Date range tracking
        self.first_day = None
        self.last_day = None
        
        # Total usable entries processed
        self.usable_count = 0
    
    def add_entry(self, entry: dict, date: str):
        """Process one usable entry."""
        self.usable_count += 1
        
        # Track date range
        if self.first_day is None or date < self.first_day:
            self.first_day = date
        if self.last_day is None or date > self.last_day:
            self.last_day = date
        
        # Extract symbol for per-symbol tracking
        symbol = entry.get("symbol", "UNKNOWN")
        if symbol not in self.per_symbol:
            self.per_symbol[symbol] = {
                "tweets_lc": [],
                "spread_bps": [],
                "liq_qv_usd": []
            }
        
        # Extract spread_bps
        spot_raw = entry.get("spot_raw", {})
        spread_bps = spot_raw.get("spread_bps")
        if is_valid_number(spread_bps) and spread_bps >= 0:
            spread_val = float(spread_bps)
            self.n_spread = reservoir_sample(
                spread_val, 
                self.spread_bps_samples, 
                self.max_samples, 
                self.n_spread
            )
            # Track per-symbol (bounded to avoid memory issues)
            if len(self.per_symbol[symbol]["spread_bps"]) < 10_000:
                self.per_symbol[symbol]["spread_bps"].append(spread_val)
        else:
            self.missing_spread += 1
        
        # Extract liq_qv_usd
        liq_qv_usd = spot_raw.get("liq_qv_usd")
        if is_valid_number(liq_qv_usd) and liq_qv_usd >= 0:
            liq_val = float(liq_qv_usd)
            self.n_liq = reservoir_sample(
                liq_val, 
                self.liq_qv_usd_samples, 
                self.max_samples, 
                self.n_liq
            )
            # Track per-symbol (bounded)
            if len(self.per_symbol[symbol]["liq_qv_usd"]) < 10_000:
                self.per_symbol[symbol]["liq_qv_usd"].append(liq_val)
        else:
            self.missing_liq += 1
        
        # Compute abs_return
        spot_prices = entry.get("spot_prices", [])
        abs_ret = compute_abs_return(spot_prices)
        if abs_ret is not None:
            self.n_return = reservoir_sample(
                abs_ret, 
                self.abs_return_samples, 
                self.max_samples, 
                self.n_return
            )
        else:
            self.missing_return += 1
        
        # Extract tweet counts
        tweets_lc = get_tweets_last_cycle(entry)
        if tweets_lc is not None and tweets_lc >= 0:
            self.n_tweets_lc = reservoir_sample(
                tweets_lc, 
                self.tweets_last_cycle_samples, 
                self.max_samples, 
                self.n_tweets_lc
            )
            
            # Track for daily time series
            if date not in self.daily_tweets:
                self.daily_tweets[date] = []
            # Also use bounded sampling per day to avoid memory issues
            if len(self.daily_tweets[date]) < 50_000:
                self.daily_tweets[date].append(tweets_lc)
            
            # Track per-symbol (bounded)
            if len(self.per_symbol[symbol]["tweets_lc"]) < 10_000:
                self.per_symbol[symbol]["tweets_lc"].append(tweets_lc)
        else:
            self.missing_tweets_lc += 1
        
        tweets_l2c = get_tweets_last_2_cycles(entry)
        if tweets_l2c is not None and tweets_l2c >= 0:
            self.n_tweets_l2c = reservoir_sample(
                tweets_l2c, 
                self.tweets_last_2_cycles_samples, 
                self.max_samples, 
                self.n_tweets_l2c
            )
        else:
            self.missing_tweets_l2c += 1
    
    def get_daily_tweet_stats(self) -> List[Dict]:
        """
        Compute per-day tweet volume statistics.
        
        Returns:
            List of {"date": str, "median": float, "p90": float}
        """
        import statistics
        
        daily_stats = []
        for date in sorted(self.daily_tweets.keys()):
            counts = self.daily_tweets[date]
            if len(counts) == 0:
                continue
            
            median = statistics.median(counts)
            p90 = statistics.quantiles(counts, n=10)[8] if len(counts) >= 10 else max(counts)
            
            daily_stats.append({
                "date": date,
                "median": median,
                "p90": p90
            })
        
        return daily_stats
    
    def get_top_symbols(self, metric: str, min_samples: int = 30, top_n: int = 20) -> List[Dict]:
        """
        Get top symbols by sample count with median values for a metric.
        
        Args:
            metric: One of 'tweets_lc', 'spread_bps', 'liq_qv_usd'
            min_samples: Minimum samples required per symbol
            top_n: Number of top symbols to return
        
        Returns:
            List of {"symbol": str, "median": float, "count": int}
            sorted by sample count descending
        """
        import statistics
        
        symbol_stats = []
        for symbol, data in self.per_symbol.items():
            samples = data.get(metric, [])
            if len(samples) >= min_samples:
                median = statistics.median(samples)
                symbol_stats.append({
                    "symbol": symbol,
                    "median": median,
                    "count": len(samples)
                })
        
        # Sort by sample count (most samples first = most stable)
        symbol_stats.sort(key=lambda x: x["count"], reverse=True)
        
        return symbol_stats[:top_n]
    
    def print_summary(self):
        """Print ASCII-only summary."""
        print(f"  Usable entries processed: {self.usable_count}")
        print(f"  Samples collected:")
        print(f"    spread_bps: {len(self.spread_bps_samples)} (missing: {self.missing_spread})")
        print(f"    liq_qv_usd: {len(self.liq_qv_usd_samples)} (missing: {self.missing_liq})")
        print(f"    abs_return: {len(self.abs_return_samples)} (missing: {self.missing_return})")
        print(f"    tweets_last_cycle: {len(self.tweets_last_cycle_samples)} (missing: {self.missing_tweets_lc})")
        print(f"    tweets_last_2_cycles: {len(self.tweets_last_2_cycles_samples)} (missing: {self.missing_tweets_l2c})")
        
        # Missing rate for tweets
        if self.usable_count > 0:
            missing_rate = (self.missing_tweets_lc / self.usable_count) * 100
            print(f"  Tweet count missing rate: {missing_rate:.1f}%")


def compute_insights(archive_path: Path, is_usable_fn) -> InsightsAggregator:
    """
    Compute insights by streaming through archive.
    
    Args:
        archive_path: Path to CryptoBot archive
        is_usable_fn: Function to check if entry is usable (must match daily_stats gate)
    
    Returns:
        InsightsAggregator with collected samples
    """
    aggregator = InsightsAggregator()
    
    if not archive_path.exists():
        print(f"[WARN] Archive path does not exist: {archive_path}")
        return aggregator
    
    # Find all day folders
    day_folders = sorted([d for d in archive_path.iterdir() 
                         if d.is_dir() and d.name.isdigit() and len(d.name) == 8])
    
    print(f"Scanning {len(day_folders)} day folders for insights...")
    
    for day_folder in day_folders:
        day_str = day_folder.name  # YYYYMMDD
        
        # Parse date
        try:
            date_obj = datetime.strptime(day_str, "%Y%m%d")
            date_iso = date_obj.strftime("%Y-%m-%d")
        except ValueError:
            continue
        
        # Scan all jsonl.gz files in this day
        jsonl_files = list(day_folder.glob("*.jsonl.gz"))
        
        for jsonl_file in jsonl_files:
            try:
                with gzip.open(jsonl_file, 'rt', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        try:
                            entry = json.loads(line)
                            
                            # Check if usable using the same gate as daily_stats
                            is_usable, reason = is_usable_fn(entry)
                            if is_usable:
                                aggregator.add_entry(entry, date_iso)
                        
                        except json.JSONDecodeError:
                            continue
            
            except Exception as e:
                print(f"  Warning: Could not read {jsonl_file.name}: {e}")
                continue
    
    return aggregator
