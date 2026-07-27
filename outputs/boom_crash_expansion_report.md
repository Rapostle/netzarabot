# Boom/Crash Expansion Lab

Last updated UTC: 2026-07-11T14:23:26.855164+00:00

This is a separate research scan. It does not touch current paper trades and does not place live trades.

## Expansion Summary

- Raw expansion candidates mined: 334
- Sniper-approved research candidates: 172
- Execution candidate rows written: 172

## Strongest Symbols / Timeframes

| symbol | timeframe | approved_rules | best_profit_factor | avg_score | best_return |
| --- | --- | --- | --- | --- | --- |
| BOOM300N | 1m | 6 | inf | 83.4 | 0.3507 |
| CRASH500 | 30m | 6 | 54.91 | 88.0 | 0.3035 |
| BOOM900 | 15m | 6 | 44.45 | 87.1 | 0.1147 |
| BOOM900 | 30m | 6 | 25.41 | 84.9 | 0.4416 |
| BOOM500 | 30m | 6 | 21.64 | 86.6 | 0.3258 |
| BOOM300N | 15m | 6 | 21.32 | 92.5 | 1.0052 |
| BOOM1000 | 15m | 6 | 20.16 | 86.3 | 0.1364 |
| BOOM600 | 15m | 6 | 15.59 | 82.3 | 0.0945 |
| BOOM600 | 30m | 6 | 10.27 | 82.2 | 0.1725 |
| CRASH300N | 5m | 6 | 10.06 | 91.1 | 0.3777 |
| CRASH1000 | 30m | 6 | 8.44 | 84.3 | 0.1860 |
| CRASH300N | 15m | 6 | 7.65 | 85.9 | 0.3940 |
| CRASH500 | 15m | 6 | 6.39 | 89.1 | 0.8380 |
| CRASH600 | 15m | 6 | 6.20 | 88.5 | 0.1897 |
| BOOM900 | 5m | 5 | inf | 89.2 | 0.1332 |
| CRASH600 | 30m | 5 | 42.66 | 86.2 | 0.2224 |
| BOOM150N | 30m | 5 | 38.67 | 83.0 | 0.0729 |
| BOOM1000 | 5m | 5 | 16.24 | 80.8 | 0.0323 |
| CRASH1000 | 5m | 5 | 12.11 | 84.1 | 0.0681 |
| BOOM1000 | 30m | 5 | 10.94 | 86.3 | 0.1541 |
| CRASH150N | 30m | 5 | 8.65 | 84.1 | 0.1105 |
| CRASH500 | 5m | 5 | 8.20 | 83.7 | 0.0958 |
| CRASH1000 | 15m | 5 | 5.14 | 85.6 | 0.0885 |
| BOOM300N | 5m | 5 | 3.64 | 82.0 | 1.0010 |
| CRASH600 | 5m | 4 | 23.64 | 81.0 | 0.2097 |
| CRASH900 | 15m | 4 | 21.68 | 82.9 | 0.1131 |
| CRASH900 | 30m | 4 | 18.35 | 85.8 | 0.2521 |
| BOOM600 | 5m | 4 | 11.29 | 90.5 | 0.0973 |
| BOOM500 | 5m | 4 | 5.92 | 83.9 | 0.0497 |
| BOOM500 | 15m | 4 | 3.88 | 83.5 | 0.1691 |
| CRASH300N | 1m | 3 | 4.16 | 84.7 | 0.1788 |
| CRASH900 | 5m | 3 | 3.41 | 90.2 | 0.0249 |
| BOOM50 | 30m | 2 | 263.86 | 86.7 | 0.0246 |
| BOOM150N | 15m | 2 | 7.82 | 93.8 | 0.0154 |
| CRASH50 | 30m | 2 | 6.40 | 82.0 | 0.0115 |
| CRASH150N | 15m | 1 | 9.78 | 85.2 | 0.0170 |
| CRASH500 | 1m | 1 | 5.76 | 84.0 | 0.0451 |

## Top Approved / Near-Approved Rules

