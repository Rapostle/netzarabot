#!/usr/bin/env bash
set -euo pipefail

cd /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot

/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/external/trading_bot/.venv/bin/python \
  work/paper_stable_refresh.py \
  --track-name "Advanced sniper candidates" \
  --skip-download \
  --rules-csv /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/advanced_accuracy_execution_candidates.csv \
  --data-dir /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/pair_candidate_refreshed_data \
  --output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/advanced_sniper_paper_decisions.csv \
  --journal-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/advanced_sniper_paper_journal.csv \
  --journal-summary-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/advanced_sniper_paper_journal_summary.csv \
  --open-positions-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/advanced_sniper_open_positions.csv \
  --closed-trades-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/advanced_sniper_closed_trades.csv \
  --position-summary-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/advanced_sniper_position_summary.csv \
  --status-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/advanced_sniper_status.csv \
  --dashboard-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/advanced_sniper_dashboard.md \
  --readiness-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/advanced_sniper_go_live_readiness.md \
  --manifest-output /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/advanced_sniper_refresh_manifest.csv
