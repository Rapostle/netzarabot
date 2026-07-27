#!/usr/bin/env bash
set -euo pipefail

cd /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot

echo "Starting local trading bot app."
echo "Open this in your browser: http://127.0.0.1:8765"
echo "Press Ctrl+C to stop the local app."

/Users/ocmix/Documents/Codex/2026-07-09/can-you-help-implement-in-the/.venv/bin/python \
  work/local_app_server.py
