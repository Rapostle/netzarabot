#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TRADING_BOT_ROOT="${TRADING_BOT_ROOT:-$PROJECT_ROOT/external/trading_bot}"
if [ -x "$PROJECT_ROOT/.venv/bin/python" ]; then
  PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
else
  PYTHON_BIN="$(command -v python3)"
fi

cd $PROJECT_ROOT

PYTHONPYCACHEPREFIX=/tmp/trading_bot_pycache \
$PYTHON_BIN \
  work/boom_crash_expansion_lab.py \
  --data-dir $TRADING_BOT_ROOT/data \
  --max-rows 2500 \
  --min-samples 25 \
  --min-profit-factor 1.4 \
  --top-per-side 3
