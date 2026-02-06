#!/bin/bash
# Longevity Lab - Daily Content Pipeline + Auto Deploy
# 매일 오전 7시에 자동 실행 (launchd)
# 1. 논문 수집 + AI 분석 → JSON 생성
# 2. frontend/content/에 복사
# 3. Vercel 프로덕션 배포

set -e

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
python3 content_pipeline.py >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

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
vercel --prod --yes >> "$LOG_FILE" 2>&1
log "Step 3: Vercel deploy complete"

log "=== Pipeline finished successfully ==="
echo "---" >> "$LOG_FILE"
