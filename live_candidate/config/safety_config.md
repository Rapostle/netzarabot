# Live Candidate Safety Config

Status: DEMO / PAPER ONLY

This package is built so one candidate bot can be watched separately while the main research bot continues developing.

## Allowed Scope

Primary rule:

- CRASH300N
- 15m
- buy only
- PAIR017

Secondary watchlist rule:

- BOOM300N
- 15m
- buy only
- PAIR006

## Hard Blocks

- No real Deriv token is read by this package.
- No real order function is enabled.
- No real-money trading is approved.
- Any future live mode must require a separate manual arming file and a fresh readiness pass.

## Paper Risk Settings

- Isolated output files under `live_candidate/outputs/`
- Paper slippage enabled by the shared paper engine
- Paper profit lock enabled at 2R
- Duplicate position guard remains active
- Max open paper positions: 1

## Promotion Requirement

Before real money is considered:

- At least 30 closed paper trades on the candidate package
- Positive paper PnL
- Win rate closer to the 80% target
- No open trades
- Manual review pass
- Final live-readiness checklist must stop saying NOT READY
