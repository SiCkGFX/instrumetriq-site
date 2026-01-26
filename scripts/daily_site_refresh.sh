#!/bin/bash
#
# Daily Site Refresh Script
# Regenerates all public/data/*.json artifacts and triggers Cloudflare Pages rebuild
#
# Usage:
#   ./scripts/daily_site_refresh.sh           # Full refresh
#   ./scripts/daily_site_refresh.sh --dry-run # Show what would run
#
# Cron example (run daily at 03:00 UTC):
#   0 3 * * * /srv/instrumetriq/scripts/daily_site_refresh.sh >> /srv/instrumetriq/logs/daily_refresh.log 2>&1
#

set -e  # Exit on error

# ============================================================
# Configuration
# ============================================================
SITE_ROOT="/srv/instrumetriq"
ARCHIVE_PATH="/srv/cryptobot/data/archive"
LOG_DIR="$SITE_ROOT/logs"
TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S UTC")

# Create log directory if needed
mkdir -p "$LOG_DIR"

# ============================================================
# Logging
# ============================================================
log() {
    echo "[$TIMESTAMP] $1"
}

log_section() {
    echo ""
    echo "============================================================"
    echo "[$TIMESTAMP] $1"
    echo "============================================================"
}

# ============================================================
# Check for dry-run mode
# ============================================================
DRY_RUN=false
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
    log "DRY RUN MODE - Commands will be printed but not executed"
fi

run_cmd() {
    if $DRY_RUN; then
        echo "  [DRY-RUN] $1"
    else
        eval "$1"
    fi
}

# ============================================================
# Pre-flight checks
# ============================================================
log_section "Pre-flight checks"

if [[ ! -d "$ARCHIVE_PATH" ]]; then
    log "ERROR: Archive path not found: $ARCHIVE_PATH"
    exit 1
fi

if [[ ! -d "$SITE_ROOT" ]]; then
    log "ERROR: Site root not found: $SITE_ROOT"
    exit 1
fi

log "Archive path: $ARCHIVE_PATH"
log "Site root: $SITE_ROOT"

cd "$SITE_ROOT"

# ============================================================
# Step 1: Sync latest sample data from archive
# ============================================================
log_section "Step 1: Sync sample data from archive"

run_cmd "python3 scripts/sync_from_archive.py --n 200 --archive-path $ARCHIVE_PATH"

# ============================================================
# Step 2: Generate archive statistics (Status page)
# ============================================================
log_section "Step 2: Generate archive stats"

run_cmd "python3 scripts/generate_archive_stats.py --archive-path $ARCHIVE_PATH"

# ============================================================
# Step 3: Generate public samples (Dataset page preview)
# ============================================================
log_section "Step 3: Generate public samples"

run_cmd "python3 scripts/generate_public_samples.py"

# ============================================================
# Step 4: Generate coverage table (Dataset page)
# ============================================================
log_section "Step 4: Generate coverage table"

run_cmd "python3 scripts/generate_coverage_table.py"

# ============================================================
# Step 5: Generate dataset overview (Dataset page)
# ============================================================
log_section "Step 5: Generate dataset overview"

run_cmd "python3 scripts/generate_dataset_overview.py"

# ============================================================
# Step 6: Generate research artifacts (Research page)
# ============================================================
log_section "Step 6: Generate research artifacts"

run_cmd "python3 scripts/generate_research_artifacts.py --archive-path $ARCHIVE_PATH"

# ============================================================
# Step 6b: Generate daily update post (Updates page)
# ============================================================
log_section "Step 6b: Generate daily update post"

run_cmd "python3 scripts/generate_daily_update_post.py"

# ============================================================
# Step 7: Commit changes to git (if any)
# ============================================================
log_section "Step 7: Check for changes"

# Check if there are changes in public/data/ or src/content/updates/
if git diff --quiet public/data/ src/content/updates/; then
    log "No changes detected"
else
    log "Changes detected - committing..."
    run_cmd "git add public/data/ src/content/updates/"
    run_cmd "git commit -m 'chore: Daily site data refresh ($TIMESTAMP)'"
    run_cmd "git push origin main"
    log "Changes pushed to origin/main"
fi

# ============================================================
# Step 8: Trigger Cloudflare Pages rebuild (via webhook or wrangler)
# ============================================================
log_section "Step 8: Trigger Cloudflare rebuild"

# Option A: Use Cloudflare deploy hook (if configured)
if [[ -n "$CLOUDFLARE_DEPLOY_HOOK" ]]; then
    log "Triggering Cloudflare deploy hook..."
    run_cmd "curl -X POST '$CLOUDFLARE_DEPLOY_HOOK'"
    log "Deploy hook triggered"
# Option B: Git push already triggers Cloudflare Pages (if connected to repo)
else
    log "No deploy hook configured - Cloudflare Pages will auto-rebuild from git push"
fi

# ============================================================
# Summary
# ============================================================
log_section "Refresh complete"

log "Generated artifacts:"
ls -la "$SITE_ROOT/public/data/"*.json 2>/dev/null | while read line; do
    echo "  $line"
done

log "Done!"
