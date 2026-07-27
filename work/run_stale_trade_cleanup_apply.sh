#!/usr/bin/env bash
set -euo pipefail

cd /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot

/Users/ocmix/Documents/Codex/2026-07-09/can-you-help-implement-in-the/.venv/bin/python \
  work/stale_trade_cleanup.py \
  --apply

work/run_monitor_overview.sh >/dev/null

echo "Stale paper trade cleanup applied. Review outputs/stale_trade_cleanup_report.md"
