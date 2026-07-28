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

echo "Starting Boom/Crash expansion paper monitor."
echo "This is paper-only. It uses local downloaded candles first so it can start quickly."
echo "Press Ctrl+C only when you want to stop it."
echo

cycle=0
while true; do
  cycle=$((cycle + 1))
  echo
  echo "Boom/Crash expansion paper cycle ${cycle} started."
  work/run_boom_crash_expansion_paper_local.sh
  work/run_monitor_overview.sh >/dev/null
  echo "Next Boom/Crash expansion cycle in 15 minute(s). Press Ctrl+C to stop."
  sleep 900
done
