#!/usr/bin/env bash
set -euo pipefail

cd /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot

/Users/ocmix/Documents/Codex/2026-07-09/can-you-help-implement-in-the/.venv/bin/python \
  work/build_strict_research_lane.py

/Users/ocmix/Documents/Codex/2026-07-09/can-you-help-implement-in-the/.venv/bin/python \
  work/paper_stable_refresh.py \
  --track-name "Strict research candidates" \
  --rules-csv /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/strict_research_execution_candidates.csv \
  --data-dir /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/strict_research_refreshed_data \
  --output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/strict_research_paper_decisions.csv \
  --journal-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/strict_research_paper_journal.csv \
  --journal-summary-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/strict_research_paper_journal_summary.csv \
  --open-positions-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/strict_research_open_positions.csv \
  --closed-trades-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/strict_research_closed_trades.csv \
  --position-summary-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/strict_research_position_summary.csv \
  --status-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/strict_research_status.csv \
  --dashboard-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/strict_research_dashboard.md \
  --readiness-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/strict_research_go_live_readiness.md \
  --manifest-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/strict_research_refresh_manifest.csv \
  --readiness-min-closed-trades 30
