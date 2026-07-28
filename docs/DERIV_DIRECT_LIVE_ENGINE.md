# Deriv-Direct Live Engine

This is the Deriv WebSocket API route. It is separate from the MT5/CFD bridge.

## Files

```text
external/deriv_direct/deriv_direct_executor.py
live_candidate/config/deriv_direct_live_config.json
live_candidate/config/ALLOW_REAL_LIVE_TRADING.txt
work/run_deriv_direct_dry_run.sh
work/run_deriv_direct_live_once.sh
```

## What It Does

The engine reads the latest signal from:

```text
outputs/pair_candidate_paper_decisions.csv
```

If the signal passes the filters, it uses Deriv WebSocket calls:

1. `authorize`
2. `portfolio`
3. `proposal`
4. `buy`
5. `balance`

It writes every attempt to:

```text
outputs/deriv_direct_order_journal.csv
```

It also writes track qualification checks to:

```text
outputs/deriv_direct_track_qualification.csv
```

## Track Qualification Gate

The engine recomputes track qualification on every run from each track's closed-trades CSV.

Hard-coded track qualification limits:

```text
HARD_MIN_WIN_RATE = 0.65
HARD_MIN_CLOSED_TRADES = 15
```

A track can feed live signals only if it has at least 15 closed paper trades and at least 65% win rate.

Stake limits are user-configurable in:

```text
live_candidate/config/deriv_direct_live_config.json
```

Use:

```text
stake
max_stake
max_daily_stake
```

There is no daily order-count cap in the engine. Control frequency through signal quality, track qualification, max open contracts, and the daily stake limit.

## Multiplier Contract Shape

The engine now uses Deriv Multiplier contracts:

```text
buy  -> MULTUP
sell -> MULTDOWN
```

It converts the paper signal's price stop/target into money-based Multiplier orders:

```text
risk_reward_ratio = abs(take_profit - entry) / abs(entry - stop_loss)
stop_loss_amount = max_stake
take_profit_amount = stop_loss_amount * risk_reward_ratio
```

The engine tests conservative multiplier candidates in order:

```text
10, 20, 30, 40, 50, 100, 200
```

The first multiplier accepted by Deriv's proposal API is used.

## First Test

Use plan-only first. This does not need a token or network:

```bash
work/run_deriv_direct_dry_run.sh --plan-only
```

Use dry-run next. This requests a real Deriv proposal, but does not buy:

```bash
export DERIV_API_TOKEN='paste_token_here'
work/run_deriv_direct_dry_run.sh
```

## Verification Note

On 2026-07-28, the engine was verified with `--plan-only` against the current repo files. It correctly wrote/printed track qualification:

- Advanced sniper candidates qualified.
- Boom/Crash expansion candidates did not qualify because it had only 4 closed trades.
- Original stable rules did not qualify.
- Experimental pair candidates no longer qualified from the actual CSV at that moment because its computed win rate was 62.5%, below the hard 65% gate.

A network dry-run proposal was also attempted against Deriv with `MULTUP`/`MULTDOWN` for `BOOM300N` and `CRASH300N`. Deriv's public WebSocket responded that these Multiplier trades were temporarily unavailable / no contract offering was available for those exact symbols. This means the engine is built, but real Deriv-direct Boom/Crash execution depends on Deriv exposing tradable contract symbols for the connected account.

## Real Buy

Real buys require all three:

```bash
export DERIV_API_TOKEN='paste_token_here'
export ALLOW_REAL_DERIV_DIRECT=true
export DERIV_DIRECT_CONSENT=I_UNDERSTAND_REAL_MONEY_TRADING
work/run_deriv_direct_live_once.sh
```

## Current Defaults

- Stake: set by `stake`
- Max stake: set by `max_stake`
- Max daily stake: set by `max_daily_stake`
- Max daily orders: unlimited
- Max open contracts: `1`
- Allowed symbols: `BOOM300N`, `CRASH300N`
- Buy signal maps to `CALL`
- Sell signal maps to `PUT`
- Duration: `5m`

Adjust these in:

```text
live_candidate/config/deriv_direct_live_config.json
```
