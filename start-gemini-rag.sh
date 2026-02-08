#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAG_DIR="$ROOT_DIR/rag"
ENV_FILE="$RAG_DIR/.env.gemini"
ENV_EXAMPLE="$RAG_DIR/.env.example.gemini"

echo "Starting Gemini RAG (local)"
echo "==========================="

if [ ! -d "$RAG_DIR" ]; then
  echo "ERROR: rag/ directory not found at: $RAG_DIR"
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing: rag/.env.gemini"
  if [ -f "$ENV_EXAMPLE" ]; then
    echo "Run:"
    echo "  cp rag/.env.example.gemini rag/.env.gemini"
  else
    echo "Run:"
    echo "  ./setup-complete-gemini-rag.sh"
  fi
  exit 1
fi

# Export vars from .env.gemini for Node.
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

if [ -z "${GEMINI_RAG_PORT:-}" ]; then
  export GEMINI_RAG_PORT=3003
fi

echo "Env loaded from: rag/.env.gemini"
echo "Port: ${GEMINI_RAG_PORT}"
echo ""
echo "Starting health endpoint: GET http://localhost:${GEMINI_RAG_PORT}/api/health"

cd "$RAG_DIR"
exec node health-server.js

