# Go-Live Readiness

Last updated UTC: 2026-07-27T20:36:16.623787+00:00

Verdict: NOT READY FOR LIVE TRADING

This gate is intentionally strict. It is meant to protect the account, not make the bot look busy.

## Checks

| check | status | detail |
| --- | --- | --- |
| Enough paper-monitor runs | pass | 325/30 runs |
| Rules produced paper orders | pass | 2 historical order rows |
| Enough closed paper trades | fail | 2/30 closed trades |
| Closed paper PnL is positive | pass | 53.68 minimum 0.00 |
| No unresolved open paper positions | pass | 0 open positions |

## Paper Results

- Paper monitor runs: 325
- Paper order rows: 2
- Open paper positions: 0
- Closed paper trades: 2
- Closed paper PnL: 53.68
- Closed paper wins/losses: 2/0
- Closed paper win rate: 100.00%

## Required Before Real Money

- Keep this in paper mode until the verdict changes.
- Do not add a real Deriv token yet.
- When it becomes ready, start only with a tiny live pilot and daily loss limits.
