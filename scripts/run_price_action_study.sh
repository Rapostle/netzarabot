#!/usr/bin/env bash
# Runs the price-action study (trendlines, structure, candle patterns, fair value gaps, order blocks, higher timeframe)
# through the walk-forward search with a shuffled-data comparison. Research only: it never trades.
#   nohup bash scripts/run_price_action_study.sh > outputs/price_action_study.log 2>&1 &
set -u
cd /root/netzarabot
PY=.venv/bin/python
DERIV="BOOM50 BOOM150N BOOM300N BOOM500 BOOM600 BOOM900 BOOM1000 CRASH50 CRASH150N CRASH300N CRASH500 CRASH600 CRASH900 CRASH1000"
NULL=${NULL_RUNS:-100}
echo "start $(date -u +%FT%TZ)"
for MODE in only add; do
  echo "=== Deriv 5m, price action: $MODE ==="
  $PY work/walk_forward_rule_search.py --data-dir outputs/history --symbols $DERIV --timeframe 5m --min-bars 5000 \
      --null-runs "$NULL" --price-action "$MODE" --htf-factor 12 --tag "pa5m_$MODE" | grep -E '^## |passed the final|chance of doing|Candidate rules'
  echo "=== Coins daily (12 years), price action: $MODE ==="
  $PY work/walk_forward_rule_search.py --data-dir checker_cache --symbols BTC ETH SOL BNB --timeframe 1d --min-bars 2500 \
      --cost 0.002 --null-runs "$NULL" --price-action "$MODE" --htf-factor 7 --tag "pacoin_$MODE" | grep -E '^## |passed the final|chance of doing|Candidate rules'
done
echo "finished $(date -u +%FT%TZ)"
