#!/usr/bin/env bash
set -euo pipefail

cd /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot

PYTHONPYCACHEPREFIX=/tmp/trading_bot_pycache \
/Users/ocmix/Documents/Codex/2026-07-09/can-you-help-implement-in-the/.venv/bin/python \
  work/boom_crash_expansion_lab.py \
  --data-dir /Users/ocmix/Documents/Codex/2026-07-09/can-you-help-implement-in-the/data \
  --max-rows 2500 \
  --min-samples 25 \
  --min-profit-factor 1.4 \
  --top-per-side 3
