"""Cost check for the Power of Three rules on every coin already downloaded: gross, break-even cost, net at several round-trip costs.
Uses the saved files in outputs/history_crypto_1h. No download, no shuffles.

    python work/power_of_three_costs.py --symbols BTCUSDT ETHUSDT ...
"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import power_of_three_test as P  # noqa: E402

COSTS = (0.0002, 0.0004, 0.0006, 0.0008, 0.001, 0.002)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", required=True)
    ap.add_argument("--rules", nargs="+", default=list(P.RULES))
    a = ap.parse_args()
    frames = {s: P.load(s) for s in a.symbols}
    frames = {s: f for s, f in frames.items() if f is not None and len(f) > 24 * 400}
    print(f"{len(frames)} coins with saved data.\n")
    for rule in a.rules:
        g = np.concatenate([P.trades(f, rule, 0.0) for f in frames.values()])
        n = np.concatenate([P.trades(f, rule, P.NET_COST) for f in frames.values()])
        load = (g.mean() - n.mean()) / P.NET_COST          # average of entry/risk, so cost in R = cost * load
        print(f"=== {rule} ===\n{len(g)} trades | gross {g.mean():+.3f}R | average stop {100 / load:.2f}% of price | break-even round-trip cost {100 * g.mean() / load:.3f}% of price")
        for c in COSTS:
            print(f"  round trip {c * 100:.2f}% of price: net {g.mean() - c * load:+.3f}R per trade")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
