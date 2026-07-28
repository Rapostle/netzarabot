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

## First Test

Use dry-run first. This authorizes your token and requests a proposal, but does not buy:

```bash
export DERIV_API_TOKEN='paste_token_here'
work/run_deriv_direct_dry_run.sh
```

## Real Buy

Real buys require all three:

```bash
export DERIV_API_TOKEN='paste_token_here'
export ALLOW_REAL_DERIV_DIRECT=true
export DERIV_DIRECT_CONSENT=I_UNDERSTAND_REAL_MONEY_TRADING
work/run_deriv_direct_live_once.sh
```

## Current Defaults

- Stake: `$1`
- Max stake: `$1`
- Max daily stake: `$5`
- Max daily orders: `3`
- Max open contracts: `1`
- Allowed symbols: `BOOM300N`, `CRASH300N`
- Buy signal maps to `CALL`
- Sell signal maps to `PUT`
- Duration: `5m`

Adjust these in:

```text
live_candidate/config/deriv_direct_live_config.json
```

