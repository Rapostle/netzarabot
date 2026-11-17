"""Mechanical price-action features for the walk-forward search (no hand-drawn lines, no hindsight).

Every column is computed for candle t from candles up to and including t only. Swing points need `PIVOT_K`
candles on each side, so a swing is only used from `PIVOT_K` candles AFTER it happened (when it is confirmed).
Each column holds a small set of text labels, like the existing indicator conditions, so the same train /
validation / test protocol and shuffled-data comparison judge them.

Families: market structure, break of structure, liquidity sweeps, trendline breaks, support/resistance touches,
candlestick patterns, fair value gaps, order blocks and higher-timeframe trend.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

PIVOT_K = 3          # candles each side to confirm a swing high or low
NEAR_ATR = 0.5       # "at" a level means within this many ATRs
FVG_MIN_ATR = 0.3    # a gap must be at least this many ATRs to count
FVG_LIFE = 20        # candles a fair value gap or order block stays "fresh"
OB_LIFE = 30
DISPLACEMENT_ATR = 1.5

COLUMNS = ["structure", "bos", "sweep", "trendline", "sr_zone", "candle_pattern", "fvg", "order_block", "htf_trend"]


def _swings(high: np.ndarray, low: np.ndarray):
    """Confirmed swing highs/lows as of each candle: (price, index) of the latest two of each."""
    n = len(high)
    sh = [[np.nan, -1], [np.nan, -1]]   # [latest, previous]
    sl = [[np.nan, -1], [np.nan, -1]]
    out = np.full((n, 8), np.nan)
    k = PIVOT_K
    for t in range(n):
        i = t - k
        if i >= k:
            if high[i] >= high[i - k:i + k + 1].max() and high[i] > high[i - 1]:
                sh = [[high[i], i], sh[0]]
            if low[i] <= low[i - k:i + k + 1].min() and low[i] < low[i - 1]:
                sl = [[low[i], i], sl[0]]
        out[t] = [sh[0][0], sh[0][1] if sh[0][1] >= 0 else np.nan, sh[1][0], sh[1][1] if sh[1][1] >= 0 else np.nan,
                  sl[0][0], sl[0][1] if sl[0][1] >= 0 else np.nan, sl[1][0], sl[1][1] if sl[1][1] >= 0 else np.nan]
    return out


def price_action_conditions(df: pd.DataFrame, htf_factor: int = 12) -> pd.DataFrame:
    o, h, l, c = (df[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    atr = df["atr_14"].to_numpy(float)
    n = len(df)
    sw = _swings(h, l)
    h1, h1i, h0, h0i, l1, l1i, l0, l0i = (sw[:, j] for j in range(8))
    none = np.full(n, "None", dtype=object)  # "None" is skipped by the search (no condition)

    structure, bos, sweep, trend, sr = (none.copy() for _ in range(5))
    ok_h = np.isfinite(h0) & np.isfinite(h1)
    ok_l = np.isfinite(l0) & np.isfinite(l1)
    both = ok_h & ok_l
    structure[both & (h1 > h0) & (l1 > l0)] = "uptrend_hh_hl"
    structure[both & (h1 < h0) & (l1 < l0)] = "downtrend_lh_ll"
    structure[both & ~((h1 > h0) & (l1 > l0)) & ~((h1 < h0) & (l1 < l0))] = "mixed"

    prev_c = np.r_[np.nan, c[:-1]]
    bos[np.isfinite(h1) & (c > h1) & (prev_c <= h1)] = "bos_up"
    bos[np.isfinite(l1) & (c < l1) & (prev_c >= l1)] = "bos_down"

    sweep[np.isfinite(h1) & (h > h1) & (c < h1)] = "sweep_high"
    sweep[np.isfinite(l1) & (l < l1) & (c > l1)] = "sweep_low"

    # trendlines through the last two confirmed swings, only when they slope the "right" way
    t_idx = np.arange(n, dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        res_slope = (h1 - h0) / (h1i - h0i)
        sup_slope = (l1 - l0) / (l1i - l0i)
        res_now = h1 + res_slope * (t_idx - h1i)
        res_prev = h1 + res_slope * (t_idx - 1 - h1i)
        sup_now = l1 + sup_slope * (t_idx - l1i)
        sup_prev = l1 + sup_slope * (t_idx - 1 - l1i)
    falling = ok_h & (h1 < h0)
    rising = ok_l & (l1 > l0)
    trend[falling & (c > res_now) & (prev_c <= res_prev)] = "resistance_line_break_up"
    trend[rising & (c < sup_now) & (prev_c >= sup_prev)] = "support_line_break_down"
    trend[rising & (np.abs(l - sup_now) <= NEAR_ATR * atr) & (c > sup_now)] = "support_line_bounce"
    trend[falling & (np.abs(h - res_now) <= NEAR_ATR * atr) & (c < res_now)] = "resistance_line_rejection"

    sr[np.isfinite(l1) & (np.abs(l - l1) <= NEAR_ATR * atr) & (c > l1)] = "at_support"
    sr[np.isfinite(h1) & (np.abs(h - h1) <= NEAR_ATR * atr) & (c < h1)] = "at_resistance"

    body = np.abs(c - o)
    top, bot = np.maximum(o, c), np.minimum(o, c)
    rng = np.maximum(h - l, 1e-12)
    po, pc = np.r_[np.nan, o[:-1]], np.r_[np.nan, c[:-1]]
    ph, pl = np.r_[np.nan, h[:-1]], np.r_[np.nan, l[:-1]]
    ptop, pbot = np.maximum(po, pc), np.minimum(po, pc)
    candle = none.copy()
    candle[(h < ph) & (l > pl)] = "inside_bar"
    candle[(pc < po) & (c > o) & (top >= ptop) & (bot <= pbot) & (body > 0)] = "bull_engulfing"
    candle[(pc > po) & (c < o) & (top >= ptop) & (bot <= pbot) & (body > 0)] = "bear_engulfing"
    lower, upper = bot - l, h - top
    candle[(lower >= 2 * np.maximum(body, 1e-12)) & (lower >= 0.6 * rng) & (upper <= 0.2 * rng)] = "bull_pin_bar"
    candle[(upper >= 2 * np.maximum(body, 1e-12)) & (upper >= 0.6 * rng) & (lower <= 0.2 * rng)] = "bear_pin_bar"

    # fair value gaps and order blocks, each fresh for a limited number of candles
    fvg, ob = none.copy(), none.copy()
    bull_gap = None  # (low_edge, high_edge, born)
    bear_gap = None
    bull_ob = None
    bear_ob = None
    for t in range(2, n):
        a = atr[t]
        if not np.isfinite(a) or a <= 0:
            continue
        if l[t] - h[t - 2] >= FVG_MIN_ATR * a and c[t] > o[t]:
            bull_gap = (h[t - 2], l[t], t)
            fvg[t] = "bull_fvg_formed"
        elif l[t - 2] - h[t] >= FVG_MIN_ATR * a and c[t] < o[t]:
            bear_gap = (h[t], l[t - 2], t)
            fvg[t] = "bear_fvg_formed"
        else:
            if bull_gap and t - bull_gap[2] <= FVG_LIFE and t > bull_gap[2] and l[t] <= bull_gap[1] and c[t] >= bull_gap[0]:
                fvg[t] = "bull_fvg_retest"
            elif bear_gap and t - bear_gap[2] <= FVG_LIFE and t > bear_gap[2] and h[t] >= bear_gap[0] and c[t] <= bear_gap[1]:
                fvg[t] = "bear_fvg_retest"
        if body[t] >= DISPLACEMENT_ATR * a:
            if c[t] > o[t] and c[t - 1] < o[t - 1]:
                bull_ob = (l[t - 1], h[t - 1], t)
            elif c[t] < o[t] and c[t - 1] > o[t - 1]:
                bear_ob = (l[t - 1], h[t - 1], t)
        else:
            if bull_ob and t - bull_ob[2] <= OB_LIFE and l[t] <= bull_ob[1] and c[t] >= bull_ob[0]:
                ob[t] = "bull_order_block_retest"
            elif bear_ob and t - bear_ob[2] <= OB_LIFE and h[t] >= bear_ob[0] and c[t] <= bear_ob[1]:
                ob[t] = "bear_order_block_retest"

    # higher timeframe: last COMPLETED block of `htf_factor` candles, close versus its 20-block average
    f = max(2, int(htf_factor))
    blocks = n // f
    htf = none.copy()
    if blocks >= 25:
        block_close = pd.Series(c[f - 1: blocks * f: f])
        ema = block_close.ewm(span=20, adjust=False).mean()
        up = (block_close > ema) & (ema > ema.shift(1))
        down = (block_close < ema) & (ema < ema.shift(1))
        done = (np.arange(n) + 1) // f - 1  # last completed block as of candle t
        valid = done >= 20
        idx = np.clip(done, 0, blocks - 1)
        htf[valid & up.to_numpy()[idx]] = "htf_up"
        htf[valid & down.to_numpy()[idx]] = "htf_down"

    return pd.DataFrame({"structure": structure, "bos": bos, "sweep": sweep, "trendline": trend, "sr_zone": sr,
                         "candle_pattern": candle, "fvg": fvg, "order_block": ob, "htf_trend": htf}, index=df.index)
