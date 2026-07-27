# Paper Stable Rules Dashboard

Last updated UTC: 2026-07-27T20:36:06.012300+00:00

This is a paper-trading monitor only. It does not place real trades.

## Current Verdict

- Latest decisions: BOOM300N:no_trade, CRASH300N:no_trade
- New paper orders on latest run: 0
- Open paper positions: 0
- Closed paper trades: 19
- Closed paper PnL: 153.60831494341085

## Data Refresh

| symbol | timeframe | status | candles | error |
| --- | --- | --- | --- | --- |
| BOOM300N | 15m | local_copy | 5000 |  |
| CRASH300N | 15m | local_copy | 5000 |  |

## Latest Decisions

| symbol | timeframe | decision | side | entry | stop_loss | take_profit | reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BOOM300N | 15m | no_trade | hold | 990.267 |  |  | no trade signal |
| CRASH300N | 15m | no_trade | hold | 2083.91 |  |  | no trade signal |

## Open Positions

No open paper positions.

## Closed Trades

| paper_order_id | symbol | timeframe | closed_at | exit_price | paper_pnl | exit_reason |
| --- | --- | --- | --- | --- | --- | --- |
| paper-1 | CRASH300N | 15m | 2026-07-14 19:15:00+00:00 | 1688.7171890000002 | 7.052463577975831 | paper time exit |
| paper-1 | CRASH300N | 15m | 2026-07-16 00:00:00+00:00 | 1621.2566838 | 18.313276048497148 | paper time exit |
| paper-1 | CRASH300N | 15m | 2026-07-16 04:00:00+00:00 | 1666.062035222857 | 35.68991939604172 | paper take profit |
| paper-1 | CRASH300N | 15m | 2026-07-16 16:45:00+00:00 | 1581.2766099857142 | -30.331558432224043 | paper stop loss |
| paper-1 | BOOM300N | 15m | 2026-07-17 07:15:00+00:00 | 1120.7155977571426 | -30.284716692217685 | paper stop loss |
| paper-1 | BOOM300N | 15m | 2026-07-17 12:15:00+00:00 | 1106.1847188 | 26.52958177083332 | paper time exit |
| paper-1 | BOOM300N | 15m | 2026-07-18 00:00:00+00:00 | 1036.1737238 | -5.414747778339726 | paper time exit |
| paper-1 | CRASH300N | 15m | 2026-07-21 14:30:00+00:00 | 1832.1464974 | 18.9378001548105 | paper time exit |
| paper-1 | CRASH300N | 15m | 2026-07-23 22:00:00+00:00 | 1900.2973502171428 | 35.70588804739481 | paper take profit |
| paper-1 | CRASH300N | 15m | 2026-07-25 04:00:00+00:00 | 1884.7568303714284 | 35.697314860796496 | paper take profit |

## Journal Summary

| symbol | timeframe | decision | runs | rows | last_seen |
| --- | --- | --- | --- | --- | --- |
| BOOM300N | 15m | blocked_guard | 12 | 12 | 2026-07-17T05:29:04.913678+00:00 |
| BOOM300N | 15m | blocked_rule | 23 | 23 | 2026-07-27T01:15:47.019301+00:00 |
| BOOM300N | 15m | no_trade | 926 | 928 | 2026-07-27T20:36:05.965013+00:00 |
| BOOM300N | 15m | paper_order | 7 | 7 | 2026-07-17T21:14:28.242767+00:00 |
| CRASH300N | 15m | blocked_guard | 38 | 38 | 2026-07-23T21:28:01.852615+00:00 |
| CRASH300N | 15m | blocked_rule | 22 | 22 | 2026-07-27T12:17:33.712814+00:00 |
| CRASH300N | 15m | no_trade | 896 | 898 | 2026-07-27T20:36:05.965013+00:00 |
| CRASH300N | 15m | paper_order | 12 | 12 | 2026-07-25T02:54:49.321256+00:00 |

## What To Run Next

- Read go-live readiness: `/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/advanced_sniper_go_live_readiness.md`
- Read signal-frequency report: `/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/stable_rules_signal_frequency_report.md`
- Rebuild signal-frequency report: `work/run_near_miss_report.sh`
- Continuous paper monitor: `work/run_paper_monitor.sh`
- Fast local paper check: `work/run_paper_local.sh`
- Fresh Deriv data paper check: `work/run_paper_refresh.sh`
