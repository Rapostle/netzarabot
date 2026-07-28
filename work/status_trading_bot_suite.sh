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

status_one() {
  local name="$1"
  local pid_file="outputs/service_logs/${name}.pid"
  local log_file="outputs/service_logs/${name}.log"

  if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    echo "$name: running, PID $(cat "$pid_file")"
  else
    echo "$name: not running through background helper"
  fi
  if [[ -f "$log_file" ]]; then
    echo "Recent $name log:"
    tail -n 8 "$log_file"
  fi
  echo
}

status_one "main_monitor"
status_one "expansion_monitor"

echo "Paper status summary:"
work/check_bot_status.sh
