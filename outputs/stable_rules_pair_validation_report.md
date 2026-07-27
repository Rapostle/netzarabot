# Stable Pair Validation Report

Last updated UTC: 2026-07-10T12:49:42.923806+00:00

Verdict: EXPERIMENTAL PAPER ONLY

These rules passed the first backtest and walk-forward gates, but they are not live-trading rules yet.

- Promoted experimental paper rules: 10
- Symbols: 2

## Final Subset Validation

| test | trades | account_return | win_rate | profit_factor | max_drawdown |
| --- | --- | --- | --- | --- | --- |
| Backtest | 278 | 0.41% | 56.83% | 1.98 | 0.03% |
| Walk-forward | 214 | 0.32% | 57.48% | 2.01 | 0.03% |

Both BOOM300N and CRASH300N were profitable across all walk-forward folds in this subset test.

## Experimental Paper Rules

| rule_id | symbol | timeframe | suggested_side | feature | condition | backtest_trades | backtest_profit_factor | walk_forward_trades | walk_forward_profit_factor |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PAIR001 | BOOM300N | 15m | buy | bb_position+supertrend_side | below_lower_band_area & supertrend_up | 30 | 1.3415694339796231 | 27 | 1.923956526566555 |
| PAIR002 | BOOM300N | 15m | buy | rsi_zone+trend_zone | rsi_overbought & strong_downtrend | 30 | 1.4666952390900458 | 25 | 1.7222226848194595 |
| PAIR006 | BOOM300N | 15m | buy | trend_zone+candle_body | strong_downtrend & large_bear_body | 50 | 2.129044011367271 | 38 | 1.649773790543147 |
| PAIR005 | BOOM300N | 15m | buy | trend_zone+bb_width_regime | downtrend & bb_expanded | 12 | 1.4735035745898073 | 8 | 1.3688838246826716 |
| PAIR016 | BOOM300N | 15m | sell | supertrend_side+lower_wick | supertrend_up & large_lower_wick | 13 | 2.093871767496259 | 8 | 8.37045456103545 |
| PAIR023 | CRASH300N | 15m | buy | rsi_zone+bb_position | rsi_low & upper_band_area | 20 | 6.969312351356753 | 14 | 30.58729786201292 |
| PAIR017 | CRASH300N | 15m | buy | trend_zone+atr_regime | flat_trend & atr_mid_low | 12 | 5.077380814195168 | 11 | 4.507393179937764 |
| PAIR024 | CRASH300N | 15m | buy | bb_position+atr_regime | middle_band_area & atr_low | 26 | 2.768583640158948 | 19 | 2.2947234933631577 |
| PAIR019 | CRASH300N | 15m | buy | rsi_zone+atr_regime | rsi_low & atr_low | 15 | 2.301992454227534 | 10 | 1.2904318365276095 |
| PAIR029 | CRASH300N | 15m | sell | bb_position+candle_body | lower_band_area & large_bull_body | 17 | 5.399837064725267 | 14 | 5.586127336504673 |

## Decision

- Use these only in a separate experimental paper monitor.
- Do not mix them into the approved stable execution file yet.
- Promote to the main paper set only after live paper journaling shows real closed-trade performance.
