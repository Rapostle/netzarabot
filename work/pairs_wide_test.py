"""Wider pairs test: every pair among the checker's coins, same rule as work/pairs_test.py, fixed in advance. Research only; never trades.

Daily closes come from checker.data (Binance, cached). All pairs are traded; nothing is picked afterwards.
Judges, both against shuffled spreads (same size of moves, random order):
  1. all pairs pooled: does the average trade beat the shuffles' average?
  2. the BEST single pair: does it beat the best pair of each shuffle? (Looking at many pairs always turns up a lucky one; this measures that.)

    .venv/bin/python work/pairs_wide_test.py --null-runs 200
"""
from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pairs_test as PT  # noqa: E402

MIN_DAYS = 500
MIN_TRADES = 10


def build_spreads(closes: dict[str, pd.Series]) -> dict[tuple[str, str], np.ndarray]:
    out = {}
    for a, b in itertools.combinations(sorted(closes), 2):
        j = pd.concat([closes[a], closes[b]], axis=1, join="inner").dropna()
        if len(j) >= MIN_DAYS:
            out[(a, b)] = np.log(j.iloc[:, 0].to_numpy() / j.iloc[:, 1].to_numpy())
    return out


def shuffled(sp: np.ndarray, rng) -> np.ndarray:
    d = np.diff(sp)
    return np.r_[sp[0], sp[0] + np.cumsum(rng.permutation(d))]


def evaluate(spreads: dict, null_runs: int, seed: int = 9) -> dict:
    real = {k: np.array(PT.trades(sp, 0.0)) for k, sp in spreads.items()}
    real = {k: v for k, v in real.items() if len(v) >= MIN_TRADES}
    if not real:
        return {"pairs": 0}
    allg = np.concatenate(list(real.values()))
    means = {k: float(v.mean()) for k, v in real.items()}
    best = max(means, key=means.get)
    rng = np.random.default_rng(seed)
    null_pool, null_best = [], []
    for _ in range(null_runs):
        per = []
        for k in real:
            r = PT.trades(shuffled(spreads[k], rng), 0.0)
            if len(r) >= MIN_TRADES:
                per.append(r)
        if per:
            null_pool.append(float(np.concatenate([np.array(x) for x in per]).mean()))
            null_best.append(max(float(np.mean(x)) for x in per))
    np_, nb = np.array(null_pool), np.array(null_best)
    return {"pairs": len(real), "trades": len(allg), "gross": float(allg.mean()), "net": float(allg.mean() - PT.COST),
            "positive": int(sum(m > 0 for m in means.values())), "means": means, "best": best, "best_mean": means[best],
            "pool_null": float(np.nanmean(np_)), "pool_luck": float((np.sum(np_ >= allg.mean()) + 1) / (len(np_) + 1)),
            "best_null": float(np.nanmean(nb)), "best_luck": float((np.sum(nb >= means[best]) + 1) / (len(nb) + 1)),
            "first_half": float(np.concatenate([v[:len(v) // 2] for v in real.values()]).mean()),
            "second_half": float(np.concatenate([v[len(v) // 2:] for v in real.values()]).mean())}


def render(r: dict) -> str:
    if not r.get("pairs"):
        return "No pair had enough trades."
    top = sorted(r["means"].items(), key=lambda kv: -kv[1])[:5]
    lines = [f"{r['pairs']} pairs, {r['trades']} trades | gross {r['gross'] * 100:+.2f}% per trade | net {r['net'] * 100:+.2f}% (cost {PT.COST * 100:.1f}%)",
             f"pairs positive before costs: {r['positive']} of {r['pairs']} | first halves {r['first_half'] * 100:+.2f}%, second halves {r['second_half'] * 100:+.2f}%",
             f"all pairs pooled vs shuffles: shuffles average {r['pool_null'] * 100:+.2f}% | chance of matching by luck {r['pool_luck']:.2f}",
             f"best pair {r['best'][0]}/{r['best'][1]}: {r['best_mean'] * 100:+.2f}% per trade vs the best pair of a shuffle averaging {r['best_null'] * 100:+.2f}% | chance by luck {r['best_luck']:.2f}",
             "top five: " + ", ".join(f"{a}/{b} {m * 100:+.2f}%" for (a, b), m in top)]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--null-runs", type=int, default=200)
    ap.add_argument("--seed", type=int, default=9)
    a = ap.parse_args()
    from checker.data import COINS, fetch_close
    closes = {}
    for c in COINS:
        try:
            closes[c] = fetch_close(c)
        except Exception as exc:
            print(f"{c}: no prices ({exc})")
    spreads = build_spreads(closes)
    print(f"{len(closes)} coins, {len(spreads)} pairs with at least {MIN_DAYS} common days.\n")
    print(render(evaluate(spreads, a.null_runs, a.seed)))
    print("\nCount it only if both luck chances are about 0.05 or below, both halves are positive, and net is positive.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
