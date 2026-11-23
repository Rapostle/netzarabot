"""Pairs test on crypto: does the price ratio of two coins snap back to its average? Research only; it never trades.

Spread = log(A / B) on DAILY closes (from the saved hourly files, UTC days). Rule, fixed in advance:
  z = (spread - mean of the last 60 days) / standard deviation of the last 60 days, using data up to the day's close.
  z >= +2: the ratio is stretched high, so SHORT A and LONG B in equal dollars. z <= -2: the reverse.
  Exit when z crosses back through 0, or after 30 days, or when |z| reaches 4 against us (stop). One position per pair at a time.
Result of a trade = change in the spread in our favour (equal-dollar legs), as a share of ONE leg's dollars.
Costs: four taker trades of 0.1% = 0.4% of one leg's dollars per round trip (shown as net). Gross = zero cost.
Judge: the same rule on shuffled spread changes (same size of moves, random order, mean reversion destroyed). Count only a result that beats its shuffles.

    python work/pairs_test.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import power_of_three_test as P  # noqa: E402

PAIRS = [("ETHUSDT", "BTCUSDT"), ("SOLUSDT", "ETHUSDT"), ("BNBUSDT", "BTCUSDT"), ("LTCUSDT", "BTCUSDT"),
         ("ADAUSDT", "XRPUSDT"), ("DOGEUSDT", "ADAUSDT"), ("LINKUSDT", "ETHUSDT"), ("DOTUSDT", "ADAUSDT")]
WINDOW, ENTER_Z, STOP_Z, MAX_DAYS = 60, 2.0, 4.0, 30
COST = 0.004


def daily_close(symbol: str) -> pd.Series | None:
    f = P.load(symbol)
    if f is None:
        return None
    d = P.whole_days(f)
    if len(d) < 24 * 400:
        return None
    return d.groupby("day")["close"].last()


def trades(spread: np.ndarray, cost: float = 0.0) -> list[float]:
    s = pd.Series(spread)
    z = ((s - s.rolling(WINDOW).mean()) / s.rolling(WINDOW).std()).to_numpy()
    out, t = [], WINDOW
    while t < len(s) - 1:
        if np.isfinite(z[t]) and abs(z[t]) >= ENTER_Z:
            side = -1.0 if z[t] > 0 else 1.0           # +1 = long the spread (long A, short B)
            for k in range(t + 1, min(t + MAX_DAYS, len(s) - 1) + 1):
                crossed = z[k] * z[t] <= 0
                stopped = np.isfinite(z[k]) and (side * z[k] <= -STOP_Z)
                if crossed or stopped or k == min(t + MAX_DAYS, len(s) - 1):
                    out.append(side * (spread[k] - spread[t]) - cost)
                    t = k
                    break
        t += 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--null-runs", type=int, default=200)
    ap.add_argument("--seed", type=int, default=9)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    spreads = {}
    for x, y in PAIRS:
        cx, cy = daily_close(x), daily_close(y)
        if cx is None or cy is None:
            continue
        j = pd.concat([cx, cy], axis=1, join="inner").dropna()
        if len(j) > 500:
            spreads[(x, y)] = np.log(j.iloc[:, 0].to_numpy() / j.iloc[:, 1].to_numpy())
    print(f"{len(spreads)} pairs with enough data.\n")
    g_all, n_all, h1, h2, pos = [], [], [], [], 0
    for (x, y), sp in spreads.items():
        g = np.array(trades(sp, 0.0))
        if len(g) == 0:
            continue
        h = len(g) // 2
        g_all.append(g); n_all.append(g - COST); h1.append(g[:h]); h2.append(g[h:])
        pos += g.mean() > 0
        print(f"  {x}/{y}: {len(sp)} days, {len(g)} trades, gross {g.mean() * 100:+.2f}% per trade, win rate {(g > 0).mean():.0%}")
    if not g_all:
        print("no trades"); return 0
    g, n = np.concatenate(g_all), np.concatenate(n_all)
    se = g.std() / np.sqrt(len(g))
    print(f"\n=== pairs, all together ===\n{len(g)} trades | win rate {(g > 0).mean():.0%} | gross {g.mean() * 100:+.2f}% per trade ({g.mean() / se:+.1f} std errors) | net {n.mean() * 100:+.2f}% per trade")
    print(f"first halves {np.concatenate(h1).mean() * 100:+.2f}%, second halves {np.concatenate(h2).mean() * 100:+.2f}% | pairs positive: {pos} of {len(g_all)}")
    null = []
    for _ in range(a.null_runs):
        rs = []
        for sp in spreads.values():
            d = np.diff(sp)
            fake = np.r_[sp[0], sp[0] + np.cumsum(rng.permutation(d))]
            rs += trades(fake, 0.0)
        null.append(np.mean(rs) if rs else np.nan)
    null = np.array(null)
    luck = (np.nansum(null >= g.mean()) + 1) / (np.isfinite(null).sum() + 1)
    print(f"shuffled spreads: average {np.nanmean(null) * 100:+.2f}% per trade, best {np.nanmax(null) * 100:+.2f}% | chance of matching the real gross by luck: {luck:.2f}")
    print("Count the rule only if: gross beats its shuffles (luck chance about 0.02 or below), positive in both halves and most pairs, and still positive net.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
