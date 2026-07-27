# Paper Stable Rules Dashboard

Last updated UTC: 2026-07-27T20:39:02.980291+00:00

This is a paper-trading monitor only. It does not place real trades.

## Current Verdict

- Latest decisions: CRASH300N:no_trade
- New paper orders on latest run: 0
- Open paper positions: 0
- Closed paper trades: 0
- Closed paper PnL: 0

## Data Refresh

| symbol | timeframe | status | candles | error |
| --- | --- | --- | --- | --- |
| CRASH300N | 15m | refreshed | 5000 |  |

## Latest Decisions

| symbol | timeframe | decision | side | entry | stop_loss | take_profit | reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CRASH300N | 15m | no_trade | hold | 2087.624 |  |  | no trade signal |

## Open Positions

No open paper positions.

## Closed Trades

No closed paper trades yet.

## Journal Summary

| symbol | timeframe | decision | runs | rows | last_seen |
| --- | --- | --- | --- | --- | --- |
| CRASH300N | 15m | no_trade | 27 | 27 | 2026-07-27T20:39:02.953287+00:00 |

## What To Run Next

- Read go-live readiness: `/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/live_candidate/outputs/primary_readiness.md`
- Read signal-frequency report: `/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/stable_rules_signal_frequency_report.md`
- Rebuild signal-frequency report: `work/run_near_miss_report.sh`
- Continuous paper monitor: `work/run_paper_monitor.sh`
- Fast local paper check: `work/run_paper_local.sh`
- Fresh Deriv data paper check: `work/run_paper_refresh.sh`
