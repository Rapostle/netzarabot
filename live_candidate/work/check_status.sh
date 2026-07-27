#!/usr/bin/env bash
set -euo pipefail

cd /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot

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
