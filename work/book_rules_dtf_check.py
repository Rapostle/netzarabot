"""Follow-up on the dual time frame stochastic rule (dtf): is its small gross gain real, and what cost can it survive?
For every market: gross result in both halves. Pooled: net result at several round-trip costs (slippage off),
break-even cost, and a shuffled-price luck test at zero cost.
Usage: python work/book_rules_dtf_check.py --symbols A B C --timeframe 5m --null-runs 50
"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import book_rules_test as b  # noqa: E402
import walk_forward_rule_search as wf  # noqa: E402

RULE = "dtf"
COSTS = (0.0, 0.0001, 0.0002, 0.0003, 0.0005, 0.001)   # round trip as a share of price


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", default="outputs/history")
    p.add_argument("--symbols", nargs="+", required=True)
    p.add_argument("--timeframe", default="5m")
    p.add_argument("--min-bars", type=int, default=5000)
    p.add_argument("--null-runs", type=int, default=50)
    p.add_argument("--seed", type=int, default=9)
    a = p.parse_args()
    frames = {}
    for sym in a.symbols:
        df = wf.load_history(Path(a.data_dir), sym, a.timeframe)
        if df is not None and len(df) >= a.min_bars:
            frames[sym] = df.reset_index(drop=True)
    sigs = {s: b.find_signals(d, RULE) for s, d in frames.items()}
    b.SLIP = 0.0
    print("dtf, zero cost and zero slippage, per market:")
    allg, first, second, pos = [], [], [], 0
    for s, d in frames.items():
        b.COST = 0.0
        r = b.simulate(d, sigs[s])["r"].to_numpy()
        h = len(r) // 2
        allg.append(r); first.append(r[:h]); second.append(r[h:])
        pos += r.mean() > 0
        print(f"  {s}: {len(r)} trades, {r.mean():+.2f}R per trade (first half {r[:h].mean():+.2f}R, second half {r[h:].mean():+.2f}R)")
    g, f1, f2 = np.concatenate(allg), np.concatenate(first), np.concatenate(second)
    se = g.std() / np.sqrt(len(g))
    print(f"\nPooled gross: {g.mean():+.3f}R per trade over {len(g)} trades (about {g.mean() / se:.1f} standard errors from zero). "
          f"First halves {f1.mean():+.3f}R, second halves {f2.mean():+.3f}R. Markets positive: {pos} of {len(frames)}.")
    print("\nPooled result if the round-trip cost were this share of price (no extra slippage):")
    for c in COSTS:
        b.COST = c
        rr = np.concatenate([b.simulate(d, sigs[s])["r"].to_numpy() for s, d in frames.items()])
        print(f"  {c * 100:.3f}% of price: {rr.mean():+.3f}R per trade")
    rng = np.random.default_rng(a.seed)
    b.COST = 0.0
    null = []
    for _ in range(a.null_runs):
        rs = [b.evaluate(wf.shuffle_bars(d, rng), RULE)["r"].to_numpy() for d in frames.values()]
        null.append(np.concatenate(rs).mean())
    null = np.array(null)
    beat = (np.sum(null >= g.mean()) + 1) / (len(null) + 1)
    print(f"\nShuffled-price luck test at zero cost: {len(null)} shuffles averaged {null.mean():+.3f}R (best {null.max():+.3f}R); "
          f"chance of matching the real {g.mean():+.3f}R by luck: {beat:.2f}")
    print("\nA real edge needs: gross positive in both halves and in most markets, luck chance near 0.02 or below, AND a break-even cost above what Deriv really charges.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
