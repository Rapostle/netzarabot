#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TRADING_BOT_ROOT="${TRADING_BOT_ROOT:-$PROJECT_ROOT/external/trading_bot}"
if [ -x "$PROJECT_ROOT/.venv/bin/python" ]; then
  PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
else
  PYTHON_BIN="$(command -v python3)"
fi

cd $PROJECT_ROOT

$PYTHON_BIN \
  work/paper_stable_refresh.py \
  --track-name "Live candidate watchlist demo" \
  --rules-csv $PROJECT_ROOT/live_candidate/config/watchlist_rules.csv \
  --data-dir $PROJECT_ROOT/live_candidate/outputs/watchlist_refreshed_data \
  --output $PROJECT_ROOT/live_candidate/outputs/watchlist_decisions.csv \
  --journal-output $PROJECT_ROOT/live_candidate/outputs/watchlist_journal.csv \
  --journal-summary-output $PROJECT_ROOT/live_candidate/outputs/watchlist_journal_summary.csv \
  --open-positions-output $PROJECT_ROOT/live_candidate/outputs/watchlist_open_positions.csv \
  --closed-trades-output $PROJECT_ROOT/live_candidate/outputs/watchlist_closed_trades.csv \
  --position-summary-output $PROJECT_ROOT/live_candidate/outputs/watchlist_position_summary.csv \
  --status-output $PROJECT_ROOT/live_candidate/outputs/watchlist_status.csv \
  --dashboard-output $PROJECT_ROOT/live_candidate/outputs/watchlist_dashboard.md \
  --readiness-output $PROJECT_ROOT/live_candidate/outputs/watchlist_readiness.md \
  --manifest-output $PROJECT_ROOT/live_candidate/outputs/watchlist_refresh_manifest.csv \
  --max-open-positions 1 \
  --max-family-side-open 1 \
  --paper-profit-lock-r 2
