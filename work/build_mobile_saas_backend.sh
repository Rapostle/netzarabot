#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="/Users/ocmix/Documents/Codex/2026-07-09/can-you-help-implement-in-the/.venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

"$PYTHON_BIN" "$ROOT_DIR/work/mobile_saas_backend.py" --seed-demo
