# Advanced Accuracy Lab

Last updated UTC: 2026-07-11T13:46:42.031665+00:00

This is an offline research gate. It does not touch the running paper trade and does not place real trades.

## What Was Built

- Sniper entry score.
- Market regime filter.
- Boom/Crash spike filter.
- Multi-timeframe-style trend confirmation using EMA and supertrend.
- Exit recommendation testing from MFE/MAE behavior.
- No-trade zone detector.
- Symbol-specific profiles.
- Trade quality grading.
- Walk-forward train/test split.
- Risk governor recommendations.

## Top Research Results

| rule_id | symbol | timeframe | side | verdict | approved_matches | avg_sniper_score | approved_win_rate | approved_return | approved_profit_factor | walk_forward_test_return | walk_forward_test_pf | best_exit_mode |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PAIR023 | CRASH300N | 15m | buy | APPROVED_RESEARCH | 29 | 85.62 | 0.7241 | 0.283689 | 5.6028 | 0.146663 | 7.6624 | test fixed_1r_or_breakeven |
| PAIR017 | CRASH300N | 15m | buy | APPROVED_RESEARCH | 80 | 88.9 | 0.7375 | 0.535187 | 5.1791 | 0.210789 | 5.9298 | test fixed_2r_or_trail_after_1r |
| PAIR019 | CRASH300N | 15m | buy | APPROVED_RESEARCH | 34 | 86.53 | 0.7941 | 0.383997 | 5.0005 | 0.158982 | 4.7946 | test fixed_2r_or_trail_after_1r |
| PAIR029 | CRASH300N | 15m | sell | APPROVED_RESEARCH | 30 | 85.87 | 0.6333 | 0.260335 | 3.7675 | 0.152487 | 7.7448 | test fixed_1r_or_breakeven |
| PAIR001 | BOOM300N | 15m | buy | APPROVED_RESEARCH | 92 | 93.88 | 0.6957 | 0.969697 | 3.4231 | 0.457521 | 4.5541 | test fixed_1r_or_breakeven |
| PAIR024 | CRASH300N | 15m | buy | APPROVED_RESEARCH | 55 | 86.64 | 0.6909 | 0.510483 | 3.1525 | 0.175221 | 2.6399 | test fixed_1r_or_breakeven |
| PAIR006 | BOOM300N | 15m | buy | APPROVED_RESEARCH | 16 | 80.0 | 0.6875 | 0.111153 | 3.1222 | 0.039975 | 2.779 | test fixed_1r_or_breakeven |
| PAIR002 | BOOM300N | 15m | buy | APPROVED_RESEARCH | 128 | 85.56 | 0.5859 | 1.08944 | 2.5851 | 1.069125 | 8.8583 | test fixed_2r_or_trail_after_1r |
| PAIR005 | BOOM300N | 15m | buy | NEEDS_MORE_TRADES | 7 | 79.0 | 0.4286 | 0.017953 | 1.5739 | -0.010097 | 0.5281 | test fixed_2r_or_trail_after_1r |
| PAIR016 | BOOM300N | 15m | sell | NEEDS_MORE_TRADES | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | none |

## Promotion Result

- Research-approved candidates: 8
- These are not live rules yet. They must be paper-tested separately before promotion.

## Next Safe Step

Use the approved research candidates only in a new experimental paper track after the current open paper trade closes or in a separate runner with different output files.
