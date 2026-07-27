# Self-Healing Monitor Check

Last updated UTC: 2026-07-27T20:20:08.331991+00:00

This is the monitor's own health check. It does not place trades.

| track | health | why | age_min | open | closed_pnl |
| --- | --- | --- | --- | --- | --- |
| Original stable rules | QUARANTINE | Closed paper PnL has breached the loss limit. | 0.7 | 0 | -134.75 |
| Experimental pair candidates | MANUAL REVIEW | Positive enough for human review, still not live-ready. | 0.4 | 0 | 161.69 |
| Advanced sniper candidates | MANUAL REVIEW | Positive enough for human review, still not live-ready. | 0.4 | 0 | 153.61 |
| Boom/Crash expansion candidates | KEEP PAPER TESTING | Sample size is still too small. | 3.4 | 0 | 10.71 |

If any row says `RESTART MONITOR`, stop the old Terminal loop with Ctrl+C, then start it again with:

`work/run_combined_paper_monitor.sh`
