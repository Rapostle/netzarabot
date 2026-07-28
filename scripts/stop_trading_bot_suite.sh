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

stop_one() {
  local name="$1"
  local pid_file="outputs/service_logs/${name}.pid"

  if [[ ! -f "$pid_file" ]]; then
    echo "$name is not registered as running."
    return
  fi

  local pid
  pid="$(cat "$pid_file")"
  if kill -0 "$pid" 2>/dev/null; then
    echo "Stopping $name with PID $pid..."
    kill "$pid" 2>/dev/null || true
  else
    echo "$name PID file exists, but process is not running."
  fi
  rm -f "$pid_file"
}

stop_one "main_monitor"
stop_one "expansion_monitor"

echo "Requested suite stop. Existing Terminal-run monitors are not affected by this helper."
