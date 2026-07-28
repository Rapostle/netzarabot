#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
if [ -x "$PROJECT_ROOT/.venv/bin/python" ]; then
  PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
else
  PYTHON_BIN="$(command -v python3)"
fi

cd "$PROJECT_ROOT"

"$PYTHON_BIN" -m external.deriv_direct.deriv_direct_executor \
  --repo-root "$PROJECT_ROOT" \
  --config live_candidate/config/deriv_direct_live_config.json \
  --dry-run \
  "$@"

