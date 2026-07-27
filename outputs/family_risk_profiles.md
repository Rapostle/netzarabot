# Family-Specific Risk Profiles

Last updated UTC: 2026-07-27T20:47:51.425964+00:00

These are paper risk profiles. They are not live-money settings yet.

| family | paper_risk | max_open | time_stop | notes |
| --- | --- | --- | --- | --- |
| Boom/Crash 1m | 0.15%-0.25% | 1 | 8 candles | Fastest and noisiest. Require spike and spread guard. |
| Boom/Crash 5m | 0.25%-0.40% | 2 | 10 candles | Good for expansion, but kill losers quickly. |
| Boom/Crash 15m | 0.30%-0.50% | 2 | 12 candles | Current main testing zone. |
| Boom/Crash 30m | 0.30%-0.50% | 2 | 10 candles | Needs patience but avoid stale trades. |
| Volatility indices | 0.20%-0.35% | 1 | 12 candles | Separate profile; do not share Boom/Crash rules blindly. |
| Forex | 0.25%-0.50% | 2 | session-based | Needs session, spread, and news filters. |
| Crypto | 0.15%-0.30% | 1 | volatility-based | Use wider volatility guard and weekend rules. |
