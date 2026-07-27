#!/usr/bin/env bash
set -euo pipefail

cd /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot

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
