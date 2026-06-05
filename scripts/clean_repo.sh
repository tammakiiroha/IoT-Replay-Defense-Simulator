#!/usr/bin/env bash
# Remove macOS sidecars and untrack generated/dependency dirs that should never be committed.
# Safe to run repeatedly. Does not touch source files.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "[clean_repo] deleting macOS sidecar files..."
find . -name '._*' -type f -not -path './.git/*' -delete || true
find . -name '.DS_Store' -type f -not -path './.git/*' -delete || true

echo "[clean_repo] untracking generated/dependency dirs (no-op if already untracked)..."
git rm -r --cached --ignore-unmatch \
  .venv \
  web/node_modules \
  web/.next \
  web/out \
  web/tsconfig.tsbuildinfo \
  .mypy_cache \
  .ruff_cache \
  .pytest_cache \
  .serena/cache >/dev/null 2>&1 || true

echo "[clean_repo] done. Review 'git status' before committing."
