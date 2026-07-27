# Trading Bot Monitor Overview

Last updated UTC: 2026-07-27T20:20:03.353440+00:00

This is the single summary for the paper tracks. None of these tracks places real trades.

## Monitor Comparison

| monitor | last_run_utc | age_minutes | latest_decisions | journal_rows | paper_orders | open_positions | closed_trades | closed_pnl | readiness |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Original stable rules | 2026-07-27T20:19:26.113872+00:00 | 0.6 | BOOM300N:no_trade, CRASH300N:no_trade | 2130 | 422 | 0 | 9 | -134.75120968391016 | NOT READY FOR LIVE TRADING |
| Experimental pair candidates | 2026-07-27T20:19:44.271068+00:00 | 0.3 | BOOM300N:no_trade, CRASH300N:no_trade | 2102 | 23 | 0 | 23 | 161.68789167326113 | READY FOR TINY LIVE PILOT |
| Advanced sniper candidates | 2026-07-27T20:19:46.453137+00:00 | 0.3 | BOOM300N:no_trade, CRASH300N:no_trade | 1938 | 19 | 0 | 19 | 153.60831494341085 | READY FOR TINY LIVE PILOT |
| Boom/Crash expansion candidates | 2026-07-27T20:16:44.180838+00:00 | 3.3 | BOOM1000:blocked_guard, BOOM1000:no_trade, BOOM1000:no_trade, BOOM150N:no_trade, BOOM150N:no_trade, BOOM300N:no_trade, BOOM300N:no_trade, BOOM300N:no_trade, BOOM50:no_trade, BOOM500:no_trade, BOOM500:no_trade, BOOM500:no_trade, BOOM600:no_trade, BOOM600:no_trade, BOOM600:no_trade, BOOM900:no_trade, BOOM900:no_trade, BOOM900:no_trade, CRASH1000:no_trade, CRASH1000:no_trade, CRASH1000:no_trade, CRASH150N:no_trade, CRASH150N:no_trade, CRASH300N:no_trade, CRASH300N:no_trade, CRASH300N:no_trade, CRASH50:no_trade, CRASH500:no_trade, CRASH500:no_trade, CRASH500:no_trade, CRASH500:no_trade, CRASH600:no_trade, CRASH600:no_trade, CRASH600:no_trade, CRASH900:no_trade, CRASH900:no_trade, CRASH900:no_trade | 3626 | 16 | 0 | 4 | 10.709697611500605 | NOT READY FOR LIVE TRADING |

## What Each Track Means

- Original stable rules: Conservative approved rules currently used as the main paper baseline.
- Experimental pair candidates: Separate experimental paper track for the 10 stronger two-condition candidates.
- Advanced sniper candidates: Separate offline-gated sniper track using regime, spike, score, exit, walk-forward, and risk filters.
- Boom/Crash expansion candidates: Separate wider Boom/Crash paper track for expansion candidates across more instruments and timeframes.

## Experimental Pair No-Trade Check

Experimental pair is not frozen: it has 0 exact matches right now, 4 near miss(es), and 10 relaxed research candidate(s). It is probably too selective for fast evidence because it only watches BOOM300N/CRASH300N on 15m.

## Next Action

Review the experimental pair track manually for drawdown, win rate, and repeated behavior.

Use this one command to run all paper tracks and refresh this overview:

- Combined monitor: `work/run_combined_paper_monitor.sh`
- One-time combined check: `work/run_all_paper_checks.sh`

The older individual runners still work if you ever want to inspect one track by itself:

- Original stable only: `work/run_paper_monitor.sh`
- Experimental pair only: `work/run_pair_candidate_paper_monitor.sh`

Useful files:

- Original dashboard: `outputs/paper_stable_dashboard.md`
- Experimental dashboard: `outputs/pair_candidate_dashboard.md`
- Advanced sniper dashboard: `outputs/advanced_sniper_dashboard.md`
- Original no-trade explainer: `outputs/stable_rules_signal_frequency_report.md`
- Experimental no-trade explainer: `outputs/pair_candidate_signal_frequency_report.md`
- Plain decision brief: `outputs/decision_brief.md`
- Advanced accuracy report: `outputs/advanced_accuracy_report.md`
- Paper performance report: `outputs/paper_performance_report.md`
- Pair validation report: `outputs/stable_rules_pair_validation_report.md`
- Go-live readiness files stay NOT READY until paper orders and closed trades exist.
