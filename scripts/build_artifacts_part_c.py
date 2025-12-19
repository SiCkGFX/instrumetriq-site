#!/usr/bin/env python3
"""
build_artifacts_part_c.py
==========================

Generate TRANSPARENCY artifacts:
  1) Hybrid decision breakdown (C1)
  2) Confidence vs disagreement (C2)
  3) Lifecycle summary per symbol (C3)

Outputs:
  - public/data/artifacts/hybrid_decisions_v7.json
  - public/data/artifacts/confidence_disagreement_v7.json
  - public/data/artifacts/lifecycle_summary_v7.json

Usage:
  python scripts/build_artifacts_part_c.py

Testing:
  set ARTIFACT_SCAN_LIMIT=2000
  python scripts/build_artifacts_part_c.py
"""

import gzip
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional


# ============================================================================
# Configuration
# ============================================================================

ARCHIVE_ROOT = Path("D:/Sentiment-Data/CryptoBot/data/archive")
OUTPUT_DIR = Path("public/data/artifacts")

# Confidence bins: 5 bins from 0 to 1
CONFIDENCE_BINS = [
    (0.0, 0.2),
    (0.2, 0.4),
    (0.4, 0.6),
    (0.6, 0.8),
    (0.8, 1.0),
]


# ============================================================================
# Usable v7 gate (same as Parts A/B)
# ============================================================================

def is_usable_v7_entry(entry: Dict[str, Any]) -> bool:
    """
    Same gate as build_artifacts_part_a.py and part_b.py.
    Returns True if entry passes all usability checks.
    """
    # Must be schema v7
    meta = entry.get("meta", {})
    if meta.get("schema_version") != 7:
        return False
    
    # Must have spot_prices list with 700+ samples
    spot_prices = entry.get("spot_prices")
    if not isinstance(spot_prices, list):
        return False
    if len(spot_prices) < 700:
        return False
    
    # Must have spot_raw with required keys
    spot_raw = entry.get("spot_raw", {})
    required_keys = ["mid", "bid", "ask", "spread_bps"]
    if not all(k in spot_raw for k in required_keys):
        return False
    
    # Must have twitter_sentiment_windows with at least one cycle
    tsw = entry.get("twitter_sentiment_windows", {})
    has_last_cycle = "last_cycle" in tsw and isinstance(tsw["last_cycle"], dict)
    has_last_2_cycles = "last_2_cycles" in tsw and isinstance(tsw["last_2_cycles"], dict)
    
    if not (has_last_cycle or has_last_2_cycles):
        return False
    
    return True


# ============================================================================
# C1: Hybrid Decision Tracker
# ============================================================================

