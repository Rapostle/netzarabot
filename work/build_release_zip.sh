#!/usr/bin/env bash
set -euo pipefail

cd /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot

/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/external/trading_bot/.venv/bin/python \
  work/build_launch_assets.py

echo "Release zip ready: releases/v0.1-paper-alpha.zip"
