# Stable Pair Research Candidates

Last updated UTC: 2026-07-10T12:48:01.967383+00:00

These are research-only two-condition rules mined from current paper data. They still require simulator validation.

- Raw candidates: 32
- Backtest-ready rules: 32

## Top Candidates

| rule_id | symbol | timeframe | suggested_side | feature | condition | trades | win_rate | profit_factor | expectancy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PAIR025 | CRASH300N | 15m | sell | rsi_zone+trend_zone | rsi_mid & downtrend | 49 | 0.7551020408163265 | 7.437233453799727 | 0.011313567353728085 |
| PAIR017 | CRASH300N | 15m | buy | trend_zone+atr_regime | flat_trend & atr_mid_low | 79 | 0.7215189873417721 | 5.376420672462528 | 0.006973086433587949 |
| PAIR009 | BOOM300N | 15m | sell | trend_zone+atr_regime | uptrend & atr_high | 49 | 0.8367346938775511 | 5.228040449275133 | 0.009747834164421655 |
| PAIR010 | BOOM300N | 15m | sell | trend_zone+bb_width_regime | flat_trend & bb_normal_high | 51 | 0.7843137254901961 | 5.166609358620111 | 0.009616761101808145 |
| PAIR018 | CRASH300N | 15m | buy | trend_zone+bb_width_regime | flat_trend & bb_compressed | 82 | 0.7682926829268293 | 4.647895896163452 | 0.009137317730392287 |
| PAIR026 | CRASH300N | 15m | sell | trend_zone+bb_position | uptrend & lower_band_area | 42 | 0.6428571428571429 | 4.04523261764952 | 0.015154693531986996 |
| PAIR001 | BOOM300N | 15m | buy | bb_position+supertrend_side | below_lower_band_area & supertrend_up | 89 | 0.6966292134831461 | 3.884320664780049 | 0.011660820852103317 |
| PAIR011 | BOOM300N | 15m | sell | bb_width_regime+lower_wick | bb_compressed & large_lower_wick | 30 | 0.7 | 3.4414015098040007 | 0.008229815460606034 |
| PAIR019 | CRASH300N | 15m | buy | rsi_zone+atr_regime | rsi_low & atr_low | 41 | 0.6829268292682927 | 3.4265611293178297 | 0.009367218432593406 |
| PAIR002 | BOOM300N | 15m | buy | rsi_zone+trend_zone | rsi_overbought & strong_downtrend | 185 | 0.654054054054054 | 3.359371875714881 | 0.010634856557631309 |
| PAIR012 | BOOM300N | 15m | sell | bb_position+atr_regime | above_upper_band_area & atr_low | 34 | 0.6176470588235294 | 3.1119535112997037 | 0.005568643085686628 |
| PAIR013 | BOOM300N | 15m | sell | trend_zone+candle_body | uptrend & large_bull_body | 31 | 0.6774193548387096 | 3.108604285805591 | 0.00784329039685969 |

## Required Next Step

Run the promoted-rule backtest and walk-forward checks before adding any candidate to paper trading.
