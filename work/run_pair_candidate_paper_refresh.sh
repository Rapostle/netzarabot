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
  work/paper_stable_refresh.py \
  --track-name "Experimental pair candidates" \
  --rules-csv $PROJECT_ROOT/outputs/stable_rules_pair_execution_candidates.csv \
  --data-dir $PROJECT_ROOT/outputs/pair_candidate_refreshed_data \
  --output $PROJECT_ROOT/outputs/pair_candidate_paper_decisions.csv \
  --journal-output $PROJECT_ROOT/outputs/pair_candidate_paper_journal.csv \
  --journal-summary-output $PROJECT_ROOT/outputs/pair_candidate_paper_journal_summary.csv \
  --open-positions-output $PROJECT_ROOT/outputs/pair_candidate_open_positions.csv \
  --closed-trades-output $PROJECT_ROOT/outputs/pair_candidate_closed_trades.csv \
  --position-summary-output $PROJECT_ROOT/outputs/pair_candidate_position_summary.csv \
  --status-output $PROJECT_ROOT/outputs/pair_candidate_status.csv \
  --dashboard-output $PROJECT_ROOT/outputs/pair_candidate_dashboard.md \
  --readiness-output $PROJECT_ROOT/outputs/pair_candidate_go_live_readiness.md \
  --manifest-output $PROJECT_ROOT/outputs/pair_candidate_refresh_manifest.csv
