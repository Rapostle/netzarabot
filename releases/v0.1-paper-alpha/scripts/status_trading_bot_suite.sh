#!/usr/bin/env bash
set -euo pipefail

cd /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot

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
