#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TRADING_BOT_ROOT="${TRADING_BOT_ROOT:-$PROJECT_ROOT/external/trading_bot}"
if [ -x "$PROJECT_ROOT/.venv/bin/python" ]; then
  PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
else
  PYTHON_BIN="$(command -v python3)"
fi

cd $PROJECT_ROOT

echo "=== Live Candidate Demo Status ==="
echo

if [[ -f live_candidate/outputs/primary_status.csv ]]; then
  echo "Primary status:"
  cat live_candidate/outputs/primary_status.csv
else
  echo "Primary status: not run yet"
fi

echo

if [[ -f live_candidate/outputs/primary_open_positions.csv ]]; then
  echo "Primary open positions:"
  cat live_candidate/outputs/primary_open_positions.csv
else
  echo "Primary open positions: none yet"
fi

echo

if [[ -f live_candidate/outputs/primary_closed_trades.csv ]]; then
  echo "Primary recent closed trades:"
  tail -5 live_candidate/outputs/primary_closed_trades.csv
else
  echo "Primary closed trades: none yet"
fi

echo
echo "Live mode is blocked. This package is demo/paper-only."