| rule_id | symbol | timeframe | side | verdict | approved_matches | avg_sniper_score | approved_win_rate | approved_return | approved_profit_factor | walk_forward_test_return | walk_forward_test_pf | best_exit_mode |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BCX0053 | BOOM300N | 1m | buy | APPROVED_RESEARCH | 22 | 85.64 | 1.0 | 0.098167 | inf | 0.031903 | inf | test fixed_1r_or_breakeven |
| BCX0161 | BOOM900 | 5m | buy | APPROVED_RESEARCH | 14 | 84.36 | 1.0 | 0.050489 | inf | 0.0176 | inf | test fixed_1r_or_breakeven |
| BCX0083 | BOOM50 | 30m | buy | APPROVED_RESEARCH | 24 | 87.5 | 0.9583 | 0.024617 | 263.8622 | 0.006971 | 75.433 | test fixed_2r_or_trail_after_1r |
| BCX0275 | CRASH500 | 30m | buy | APPROVED_RESEARCH | 30 | 94.5 | 0.9333 | 0.303505 | 54.9062 | 0.143911 | inf | test fixed_2r_or_trail_after_1r |
| BCX0146 | BOOM900 | 15m | sell | APPROVED_RESEARCH | 25 | 88.32 | 0.96 | 0.084926 | 44.4524 | 0.037939 | inf | test fixed_2r_or_trail_after_1r |
| BCX0302 | CRASH600 | 30m | sell | APPROVED_RESEARCH | 27 | 88.81 | 0.9259 | 0.142832 | 42.6558 | 0.058553 | 34.9163 | test fixed_1r_or_breakeven |
| BCX0038 | BOOM150N | 30m | buy | APPROVED_RESEARCH | 62 | 82.61 | 0.8871 | 0.072877 | 38.667 | 0.021045 | 18.4348 | test fixed_2r_or_trail_after_1r |
| BCX0143 | BOOM900 | 15m | buy | APPROVED_RESEARCH | 33 | 90.0 | 0.8788 | 0.11471 | 28.559 | 0.064055 | 27.0011 | test fixed_1r_or_breakeven |
| BCX0054 | BOOM300N | 1m | buy | APPROVED_RESEARCH | 28 | 85.07 | 0.9643 | 0.11109 | 25.7346 | 0.059805 | inf | test fixed_1r_or_breakeven |
| BCX0158 | BOOM900 | 30m | sell | APPROVED_RESEARCH | 30 | 96.83 | 0.9333 | 0.164575 | 25.4149 | 0.080443 | inf | test fixed_2r_or_trail_after_1r |
| BCX0303 | CRASH600 | 30m | sell | APPROVED_RESEARCH | 43 | 86.84 | 0.8372 | 0.184885 | 23.9654 | 0.078706 | 28.3434 | test fixed_1r_or_breakeven |
| BCX0306 | CRASH600 | 5m | buy | APPROVED_RESEARCH | 49 | 79.63 | 0.9388 | 0.106376 | 23.635 | 0.029344 | 12.1009 | test fixed_2r_or_trail_after_1r |
| BCX0311 | CRASH900 | 15m | buy | APPROVED_RESEARCH | 22 | 78.45 | 0.8636 | 0.054085 | 21.6757 | 0.022208 | 12.1797 | test fixed_1_5r_no_partial |
| BCX0110 | BOOM500 | 30m | sell | APPROVED_RESEARCH | 45 | 90.56 | 0.9333 | 0.325792 | 21.6449 | 0.13283 | inf | test fixed_2r_or_trail_after_1r |
| BCX0312 | CRASH900 | 15m | buy | APPROVED_RESEARCH | 25 | 81.16 | 0.84 | 0.078904 | 21.3908 | 0.061017 | inf | test fixed_2r_or_trail_after_1r |
| BCX0050 | BOOM300N | 15m | sell | APPROVED_RESEARCH | 28 | 93.71 | 0.8214 | 0.281418 | 21.3234 | 0.105421 | 12.3667 | test fixed_2r_or_trail_after_1r |
| BCX0001 | BOOM1000 | 15m | buy | APPROVED_RESEARCH | 27 | 84.19 | 0.9259 | 0.082225 | 20.1563 | 0.062054 | inf | test fixed_1r_or_breakeven |
| BCX0326 | CRASH900 | 30m | sell | APPROVED_RESEARCH | 35 | 83.71 | 0.7714 | 0.242047 | 18.349 | 0.120414 | 30.3673 | test fixed_1r_or_breakeven |
| BCX0147 | BOOM900 | 15m | sell | APPROVED_RESEARCH | 23 | 81.39 | 0.913 | 0.072457 | 17.6361 | 0.026035 | 34.7118 | test fixed_2r_or_trail_after_1r |
| BCX0313 | CRASH900 | 15m | buy | APPROVED_RESEARCH | 44 | 79.59 | 0.8409 | 0.113072 | 16.4637 | 0.06521 | 20.6147 | test fixed_2r_or_trail_after_1r |

## What To Do With This

- Keep these separate from the current paper tracks.
- Only paper-test expansion candidates after the current open paper trades close, or in a separate ledger.
- Do not promote any expansion candidate to live trading yet.
