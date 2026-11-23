"""Miner, 'High Probability Trading Strategies' chapter 4 (internal retracements), coded as stated and fixed BEFORE any result. Research only.

The book's claim: a correction against a trend leg usually ends near the .382, .50, .618 or .786 retracement of that leg, and the trend then resumes.
Test of that claim on 1-hour swings built from 5-minute data:
  A leg is a confirmed 1-hour pivot high with the previous pivot low before it (or the mirror for down legs), at least 2 hourly ATR tall.
  The limit order sits at the chosen retracement of the leg, valid for 24 hours, only if price has not yet reached it when the pivot is confirmed.
  Cancelled if price makes a new extreme beyond the leg's end first (the trend resumed without a correction).
  Stop: below the .786 retracement by 0.1 ATR. Target: the leg's end (the swing high for a buy). Costs and shuffles as in the other tests.
fib618   limit at the .618 retracement
fib50    limit at the .50 retracement

    python work/book_fib_test.py --data-dir outputs/history --symbols CRASH300N R_75 --timeframe 5m
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import walk_forward_rule_search as wf  # noqa: E402
import book_rules_test as b  # noqa: E402
import book_levels_test as L  # noqa: E402

MIN_LEG_ATR = 2.0
STOP_RATIO, PAD_ATR = 0.786, 0.1
RATIOS = {"fib618": 0.618, "fib50": 0.50}
RULES = tuple(RATIOS)
NET_COST = 0.0002


def fib_signals(df, ratio: float):
    df = df.reset_index(drop=True)
    o5, h5, l5 = (df[x].to_numpy(float) for x in ("open", "high", "low"))
    o, h, l, c, atr = L.htf(df)
    ph, pl = L.pivots(h, l)
    out, K = [], L.PIVOT_K
    for p in ph:                                   # up leg: pivot low q, then pivot high p; buy the pullback
        j = p + K
        q = [x for x in pl if x < p]
        if not q or j + 1 >= len(c):
            continue
        q = q[-1]
        a = atr[j]
        leg = h[p] - l[q]
        if not np.isfinite(a) or leg < MIN_LEG_ATR * a:
            continue
        level = h[p] - ratio * leg
        stop = h[p] - STOP_RATIO * leg - PAD_ATR * a
        if c[j] <= level or h[p + 1:j + 1].max() > h[p]:
            continue
        _place(df, j, 1, level, stop, h[p], a, out, h5, l5, o5)
    for p in pl:                                   # down leg: pivot high q, then pivot low p; sell the bounce
        j = p + K
        q = [x for x in ph if x < p]
        if not q or j + 1 >= len(c):
            continue
        q = q[-1]
        a = atr[j]
        leg = h[q] - l[p]
        if not np.isfinite(a) or leg < MIN_LEG_ATR * a:
            continue
        level = l[p] + ratio * leg
        stop = l[p] + STOP_RATIO * leg + PAD_ATR * a
        if c[j] >= level or l[p + 1:j + 1].min() < l[p]:
            continue
        _place(df, j, -1, level, stop, l[p], a, out, h5, l5, o5)
    return sorted(out)


def _place(df, j, side, level, stop, end, a, out, h5, l5, o5):
    t0 = (j + 1) * L.FACTOR
    for t in range(t0, min(t0 + L.ENTRY_HOURS * L.FACTOR, len(df) - 1)):
        if (side > 0 and h5[t] > end) or (side < 0 and l5[t] < end):
            return                                  # trend resumed without a pullback to the level
        touched = (l5[t] <= level) if side > 0 else (h5[t] >= level)
        if touched:
            entry = min(level, o5[t]) if side > 0 else max(level, o5[t])
            risk, reward = side * (entry - stop), side * (end - entry)
            if 0 < risk <= L.MAX_STOP_ATR * a and reward >= 0.5 * risk:
                out.append((t, side, entry, stop, end))
            return


def trades(df, rule, cost):
    df = df.reset_index(drop=True)
    b.COST, b.SLIP = cost, 0.0
    return b.simulate(df, fib_signals(df, RATIOS[rule]))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--data-dir", default="outputs/history")
    p.add_argument("--symbols", nargs="+", required=True)
    p.add_argument("--timeframe", default="5m")
    p.add_argument("--rules", nargs="+", default=list(RULES), choices=RULES)
    p.add_argument("--null-runs", type=int, default=30)
    p.add_argument("--min-bars", type=int, default=5000)
    p.add_argument("--seed", type=int, default=9)
    a = p.parse_args()
    frames = {}
    for s in a.symbols:
        d = wf.load_history(Path(a.data_dir), s, a.timeframe)
        if d is not None and len(d) >= a.min_bars:
            frames[s] = d.reset_index(drop=True)
    print(f"{len(frames)} markets. Gross = zero cost. Net = round-trip cost {NET_COST * 100:.2f}% of price. Shuffles are run at zero cost too.\n")
    for rule in a.rules:
        g_all, n_all, f1, f2, pos = [], [], [], [], 0
        for s, d in frames.items():
            g, n = trades(d, rule, 0.0)["r"].to_numpy(), trades(d, rule, NET_COST)["r"].to_numpy()
            if len(g) == 0:
                continue
            h = len(g) // 2
            g_all.append(g); n_all.append(n); f1.append(g[:h]); f2.append(g[h:])
            pos += g.mean() > 0
        if not g_all:
            print(f"=== {rule}: no trades ===\n"); continue
        g, n = np.concatenate(g_all), np.concatenate(n_all)
        se = g.std() / np.sqrt(len(g)) if len(g) > 1 else float("nan")
        print(f"=== {rule} ===\n{len(g)} trades in {len(g_all)} markets | win rate {(g > 0).mean():.0%} | gross {g.mean():+.3f}R ({g.mean() / se:+.1f} std errors) | net {n.mean():+.3f}R")
        print(f"first halves {np.concatenate(f1).mean():+.3f}R, second halves {np.concatenate(f2).mean():+.3f}R | markets with positive gross: {pos} of {len(g_all)}")
        rng = np.random.default_rng(a.seed)
        null = []
        for _ in range(a.null_runs):
            rs = [trades(wf.shuffle_bars(d, rng), rule, 0.0)["r"].to_numpy() for d in frames.values()]
            rs = [x for x in rs if len(x)]
            null.append(np.concatenate(rs).mean() if rs else np.nan)
        null = np.array(null)
        luck = (np.nansum(null >= g.mean()) + 1) / (np.isfinite(null).sum() + 1)
        print(f"shuffled prices (zero cost): average {np.nanmean(null):+.3f}R, best {np.nanmax(null):+.3f}R | chance of matching the real gross by luck: {luck:.2f}\n")
    print("Count a rule only if: gross beats its shuffles (luck chance about 0.02 or below), positive in both halves and most markets, and still positive net.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
