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

PY=$PYTHON_BIN

"$PY" work/analyze_stable_near_misses.py \
  --label "Original Stable Rules" \
  --rules-csv $PROJECT_ROOT/outputs/crash_boom_execution_approved_stable_rules_15m_30m.csv \
  --data-dir $PROJECT_ROOT/outputs/paper_refreshed_data \
  --near-miss-output $PROJECT_ROOT/outputs/stable_rules_near_misses.csv \
  --relaxed-output $PROJECT_ROOT/outputs/stable_rules_relaxed_research_candidates.csv \
  --relaxed-rules-output $PROJECT_ROOT/outputs/stable_rules_relaxed_promoted_research_rules.csv \
  --report-output $PROJECT_ROOT/outputs/stable_rules_signal_frequency_report.md

"$PY" work/analyze_stable_near_misses.py \
  --label "Experimental Pair Candidates" \
  --rules-csv $PROJECT_ROOT/outputs/stable_rules_pair_execution_candidates.csv \
  --data-dir $PROJECT_ROOT/outputs/pair_candidate_refreshed_data \
  --near-miss-output $PROJECT_ROOT/outputs/pair_candidate_near_misses.csv \
  --relaxed-output $PROJECT_ROOT/outputs/pair_candidate_relaxed_research_candidates.csv \
  --relaxed-rules-output $PROJECT_ROOT/outputs/pair_candidate_relaxed_promoted_research_rules.csv \
  --report-output $PROJECT_ROOT/outputs/pair_candidate_signal_frequency_report.md
