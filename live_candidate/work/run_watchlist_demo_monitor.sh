#!/usr/bin/env bash
set -euo pipefail

cd /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot

while true; do
  live_candidate/work/run_watchlist_demo_once.sh
  echo
  echo "Next live-candidate watchlist demo check in 15 minutes. Press Ctrl+C to stop."
  sleep 900
done
