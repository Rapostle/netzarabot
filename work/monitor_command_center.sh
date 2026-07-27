#!/usr/bin/env bash
set -euo pipefail

cd /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot

printf '\nTrading Bot Monitor Command Center\n\n'
printf 'Use two Terminal windows:\n\n'
printf 'Window 1 - main monitor:\n'
printf '  work/run_combined_paper_monitor.sh\n\n'
printf 'Window 2 - Boom/Crash expansion monitor:\n'
printf '  work/run_boom_crash_expansion_paper_monitor.sh\n\n'
printf 'Any window - quick status:\n'
printf '  work/check_bot_status.sh\n\n'
printf 'Dashboard files:\n'
printf '  outputs/monitor_dashboard.html\n'
printf '  outputs/expansion_control_dashboard.html\n\n'
printf 'Current protection reports:\n'
printf '  outputs/paper_protection_bundle_report.md\n'
printf '  outputs/open_trade_watchdog.md\n'
printf '  outputs/live_readiness_checklist.md\n'
printf '  outputs/final_gap_report.md\n\n'
printf 'Stale cleanup tools:\n'
printf '  Review only: work/run_stale_trade_cleanup.sh\n'
printf '  Apply quarantine: work/run_stale_trade_cleanup_apply.sh\n'
printf '  Apply only after confirming the stale trade is bad paper data.\n'