class HybridDecisionTracker:
    """
    Track hybrid decision breakdown across all entries.
    Aggregates decision_sources and posts_scored.
    """
    
    def __init__(self):
        # Decision source counts
        self.primary_lexicon = 0
        self.primary_ai = 0
        self.referee_override = 0
        self.full_agreement = 0
        
        # Posts scored tracking
        self.posts_scored_total = 0
        self.entries_with_posts = 0
        
        # Coverage
        self.total_usable = 0
        self.entries_with_decision_sources = 0
    
    def ingest(self, entry: Dict[str, Any]) -> None:
        """Process one usable v7 entry."""
        self.total_usable += 1
        
        # Extract hybrid_decision_stats
        tsw = entry.get("twitter_sentiment_windows", {})
        last_cycle = tsw.get("last_cycle", {})
        hybrid_stats = last_cycle.get("hybrid_decision_stats", {})
        
        # Extract decision_sources
        decision_sources = hybrid_stats.get("decision_sources", {})
        if decision_sources:
            self.entries_with_decision_sources += 1
            
            self.primary_lexicon += decision_sources.get("primary_lexicon", 0)
            self.primary_ai += decision_sources.get("primary_ai", 0)
            self.referee_override += decision_sources.get("referee_override", 0)
            self.full_agreement += decision_sources.get("full_agreement", 0)
        
        # Extract posts_scored
        posts_scored = hybrid_stats.get("posts_scored")
        if posts_scored is not None and posts_scored > 0:
            self.entries_with_posts += 1
            self.posts_scored_total += posts_scored
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        # Total decisions
        total_decisions = (
            self.primary_lexicon +
            self.primary_ai +
            self.referee_override +
            self.full_agreement
        )
        
        # Compute percentages
        if total_decisions > 0:
            pct_primary_lexicon = self.primary_lexicon / total_decisions
            pct_primary_ai = self.primary_ai / total_decisions
            pct_referee_override = self.referee_override / total_decisions
            pct_full_agreement = self.full_agreement / total_decisions
        else:
            pct_primary_lexicon = 0
            pct_primary_ai = 0
            pct_referee_override = 0
            pct_full_agreement = 0
        
        return {
            "description": "Hybrid decision breakdown showing how sentiment decisions are made. Transparency into primary vs referee roles.",
            "data_version": "v7",
            "coverage": {
                "total_usable_entries": self.total_usable,
                "entries_with_decision_sources": self.entries_with_decision_sources,
            },
            "decision_sources": {
                "primary_lexicon": {
                    "count": self.primary_lexicon,
                    "percentage": round(pct_primary_lexicon, 4),
                },
                "primary_ai": {
                    "count": self.primary_ai,
                    "percentage": round(pct_primary_ai, 4),
                },
                "referee_override": {
                    "count": self.referee_override,
                    "percentage": round(pct_referee_override, 4),
                },
                "full_agreement": {
                    "count": self.full_agreement,
                    "percentage": round(pct_full_agreement, 4),
                },
                "total": total_decisions,
            },
            "posts_scored": {
                "total": self.posts_scored_total,
                "entries_with_posts": self.entries_with_posts,
            },
        }


# ============================================================================
# C2: Confidence/Disagreement Tracker
# ============================================================================

class ConfidenceDisagreementTracker:
    """
    Track confidence vs disagreement patterns.
    Bins by referee_conf_mean, tracks disagreement rate.
    """
    
    def __init__(self):
        # Bins: dict from bin_label -> {"samples": [...], "disagreements": count}
        self.bins: Dict[str, Dict[str, Any]] = {}
        for low, high in CONFIDENCE_BINS:
            label = f"[{low:.1f}..{high:.1f})"
            self.bins[label] = {
                "samples": [],
                "disagreements": 0,
            }
        
        # Coverage
        self.total_usable = 0
        self.entries_with_referee_conf = 0
    
    def ingest(self, entry: Dict[str, Any]) -> None:
        """Process one usable v7 entry."""
        self.total_usable += 1
        
        # Extract confidence and decision sources
        tsw = entry.get("twitter_sentiment_windows", {})
        last_cycle = tsw.get("last_cycle", {})
        hybrid_stats = last_cycle.get("hybrid_decision_stats", {})
        
        referee_conf = hybrid_stats.get("referee_conf_mean")
        decision_sources = hybrid_stats.get("decision_sources", {})
        
        if referee_conf is None:
            return
        
        self.entries_with_referee_conf += 1
        
        # Determine if there was disagreement (referee override)
        has_disagreement = decision_sources.get("referee_override", 0) > 0
        
        # Find matching bin
        for low, high in CONFIDENCE_BINS:
            if low <= referee_conf < high:
                label = f"[{low:.1f}..{high:.1f})"
                self.bins[label]["samples"].append(referee_conf)
                if has_disagreement:
                    self.bins[label]["disagreements"] += 1
                break
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        bins_data = []
        
        for low, high in CONFIDENCE_BINS:
            label = f"[{low:.1f}..{high:.1f})"
            bin_info = self.bins[label]
            
            sample_count = len(bin_info["samples"])
            disagreement_count = bin_info["disagreements"]
            
            if sample_count > 0:
                disagreement_rate = disagreement_count / sample_count
            else:
                disagreement_rate = None
            
            bins_data.append({
                "bin_label": label,
                "bin_low": low,
                "bin_high": high,
                "sample_count": sample_count,
                "disagreement_count": disagreement_count,
                "disagreement_rate": round(disagreement_rate, 4) if disagreement_rate is not None else None,
            })
        
        return {
            "description": "Confidence vs disagreement patterns. Shows when referee overrides primary decision, binned by referee confidence. Descriptive only.",
            "data_version": "v7",
            "coverage": {
                "total_usable_entries": self.total_usable,
                "entries_with_referee_conf": self.entries_with_referee_conf,
            },
            "bins": bins_data,
        }


