#!/bin/bash

# Stop on error
set -e

echo "🚀 Building Static Website for Deployment..."

PYTHON_BIN="${PYTHON_BIN:-$(pwd)/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3)"
fi

echo "🧬 Refreshing contracts and demo artifacts..."
"$PYTHON_BIN" - <<'PY'
from replay.services import build_demo_artifacts

build_demo_artifacts()
PY

cd web

# 1. Install dependencies
echo "📦 Installing dependencies..."
if [ -f package-lock.json ]; then
    npm ci
else
    npm install
fi

# 2. Build static export
echo "🏗️  Building project..."
npm run build

echo ""
echo "✅ Build Successful!"
echo "📂 The website files are in: $(pwd)/out"
echo ""
echo "👉 How to publish:"
echo "   Option 1: Drag the 'web/out' folder to https://app.netlify.com/drop"
echo "   Option 2: Push this code to GitHub and enable GitHub Pages."
echo ""

if command -v open >/dev/null 2>&1; then
    # macOS Finder
    open out
elif command -v xdg-open >/dev/null 2>&1; then
    # Linux desktop environments
    xdg-open out
else
    echo "ℹ️  Open the output folder manually: $(pwd)/out"
fi
