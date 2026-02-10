#!/bin/bash
# Longevity Lab - Daily Content Pipeline + Auto Deploy
# 매일 오전 7시에 자동 실행 (launchd)
# 1. 논문 수집 + AI 분석 → JSON 생성
# 2. frontend/content/에 복사
# 3. Vercel 프로덕션 배포

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
LOG_FILE="$SCRIPT_DIR/pipeline.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

log "=== Pipeline started ==="

cd "$SCRIPT_DIR"

# Activate venv if exists
if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
fi

# Step 1: Run content pipeline (fetch papers + AI analysis)
log "Step 1: Running content pipeline..."
set +e
PYTHONUNBUFFERED=1 python3 content_pipeline.py >> "$LOG_FILE" 2>&1
EXIT_CODE=$?
set -e

if [ $EXIT_CODE -ne 0 ]; then
    log "Step 1 FAILED with exit code $EXIT_CODE"
    echo "---" >> "$LOG_FILE"
    exit $EXIT_CODE
fi
log "Step 1: Content generation complete"

# Step 2: Copy content to frontend
log "Step 2: Copying content to frontend..."
mkdir -p "$FRONTEND_DIR/content"

BEFORE_COUNT=$(ls "$FRONTEND_DIR/content/"*.json 2>/dev/null | wc -l | tr -d ' ')
cp "$SCRIPT_DIR/content_drafts/"*.json "$FRONTEND_DIR/content/" 2>/dev/null || true
AFTER_COUNT=$(ls "$FRONTEND_DIR/content/"*.json 2>/dev/null | wc -l | tr -d ' ')

log "Step 2: $BEFORE_COUNT → $AFTER_COUNT articles"

if [ "$BEFORE_COUNT" -eq "$AFTER_COUNT" ]; then
    # Check if file contents actually changed
    DIFF=$(diff -rq "$SCRIPT_DIR/content_drafts/" "$FRONTEND_DIR/content/" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$DIFF" -eq 0 ]; then
        log "No content changes detected, skipping deploy"
        log "=== Pipeline finished (no changes) ==="
        echo "---" >> "$LOG_FILE"
        exit 0
    fi
fi

# Step 3: Deploy to Vercel
log "Step 3: Deploying to Vercel..."
cd "$FRONTEND_DIR"
set +e
vercel --prod --yes >> "$LOG_FILE" 2>&1
EXIT_CODE=$?
set -e
if [ $EXIT_CODE -ne 0 ]; then
    log "Step 3 FAILED with exit code $EXIT_CODE"
    echo "---" >> "$LOG_FILE"
    exit $EXIT_CODE
fi
log "Step 3: Vercel deploy complete"

# Step 4: Trigger newsletter digest (optional)
# This relies on Vercel function + Resend env vars configured in production.
if [ "${TRIGGER_DIGEST:-false}" = "true" ]; then
    if [ -z "${DIGEST_URL:-}" ] || [ -z "${CRON_SECRET:-}" ]; then
        log "Step 4: Skipped digest trigger (missing DIGEST_URL or CRON_SECRET)"
    else
        log "Step 4: Triggering digest..."
        curl -fsS -X POST \
            -H "Authorization: Bearer ${CRON_SECRET}" \
            -H "Content-Type: application/json" \
            "$DIGEST_URL" >> "$LOG_FILE" 2>&1 || log "Step 4: Digest trigger failed"
        log "Step 4: Digest trigger complete"
    fi
fi

log "=== Pipeline finished successfully ==="
echo "---" >> "$LOG_FILE"
