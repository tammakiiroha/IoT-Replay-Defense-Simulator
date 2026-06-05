#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"

APT_PACKAGES=(
  python3
  python3-venv
  python3-pip
  gnuradio
  gr-osmosdr
  hackrf
  libhackrf-dev
  hackrf-tools
)

echo "Project root: $ROOT_DIR"
echo "Python: $PYTHON_BIN"
echo "Virtualenv: $VENV_DIR"

if command -v apt-get >/dev/null 2>&1; then
  echo
  echo "Installing Ubuntu packages..."
  sudo apt-get update
  sudo apt-get install -y "${APT_PACKAGES[@]}"
else
  echo "apt-get not found. This script is intended for Ubuntu." >&2
  exit 1
fi

echo
echo "Creating virtual environment..."
"$PYTHON_BIN" -m venv "$VENV_DIR"

echo
echo "Installing Python dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$ROOT_DIR/requirements.txt"

echo
echo "Running environment doctor..."
"$VENV_DIR/bin/python" "$ROOT_DIR/physical_experiment/scripts/doctor.py" --fix

echo
echo "Bootstrap completed."
