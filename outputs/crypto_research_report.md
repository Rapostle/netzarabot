# Crypto Research Report

Last updated UTC: 2026-07-27T20:47:42.502299+00:00

Status: **RESEARCH ONLY**

No crypto recipe has passed the same evidence gates as Experimental pair or Advanced sniper.

## Available Crypto Data

| symbol | timeframes | files | total_candles |
| --- | --- | --- | --- |
| cryBTCUSD | 15m, 1h, 1m, 30m, 5m | 5 | 25000 |
| cryETHUSD | 15m, 1h, 1m, 30m, 5m | 5 | 25000 |

## Current Evidence

| source | strategy | recipe | symbols | trades | avg_return | profit_factor | decision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| existing combined optimizer | breakout_retest | avoid_dead_spiking__baseline_config | 2 | 0 | 0.0 | 0.0 | reject |
| existing combined optimizer | breakout_retest | avoid_dead_spiking__breakeven_1r_fixed_2r | 2 | 0 | 0.0 | 0.0 | reject |
| existing combined optimizer | breakout_retest | avoid_dead_spiking__fixed_1_5r_no_partial | 2 | 0 | 0.0 | 0.0 | reject |
| existing combined optimizer | breakout_retest | avoid_dead_spiking__fixed_1r_no_partial | 2 | 0 | 0.0 | 0.0 | reject |
| existing combined optimizer | breakout_retest | avoid_dead_spiking__fixed_2r_no_partial | 2 | 0 | 0.0 | 0.0 | reject |

## Rule

- Crypto stays separate from the current profitable Boom/Crash paper tracks.
- Crypto must pass backtest, walk-forward, and paper testing before any live step.
- Do not promote crypto just because BTC/ETH are popular; promote only if the numbers prove it.

## Commands

Refresh/download crypto data:

`work/download_crypto_data.sh`

Run crypto research locally:

`work/run_crypto_research.sh`
