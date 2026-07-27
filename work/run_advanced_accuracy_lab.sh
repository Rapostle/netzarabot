#!/usr/bin/env bash
set -euo pipefail

cd /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot

/Users/ocmix/Documents/Codex/2026-07-09/can-you-help-implement-in-the/.venv/bin/python \
  work/advanced_accuracy_lab.py \
  --rules-csv outputs/stable_rules_pair_execution_candidates.csv \
  --data-dir outputs/pair_candidate_refreshed_data \
  --max-rows 5000
