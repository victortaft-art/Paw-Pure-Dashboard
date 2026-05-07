#!/bin/bash
# Daily refresh job — runs amazon_api pipeline, commits new JSONs, pushes.
# Invoked by launchd (see com.pawpure.dailypipeline.plist).
#
# - Never force-pushes.
# - Only commits if there are data changes to track.
# - Exits non-zero if the pipeline fails so launchd surfaces the failure.
set -euo pipefail

PROJECT_ROOT="/Users/victortaft/Documents/Claude/Projects/AI Automations"
LOG_DIR="$PROJECT_ROOT/amazon_api/data/logs"
LOG="$LOG_DIR/cron.log"

mkdir -p "$LOG_DIR"

# Make node/npm/vercel available for any downstream deploy scripts.
export PATH="/Users/victortaft/.local/nodejs/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

{
  echo "============================================================"
  echo "Run started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "============================================================"

  cd "$PROJECT_ROOT"

  echo "→ Running daily pipeline…"
  python3 amazon_api/daily_pipeline.py

  DASHBOARD_DIR="$PROJECT_ROOT/dashboard"
  if [ -d "$DASHBOARD_DIR/.git" ]; then
    DATE=$(date +%Y-%m-%d)
    cd "$DASHBOARD_DIR"
    echo "→ Staging data changes in dashboard/…"
    git add public/data/sc_data public/data/pl_data public/data/manifest.json public/data/active_tracker.json

    if git diff --cached --quiet; then
      echo "  (no data changes — skipping commit)"
    else
      git commit -m "data: auto-refresh $DATE"
      echo "→ Pushing to remote…"
      git push --set-upstream origin HEAD
    fi

    echo "→ Deploying to Vercel (prod)…"
    vercel deploy --prod --yes || echo "  (vercel deploy failed — check token/login)"
  else
    echo "→ dashboard/ is not a git repo; skipping commit/push."
  fi

  echo "Run finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo
} >> "$LOG" 2>&1
