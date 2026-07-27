# Go-Live Readiness

Last updated UTC: 2026-07-27T20:19:26.113872+00:00

Verdict: NOT READY FOR LIVE TRADING

This gate is intentionally strict. It is meant to protect the account, not make the bot look busy.

## Checks

| check | status | detail |
| --- | --- | --- |
| Enough paper-monitor runs | pass | 1063/30 runs |
| Rules produced paper orders | pass | 422 historical order rows |
| Enough closed paper trades | fail | 9/10 closed trades |
| Closed paper PnL is positive | fail | -134.75 minimum 0.00 |
| No unresolved open paper positions | pass | 0 open positions |

## Paper Results

- Paper monitor runs: 1063
- Paper order rows: 422
- Open paper positions: 0
- Closed paper trades: 9
- Closed paper PnL: -134.75
- Closed paper wins/losses: 1/8
- Closed paper win rate: 11.11%

## Required Before Real Money

- Keep this in paper mode until the verdict changes.
- Do not add a real Deriv token yet.
- When it becomes ready, start only with a tiny live pilot and daily loss limits.
