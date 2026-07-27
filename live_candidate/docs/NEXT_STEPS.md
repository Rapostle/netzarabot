# Next Steps

1. Run the primary demo monitor first.
2. Let it collect separate closed paper trades.
3. Do not use real money yet.
4. Review after at least 30 closed trades.
5. If the win rate improves and drawdown stays acceptable, build the real Deriv live-pilot connector as a separate guarded step.

## Promotion Rules

The candidate should not move to a real-money pilot until:

- It has at least 30 closed paper trades in `live_candidate/outputs/`.
- Closed paper PnL is positive.
- There are no open trades.
- The win rate is materially closer to the 80% target.
- Manual review still passes.
- A daily loss limit and emergency stop-all are implemented for real orders.

## What To Watch

- Whether PAIR017 stays clean after more paper trades.
- Whether PAIR006 keeps helping or starts hurting.
- Whether the 2R profit lock improves captured profit.
- Whether losses remain near the planned risk.
