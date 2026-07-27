# Instrument Expansion Plan

Last updated UTC: 2026-07-27T20:20:07.202642+00:00

The app should expand only from rules that survive the sniper gate, not from losing tracks.

## Current Strong Base

| symbol | approved_rules | best_profit_factor | next_step |
| --- | --- | --- | --- |
| BOOM300N | 3 | 3.42 | paper-test sniper rules, then test sibling Boom/Crash symbols |
| CRASH300N | 5 | 5.60 | paper-test sniper rules, then test sibling Boom/Crash symbols |

## Expansion Queue

| family | timeframes | status |
| --- | --- | --- |
| Boom/Crash | 1m, 5m, 15m, 30m | next expansion target |
| Volatility indices | 5m, 15m, 30m | after Boom/Crash sniper rules stabilize |
| Forex | 5m, 15m, 1h | separate profile required |
| Crypto | 5m, 15m, 1h | separate volatility limits required |
| Commodities | 15m, 1h | lower priority |

## Completed Expansion Research

- Boom/Crash expansion report: `outputs/boom_crash_expansion_report.md`
- Boom/Crash expansion execution candidates: `outputs/boom_crash_expansion_execution_candidates.csv`

Instruction: do not mix new instruments into the current paper ledgers. Use separate output files for each expansion batch.
