# Experimental Pair Candidates Signal Frequency Report

Last updated UTC: 2026-07-27T20:36:21.639317+00:00

This report explains why the paper rules are not firing often. Relaxed candidates are research-only.

## Current Signal State

- Exact rule matches right now: 0
- Near misses right now: 3
- Research-only relaxed candidates passing floor: 10

## Latest Near Misses

| symbol | timeframe | rule_id | side | latest_status | latest_match_parts | required_parts | missing_features | recent_exact_matches | recent_one_missing_matches |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CRASH300N | 15m | PAIR029 | sell | near_miss | 1 | 2 | candle_body=large_bull_body (now bull_body) | 1 | 39 |
| BOOM300N | 15m | PAIR006 | buy | near_miss | 1 | 2 | candle_body=large_bear_body (now small_body) | 3 | 37 |
| BOOM300N | 15m | PAIR002 | buy | near_miss | 1 | 2 | rsi_zone=rsi_overbought (now rsi_low) | 10 | 28 |
| CRASH300N | 15m | PAIR019 | buy | blocked | 0 | 2 | rsi_zone=rsi_low (now rsi_mid); atr_regime=atr_low (now atr_mid_high) | 0 | 67 |
| BOOM300N | 15m | PAIR001 | buy | blocked | 0 | 2 | bb_position=below_lower_band_area (now lower_band_area); supertrend_side=supertrend_up (now supertrend_down) | 1 | 64 |
| CRASH300N | 15m | PAIR023 | buy | blocked | 0 | 2 | rsi_zone=rsi_low (now rsi_mid); bb_position=upper_band_area (now lower_band_area) | 0 | 55 |
| BOOM300N | 15m | PAIR016 | sell | blocked | 0 | 2 | supertrend_side=supertrend_up (now supertrend_down); lower_wick=large_lower_wick (now small_lower_wick) | 0 | 51 |
| CRASH300N | 15m | PAIR024 | buy | blocked | 0 | 2 | bb_position=middle_band_area (now lower_band_area); atr_regime=atr_low (now atr_mid_high) | 0 | 35 |
| BOOM300N | 15m | PAIR005 | buy | blocked | 0 | 2 | trend_zone=downtrend (now strong_downtrend); bb_width_regime=bb_expanded (now bb_normal_high) | 17 | 33 |
| CRASH300N | 15m | PAIR017 | buy | blocked | 0 | 2 | trend_zone=flat_trend (now strong_uptrend); atr_regime=atr_mid_low (now atr_mid_high) | 0 | 20 |

## Best Relaxed Research Candidates

| symbol | timeframe | source_rule_id | suggested_side | relaxed_feature | relaxed_condition | trades | win_rate | profit_factor | expectancy | total_return |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CRASH300N | 15m | PAIR017 | buy | trend_zone | flat_trend | 221 | 0.6244343891402715 | 1.5461141129468243 | 0.0029253512459719894 | 0.6465026253598096 |
| BOOM300N | 15m | PAIR001 | buy | bb_position | below_lower_band_area | 1219 | 0.5397867104183757 | 1.5447379566981714 | 0.0032673419679819823 | 3.9828898589700366 |
| BOOM300N | 15m | PAIR016 | sell | lower_wick | large_lower_wick | 104 | 0.5865384615384616 | 1.362027864050713 | 0.002321662280850653 | 0.24145287720846792 |
| BOOM300N | 15m | PAIR002 | buy | trend_zone | strong_downtrend | 1860 | 0.5032258064516129 | 1.3464635259440738 | 0.0023697764603080994 | 4.407784216173065 |
| BOOM300N | 15m | PAIR006 | buy | trend_zone | strong_downtrend | 1860 | 0.5032258064516129 | 1.3464635259440738 | 0.0023697764603080994 | 4.407784216173065 |
| CRASH300N | 15m | PAIR017 | buy | atr_regime | atr_mid_low | 1244 | 0.5594855305466238 | 1.3256812269699598 | 0.0020579816826671394 | 2.5601292132379214 |
| BOOM300N | 15m | PAIR005 | buy | bb_width_regime | bb_expanded | 1244 | 0.5112540192926045 | 1.2410910910180386 | 0.001622769781412233 | 2.0187256080768177 |
| CRASH300N | 15m | PAIR024 | buy | atr_regime | atr_low | 1240 | 0.5491935483870968 | 1.2319542153311347 | 0.0015293004935976948 | 1.8963326120611415 |
| CRASH300N | 15m | PAIR019 | buy | atr_regime | atr_low | 1240 | 0.5491935483870968 | 1.2319542153311347 | 0.0015293004935976948 | 1.8963326120611415 |
| CRASH300N | 15m | PAIR024 | buy | bb_position | middle_band_area | 428 | 0.544392523364486 | 1.2278673461490313 | 0.0015494870091981936 | 0.6631804399368268 |

## What This Means

- If near misses are common but exact matches are rare, the approved rules are probably too strict for frequent paper signals.
- Relaxed candidates must be re-tested with backtest and walk-forward before promotion.
- Nothing in this report changes live or paper trading rules automatically.
