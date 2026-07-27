# Paper Protection Bundle Report

Last updated UTC: 2026-07-27T20:47:51.486025+00:00

These protections run before new paper entries are added or when open paper positions are updated.

| guard | status | what_it_does |
| --- | --- | --- |
| Emergency paper stop enforcer | active | Closes paper trades when latest candles breach stop or take-profit. |
| Duplicate trade guard | active | Blocks another open paper trade on the same symbol/timeframe. |
| Max open trades limit | active | Caps each paper track at 4 open positions by default. |
| Rule cooldown | active | Blocks a rule after recent closed losses. |
| Instrument exposure guard | active | Limits stacked Boom/Crash exposure in the same direction. |
| Fresh candle guard | active | Blocks entries when local candle data is too stale. |
| Paper slippage/spread simulation | active | Charges paper exits a small cost so results are less optimistic. |
| Promotion pack generator | active | Builds a paper-evidence package for promising rules. |

## Current Protection Alerts

No current protection alerts.
