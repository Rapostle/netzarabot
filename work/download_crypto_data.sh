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

cd $TRADING_BOT_ROOT

.venv/bin/python -m trading_bot.cli.main \
  --config config.deriv_crypto.yaml \
  --mode download-deriv-all \
  --instrument-group crypto \
  --timeframe 1m \
  --timeframe 5m \
  --timeframe 15m \
  --timeframe 30m \
  --timeframe 1h \
  --count 5000 \
  --workers 4
