# Paper Stable Rules Dashboard

Last updated UTC: 2026-07-27T20:36:03.825974+00:00

This is a paper-trading monitor only. It does not place real trades.

## Current Verdict

- Latest decisions: BOOM300N:no_trade, CRASH300N:no_trade
- New paper orders on latest run: 0
- Open paper positions: 0
- Closed paper trades: 23
- Closed paper PnL: 161.6878916732611

## Data Refresh

| symbol | timeframe | status | candles | error |
| --- | --- | --- | --- | --- |
| BOOM300N | 15m | refreshed | 5000 |  |
| CRASH300N | 15m | refreshed | 5000 |  |

## Latest Decisions

| symbol | timeframe | decision | side | entry | stop_loss | take_profit | reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BOOM300N | 15m | no_trade | hold | 990.072 |  |  | no trade signal |
| CRASH300N | 15m | no_trade | hold | 2084.267 |  |  | no trade signal |

## Open Positions

No open paper positions.

## Closed Trades

| paper_order_id | symbol | timeframe | closed_at | exit_price | paper_pnl | exit_reason |
| --- | --- | --- | --- | --- | --- | --- |
| paper-1 | CRASH300N | 15m | 2026-07-16 03:45:00+00:00 | 1662.6019559485717 | 35.69284345904445 | paper take profit |
| paper-1 | BOOM300N | 15m | 2026-07-16 12:45:00+00:00 | 1148.178889714285 | -30.319217726244243 | paper stop loss |
| paper-1 | CRASH300N | 15m | 2026-07-16 16:45:00+00:00 | 1581.4337214142854 | -30.331095593017945 | paper stop loss |
| paper-1 | BOOM300N | 15m | 2026-07-17 07:15:00+00:00 | 1120.3696669571427 | -30.28462880883902 | paper stop loss |
| paper-1 | BOOM300N | 15m | 2026-07-17 12:15:00+00:00 | 1105.8457866 | 26.25118528149807 | paper time exit |
| paper-1 | CRASH300N | 15m | 2026-07-21 14:30:00+00:00 | 1832.1464974 | 18.38013336581067 | paper time exit |
| paper-1 | BOOM300N | 15m | 2026-07-23 20:45:00+00:00 | 1039.465422942857 | -30.29341573396238 | paper stop loss |
| paper-2 | CRASH300N | 15m | 2026-07-23 22:00:00+00:00 | 1900.4813134171432 | 35.70585957512664 | paper take profit |
| paper-1 | CRASH300N | 15m | 2026-07-25 04:00:00+00:00 | 1885.8779775257144 | 35.69867611609057 | paper take profit |
| paper-1 | BOOM300N | 15m | 2026-07-26 22:30:00+00:00 | 1008.518256 | 35.650053772766825 | paper take profit |

## Journal Summary

| symbol | timeframe | decision | runs | rows | last_seen |
| --- | --- | --- | --- | --- | --- |
| BOOM300N | 15m | blocked_guard | 15 | 15 | 2026-07-17T05:29:02.999061+00:00 |
| BOOM300N | 15m | blocked_rule | 47 | 47 | 2026-07-27T15:14:48.886276+00:00 |
| BOOM300N | 15m | no_trade | 978 | 979 | 2026-07-27T20:36:03.783568+00:00 |
| BOOM300N | 15m | paper_order | 11 | 11 | 2026-07-26T20:11:24.173619+00:00 |
| CRASH300N | 15m | blocked_guard | 39 | 39 | 2026-07-23T21:27:59.804651+00:00 |
| CRASH300N | 15m | blocked_rule | 24 | 24 | 2026-07-27T12:17:31.443299+00:00 |
| CRASH300N | 15m | no_trade | 976 | 977 | 2026-07-27T20:36:03.783568+00:00 |
| CRASH300N | 15m | paper_order | 12 | 12 | 2026-07-25T02:54:28.606027+00:00 |

## What To Run Next

- Read go-live readiness: `/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/pair_candidate_go_live_readiness.md`
- Read signal-frequency report: `/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/stable_rules_signal_frequency_report.md`
- Rebuild signal-frequency report: `work/run_near_miss_report.sh`
- Continuous paper monitor: `work/run_paper_monitor.sh`
- Fast local paper check: `work/run_paper_local.sh`
- Fresh Deriv data paper check: `work/run_paper_refresh.sh`
