#!/usr/bin/env bash
set -euo pipefail

cd /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot

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
