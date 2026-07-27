# Supervision Tools Summary

Last updated UTC: 2026-07-27T20:47:46.817353+00:00

Built the eight supervision tools:

- Self-healing monitor check: `outputs/self_healing_monitor_check.md`
- One-click status command: `work/check_bot_status.sh`
- Expansion monitor health guard: `outputs/expansion_monitor_health_guard.md`
- Best track leaderboard: `outputs/best_track_leaderboard.md`
- Trade replay report: `outputs/trade_replay_report.md`
- Rule kill-switch report: `outputs/rule_kill_switch_report.md`
- Rule kill-switch blocklist: `outputs/rule_kill_switch_blocklist.csv`
- Candidate promotion queue: `outputs/candidate_promotion_queue.md`
- Daily summary report: `outputs/daily_summary_report.md`

Current action read:

- Original stable rules: QUARANTINE (Closed paper PnL has breached the loss limit.)
- Experimental pair candidates: MANUAL REVIEW (Positive enough for human review, still not live-ready.)
- Advanced sniper candidates: MANUAL REVIEW (Positive enough for human review, still not live-ready.)
- Boom/Crash expansion candidates: KEEP PAPER TESTING (Sample size is still too small.)

This is still paper monitoring only. No live trades are approved.
