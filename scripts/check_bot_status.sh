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

work/run_monitor_overview.sh >/dev/null

printf '\n=== Trading Bot Quick Status ===\n\n'

if [[ -f outputs/monitor_alerts.md ]]; then
  printf 'Monitor alerts:\n'
  sed -n '1,80p' outputs/monitor_alerts.md
  printf '\n'
fi

if [[ -f outputs/self_healing_monitor_check.md ]]; then
  printf 'Monitor health:\n'
  sed -n '1,120p' outputs/self_healing_monitor_check.md
  printf '\n'
fi

if [[ -f outputs/best_track_leaderboard.md ]]; then
  printf 'Best track leaderboard:\n'
  sed -n '1,120p' outputs/best_track_leaderboard.md
  printf '\n'
fi

if [[ -f outputs/auto_promotion_gate.md ]]; then
  printf 'Promotion gate:\n'
  sed -n '1,120p' outputs/auto_promotion_gate.md
  printf '\n'
fi

if [[ -f outputs/boom_crash_expansion_status.csv ]]; then
  printf 'Boom/Crash expansion status:\n'
  sed -n '1,80p' outputs/boom_crash_expansion_status.csv
  printf '\n'
fi

if [[ -f outputs/boom_crash_expansion_open_positions.csv ]]; then
  printf 'Boom/Crash expansion open paper trades:\n'
  sed -n '1,120p' outputs/boom_crash_expansion_open_positions.csv
  printf '\n'
fi

if [[ -f outputs/open_trade_watchdog.md ]]; then
  printf 'Open trade watchdog:\n'
  sed -n '1,140p' outputs/open_trade_watchdog.md
  printf '\n'
fi

if [[ -f outputs/live_readiness_checklist.md ]]; then
  printf 'Live-readiness checklist:\n'
  sed -n '1,120p' outputs/live_readiness_checklist.md
  printf '\n'
fi

if [[ -f outputs/paper_protection_bundle_report.md ]]; then
  printf 'Paper protection bundle:\n'
  sed -n '1,140p' outputs/paper_protection_bundle_report.md
  printf '\n'
fi

if [[ -f outputs/rule_kill_switch_report.md ]]; then
  printf 'Strict rule filter:\n'
  sed -n '1,140p' outputs/rule_kill_switch_report.md
  printf '\n'
fi

if [[ -f outputs/manual_review_package.md ]]; then
  printf 'Manual review package:\n'
  sed -n '1,180p' outputs/manual_review_package.md
  printf '\n'
fi

if [[ -f outputs/strict_research_lane_report.md ]]; then
  printf 'Strict research lane:\n'
  sed -n '1,120p' outputs/strict_research_lane_report.md
  printf '\n'
fi

if [[ -f outputs/strict_research_status.csv ]]; then
  printf 'Strict research status:\n'
  sed -n '1,80p' outputs/strict_research_status.csv
  printf '\n'
fi

if [[ -f outputs/crypto_research_report.md ]]; then
  printf 'Crypto research:\n'
  sed -n '1,160p' outputs/crypto_research_report.md
  printf '\n'
fi

if [[ -f outputs/promotion_pack.md ]]; then
  printf 'Promotion pack:\n'
  sed -n '1,120p' outputs/promotion_pack.md
  printf '\n'
fi

if [[ -f outputs/product_layer_summary.md ]]; then
  printf 'Product layer:\n'
  sed -n '1,140p' outputs/product_layer_summary.md
  printf '\n'
fi

if [[ -f outputs/release_package_summary.md ]]; then
  printf 'Release package:\n'
  sed -n '1,140p' outputs/release_package_summary.md
  printf '\n'
fi

if [[ -f outputs/stale_trade_cleanup_report.md ]]; then
  printf 'Stale cleanup:\n'
  sed -n '1,120p' outputs/stale_trade_cleanup_report.md
  printf '\n'
fi

if [[ -f outputs/launch_assets_summary.md ]]; then
  printf 'Launch assets:\n'
  sed -n '1,120p' outputs/launch_assets_summary.md
  printf '\n'
fi

if [[ -f outputs/final_gap_report.md ]]; then
  printf 'Final gaps:\n'
  sed -n '1,120p' outputs/final_gap_report.md
  printf '\n'
fi

printf 'Full dashboard file:\n'
printf '%s\n' '$PROJECT_ROOT/outputs/monitor_dashboard.html'
printf 'Expansion control dashboard file:\n'
printf '%s\n' '$PROJECT_ROOT/outputs/expansion_control_dashboard.html'
printf 'App dashboard file:\n'
printf '%s\n' '$PROJECT_ROOT/outputs/trading_bot_app_dashboard.html'
printf 'Operator console file:\n'
printf '%s\n' '$PROJECT_ROOT/outputs/operator_console.html'
printf 'Local clickable app command:\n'
printf '%s\n' 'work/start_local_app.sh'
