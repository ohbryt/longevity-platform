#!/usr/bin/env bash
set -euo pipefail

echo "Gemini RAG setup (local)"
echo "======================="

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAG_DIR="$ROOT_DIR/rag"
ENV_EXAMPLE="$RAG_DIR/.env.example.gemini"
ENV_FILE="$RAG_DIR/.env.gemini"

if [ ! -d "$RAG_DIR" ]; then
  echo "ERROR: rag/ directory not found at: $RAG_DIR"
  exit 1
fi

if [ ! -f "$ENV_EXAMPLE" ]; then
  cat >"$ENV_EXAMPLE" <<'EOF'
# Gemini RAG (example)
# Copy to .env.gemini and fill in real values.

GEMINI_API_KEY="your-gemini-api-key-here"
PINECONE_API_KEY="your-pinecone-api-key-here"
PINECONE_ENVIRONMENT="us-west1-gcp-free"
GEMINI_RAG_PORT=3003
EOF
  echo "Created: rag/.env.example.gemini"
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing: rag/.env.gemini"
  echo "Run:"
  echo "  cp rag/.env.example.gemini rag/.env.gemini"
  echo "  $EDITOR rag/.env.gemini"
  exit 1
fi

echo "OK: rag/.env.gemini exists"
echo ""
echo "Next:"
echo "  1) Start health server: ./start-gemini-rag.sh"
echo "  2) Test:               ./rag/test-gemini-rag.sh"
echo "  3) Frontend dev:       (cd frontend && npm run dev)"

