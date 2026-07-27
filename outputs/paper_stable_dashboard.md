# Paper Stable Rules Dashboard

Last updated UTC: 2026-07-27T20:19:26.113872+00:00

This is a paper-trading monitor only. It does not place real trades.

## Current Verdict

- Latest decisions: BOOM300N:no_trade, CRASH300N:no_trade
- New paper orders on latest run: 0
- Open paper positions: 0
- Closed paper trades: 9
- Closed paper PnL: -134.75120968391016

## Data Refresh

| symbol | timeframe | status | candles | error |
| --- | --- | --- | --- | --- |
| BOOM300N | 15m | refreshed | 5000 |  |
| CRASH300N | 15m | refreshed | 5000 |  |

## Latest Decisions

| symbol | timeframe | decision | side | entry | stop_loss | take_profit | reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BOOM300N | 15m | no_trade | hold | 989.355 |  |  | no trade signal |
| CRASH300N | 15m | no_trade | hold | 2098.587 |  |  | no trade signal |

## Open Positions

No open paper positions.

## Closed Trades

| paper_order_id | symbol | timeframe | closed_at | exit_price | paper_pnl | exit_reason |
| --- | --- | --- | --- | --- | --- | --- |
| paper-1 | BOOM300N | 15m | 2026-07-10 19:15:00+00:00 | 1135.659 | -3.145973405049851 | paper time exit |
| paper-1 | CRASH300N | 15m | 2026-07-10 19:45:00+00:00 | 1580.915642857143 | -30.00000000000008 | paper stop loss |
| paper-1 | CRASH300N | 15m | 2026-07-10 20:45:00+00:00 | 1606.3434285714286 | -29.999999999999886 | paper stop loss |
| paper-1 | CRASH300N | 15m | 2026-07-10 21:45:00+00:00 | 1619.136357142857 | -29.999999999999854 | paper stop loss |
| paper-1 | CRASH300N | 15m | 2026-07-11 00:45:00+00:00 | 1629.974 | -5.702036441586253 | paper time exit |
| paper-1 | CRASH300N | 15m | 2026-07-11 02:45:00+00:00 | 1681.434857142857 | -29.99999999999997 | paper stop loss |
| paper-1 | CRASH300N | 15m | 2026-07-11 06:00:00+00:00 | 1694.265 | -5.16845055305469 | paper time exit |
| paper-1 | CRASH300N | 15m | 2026-07-11 11:30:00+00:00 | 1631.1882857142857 | -30.0 | paper stop loss |
| paper-1 | CRASH300N | 15m | 2026-07-11 14:45:00+00:00 | 1665.113 | 29.26525071578041 | paper time exit |

## Journal Summary

| symbol | timeframe | decision | runs | rows | last_seen |
| --- | --- | --- | --- | --- | --- |
| BOOM300N | 15m | no_trade | 792 | 794 | 2026-07-27T20:19:26.070223+00:00 |
| BOOM300N | 15m | paper_order | 271 | 271 | 2026-07-27T19:47:25.283720+00:00 |
| CRASH300N | 15m | blocked_rule | 194 | 194 | 2026-07-27T19:47:25.283720+00:00 |
| CRASH300N | 15m | no_trade | 718 | 720 | 2026-07-27T20:19:26.070223+00:00 |
| CRASH300N | 15m | paper_order | 151 | 151 | 2026-07-27T17:55:11.700109+00:00 |

## What To Run Next

- Read go-live readiness: `/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/paper_stable_go_live_readiness.md`
- Read signal-frequency report: `/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/stable_rules_signal_frequency_report.md`
- Rebuild signal-frequency report: `work/run_near_miss_report.sh`
- Continuous paper monitor: `work/run_paper_monitor.sh`
- Fast local paper check: `work/run_paper_local.sh`
- Fresh Deriv data paper check: `work/run_paper_refresh.sh`
