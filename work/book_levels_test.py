"""MSNR key-level rules from the book 'The MSNR' (S Fx 1075), coded as the book defines them and fixed BEFORE any result. Research only.

All levels come from 1-hour candles built from 5-minute data. A level is ONE price (the book says no zones). Entry is a limit order at the level
on the 5-minute chart after the setup candle has closed, valid for 24 hours. Stop is small. Target 2R. One trade at a time per market.

sbr_rbs  A pivot high's body top (resistance) broken by a candle BODY (opens below, closes above) becomes support: RBS, buy the retest.
         A pivot low's body bottom (support) broken by a candle body (opens above, closes below) becomes resistance: SBR, sell the retest.
         Stop 0.5 hourly ATR beyond the level.
qml      Quasimodo. Bullish: pivot low L1, then a pivot high H, then a LOWER pivot low LL (liquidity grab), then a 1-hour close above H (structure
         break). Buy limit at L1's body bottom, stop below LL by 0.1 ATR. Bearish is the mirror (sell at the body top of the first pivot high).
ocl      Open-Close Level. Two consecutive same-colour 1-hour candles whose bodies are each at least 0.5 ATR and where the second opens within
         0.15 ATR of the first's close. Level = the second candle's open. Bullish pair: buy the return to it; bearish pair: sell it.
         Stop 0.5 hourly ATR beyond the level.

The judge: gross (no cost) AND the same rule on shuffled prices at zero cost. A rule only counts if it beats its own shuffles.

    python work/book_levels_test.py --data-dir outputs/history --symbols CRASH300N R_75 --timeframe 5m
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import walk_forward_rule_search as wf  # noqa: E402
import book_rules_test as b  # noqa: E402

FACTOR = 12
PIVOT_K = 3
LOOKBACK = 60            # 1-hour candles a level stays alive
ENTRY_HOURS = 24
STOP_ATR, QML_PAD_ATR = 0.5, 0.1
BREAK_ATR = 0.1
OCL_BODY_ATR, OCL_GAP_ATR = 0.5, 0.15
MAX_STOP_ATR = 3.0
REWARD = 2.0
NET_COST = 0.0002        # round trip share of price used for the 'net' line
RULES = ("sbr_rbs", "qml", "ocl")


def htf(df: pd.DataFrame):
    n = len(df) // FACTOR
    sl = slice(0, n * FACTOR)
    o = df["open"].to_numpy(float)[sl].reshape(n, FACTOR)[:, 0]
    h = df["high"].to_numpy(float)[sl].reshape(n, FACTOR).max(axis=1)
    l = df["low"].to_numpy(float)[sl].reshape(n, FACTOR).min(axis=1)
    c = df["close"].to_numpy(float)[sl].reshape(n, FACTOR)[:, -1]
    return o, h, l, c, b._atr(h, l, c)


def pivots(h, l):
    """Pivot highs and lows: arrays of (index, confirmed_at). A pivot at i is known only after PIVOT_K more candles."""
    ph, pl = [], []
    for i in range(PIVOT_K, len(h) - PIVOT_K):
        if h[i] > h[i - PIVOT_K:i].max() and h[i] >= h[i + 1:i + 1 + PIVOT_K].max():
            ph.append(i)
        if l[i] < l[i - PIVOT_K:i].min() and l[i] <= l[i + 1:i + 1 + PIVOT_K].min():
            pl.append(i)
    return ph, pl


def place(df5, j, side, level, stop, atr, out, o5, h5, l5):
    """Limit order at `level` after hourly candle j closed. First 5-minute candle that trades through it fills."""
    risk0 = side * (level - stop)
    if not (0 < risk0 <= MAX_STOP_ATR * atr):
        return
    t0 = (j + 1) * FACTOR
    for t in range(t0, min(t0 + ENTRY_HOURS * FACTOR, len(df5) - 1)):
        touched = (l5[t] <= level) if side > 0 else (h5[t] >= level)
        if not touched:
            if (side > 0 and l5[t] <= stop) or (side < 0 and h5[t] >= stop):
                return                      # price went through the stop without touching the level: setup is dead
            continue
        entry = min(level, o5[t]) if side > 0 else max(level, o5[t])
        risk = side * (entry - stop)
        if risk > 0:
            out.append((t, side, entry, stop, entry + side * REWARD * risk))
        return


def sbr_rbs(df):
    o5, h5, l5 = (df[x].to_numpy(float) for x in ("open", "high", "low"))
    o, h, l, c, atr = htf(df)
    ph, pl = pivots(h, l)
    out, used = [], set()
    for j in range(PIVOT_K * 2 + 2, len(c)):
        a = atr[j]
        if not np.isfinite(a) or a <= 0:
            continue
        for p in ph:                      # resistance broken by a body -> RBS buy
            if p + PIVOT_K >= j or j - p > LOOKBACK or ("h", p) in used:
                continue
            lvl = max(o[p], c[p])
            if c[p + PIVOT_K + 1:j].size and c[p + PIVOT_K + 1:j].max() > lvl:
                used.add(("h", p)); continue
            if o[j] <= lvl < c[j] and c[j] - lvl >= BREAK_ATR * a:
                used.add(("h", p))
                place(df, j, 1, lvl, lvl - STOP_ATR * a, a, out, o5, h5, l5)
        for p in pl:                      # support broken by a body -> SBR sell
            if p + PIVOT_K >= j or j - p > LOOKBACK or ("l", p) in used:
                continue
            lvl = min(o[p], c[p])
            if c[p + PIVOT_K + 1:j].size and c[p + PIVOT_K + 1:j].min() < lvl:
                used.add(("l", p)); continue
            if o[j] >= lvl > c[j] and lvl - c[j] >= BREAK_ATR * a:
                used.add(("l", p))
                place(df, j, -1, lvl, lvl + STOP_ATR * a, a, out, o5, h5, l5)
    return out


def qml(df):
    o5, h5, l5 = (df[x].to_numpy(float) for x in ("open", "high", "low"))
    o, h, l, c, atr = htf(df)
    ph, pl = pivots(h, l)
    out, used = [], set()
    for j in range(PIVOT_K * 2 + 2, len(c)):
        a = atr[j]
        if not np.isfinite(a) or a <= 0:
            continue
        lows = [p for p in pl if p + PIVOT_K < j]
        highs = [p for p in ph if p + PIVOT_K < j]
        if len(lows) >= 2 and highs:        # bullish: L1, H, LL(lower), then close above H
            ll, l1 = lows[-1], lows[-2]
            hs = [p for p in highs if l1 < p < ll]
            if hs and l[ll] < l[l1] and j - ll <= 20 and ("b", ll) not in used:
                hp = hs[-1]
                if c[j] > h[hp] and c[j - 1] <= h[hp]:
                    used.add(("b", ll))
                    lvl = min(o[l1], c[l1])
                    place(df, j, 1, lvl, l[ll] - QML_PAD_ATR * a, a, out, o5, h5, l5)
        if len(highs) >= 2 and lows:        # bearish: H1, L, HH(higher), then close below L
            hh, h1 = highs[-1], highs[-2]
            ls = [p for p in lows if h1 < p < hh]
            if ls and h[hh] > h[h1] and j - hh <= 20 and ("s", hh) not in used:
                lp = ls[-1]
                if c[j] < l[lp] and c[j - 1] >= l[lp]:
                    used.add(("s", hh))
                    lvl = max(o[h1], c[h1])
                    place(df, j, -1, lvl, h[hh] + QML_PAD_ATR * a, a, out, o5, h5, l5)
    return out


def ocl(df):
    o5, h5, l5 = (df[x].to_numpy(float) for x in ("open", "high", "low"))
    o, h, l, c, atr = htf(df)
    out = []
    for j in range(2, len(c)):
        a = atr[j]
        if not np.isfinite(a) or a <= 0:
            continue
        b1, b2 = c[j - 1] - o[j - 1], c[j] - o[j]
        if abs(o[j] - c[j - 1]) > OCL_GAP_ATR * a or min(abs(b1), abs(b2)) < OCL_BODY_ATR * a:
            continue
        if b1 > 0 and b2 > 0:
            place(df, j, 1, o[j], o[j] - STOP_ATR * a, a, out, o5, h5, l5)
        elif b1 < 0 and b2 < 0:
            place(df, j, -1, o[j], o[j] + STOP_ATR * a, a, out, o5, h5, l5)
    return out


FINDERS = {"sbr_rbs": sbr_rbs, "qml": qml, "ocl": ocl}


def trades(df, rule, cost):
    df = df.reset_index(drop=True)
    b.COST, b.SLIP = cost, 0.0
    return b.simulate(df, FINDERS[rule](df))


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
            g = trades(d, rule, 0.0)["r"].to_numpy()
            n = trades(d, rule, NET_COST)["r"].to_numpy()
            if len(g) == 0:
                continue
            h = len(g) // 2
            g_all.append(g); n_all.append(n); f1.append(g[:h]); f2.append(g[h:])
            pos += g.mean() > 0
        if not g_all:
            print(f"=== {rule}: no trades ===\n"); continue
        g, n = np.concatenate(g_all), np.concatenate(n_all)
        se = g.std() / np.sqrt(len(g)) if len(g) > 1 else float("nan")
        print(f"=== {rule} ===")
        print(f"{len(g)} trades in {len(g_all)} markets | win rate {(g > 0).mean():.0%} | gross {g.mean():+.3f}R ({g.mean() / se:+.1f} std errors) | net {n.mean():+.3f}R")
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
