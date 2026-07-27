# Bot Format / Export Plan

Last updated UTC: 2026-07-27T20:47:53.175502+00:00

Recommended final format: Web dashboard + Python Deriv engine first.

| format | status | why |
| --- | --- | --- |
| Python Deriv API bot | best first version | Matches the current code and Deriv data flow. |
| Web dashboard | build now | Gives users buttons and reports without touching code. |
| MT5 EA | later/export target | Useful for MT5 users, but it would require translating rules and execution. |
| Hybrid | later | Python research engine plus EA execution bridge after rules prove themselves. |

Do not export to EA until the paper tracks have enough closed trades and stable rule scorecards.
