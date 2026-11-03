#!/usr/bin/env bash
# Runs the pair and sniper paper tracks 40 seconds after every 15-minute candle closes,
# so the rules see the candle that just finished (not one still forming).
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
if [ -x "$ROOT/.venv/bin/python" ]; then PY="$ROOT/.venv/bin/python"; else PY="$(command -v python3)"; fi

pair() {
  "$PY" work/paper_stable_refresh.py \
    --track-name "Experimental pair candidates" \
    --rules-csv "$ROOT/outputs/stable_rules_pair_execution_candidates.csv" \
    --data-dir "$ROOT/outputs/pair_candidate_refreshed_data" \
    --output "$ROOT/outputs/pair_candidate_paper_decisions.csv" \
    --journal-output "$ROOT/outputs/pair_candidate_paper_journal.csv" \
    --journal-summary-output "$ROOT/outputs/pair_candidate_paper_journal_summary.csv" \
    --open-positions-output "$ROOT/outputs/pair_candidate_open_positions.csv" \
    --closed-trades-output "$ROOT/outputs/pair_candidate_closed_trades.csv" \
    --position-summary-output "$ROOT/outputs/pair_candidate_position_summary.csv" \
    --status-output "$ROOT/outputs/pair_candidate_status.csv" \
    --dashboard-output "$ROOT/outputs/pair_candidate_dashboard.md" \
    --readiness-output "$ROOT/outputs/pair_candidate_go_live_readiness.md" \
    --manifest-output "$ROOT/outputs/pair_candidate_refresh_manifest.csv"
}

sniper() {
  "$PY" work/paper_stable_refresh.py \
    --track-name "Advanced sniper candidates" \
    --skip-download \
    --rules-csv "$ROOT/outputs/advanced_accuracy_execution_candidates.csv" \
    --data-dir "$ROOT/outputs/pair_candidate_refreshed_data" \
    --output "$ROOT/outputs/advanced_sniper_paper_decisions.csv" \
    --journal-output "$ROOT/outputs/advanced_sniper_paper_journal.csv" \
    --journal-summary-output "$ROOT/outputs/advanced_sniper_paper_journal_summary.csv" \
    --open-positions-output "$ROOT/outputs/advanced_sniper_open_positions.csv" \
    --closed-trades-output "$ROOT/outputs/advanced_sniper_closed_trades.csv" \
    --position-summary-output "$ROOT/outputs/advanced_sniper_position_summary.csv" \
    --status-output "$ROOT/outputs/advanced_sniper_status.csv" \
    --dashboard-output "$ROOT/outputs/advanced_sniper_dashboard.md" \
    --readiness-output "$ROOT/outputs/advanced_sniper_go_live_readiness.md" \
    --manifest-output "$ROOT/outputs/advanced_sniper_refresh_manifest.csv"
}

while true; do
  now=$(date +%s)
  next=$(( (now / 900 + 1) * 900 + 40 ))
  echo "$(date -u +%FT%TZ) next run at $(date -u -d @$next +%FT%TZ)"
  sleep $(( next - now ))
  pair || echo "pair run failed"
  sniper || echo "sniper run failed"
done
