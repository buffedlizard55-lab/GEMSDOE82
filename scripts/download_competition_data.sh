#!/usr/bin/env bash
set -euo pipefail
# Autonomous SHA-256 verified competition & public geoscience data restoration for GEMSDOE82.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

"$PYTHON_BIN" scripts/prepare_data.py
