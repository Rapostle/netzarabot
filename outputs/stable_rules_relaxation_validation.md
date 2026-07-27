# Stable Rule Relaxation Validation

Last updated UTC: 2026-07-10T12:44:00+00:00

Verdict: DO NOT PROMOTE THE RELAXED RULE YET

## What Was Tested

The near-miss report found one research-only relaxed rule:

| rule_id | symbol | timeframe | side | feature | condition |
| --- | --- | --- | --- | --- | --- |
| RELAXED_SR007_bb_position | BOOM300N | 15m | buy | bb_position | below_lower_band_area |

## Backtest Result

| trades | account_return | raw_edge_return | win_rate | profit_factor | max_drawdown |
| --- | --- | --- | --- | --- | --- |
| 203 | -0.02% | -8.18% | 43.84% | 0.96 | 0.10% |

## Decision

The relaxed rule created more signals, but the proper promoted-rule trade simulator showed negative return and profit factor below 1.0. It should stay research-only and must not be added to paper or live trading.

## Next Research Direction

- Keep the original approved stable rules in paper mode.
- Use the near-miss report to find stricter variants that increase signal frequency without damaging profit factor.
- Prefer new two-condition or exit-improved candidates over single-condition relaxations.
