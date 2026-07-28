#!/usr/bin/env bash
set -euo pipefail

cd /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot

PY=/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/external/trading_bot/.venv/bin/python

"$PY" work/analyze_stable_near_misses.py \
  --label "Original Stable Rules" \
  --rules-csv /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/crash_boom_execution_approved_stable_rules_15m_30m.csv \
  --data-dir /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/paper_refreshed_data \
  --near-miss-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/stable_rules_near_misses.csv \
  --relaxed-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/stable_rules_relaxed_research_candidates.csv \
  --relaxed-rules-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/stable_rules_relaxed_promoted_research_rules.csv \
  --report-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/stable_rules_signal_frequency_report.md

"$PY" work/analyze_stable_near_misses.py \
  --label "Experimental Pair Candidates" \
  --rules-csv /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/stable_rules_pair_execution_candidates.csv \
  --data-dir /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/pair_candidate_refreshed_data \
  --near-miss-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/pair_candidate_near_misses.csv \
  --relaxed-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/pair_candidate_relaxed_research_candidates.csv \
  --relaxed-rules-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/pair_candidate_relaxed_promoted_research_rules.csv \
  --report-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/pair_candidate_signal_frequency_report.md
