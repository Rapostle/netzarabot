# Original Stable Rules Signal Frequency Report

Last updated UTC: 2026-07-27T20:19:59.686166+00:00

This report explains why the paper rules are not firing often. Relaxed candidates are research-only.

## Current Signal State

- Exact rule matches right now: 0
- Near misses right now: 5
- Research-only relaxed candidates passing floor: 6

## Latest Near Misses

| symbol | timeframe | rule_id | side | latest_status | latest_match_parts | required_parts | missing_features | recent_exact_matches | recent_one_missing_matches |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CRASH300N | 15m | SR017 | buy | near_miss | 1 | 2 | rsi_zone=rsi_low (now rsi_high) | 37 | 59 |
| CRASH300N | 15m | SR010 | sell | near_miss | 1 | 2 | bb_position=above_upper_band_area (now upper_band_area) | 14 | 53 |
| BOOM300N | 15m | SR003 | buy | near_miss | 1 | 2 | bb_width_regime=bb_expanded (now bb_normal_high) | 14 | 50 |
| CRASH300N | 15m | SR011 | buy | near_miss | 1 | 2 | atr_regime=atr_low (now atr_mid_low) | 11 | 27 |
| BOOM300N | 15m | SR007 | buy | near_miss | 1 | 2 | bb_position=below_lower_band_area (now lower_band_area) | 7 | 23 |
| BOOM300N | 15m | SR001 | buy | blocked | 0 | 2 | bb_position=below_lower_band_area (now lower_band_area); atr_regime=atr_mid_low (now atr_low) | 3 | 24 |
| BOOM300N | 15m | SR006 | buy | blocked | 0 | 2 | rsi_zone=rsi_oversold (now rsi_low); bb_position=below_lower_band_area (now lower_band_area) | 6 | 16 |

## Best Relaxed Research Candidates

| symbol | timeframe | source_rule_id | suggested_side | relaxed_feature | relaxed_condition | trades | win_rate | profit_factor | expectancy | total_return |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BOOM300N | 15m | SR007 | buy | bb_position | below_lower_band_area | 1219 | 0.5397867104183757 | 1.5462603283188894 | 0.0032732473095111745 | 3.9900884702941215 |
| BOOM300N | 15m | SR001 | buy | bb_position | below_lower_band_area | 1219 | 0.5397867104183757 | 1.5462603283188894 | 0.0032732473095111745 | 3.9900884702941215 |
| BOOM300N | 15m | SR006 | buy | bb_position | below_lower_band_area | 1219 | 0.5397867104183757 | 1.5462603283188894 | 0.0032732473095111745 | 3.9900884702941215 |
| BOOM300N | 15m | SR006 | buy | rsi_zone | rsi_oversold | 699 | 0.5293276108726752 | 1.3491054554950068 | 0.0021796173716053043 | 1.5235525427521077 |
| BOOM300N | 15m | SR003 | buy | bb_width_regime | bb_expanded | 1244 | 0.5112540192926045 | 1.2410910910180386 | 0.001622769781412233 | 2.0187256080768177 |
| CRASH300N | 15m | SR011 | buy | atr_regime | atr_low | 1239 | 0.5504439063761097 | 1.2334104635972656 | 0.001539743204832493 | 1.907741830787459 |

## What This Means

- If near misses are common but exact matches are rare, the approved rules are probably too strict for frequent paper signals.
- Relaxed candidates must be re-tested with backtest and walk-forward before promotion.
- Nothing in this report changes live or paper trading rules automatically.
