"""Sam's sniper entry, coded exactly as he described it and fixed BEFORE looking at any result.

Direction: the 4-hour trend (built from the 5-minute candles, finished 4-hour candles only).
    up   = last finished 4h close is above its 20-candle average and that average is rising
    down = the reverse
Zone: the latest CONFIRMED 4-hour swing low (support) or swing high (resistance); a swing needs 3 finished 4h candles after it.
Touch (5-minute): for a buy, a candle's low comes within 0.5 ATR of support (or below it) while it closes back above it;
    for a sell, the mirror at resistance.
Confirmation (5-minute): within the last 3 candles there was a touch, and this candle is a bullish engulfing or bullish pin bar (buy),
    or a bearish engulfing or bearish pin bar (sell).
Agreement: buys only when the 4h trend is up, sells only when it is down.
Entry: at the close of the confirmation candle.  Stop: beyond the lowest low (highest high) of the last 3 candles plus 0.25 ATR; skip if the stop
    is more than 3 ATR away.  Target: 3 times the stop distance.  Time limit: 48 candles (4 hours).
Costs: 0.1% of price per trade, plus 20% of the stop distance extra when stopped out.  Trades never overlap.
Research only: it never trades.

    python work/sniper_test.py --data-dir outputs/history --symbols CRASH300N BOOM300N --timeframe 5m
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

BLOCK = 48            # 5-minute candles in a 4-hour candle
TOUCH_ATR = 0.5
CONFIRM_WINDOW = 3
STOP_PAD_ATR = 0.25
MAX_STOP_ATR = 3.0
REWARD_R = 3.0
LIMIT = 48
COST = 0.001
SLIP = 0.2
BULL = ("bull_engulfing", "bull_pin_bar")
BEAR = ("bear_engulfing", "bear_pin_bar")


def four_hour_context(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """For each 5-minute candle: 4h trend (+1 up, -1 down, 0 none), latest confirmed 4h swing low and swing high (NaN if none)."""
    n = len(df)
    blocks = n // BLOCK
    trend = np.zeros(n)
    low_lvl = np.full(n, np.nan)
    high_lvl = np.full(n, np.nan)
    if blocks < 25:
        return trend, low_lvl, high_lvl
    h = df["high"].to_numpy(float)[: blocks * BLOCK].reshape(blocks, BLOCK).max(axis=1)
    l = df["low"].to_numpy(float)[: blocks * BLOCK].reshape(blocks, BLOCK).min(axis=1)
    c = df["close"].to_numpy(float)[BLOCK - 1: blocks * BLOCK: BLOCK]
    ema = pd.Series(c).ewm(span=20, adjust=False).mean().to_numpy()
    up = (c > ema) & (np.r_[False, ema[1:] > ema[:-1]])
    down = (c < ema) & (np.r_[False, ema[1:] < ema[:-1]])
    sw = pa._swings(h, l)           # latest confirmed swing as of each finished 4h candle
    done = (np.arange(n) + 1) // BLOCK - 1     # last finished 4h candle as of each 5-minute candle
    ok = (done >= 20) & (done < blocks)
    idx = np.clip(done, 0, blocks - 1)
    trend[ok & up[idx]] = 1.0
    trend[ok & down[idx]] = -1.0
    low_lvl[ok] = sw[idx[ok], 4]
    high_lvl[ok] = sw[idx[ok], 0]
    return trend, low_lvl, high_lvl


def find_signals(df: pd.DataFrame) -> list[tuple[int, int, float, float]]:
    """(candle index, side, entry, stop) for every confirmation that satisfies the whole description."""
    ind = wf.add_indicators(df).reset_index(drop=True)
    o, h, l, c = (ind[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    atr = ind["atr_14"].to_numpy(float)
    pattern = pa.price_action_conditions(ind, BLOCK)["candle_pattern"].to_numpy()
    trend, s_low, s_high = four_hour_context(ind)
    touch_buy = np.isfinite(s_low) & (l <= s_low + TOUCH_ATR * atr) & (c >= s_low)
    touch_sell = np.isfinite(s_high) & (h >= s_high - TOUCH_ATR * atr) & (c <= s_high)
    out = []
    for t in range(wf.WARMUP_BARS, len(ind)):
        a = atr[t]
        if not np.isfinite(a) or a <= 0:
            continue
        lo, hi = t - CONFIRM_WINDOW + 1, t + 1
        if trend[t] > 0 and pattern[t] in BULL and touch_buy[lo:hi].any():
            stop = l[lo:hi].min() - STOP_PAD_ATR * a
            if 0 < c[t] - stop <= MAX_STOP_ATR * a:
                out.append((t, 1, c[t], stop))
        elif trend[t] < 0 and pattern[t] in BEAR and touch_sell[lo:hi].any():
            stop = h[lo:hi].max() + STOP_PAD_ATR * a
            if 0 < stop - c[t] <= MAX_STOP_ATR * a:
                out.append((t, -1, c[t], stop))
    return out


def simulate(df: pd.DataFrame, signals: list[tuple[int, int, float, float]]) -> pd.DataFrame:
    """Walk each signal forward; one trade at a time. Net result in R (1R = the stop distance)."""
    h, l, c = (df[x].to_numpy(float) for x in ("high", "low", "close"))
    rows, free = [], 0
    for t, side, entry, stop in signals:
        if t < free or t + 1 >= len(df):
            continue
        risk = abs(entry - stop)
        target = entry + side * REWARD_R * risk
        exit_i, r = None, None
        for k in range(t + 1, min(t + LIMIT, len(df) - 1) + 1):
            stop_hit = l[k] <= stop if side > 0 else h[k] >= stop
            take_hit = h[k] >= target if side > 0 else l[k] <= target
            if stop_hit:
                exit_i, r = k, -1.0 - SLIP
                break
            if take_hit:
                exit_i, r = k, REWARD_R
                break
        if exit_i is None:
            exit_i = min(t + LIMIT, len(df) - 1)
            r = side * (c[exit_i] - entry) / risk
        r -= COST * entry / risk
        rows.append({"i": t, "side": side, "exit": exit_i, "r": r})
        free = exit_i + 1
    return pd.DataFrame(rows, columns=["i", "side", "exit", "r"])


def evaluate(df: pd.DataFrame) -> pd.DataFrame:
    return simulate(df.reset_index(drop=True), find_signals(df))


def luck_chance(df: pd.DataFrame, real_mean: float, runs: int, seed: int) -> float:
    rng = np.random.default_rng(seed)
    beat = 0
    for _ in range(runs):
        t = evaluate(wf.shuffle_bars(df, rng))
        if len(t) and t["r"].mean() >= real_mean:
            beat += 1
    return (beat + 1) / (runs + 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data-dir", default="outputs/history")
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--timeframe", default="5m")
    parser.add_argument("--null-runs", type=int, default=100)
    parser.add_argument("--min-bars", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=9)
    args = parser.parse_args()
    print("Sniper entry (4h direction, 5m touch + confirmation, stop beyond the zone, target 3R). Fixed in advance; one test per market.\n")
    total = 0
    for sym in args.symbols:
        df = wf.load_history(Path(args.data_dir), sym, args.timeframe)
        if df is None or len(df) < args.min_bars:
            print(f"{sym}: skipped (not enough history)")
            continue
        t = evaluate(df)
        if len(t) == 0:
            print(f"{sym}: no trades")
            continue
        total += 1
        wins = int((t["r"] > 0).sum())
        half = len(t) // 2
        p = luck_chance(df, float(t["r"].mean()), args.null_runs, args.seed)
        be = 1 / (1 + REWARD_R)
        print(f"{sym}: {len(t)} trades ({int((t['side'] > 0).sum())} buys, {int((t['side'] < 0).sum())} sells), win rate {wins / len(t):.0%} "
              f"(break-even about {be:.0%} before costs), average {t['r'].mean():+.2f}R per trade, total {t['r'].sum():+.1f}R, luck chance {p:.2f}")
        print(f"   first half {t['r'].iloc[:half].mean():+.2f}R | second half {t['r'].iloc[half:].mean():+.2f}R")
    print(f"\nMarkets with trades: {total}. With that many tests, one at 0.05 is expected by chance; judge the pattern across markets, not one market.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
