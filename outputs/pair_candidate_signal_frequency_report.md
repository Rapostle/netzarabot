# Experimental Pair Candidates Signal Frequency Report

Last updated UTC: 2026-07-27T20:20:02.637362+00:00

This report explains why the paper rules are not firing often. Relaxed candidates are research-only.

## Current Signal State

- Exact rule matches right now: 0
- Near misses right now: 4
- Research-only relaxed candidates passing floor: 10

## Latest Near Misses

| symbol | timeframe | rule_id | side | latest_status | latest_match_parts | required_parts | missing_features | recent_exact_matches | recent_one_missing_matches |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CRASH300N | 15m | PAIR023 | buy | near_miss | 1 | 2 | rsi_zone=rsi_low (now rsi_high) | 0 | 57 |
| BOOM300N | 15m | PAIR006 | buy | near_miss | 1 | 2 | candle_body=large_bear_body (now small_body) | 3 | 37 |
| BOOM300N | 15m | PAIR002 | buy | near_miss | 1 | 2 | rsi_zone=rsi_overbought (now rsi_low) | 10 | 28 |
| CRASH300N | 15m | PAIR017 | buy | near_miss | 1 | 2 | trend_zone=flat_trend (now strong_uptrend) | 0 | 22 |
| CRASH300N | 15m | PAIR019 | buy | blocked | 0 | 2 | rsi_zone=rsi_low (now rsi_high); atr_regime=atr_low (now atr_mid_low) | 0 | 67 |
| BOOM300N | 15m | PAIR001 | buy | blocked | 0 | 2 | bb_position=below_lower_band_area (now lower_band_area); supertrend_side=supertrend_up (now supertrend_down) | 1 | 64 |
| BOOM300N | 15m | PAIR016 | sell | blocked | 0 | 2 | supertrend_side=supertrend_up (now supertrend_down); lower_wick=large_lower_wick (now small_lower_wick) | 0 | 51 |
| CRASH300N | 15m | PAIR029 | sell | blocked | 0 | 2 | bb_position=lower_band_area (now upper_band_area); candle_body=large_bull_body (now bear_body) | 1 | 37 |
| CRASH300N | 15m | PAIR024 | buy | blocked | 0 | 2 | bb_position=middle_band_area (now upper_band_area); atr_regime=atr_low (now atr_mid_low) | 0 | 35 |
| BOOM300N | 15m | PAIR005 | buy | blocked | 0 | 2 | trend_zone=downtrend (now strong_downtrend); bb_width_regime=bb_expanded (now bb_normal_high) | 17 | 34 |

## Best Relaxed Research Candidates

| symbol | timeframe | source_rule_id | suggested_side | relaxed_feature | relaxed_condition | trades | win_rate | profit_factor | expectancy | total_return |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CRASH300N | 15m | PAIR017 | buy | trend_zone | flat_trend | 220 | 0.6272727272727273 | 1.6076868852552149 | 0.003176155615404614 | 0.698754235389015 |
| BOOM300N | 15m | PAIR001 | buy | bb_position | below_lower_band_area | 1219 | 0.5397867104183757 | 1.5462603283188894 | 0.0032732473095111745 | 3.9900884702941215 |
| BOOM300N | 15m | PAIR016 | sell | lower_wick | large_lower_wick | 104 | 0.5865384615384616 | 1.362027864050713 | 0.002321662280850653 | 0.24145287720846792 |
| BOOM300N | 15m | PAIR002 | buy | trend_zone | strong_downtrend | 1871 | 0.5024051309460181 | 1.3357542012681909 | 0.002307158752611589 | 4.316694026136283 |
| BOOM300N | 15m | PAIR006 | buy | trend_zone | strong_downtrend | 1871 | 0.5024051309460181 | 1.3357542012681909 | 0.002307158752611589 | 4.316694026136283 |
| CRASH300N | 15m | PAIR017 | buy | atr_regime | atr_mid_low | 1243 | 0.5591311343523733 | 1.3230619519137825 | 0.002043072808912566 | 2.5395395014783197 |
| BOOM300N | 15m | PAIR005 | buy | bb_width_regime | bb_expanded | 1244 | 0.5112540192926045 | 1.2410910910180386 | 0.001622769781412233 | 2.0187256080768177 |
| CRASH300N | 15m | PAIR024 | buy | atr_regime | atr_low | 1239 | 0.5504439063761097 | 1.2334104635972656 | 0.001539743204832493 | 1.907741830787459 |
| CRASH300N | 15m | PAIR019 | buy | atr_regime | atr_low | 1239 | 0.5504439063761097 | 1.2334104635972656 | 0.001539743204832493 | 1.907741830787459 |
| CRASH300N | 15m | PAIR024 | buy | bb_position | middle_band_area | 428 | 0.544392523364486 | 1.2278673461490313 | 0.0015494870091981936 | 0.6631804399368268 |

## What This Means

- If near misses are common but exact matches are rare, the approved rules are probably too strict for frequent paper signals.
- Relaxed candidates must be re-tested with backtest and walk-forward before promotion.
- Nothing in this report changes live or paper trading rules automatically.
