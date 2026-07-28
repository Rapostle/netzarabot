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

TASK_ROOT=$PROJECT_ROOT
BOT_ROOT=$TRADING_BOT_ROOT

cd "$BOT_ROOT"

.venv/bin/python -m trading_bot.cli.main \
  --config config.deriv_crypto.yaml \
  --mode audit-timeframes \
  --instrument-group crypto \
  --data-dir data \
  --timeframe 1m \
  --timeframe 5m \
  --timeframe 15m \
  --timeframe 30m \
  --higher-timeframe 1h \
  --max-rows 2500 \
  --audit-output "$TASK_ROOT/outputs/crypto_timeframe_audit.csv"

.venv/bin/python -m trading_bot.cli.main \
  --config config.deriv_crypto.yaml \
  --mode audit-combinations \
  --instrument-group crypto \
  --data-dir data \
  --timeframe 5m \
  --higher-timeframe 1h \
  --max-rows 2500 \
  --combo-profile promising \
  --max-combinations 80 \
  --workers 4 \
  --audit-output "$TASK_ROOT/outputs/crypto_combined_research_5m.csv"

cd "$TASK_ROOT"
$PYTHON_BIN \
  work/build_crypto_research_report.py
