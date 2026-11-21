"""Rules taken from the books Sam supplied, coded exactly and fixed BEFORE looking at any result. Research only: it never trades.

dtf         Miner, 'Dual Time Frame Momentum': a higher-time-frame (1 hour) stochastic sets direction, a 5-minute stochastic reversal in that
            direction, made inside the not-overbought / not-oversold zone, gives the setup. Entry: buy-stop at the reversal candle's high
            (sell-stop at its low), valid for 3 candles. Stop: beyond the last 5 candles' extreme. Target 2R.
tri_height  Advanced Sniper (triangles) and the chart-pattern book (rectangles, triangles): 1-hour consolidation between two lines through the
            last two swing highs and last two swing lows; a 1-hour close beyond a line breaks it; then wait for the pullback and enter on the
            first 5-minute candle that resumes the break. Stop back inside the pattern. Target: the pattern height projected from the break.
tri_3r      The same entries, with the book's fixed 3R target instead of the pattern height.

    python work/book_rules_test.py --data-dir outputs/history --symbols CRASH300N R_75 --timeframe 5m
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import walk_forward_rule_search as wf  # noqa: E402
import price_action_features as pa  # noqa: E402

FACTOR = 12            # 5-minute candles in one 1-hour candle
STOCH_N, STOCH_SMOOTH = 14, 3
OB, OS = 75.0, 25.0
DTF_WINDOW = 3         # candles the buy-stop / sell-stop stays valid
DTF_STOP_BARS, DTF_PAD_ATR, DTF_REWARD = 5, 0.1, 2.0
TRI_MIN_SPAN, TRI_MAX_SPAN, TRI_MIN_GAP = 8, 80, 3
TRI_BREAK_ATR, TRI_PAD_ATR, TRI_ENTRY_WINDOW = 0.1, 0.5, 24
MAX_STOP_ATR = 3.0
LIMIT = 96
COST = 0.001
SLIP = 0.2
FIXED_REWARD = 3.0
RULES = ("dtf", "tri_height", "tri_3r")


def slow_stochastic(high, low, close) -> np.ndarray:
    h, l, c = (pd.Series(x, dtype=float) for x in (high, low, close))
    hh, ll = h.rolling(STOCH_N).max(), l.rolling(STOCH_N).min()
    raw = 100.0 * (c - ll) / (hh - ll).replace(0.0, np.nan)
    return raw.rolling(STOCH_SMOOTH).mean().to_numpy()


def _atr(high, low, close, n=14) -> np.ndarray:
    h, l, c = (pd.Series(x, dtype=float) for x in (high, low, close))
    prev = c.shift(1)
    tr = pd.concat([h - l, (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean().to_numpy()


def htf_bars(df: pd.DataFrame):
    """1-hour candles built from the 5-minute ones (finished candles only): high, low, close, atr."""
    blocks = len(df) // FACTOR
    h = df["high"].to_numpy(float)[: blocks * FACTOR].reshape(blocks, FACTOR).max(axis=1)
    l = df["low"].to_numpy(float)[: blocks * FACTOR].reshape(blocks, FACTOR).min(axis=1)
    c = df["close"].to_numpy(float)[FACTOR - 1: blocks * FACTOR: FACTOR]
    return h, l, c, _atr(h, l, c)


def dtf_signals(df: pd.DataFrame) -> list[tuple[int, int, float, float, float]]:
    """(entry candle, side, entry, stop, target)."""
    o, h, l, c = (df[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    n = len(df)
    atr = _atr(h, l, c)
    k5 = slow_stochastic(h, l, c)
    hh, hl, hc, _ = htf_bars(df)
    kh = slow_stochastic(hh, hl, hc)
    out, last_entry = [], -1
    for t in range(wf.WARMUP_BARS, n - DTF_WINDOW - 1):
        a = atr[t]
        if not np.isfinite(a) or a <= 0 or not np.isfinite(k5[t - 2:t + 1]).all():
            continue
        j = (t + 1) // FACTOR - 1
        if j < 2 or j >= len(kh) or not np.isfinite(kh[j - 1:j + 1]).all():
            continue
        bull_htf = kh[j] > kh[j - 1] and kh[j] < OB
        bear_htf = kh[j] < kh[j - 1] and kh[j] > OS
        up = k5[t] > k5[t - 1] and k5[t - 1] <= k5[t - 2] and k5[t] < OB
        down = k5[t] < k5[t - 1] and k5[t - 1] >= k5[t - 2] and k5[t] > OS
        if bull_htf and up:
            side, level = 1, h[t]
            stop = l[t - DTF_STOP_BARS + 1:t + 1].min() - DTF_PAD_ATR * a
        elif bear_htf and down:
            side, level = -1, l[t]
            stop = h[t - DTF_STOP_BARS + 1:t + 1].max() + DTF_PAD_ATR * a
        else:
            continue
        for k in range(t + 1, t + 1 + DTF_WINDOW):
            fill = (h[k] >= level) if side > 0 else (l[k] <= level)
            if fill:
                entry = max(level, o[k]) if side > 0 else min(level, o[k])
                risk = side * (entry - stop)
                if 0 < risk <= MAX_STOP_ATR * a and k > last_entry:
                    out.append((k, side, entry, stop, entry + side * DTF_REWARD * risk))
                    last_entry = k
                break
    return out


def tri_signals(df: pd.DataFrame, fixed: bool) -> list[tuple[int, int, float, float, float]]:
    o, c5 = df["open"].to_numpy(float), df["close"].to_numpy(float)
    hh, hl, hc, ha = htf_bars(df)
    blocks = len(hh)
    sw = pa._swings(hh, hl)
    out = []
    for j in range(30, blocks):
        s = sw[j]
        sh0, ih0, sh1, ih1, sl0, il0, sl1, il1 = s[0], s[1], s[2], s[3], s[4], s[5], s[6], s[7]
        if not np.isfinite(s).all() or ih0 == ih1 or il0 == il1:
            continue
        if min(abs(ih0 - ih1), abs(il0 - il1)) < TRI_MIN_GAP:
            continue
        start = min(ih1, il1)
        if not (TRI_MIN_SPAN <= j - start <= TRI_MAX_SPAN):
            continue
        su, sl_ = (sh0 - sh1) / (ih0 - ih1), (sl0 - sl1) / (il0 - il1)
        up = lambda i: sh0 + su * (i - ih0)
        lo = lambda i: sl0 + sl_ * (i - il0)
        a = ha[j]
        if not np.isfinite(a) or a <= 0:
            continue
        height0 = up(start) - lo(start)
        if height0 < a or up(j) - lo(j) <= 0 or up(j) - lo(j) > 1.05 * height0:   # converging or parallel only
            continue
        buy = hc[j] > up(j) + TRI_BREAK_ATR * a and hc[j - 1] <= up(j - 1)
        sell = hc[j] < lo(j) - TRI_BREAK_ATR * a and hc[j - 1] >= lo(j - 1)
        if not (buy or sell):
            continue
        side = 1 if buy else -1
        line = up(j) if buy else lo(j)
        t0 = (j + 1) * FACTOR
        for t in range(t0, min(t0 + TRI_ENTRY_WINDOW, len(df) - 1)):
            resume = (c5[t - 1] < o[t - 1] and c5[t] > o[t] and c5[t] > line) if buy else (c5[t - 1] > o[t - 1] and c5[t] < o[t] and c5[t] < line)
            if not resume:
                continue
            entry = c5[t]
            stop = line - side * TRI_PAD_ATR * a
            risk = side * (entry - stop)
            if 0 < risk <= MAX_STOP_ATR * a:
                target = entry + side * FIXED_REWARD * risk if fixed else line + side * height0
                if side * (target - entry) > 0.5 * risk:
                    out.append((t, side, entry, stop, target))
            break
    return out


def find_signals(df: pd.DataFrame, rule: str):
    df = df.reset_index(drop=True)
    if rule == "dtf":
        return dtf_signals(df)
    return tri_signals(df, fixed=(rule == "tri_3r"))


def simulate(df: pd.DataFrame, signals) -> pd.DataFrame:
    """One trade at a time; result in R (1R = distance to the stop); the stop wins when both are touched in one candle."""
    h, l, c = (df[x].to_numpy(float) for x in ("high", "low", "close"))
    rows, free = [], 0
    for t, side, entry, stop, target in sorted(signals):
        if t < free or t + 1 >= len(df):
            continue
        risk = abs(entry - stop)
        exit_i, r = None, None
        for k in range(t, min(t + LIMIT, len(df) - 1) + 1):
            stop_hit = l[k] <= stop if side > 0 else h[k] >= stop
            take_hit = k > t and (h[k] >= target if side > 0 else l[k] <= target)   # the entry candle can stop us out, not reward us
            if stop_hit:
                exit_i, r = k, -1.0 - SLIP
                break
            if take_hit:
                exit_i, r = k, side * (target - entry) / risk
                break
        if exit_i is None:
            exit_i = min(t + LIMIT, len(df) - 1)
            r = side * (c[exit_i] - entry) / risk
        r -= COST * entry / risk
        rows.append({"i": t, "side": side, "exit": exit_i, "r": r})
        free = exit_i + 1
    return pd.DataFrame(rows, columns=["i", "side", "exit", "r"])


def evaluate(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    df = df.reset_index(drop=True)
    return simulate(df, find_signals(df, rule))


def luck_chance(df: pd.DataFrame, rule: str, real_mean: float, runs: int, seed: int) -> float:
    rng = np.random.default_rng(seed)
    beat = 0
    for _ in range(runs):
        t = evaluate(wf.shuffle_bars(df, rng), rule)
        if len(t) and t["r"].mean() >= real_mean:
            beat += 1
    return (beat + 1) / (runs + 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data-dir", default="outputs/history")
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--timeframe", default="5m")
    parser.add_argument("--rules", nargs="+", default=list(RULES), choices=RULES)
    parser.add_argument("--null-runs", type=int, default=100)
    parser.add_argument("--min-bars", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=9)
    args = parser.parse_args()
    print("Book rules, fixed in advance; one test per rule per market. Judge the pooled line for each rule, not single markets.\n")
    for rule in args.rules:
        print(f"=== {rule} ===")
        pooled, n_all, tested = 0.0, 0, 0
        for sym in args.symbols:
            df = wf.load_history(Path(args.data_dir), sym, args.timeframe)
            if df is None or len(df) < args.min_bars:
                print(f"{sym}: skipped (not enough history)")
                continue
            t = evaluate(df, rule)
            if len(t) == 0:
                print(f"{sym}: no trades")
                continue
            tested += 1
            pooled += float(t["r"].sum())
            n_all += len(t)
            wins = int((t["r"] > 0).sum())
            half = len(t) // 2
            p = luck_chance(df, rule, float(t["r"].mean()), args.null_runs, args.seed)
            print(f"{sym}: {len(t)} trades ({int((t['side'] > 0).sum())} buys, {int((t['side'] < 0).sum())} sells), win rate {wins / len(t):.0%}, "
                  f"average {t['r'].mean():+.2f}R per trade, total {t['r'].sum():+.1f}R, luck chance {p:.2f}")
            print(f"   first half {t['r'].iloc[:half].mean():+.2f}R | second half {t['r'].iloc[half:].mean():+.2f}R")
        avg = pooled / n_all if n_all else float("nan")
        print(f"{rule} all markets together: {n_all} trades, {pooled:+.1f}R in total, {avg:+.2f}R per trade. Markets with trades: {tested}.\n")
    print("Three rules over many markets means many chances for luck. A single market at 0.05 is expected by chance; trust only a pooled gain that holds in both halves.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
