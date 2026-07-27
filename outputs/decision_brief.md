# Trading Bot Decision Brief

Last updated UTC: 2026-07-27T20:47:39.740082+00:00

Main answer: Do not use the original stable rules live. They are quarantined.

## Track Verdicts

| track | verdict | closed_trades | closed_pnl | open_positions | opened_this_run | blocked_this_run | latest_decisions |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Original stable rules | QUARANTINED | 9 | -134.75120968391016 | 0 | 0 | 0 | BOOM300N:no_trade, CRASH300N:no_trade |
| Experimental pair candidates | REVIEW BEFORE TINY PILOT | 23 | 161.68789167326113 | 0 | 0 | 0 | BOOM300N:no_trade, CRASH300N:no_trade |
| Advanced sniper candidates | REVIEW BEFORE TINY PILOT | 19 | 153.60831494341085 | 0 | 0 | 0 | BOOM300N:no_trade, CRASH300N:no_trade |
| Boom/Crash expansion candidates | KEEP PAPER TESTING | 4 | 10.709697611500605 | 0 | 0 | 1 | BOOM1000:blocked_guard, BOOM1000:no_trade, BOOM1000:no_trade, BOOM150N:no_trade, BOOM150N:no_trade, BOOM300N:no_trade, BOOM300N:no_trade, BOOM300N:no_trade, BOOM50:no_trade, BOOM500:no_trade, BOOM500:no_trade, BOOM500:no_trade, BOOM600:no_trade, BOOM600:no_trade, BOOM600:no_trade, BOOM900:no_trade, BOOM900:no_trade, BOOM900:no_trade, CRASH1000:no_trade, CRASH1000:no_trade, CRASH1000:no_trade, CRASH150N:no_trade, CRASH150N:no_trade, CRASH300N:no_trade, CRASH300N:no_trade, CRASH300N:no_trade, CRASH50:no_trade, CRASH500:no_trade, CRASH500:no_trade, CRASH500:no_trade, CRASH500:no_trade, CRASH600:no_trade, CRASH600:no_trade, CRASH600:no_trade, CRASH900:no_trade, CRASH900:no_trade, CRASH900:no_trade |

## What This Means

- Original stable rules: QUARANTINED. Keep them blocked from new entries while the loss remains beyond the safety limit.
- Experimental pair candidates: REVIEW BEFORE TINY PILOT. This is still useful, but it needs more closed paper trades.
- Experimental pair signal drought: Experimental pair is not frozen: it has 0 exact matches right now, 3 near miss(es), and 10 relaxed research candidate(s). It is probably too selective for fast evidence because it only watches BOOM300N/CRASH300N on 15m.
- Advanced sniper candidates: REVIEW BEFORE TINY PILOT. This is the stricter research track built from the 10 accuracy layers.
- Real-money trading: NOT READY.

## Next Checkpoint

Review the experimental pair track manually for drawdown, win rate, and repeated behavior.

Stop conditions:

- Stop considering any track that drops below the loss limit.
- Do not promote a track with fewer than 10 closed paper trades.
- Do not promote while any paper trade is still open.
- Do not promote if closed paper PnL is negative.
