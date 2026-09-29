#!/usr/bin/env bash
# Urban Watch — Canonical Development Server Startup
# Usage: ./scripts/run_dev.sh [--backend-only | --frontend-only]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend-react"

run_backend() {
  echo "==> Starting backend on http://localhost:8000 ..."
  cd "$BACKEND_DIR"

  # Activate venv if present
  if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
  fi

  # --reload-exclude venv/* prevents the infinite-reload loop caused by
  # uvicorn watching installed packages inside the venv directory.
  uvicorn main:app \
    --port 8000 \
    --reload \
    --reload-exclude "venv/*" \
    --reload-exclude "__pycache__/*" \
    --reload-exclude "*.pyc" \
    --reload-exclude "uploads/*" \
    --reload-exclude "results/*" \
    --log-level info
}

run_frontend() {
  echo "==> Starting frontend on http://localhost:5173 ..."
  cd "$FRONTEND_DIR"
  npm run dev
}

case "${1:-both}" in
  --backend-only)
    run_backend
    ;;
  --frontend-only)
    run_frontend
    ;;
  *)
    # Run both — backend in background, frontend in foreground
    run_backend &
    BACKEND_PID=$!
    trap "kill $BACKEND_PID 2>/dev/null; exit" INT TERM EXIT
    sleep 2
    run_frontend
    ;;
esac
