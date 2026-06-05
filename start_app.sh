#!/bin/bash

set -e

# Kill background processes on exit
trap "trap - SIGTERM && kill -- -$$" SIGINT SIGTERM EXIT

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -z "${PYTHON_BIN:-}" ]; then
    if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
        PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
    else
        PYTHON_BIN="$(command -v python3)"
    fi
fi

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3001}"
NEXT_PUBLIC_API_BASE="${NEXT_PUBLIC_API_BASE:-http://localhost:${BACKEND_PORT}}"
export NEXT_PUBLIC_API_BASE

# Keep local development rooted at "/" unless explicitly overridden.
NEXT_PUBLIC_BASE_PATH="${NEXT_PUBLIC_BASE_PATH:-}"
if [[ -n "$NEXT_PUBLIC_BASE_PATH" && "$NEXT_PUBLIC_BASE_PATH" != /* ]]; then
    NEXT_PUBLIC_BASE_PATH="/$NEXT_PUBLIC_BASE_PATH"
fi
export NEXT_PUBLIC_BASE_PATH

# CORS allowlist for local development.
# Override by exporting CORS_ALLOW_ORIGINS before running this script.
DEFAULT_CORS_ORIGINS="http://localhost:${FRONTEND_PORT},http://127.0.0.1:${FRONTEND_PORT},http://localhost:3000,http://127.0.0.1:3000"
export CORS_ALLOW_ORIGINS="${CORS_ALLOW_ORIGINS:-$DEFAULT_CORS_ORIGINS}"

echo "Syncing web contracts and demo artifacts..."
"$PYTHON_BIN" - <<'PY'
from replay.services import build_demo_artifacts

build_demo_artifacts()
PY

echo "Starting Backend (FastAPI)..."
"$PYTHON_BIN" -m uvicorn api:app --port "$BACKEND_PORT" --reload &
BACKEND_PID=$!

echo "Starting Frontend (Next.js)..."
cd "$SCRIPT_DIR/web"
if [ ! -d node_modules ]; then
    if [ -f package-lock.json ]; then
        npm ci
    else
        npm install
    fi
fi
npm run dev -- -p "$FRONTEND_PORT" &
FRONTEND_PID=$!

FRONTEND_URL="http://localhost:${FRONTEND_PORT}${NEXT_PUBLIC_BASE_PATH}"

echo "=================================================="
echo "Simulator is ready!"
echo "Backend: http://localhost:${BACKEND_PORT}"
echo "Frontend: ${FRONTEND_URL}"
echo "=================================================="

wait $BACKEND_PID $FRONTEND_PID
