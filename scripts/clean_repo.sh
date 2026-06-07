#!/usr/bin/env bash
# Remove local cache/build outputs that should never be committed.
# Safe to run repeatedly. Does not touch source files, virtualenv contents, or experiment data.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "[clean_repo] deleting Python bytecode and macOS sidecars..."
find . \
  -path './.git' -prune -o \
  -path './.venv' -prune -o \
  -path './web/node_modules' -prune -o \
  -name '__pycache__' -type d -print -exec rm -rf {} +

find . \
  -path './.git' -prune -o \
  -path './.venv' -prune -o \
  -path './web/node_modules' -prune -o \
  \( -name '*.pyc' -o -name '*.pyo' -o -name '._*' -o -name '.DS_Store' \) \
  -type f -print -exec rm -f {} +

echo "[clean_repo] deleting local tool caches and generated web/test outputs..."
rm -rf \
  .mypy_cache \
  .pytest_cache \
  .ruff_cache \
  .serena/cache \
  htmlcov \
  test-results \
  playwright-report \
  blob-report \
  web/.next \
  web/out \
  web/tsconfig.tsbuildinfo \
  src/*.egg-info

echo "[clean_repo] untracking generated/dependency paths if they were ever added..."
git rm -r --cached --ignore-unmatch \
  .mypy_cache \
  .pytest_cache \
  .ruff_cache \
  .serena/cache \
  .venv \
  htmlcov \
  test-results \
  playwright-report \
  blob-report \
  web/node_modules \
  web/.next \
  web/out \
  web/tsconfig.tsbuildinfo \
  src/replay.egg-info >/dev/null 2>&1 || true

echo "[clean_repo] done. Review 'git status' before committing."
