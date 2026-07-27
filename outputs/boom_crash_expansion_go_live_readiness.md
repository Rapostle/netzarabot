# Go-Live Readiness

Last updated UTC: 2026-07-27T20:47:38.894131+00:00

Verdict: NOT READY FOR LIVE TRADING

This gate is intentionally strict. It is meant to protect the account, not make the bot look busy.

## Checks

| check | status | detail |
| --- | --- | --- |
| Enough paper-monitor runs | pass | 100/30 runs |
| Rules produced paper orders | pass | 16 historical order rows |
| Enough closed paper trades | fail | 4/10 closed trades |
| Closed paper PnL is positive | pass | 10.71 minimum 0.00 |
| No unresolved open paper positions | pass | 0 open positions |

## Paper Results

- Paper monitor runs: 100
- Paper order rows: 16
- Open paper positions: 0
- Closed paper trades: 4
- Closed paper PnL: 10.71
- Closed paper wins/losses: 3/1
- Closed paper win rate: 75.00%

## Required Before Real Money

- Keep this in paper mode until the verdict changes.
- Do not add a real Deriv token yet.
- When it becomes ready, start only with a tiny live pilot and daily loss limits.
