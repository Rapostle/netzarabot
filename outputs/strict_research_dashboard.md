# Paper Stable Rules Dashboard

Last updated UTC: 2026-07-27T20:19:56.669311+00:00

This is a paper-trading monitor only. It does not place real trades.

## Current Verdict

- Latest decisions: CRASH300N:no_trade
- New paper orders on latest run: 0
- Open paper positions: 0
- Closed paper trades: 2
- Closed paper PnL: 53.67827150419895

## Data Refresh

| symbol | timeframe | status | candles | error |
| --- | --- | --- | --- | --- |
| CRASH300N | 15m | refreshed | 5000 |  |

## Latest Decisions

| symbol | timeframe | decision | side | entry | stop_loss | take_profit | reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CRASH300N | 15m | no_trade | hold | 2099.163 |  |  | no trade signal |

## Open Positions

No open paper positions.

## Closed Trades

| paper_order_id | symbol | timeframe | closed_at | exit_price | paper_pnl | exit_reason |
| --- | --- | --- | --- | --- | --- | --- |
| paper-1 | CRASH300N | 15m | 2026-07-21 14:30:00+00:00 | 1832.1464974 | 17.97244009185941 | paper time exit |
| paper-1 | CRASH300N | 15m | 2026-07-23 22:00:00+00:00 | 1900.663277017143 | 35.70583141233954 | paper take profit |

## Journal Summary

| symbol | timeframe | decision | runs | rows | last_seen |
| --- | --- | --- | --- | --- | --- |
| CRASH300N | 15m | blocked_guard | 6 | 6 | 2026-07-25T06:45:21.416825+00:00 |
| CRASH300N | 15m | no_trade | 316 | 316 | 2026-07-27T20:19:56.632550+00:00 |
| CRASH300N | 15m | paper_order | 2 | 2 | 2026-07-23T19:44:13.390331+00:00 |

## What To Run Next

- Read go-live readiness: `/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/strict_research_go_live_readiness.md`
- Read signal-frequency report: `/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/stable_rules_signal_frequency_report.md`
- Rebuild signal-frequency report: `work/run_near_miss_report.sh`
- Continuous paper monitor: `work/run_paper_monitor.sh`
- Fast local paper check: `work/run_paper_local.sh`
- Fresh Deriv data paper check: `work/run_paper_refresh.sh`
