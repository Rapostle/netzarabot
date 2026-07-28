#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TRADING_BOT_ROOT="${TRADING_BOT_ROOT:-$PROJECT_ROOT/external/trading_bot}"
if [ -x "$PROJECT_ROOT/.venv/bin/python" ]; then
  PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
else
  PYTHON_BIN="$(command -v python3)"
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cp "$ROOT_DIR/app/mobile_saas_app.html" "$ROOT_DIR/outputs/mobile_saas_app.html"
echo "Saved mobile app preview to $ROOT_DIR/outputs/mobile_saas_app.html"

if [[ -x "$ROOT_DIR/work/build_mobile_saas_backend.sh" ]]; then
  "$ROOT_DIR/work/build_mobile_saas_backend.sh"
fi
