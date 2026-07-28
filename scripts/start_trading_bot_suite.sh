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

mkdir -p outputs/service_logs

start_one() {
  local name="$1"
  local command="$2"
  local pid_file="outputs/service_logs/${name}.pid"
  local log_file="outputs/service_logs/${name}.log"

  if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    echo "$name is already running with PID $(cat "$pid_file")."
    return
  fi

  echo "Starting $name..."
  nohup bash -lc "$command" >"$log_file" 2>&1 &
  echo $! >"$pid_file"
  echo "$name started with PID $(cat "$pid_file"). Log: $log_file"
}

start_one "main_monitor" "work/run_combined_paper_monitor.sh"
start_one "expansion_monitor" "work/run_boom_crash_expansion_paper_monitor.sh"

work/run_monitor_overview.sh >/dev/null

echo
echo "Trading bot suite is running in paper mode."
echo "Check status with: work/status_trading_bot_suite.sh"
echo "Quick report:       work/check_bot_status.sh"
