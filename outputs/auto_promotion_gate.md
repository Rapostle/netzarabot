# Auto-Promotion Gate

Last updated UTC: 2026-07-27T20:20:06.712747+00:00

This file decides what each paper track is allowed to become. It does not place trades.

| track | decision | reason | closed_trades | closed_pnl | open_positions |
| --- | --- | --- | --- | --- | --- |
| Original stable rules | REJECT / QUARANTINE | Closed paper PnL is beyond the loss limit. | 9 | -134.75 | 0 |
| Experimental pair candidates | ELIGIBLE FOR MANUAL REVIEW | Enough trades and positive paper PnL, but manual review is still required. | 23 | 161.69 | 0 |
| Advanced sniper candidates | KEEP PAPER TESTING | Needs a larger paper sample before any live step. | 19 | 153.61 | 0 |

Rules:

- Losing tracks are quarantined.
- Tracks with open paper trades must wait.
- Tracks with fewer than 10 closed paper trades stay in paper testing.
- No track can move toward live trading with negative closed paper PnL.