# ============================================================================
# C3: Lifecycle Summary Tracker
# ============================================================================

class LifecycleSummaryTracker:
    """
    Track lifecycle metrics per symbol.
    Aggregates sessions, durations, dates, scores.
    """
    
    def __init__(self):
        # Per-symbol tracking: symbol -> {"sessions": [...], "durations": [...], ...}
        self.symbols: Dict[str, Dict[str, Any]] = {}
        
        # Coverage
        self.total_usable = 0
    
    def ingest(self, entry: Dict[str, Any], date_iso: str = None) -> None:
        """Process one usable v7 entry."""
        self.total_usable += 1
        
        # Extract symbol
        symbol = entry.get("symbol")
        if not symbol:
            return
        
        # Initialize symbol tracking if needed
        if symbol not in self.symbols:
            self.symbols[symbol] = {
                "sessions": set(),
                "durations": [],
                "dates": set(),
                "final_scores": [],
            }
        
        symbol_data = self.symbols[symbol]
        
        # Extract meta fields
        meta = entry.get("meta", {})
        session_id = meta.get("session_id")
        duration_sec = meta.get("duration_sec")
        
        # Track session
        if session_id:
            symbol_data["sessions"].add(session_id)
        
        # Track duration
        if duration_sec is not None and duration_sec > 0:
            symbol_data["durations"].append(duration_sec)
        
        # Track date
        if date_iso:
            symbol_data["dates"].add(date_iso)
        
        # Extract final score (mean_score from hybrid_decision_stats)
        tsw = entry.get("twitter_sentiment_windows", {})
        last_cycle = tsw.get("last_cycle", {})
        hybrid_stats = last_cycle.get("hybrid_decision_stats", {})
        mean_score = hybrid_stats.get("mean_score")
        
        if mean_score is not None:
            symbol_data["final_scores"].append(mean_score)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        symbols_summary = []
        
        for symbol in sorted(self.symbols.keys()):
            data = self.symbols[symbol]
            
            # Compute aggregates
            sessions_count = len(data["sessions"])
            
            if data["durations"]:
                median_duration_sec = median(data["durations"])
            else:
                median_duration_sec = None
            
            dates_list = sorted(data["dates"])
            first_seen_day = dates_list[0] if dates_list else None
            last_seen_day = dates_list[-1] if dates_list else None
            
            if data["final_scores"]:
                median_final_score = median(data["final_scores"])
            else:
                median_final_score = None
            
            symbols_summary.append({
                "symbol": symbol,
                "sessions_count": sessions_count,
                "median_duration_sec": round(median_duration_sec, 1) if median_duration_sec is not None else None,
                "first_seen_day": first_seen_day,
                "last_seen_day": last_seen_day,
                "median_final_score": round(median_final_score, 6) if median_final_score is not None else None,
            })
        
        return {
            "description": "Lifecycle summary per symbol. Aggregated session counts, durations, date ranges, and final scores. No raw session data exposed.",
            "data_version": "v7",
            "symbols_count": len(symbols_summary),
            "symbols": symbols_summary,
        }


# ============================================================================
# Archive scanning
# ============================================================================

