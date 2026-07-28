#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]]; then
  echo "TELEGRAM_BOT_TOKEN is not set."
  echo "Create a bot with BotFather, then run:"
  echo "export TELEGRAM_BOT_TOKEN='paste_token_here'"
  echo "$ROOT_DIR/live_candidate/exports/telegram/run_telegram_bot.sh"
  exit 2
fi

"$PYTHON_BIN" "$ROOT_DIR/live_candidate/exports/telegram/telegram_bot.py" "$@"
