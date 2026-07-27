# Paper Exit Optimizer

Last updated UTC: 2026-07-27T20:47:44.304390+00:00

This checks whether simple fixed-R exits would have beaten the actual paper exit on recent closed trades.

| track | symbol | side | actual_pnl | best_exit | best_pnl | difference |
| --- | --- | --- | --- | --- | --- | --- |
| Original stable rules | CRASH300N | sell | -30.00 | fixed_1r | -30.00 | 0.00 |
| Original stable rules | CRASH300N | sell | -30.00 | actual | -30.00 | 0.00 |
| Original stable rules | CRASH300N | sell | -30.00 | actual | -30.00 | 0.00 |
| Original stable rules | CRASH300N | sell | -5.70 | actual | -5.70 | 0.00 |
| Original stable rules | CRASH300N | sell | -30.00 | actual | -30.00 | 0.00 |
| Original stable rules | CRASH300N | sell | -5.17 | actual | -5.17 | 0.00 |
| Original stable rules | CRASH300N | buy | -30.00 | actual | -30.00 | 0.00 |
| Original stable rules | CRASH300N | buy | 29.27 | fixed_1r | 30.00 | 0.73 |
| Experimental pair candidates | CRASH300N | buy | -30.33 | fixed_1r | -30.00 | 0.33 |
| Experimental pair candidates | BOOM300N | buy | -30.28 | fixed_1r | -30.00 | 0.28 |
| Experimental pair candidates | BOOM300N | buy | 26.25 | actual | 26.25 | 0.00 |
| Experimental pair candidates | CRASH300N | buy | 18.38 | fixed_1r | 30.00 | 11.62 |
| Experimental pair candidates | BOOM300N | sell | -30.29 | fixed_1r | -30.00 | 0.29 |
| Experimental pair candidates | CRASH300N | buy | 35.71 | actual | 35.71 | 0.00 |
| Experimental pair candidates | CRASH300N | buy | 35.70 | fixed_1_5r | 37.33 | 1.63 |
| Experimental pair candidates | BOOM300N | buy | 35.65 | fixed_2r | 60.00 | 24.35 |
| Advanced sniper candidates | CRASH300N | buy | 35.69 | actual | 35.69 | 0.00 |
| Advanced sniper candidates | CRASH300N | buy | -30.33 | fixed_1r | -30.00 | 0.33 |
| Advanced sniper candidates | BOOM300N | buy | -30.28 | fixed_1r | -30.00 | 0.28 |
| Advanced sniper candidates | BOOM300N | buy | 26.53 | actual | 26.53 | 0.00 |
| Advanced sniper candidates | BOOM300N | buy | -5.41 | actual | -5.41 | 0.00 |
| Advanced sniper candidates | CRASH300N | buy | 18.94 | fixed_1r | 30.00 | 11.06 |
| Advanced sniper candidates | CRASH300N | buy | 35.71 | actual | 35.71 | 0.00 |
| Advanced sniper candidates | CRASH300N | buy | 35.70 | fixed_1_5r | 38.23 | 2.54 |

Treat this as research only. Exit changes still need backtesting and paper testing.
