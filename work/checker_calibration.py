"""How often does the checker pass a planted edge, and how often does it pass pure noise?

Synthetic markets only (no network). The numbers feed the 'tested accuracy' line of the bot.
    python3 work/checker_calibration.py --series 30
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from checker import engine  # noqa: E402


def market(seed: int, drift: float, n: int = 2500) -> pd.Series:
    rng = np.random.default_rng(seed)
    r = np.zeros(n)
    sign, left = 1.0, 0
    for i in range(n):
        if left == 0:
            sign, left = rng.choice([-1.0, 1.0]), int(rng.integers(50, 110))
        left -= 1
        r[i] = sign * drift + rng.normal(0.0, 0.03)
    idx = pd.date_range("2017-01-01", periods=n + 1, freq="D", tz="UTC")
    return pd.Series(100 * np.cumprod(np.r_[1.0, 1 + r]), index=idx)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--series", type=int, default=30)
    parser.add_argument("--null-runs", type=int, default=500)
    args = parser.parse_args()
    print(f"{args.series} synthetic markets per row, 6.8 years of daily data, rule momentum_60, costs 0.2% round trip, luck chance corrected for 9 rules")
    print("planted_drift_per_day  share_passed  share_inconclusive  share_no_evidence")
    for drift in (0.0, 0.0005, 0.001, 0.002, 0.004):
        counts = {engine.VERDICT_PASS: 0, engine.VERDICT_MAYBE: 0, engine.VERDICT_NONE: 0}
        for seed in range(args.series):
            res = engine.run_check(market(1000 + seed, drift), "momentum_60", null_runs=args.null_runs, seed=seed, tests_counted=len(engine.RULE_NAMES))
            counts[res.verdict] = counts.get(res.verdict, 0) + 1
        n = args.series
        print(f"{drift:<22} {counts[engine.VERDICT_PASS] / n:<13.0%} {counts[engine.VERDICT_MAYBE] / n:<19.0%} {counts[engine.VERDICT_NONE] / n:.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
