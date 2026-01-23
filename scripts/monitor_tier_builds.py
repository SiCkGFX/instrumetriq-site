#!/usr/bin/env python3
"""
Tier Build Monitor - Verifies daily tier builds are complete and uploaded to R2

This script runs via cron every 10 minutes and checks:
1. Local tier parquet files exist for the expected date
2. R2 uploads exist for all 3 tiers
3. Alerts via Telegram if any tier is missing after the expected build time

Expected build schedule (UTC):
- Tier 3: 00:10 UTC
- Tier 2: 00:20 UTC  
- Tier 1: 00:30 UTC

After 01:00 UTC, all tiers should be present. Alerts fire if missing.

Run via cron every 10 minutes:
    */10 * * * * cd /srv/instrumetriq && python3 scripts/monitor_tier_builds.py >> logs/tier_monitor.log 2>&1
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from typing import Optional

# Add scripts directory to path for r2_config
sys.path.insert(0, str(Path(__file__).parent))

# ============================================================================
# CONFIGURATION
# ============================================================================

# Paths
INSTRUMETRIQ_ROOT = Path("/srv/instrumetriq")
OUTPUT_DIR = INSTRUMETRIQ_ROOT / "output"
LOG_DIR = INSTRUMETRIQ_ROOT / "logs"
STATE_FILE = LOG_DIR / "tier_monitor_state.json"

# Tier configuration
TIERS = {
    "tier1": {
        "local_dir": OUTPUT_DIR / "tier1_daily",
        "r2_prefix": "tier1/daily",
        "expected_after_utc_hour": 0,
        "expected_after_utc_minute": 35,  # 5 min buffer after 00:30
    },
    "tier2": {
        "local_dir": OUTPUT_DIR / "tier2_daily",
        "r2_prefix": "tier2/daily",
        "expected_after_utc_hour": 0,
        "expected_after_utc_minute": 25,  # 5 min buffer after 00:20
    },
    "tier3": {
        "local_dir": OUTPUT_DIR / "tier3_daily",
        "r2_prefix": "tier3/daily",
        "expected_after_utc_hour": 0,
        "expected_after_utc_minute": 15,  # 5 min buffer after 00:10
    },
}

# Alert settings
ALERT_COOLDOWN_SECONDS = 3600  # Don't spam - 1 alert per tier per hour

# ============================================================================
# TELEGRAM INTEGRATION
# ============================================================================

def get_telegram_config() -> tuple[Optional[str], Optional[str], bool]:
    """Load Telegram config from environment."""
    # Try to load .env if dotenv available
    try:
        from dotenv import load_dotenv
        env_path = Path("/srv/twscrape/.env")
        if env_path.exists():
            load_dotenv(env_path)
    except ImportError:
        pass
    
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    enabled = os.environ.get("TELEGRAM_ALERT", "false").lower() == "true"
    
    return token, chat_id, enabled


def send_telegram_alert(message: str) -> bool:
    """Send alert via Telegram."""
    token, chat_id, enabled = get_telegram_config()
    
    if not enabled or not token or not chat_id:
        print(f"[TELEGRAM DISABLED] Would send: {message}")
        return False
    
    try:
        import urllib.request
        import urllib.parse
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }).encode()
        
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status == 200
            
    except Exception as e:
        print(f"[ERROR] Telegram send failed: {e}")
        return False


# ============================================================================
# STATE MANAGEMENT
# ============================================================================

def load_state() -> dict:
    """Load monitor state from file."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_alerts": {}, "last_success": {}}


