#!/bin/bash
# Longevity Lab - Daily Content Pipeline
# 매일 오전 7시에 자동 실행

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="$SCRIPT_DIR/pipeline.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$TIMESTAMP] Pipeline started" >> "$LOG_FILE"

cd "$SCRIPT_DIR"

# Activate venv if exists
if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
fi

# Run pipeline
python3 content_pipeline.py >> "$LOG_FILE" 2>&1

EXIT_CODE=$?
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

if [ $EXIT_CODE -eq 0 ]; then
    echo "[$TIMESTAMP] Pipeline completed successfully" >> "$LOG_FILE"
else
    echo "[$TIMESTAMP] Pipeline failed with exit code $EXIT_CODE" >> "$LOG_FILE"
fi

echo "---" >> "$LOG_FILE"
