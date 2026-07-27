#!/usr/bin/env bash
set -euo pipefail

cd /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot

/Users/ocmix/Documents/Codex/2026-07-09/can-you-help-implement-in-the/.venv/bin/python \
  work/paper_stable_refresh.py \
  --track-name "Live candidate primary demo" \
  --rules-csv /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/live_candidate/config/primary_rules.csv \
  --data-dir /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/live_candidate/outputs/refreshed_data \
  --output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/live_candidate/outputs/primary_decisions.csv \
  --journal-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/live_candidate/outputs/primary_journal.csv \
  --journal-summary-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/live_candidate/outputs/primary_journal_summary.csv \
  --open-positions-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/live_candidate/outputs/primary_open_positions.csv \
  --closed-trades-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/live_candidate/outputs/primary_closed_trades.csv \
  --position-summary-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/live_candidate/outputs/primary_position_summary.csv \
  --status-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/live_candidate/outputs/primary_status.csv \
  --dashboard-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/live_candidate/outputs/primary_dashboard.md \
  --readiness-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/live_candidate/outputs/primary_readiness.md \
  --manifest-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/live_candidate/outputs/primary_refresh_manifest.csv \
  --max-open-positions 1 \
  --max-family-side-open 1 \
  --paper-profit-lock-r 2
