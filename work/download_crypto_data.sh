#!/usr/bin/env bash
set -euo pipefail

cd /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/external/trading_bot

.venv/bin/python -m trading_bot.cli.main \
  --config config.deriv_crypto.yaml \
  --mode download-deriv-all \
  --instrument-group crypto \
  --timeframe 1m \
  --timeframe 5m \
  --timeframe 15m \
  --timeframe 30m \
  --timeframe 1h \
  --count 5000 \
  --workers 4