def scan_archive(
    hybrid_tracker: HybridDecisionTracker,
    confidence_tracker: ConfidenceDisagreementTracker,
    lifecycle_tracker: LifecycleSummaryTracker,
) -> int:
    """
    Stream through archive, filter for usable v7, feed to trackers.
    Returns total entries scanned.
    """
    scan_limit = os.getenv("ARTIFACT_SCAN_LIMIT")
    if scan_limit:
        try:
            scan_limit = int(scan_limit)
            print(f"[SCAN] Limit set to {scan_limit}")
        except ValueError:
            scan_limit = None
    
    if not ARCHIVE_ROOT.exists():
        print(f"[ERROR] Archive root not found: {ARCHIVE_ROOT}")
        sys.exit(1)
    
    day_folders = sorted([d for d in ARCHIVE_ROOT.iterdir() if d.is_dir()])
    
    scanned = 0
    v7_count = 0
    usable_count = 0
    
    for day_folder in day_folders:
        day_str = day_folder.name  # YYYYMMDD
        
        # Parse date
        try:
            date_obj = datetime.strptime(day_str, "%Y%m%d")
            date_iso = date_obj.strftime("%Y-%m-%d")
        except ValueError:
            continue
        
        jsonl_files = sorted(day_folder.glob("*.jsonl.gz"))
        
        for jsonl_path in jsonl_files:
            try:
                with gzip.open(jsonl_path, "rt", encoding="utf-8") as f:
                    for line in f:
                        if scan_limit and scanned >= scan_limit:
                            print(f"[SCAN] Reached scan limit {scan_limit}")
                            print(f"[SCAN] Scanned: {scanned}, v7: {v7_count}, usable: {usable_count}")
                            return scanned
                        
                        scanned += 1
                        
                        # Parse entry
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        
                        if not isinstance(entry, dict):
                            continue
                        
                        # Count v7
                        meta = entry.get("meta", {})
                        if meta.get("schema_version") == 7:
                            v7_count += 1
                        
                        # Filter usable
                        if not is_usable_v7_entry(entry):
                            continue
                        
                        usable_count += 1
                        
                        # Feed to trackers
                        hybrid_tracker.ingest(entry)
                        confidence_tracker.ingest(entry)
                        lifecycle_tracker.ingest(entry, date_iso)
                        
            except Exception as e:
                print(f"[WARN] Could not read {jsonl_path.name}: {e}")
                continue
    
    print(f"[SCAN] Scanned: {scanned}, v7: {v7_count}, usable: {usable_count}")
    return scanned


# ============================================================================
# Write outputs
# ============================================================================

def write_artifacts(
    hybrid_tracker: HybridDecisionTracker,
    confidence_tracker: ConfidenceDisagreementTracker,
    lifecycle_tracker: LifecycleSummaryTracker,
) -> None:
    """Write JSON artifacts to output directory."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Hybrid decisions
    hybrid_path = OUTPUT_DIR / "hybrid_decisions_v7.json"
    with open(hybrid_path, "w", encoding="utf-8") as f:
        json.dump(hybrid_tracker.to_dict(), f, indent=2, ensure_ascii=True)
    print(f"[OUT] Wrote {hybrid_path}")
    
    # Confidence/disagreement
    confidence_path = OUTPUT_DIR / "confidence_disagreement_v7.json"
    with open(confidence_path, "w", encoding="utf-8") as f:
        json.dump(confidence_tracker.to_dict(), f, indent=2, ensure_ascii=True)
    print(f"[OUT] Wrote {confidence_path}")
    
    # Lifecycle summary
    lifecycle_path = OUTPUT_DIR / "lifecycle_summary_v7.json"
    with open(lifecycle_path, "w", encoding="utf-8") as f:
        json.dump(lifecycle_tracker.to_dict(), f, indent=2, ensure_ascii=True)
    print(f"[OUT] Wrote {lifecycle_path}")


# ============================================================================
# Main
# ============================================================================

def main():
    print("=" * 60)
    print("Artifact Builder - Part C: Transparency Summaries")
    print("=" * 60)
    
    # Initialize trackers
    hybrid_tracker = HybridDecisionTracker()
    confidence_tracker = ConfidenceDisagreementTracker()
    lifecycle_tracker = LifecycleSummaryTracker()
    
    # Scan archive
    print(f"[SCAN] Archive: {ARCHIVE_ROOT}")
    scan_archive(hybrid_tracker, confidence_tracker, lifecycle_tracker)
    
    # Write outputs
    print(f"[OUT] Output dir: {OUTPUT_DIR}")
    write_artifacts(hybrid_tracker, confidence_tracker, lifecycle_tracker)
    
    print("=" * 60)
    print("[DONE] Artifacts Part C complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
