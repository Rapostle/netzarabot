# Boom/Crash Expansion Paper Monitor Template

Last updated UTC: 2026-07-27T20:20:07.722452+00:00

Status: PREPARED, NOT RUNNING.

This template is ready for later. It is intentionally separate from the active paper tracks.

## Prepared Runners

- One-time local check: `work/run_boom_crash_expansion_paper_local.sh`
- One-time fresh-data check: `work/run_boom_crash_expansion_paper_refresh.sh`
- Repeating monitor: `work/run_boom_crash_expansion_paper_monitor.sh`

## Separate Output Files

- Decisions: `outputs/boom_crash_expansion_paper_decisions.csv`
- Journal: `outputs/boom_crash_expansion_paper_journal.csv`
- Open positions: `outputs/boom_crash_expansion_open_positions.csv`
- Closed trades: `outputs/boom_crash_expansion_closed_trades.csv`
- Dashboard: `outputs/boom_crash_expansion_dashboard.md`
- Readiness: `outputs/boom_crash_expansion_go_live_readiness.md`

## Candidate Pool

- Expansion rules prepared: 172

| symbol | timeframe | rules | best_profit_factor | best_return |
| --- | --- | --- | --- | --- |
| BOOM300N | 1m | 6 | inf | 0.3507 |
| CRASH500 | 30m | 6 | 54.91 | 0.3035 |
| BOOM900 | 15m | 6 | 44.45 | 0.1147 |
| BOOM900 | 30m | 6 | 25.41 | 0.4416 |
| BOOM500 | 30m | 6 | 21.64 | 0.3258 |
| BOOM300N | 15m | 6 | 21.32 | 1.0052 |
| BOOM1000 | 15m | 6 | 20.16 | 0.1364 |
| BOOM600 | 15m | 6 | 15.59 | 0.0945 |
| BOOM600 | 30m | 6 | 10.27 | 0.1725 |
| CRASH300N | 5m | 6 | 10.06 | 0.3777 |
| CRASH1000 | 30m | 6 | 8.44 | 0.1860 |
| CRASH300N | 15m | 6 | 7.65 | 0.3940 |
| CRASH500 | 15m | 6 | 6.39 | 0.8380 |
| CRASH600 | 15m | 6 | 6.20 | 0.1897 |
| BOOM900 | 5m | 5 | inf | 0.1332 |
| CRASH600 | 30m | 5 | 42.66 | 0.2224 |
| BOOM150N | 30m | 5 | 38.67 | 0.0729 |
| BOOM1000 | 5m | 5 | 16.24 | 0.0323 |
| CRASH1000 | 5m | 5 | 12.11 | 0.0681 |
| BOOM1000 | 30m | 5 | 10.94 | 0.1541 |

## When To Start It

- Start only after the current experimental and advanced sniper paper trades close, or when you deliberately want a separate expansion test.
- Do not add these expansion candidates to the active combined monitor yet.
- Do not use these for live trading. They need their own paper results first.

## What To Paste Later

From the project folder, run:

```bash
work/run_boom_crash_expansion_paper_monitor.sh
```