def save_state(state: dict):
    """Save monitor state to file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def should_alert(state: dict, tier: str, now: datetime) -> bool:
    """Check if we should send an alert (respects cooldown)."""
    last_alert = state.get("last_alerts", {}).get(tier)
    if not last_alert:
        return True
    
    last_alert_time = datetime.fromisoformat(last_alert)
    elapsed = (now - last_alert_time).total_seconds()
    return elapsed >= ALERT_COOLDOWN_SECONDS


def record_alert(state: dict, tier: str, now: datetime):
    """Record that we sent an alert."""
    if "last_alerts" not in state:
        state["last_alerts"] = {}
    state["last_alerts"][tier] = now.isoformat()


def record_success(state: dict, tier: str, date_str: str, now: datetime):
    """Record successful verification."""
    if "last_success" not in state:
        state["last_success"] = {}
    state["last_success"][tier] = {
        "date": date_str,
        "verified_at": now.isoformat()
    }


# ============================================================================
# VERIFICATION LOGIC
# ============================================================================

def get_expected_date() -> str:
    """
    Get the date we expect to have built.
    
    After midnight UTC, we expect yesterday's data to be built.
    The archive for day D finishes at ~23:55 UTC on day D.
    Builders run at 00:10-00:30 UTC on day D+1, building day D.
    """
    now = datetime.now(timezone.utc)
    
    # Before 00:10 UTC, we're still expecting the previous day's previous day
    # After 00:10 UTC, we expect yesterday to be built
    if now.hour == 0 and now.minute < 10:
        # Still too early, check 2 days ago
        target = now - timedelta(days=2)
    else:
        # Check yesterday
        target = now - timedelta(days=1)
    
    return target.strftime("%Y-%m-%d")


def check_local_exists(tier: str, date_str: str) -> bool:
    """Check if local parquet file exists for the tier/date."""
    config = TIERS[tier]
    parquet_path = config["local_dir"] / date_str / "data.parquet"
    return parquet_path.exists()


def check_r2_exists(tier: str, date_str: str) -> bool:
    """Check if R2 object exists for the tier/date."""
    try:
        from r2_config import get_r2_config
        import boto3
        
        config = get_r2_config()
        client = boto3.client(
            's3',
            endpoint_url=config.endpoint,
            aws_access_key_id=config.access_key_id,
            aws_secret_access_key=config.secret_access_key,
            region_name='auto'
        )
        
        tier_config = TIERS[tier]
        key = f"{tier_config['r2_prefix']}/{date_str}/data.parquet"
        
        client.head_object(Bucket=config.bucket, Key=key)
        return True
        
    except Exception as e:
        if "404" in str(e) or "Not Found" in str(e) or "NoSuchKey" in str(e):
            return False
        # Log other errors but don't treat as missing
        print(f"[WARN] R2 check error for {tier}/{date_str}: {e}")
        return False


def is_past_expected_time(tier: str) -> bool:
    """Check if we're past the expected build completion time."""
    now = datetime.now(timezone.utc)
    config = TIERS[tier]
    
    expected_hour = config["expected_after_utc_hour"]
    expected_minute = config["expected_after_utc_minute"]
    
    if now.hour > expected_hour:
        return True
    if now.hour == expected_hour and now.minute >= expected_minute:
        return True
    return False


# ============================================================================
# MAIN MONITOR LOOP
# ============================================================================

def run_monitor():
    """Main monitoring function."""
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    
    print(f"\n[{timestamp}] Tier Build Monitor Check")
    print("=" * 60)
    
    state = load_state()
    expected_date = get_expected_date()
    
    print(f"Expected date: {expected_date}")
    print()
    
    issues = []
    
    for tier in ["tier3", "tier2", "tier1"]:  # Check in build order
        config = TIERS[tier]
        
        # Check if we're past the expected build time
        if not is_past_expected_time(tier):
            print(f"[{tier.upper()}] ⏳ Not yet expected (builds at {config['expected_after_utc_hour']:02d}:{config['expected_after_utc_minute']:02d} UTC)")
            continue
        
        # Check local file
        local_ok = check_local_exists(tier, expected_date)
        
        # Check R2
        r2_ok = check_r2_exists(tier, expected_date)
        
        if local_ok and r2_ok:
            print(f"[{tier.upper()}] ✓ Local: OK | R2: OK | Date: {expected_date}")
            record_success(state, tier, expected_date, now)
        else:
            status_parts = []
            if not local_ok:
                status_parts.append("LOCAL MISSING")
            if not r2_ok:
                status_parts.append("R2 MISSING")
            
            status = " | ".join(status_parts)
            print(f"[{tier.upper()}] ✗ {status} | Date: {expected_date}")
            
            issues.append({
                "tier": tier,
                "date": expected_date,
                "local_ok": local_ok,
                "r2_ok": r2_ok,
            })
    
    # Send alerts for issues
    if issues:
        for issue in issues:
            tier = issue["tier"]
            
            if should_alert(state, tier, now):
                alert_msg = (
                    f"🚨 <b>Instrumetriq Tier Build Alert</b>\n\n"
                    f"<b>Tier:</b> {tier.upper()}\n"
                    f"<b>Date:</b> {issue['date']}\n"
                    f"<b>Local file:</b> {'✓' if issue['local_ok'] else '✗ MISSING'}\n"
                    f"<b>R2 upload:</b> {'✓' if issue['r2_ok'] else '✗ MISSING'}\n\n"
                    f"Expected by: {TIERS[tier]['expected_after_utc_hour']:02d}:{TIERS[tier]['expected_after_utc_minute']:02d} UTC\n"
                    f"Checked at: {timestamp}"
                )
                
                if send_telegram_alert(alert_msg):
                    print(f"  → Alert sent for {tier}")
                    record_alert(state, tier, now)
                else:
                    print(f"  → Alert send failed for {tier}")
    else:
        print("\n✓ All tier builds verified")
    
    save_state(state)
    print()


if __name__ == "__main__":
    # Ensure log directory exists
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        run_monitor()
    except Exception as e:
        print(f"[ERROR] Monitor failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
