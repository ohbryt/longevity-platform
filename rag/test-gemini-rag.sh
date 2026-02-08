#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAG_DIR="$ROOT_DIR/rag"
ENV_FILE="$RAG_DIR/.env.gemini"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing: rag/.env.gemini"
  echo "Run:"
  echo "  cp rag/.env.example.gemini rag/.env.gemini"
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

PORT="${GEMINI_RAG_PORT:-3003}"
URL="http://localhost:${PORT}/api/health"

echo "Testing health endpoint: ${URL}"
curl -fsS "$URL" | node -e "process.stdin.on('data',d=>process.stdout.write(d))"
echo ""
echo "OK"

