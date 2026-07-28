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

cd $PROJECT_ROOT

$PYTHON_BIN \
  work/build_monitor_overview.py

$PYTHON_BIN \
  work/build_paper_performance_report.py

$PYTHON_BIN \
  work/build_manual_review_package.py

$PYTHON_BIN \
  work/build_strict_research_lane.py

$PYTHON_BIN \
  work/build_crypto_research_report.py

$PYTHON_BIN \
  work/build_app_intelligence.py

$PYTHON_BIN \
  work/build_expansion_monitor_template_report.py

$PYTHON_BIN \
  work/build_supervision_tools.py

$PYTHON_BIN \
  work/build_expansion_control.py

$PYTHON_BIN \
  work/build_product_layer.py

$PYTHON_BIN \
  work/build_release_package.py

$PYTHON_BIN \
  work/stale_trade_cleanup.py

$PYTHON_BIN \
  work/build_launch_assets.py
