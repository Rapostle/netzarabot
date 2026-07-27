#!/usr/bin/env bash
set -euo pipefail

TASK_ROOT=/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot
BOT_ROOT=/Users/ocmix/Documents/Codex/2026-07-09/can-you-help-implement-in-the

cd "$BOT_ROOT"

.venv/bin/python -m trading_bot.cli.main \
  --config config.deriv_crypto.yaml \
  --mode audit-timeframes \
  --instrument-group crypto \
  --data-dir data \
  --timeframe 1m \
  --timeframe 5m \
  --timeframe 15m \
  --timeframe 30m \
  --higher-timeframe 1h \
  --max-rows 2500 \
  --audit-output "$TASK_ROOT/outputs/crypto_timeframe_audit.csv"

.venv/bin/python -m trading_bot.cli.main \
  --config config.deriv_crypto.yaml \
  --mode audit-combinations \
  --instrument-group crypto \
  --data-dir data \
  --timeframe 5m \
  --higher-timeframe 1h \
  --max-rows 2500 \
  --combo-profile promising \
  --max-combinations 80 \
  --workers 4 \
  --audit-output "$TASK_ROOT/outputs/crypto_combined_research_5m.csv"

cd "$TASK_ROOT"
/Users/ocmix/Documents/Codex/2026-07-09/can-you-help-implement-in-the/.venv/bin/python \
  work/build_crypto_research_report.py
