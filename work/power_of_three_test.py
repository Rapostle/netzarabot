"""Time-of-day rules from Inner Circle Trader 'The Power of Three', coded as the text states them and fixed BEFORE any result. Research only.
Crypto only, hourly candles from the Binance public mirror (UTC = GMT). Deriv synthetic indices have no sessions, so these rules do not apply to them.

judas  A 3-day swing high on the DAILY chart (middle day's high above both neighbours) means look to SELL the day after the pattern forms; a swing
       low means BUY. That day, wait for the Judas swing: between 00:00 and 11:00 UTC price first pushes at least 0.3 daily ATR against the
       trade (above the day's open for a sell), then the first hourly CLOSE back through the day's open is the entry. Stop 0.1 daily ATR beyond the
       Judas extreme. Hold to 18:00 UTC (the text's last profit time) unless stopped. Daily ATR = the previous 14 days only.
wr     Williams %R (10 periods, hourly). The Asian range is 00:00-06:59 UTC. If the 07:00 candle (London open) trades below the Asian low and
       %R is oversold (<= -80) at its close, BUY at that close; if it trades above the Asian high and %R >= -20, SELL. Stop 0.1 hourly ATR
       beyond the candle's extreme. Hold to 18:00 UTC unless stopped.

The judge: gross (no cost), net at 0.2% round trip, and the same rule on day-shuffled prices (whole days permuted, so time-of-day habits stay
but the daily conditions are random). A rule counts only if it beats its shuffles.

    python work/power_of_three_test.py --download --symbols BTCUSDT ETHUSDT SOLUSDT BNBUSDT
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

BASE = "https://data-api.binance.vision/api/v3/klines"
DATA_DIR = Path("outputs/history_crypto_1h")
START_MS = int(pd.Timestamp("2019-01-01", tz="UTC").timestamp() * 1000)
JUDAS_ATR, JUDAS_PAD_ATR, MAX_STOP_ATR = 0.3, 0.1, 3.0
WR_LEN, WR_OS, WR_OB, WR_PAD_ATR = 10, -80.0, -20.0, 0.1
EXIT_HOUR = 18
NET_COST = 0.002
RULES = ("judas", "wr")


def download(symbol: str, directory: Path = DATA_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{symbol}_1h.csv"
    rows, cursor = [], START_MS
    while True:
        url = f"{BASE}?symbol={symbol}&interval=1h&limit=1000&startTime={cursor}"
        for attempt in range(4):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "research-script"})
                data = json.loads(urllib.request.urlopen(req, timeout=40).read())
                break
            except Exception:
                time.sleep(2 * (attempt + 1))
        else:
            raise RuntimeError(f"could not download {symbol}")
        if not data:
            break
        rows += [(int(k[0]) // 1000, float(k[1]), float(k[2]), float(k[3]), float(k[4])) for k in data]
        cursor = int(data[-1][0]) + 3600_000
        if len(data) < 1000:
            break
    df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close"]).drop_duplicates("time").sort_values("time")
    df.to_csv(path, index=False)
    return path


def load(symbol: str, directory: Path = DATA_DIR) -> pd.DataFrame | None:
    path = directory / f"{symbol}_1h.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    df["ts"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df.reset_index(drop=True)


def whole_days(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only complete UTC days (24 hourly candles in a row)."""
    d = df.copy()
    d["day"] = d["ts"].dt.floor("D")
    d = d[d.groupby("day")["ts"].transform("count") == 24]
    return d.reset_index(drop=True)


def day_shuffle(df: pd.DataFrame, rng) -> pd.DataFrame:
    """Permute whole days. Each day keeps its own intraday shape (relative to its open); days are chained so prices stay continuous."""
    d = whole_days(df)
    o, h, l, c = (d[x].to_numpy(float).reshape(-1, 24) for x in ("open", "high", "low", "close"))
    day_open = o[:, 0:1]
    rel = [x / day_open for x in (o, h, l, c)]
    order = rng.permutation(len(day_open))
    price = float(day_open[0, 0])
    out = [[], [], [], []]
    for i in order:
        for k in range(4):
            out[k].append(rel[k][i] * price)
        price = out[3][-1][-1]
    res = pd.DataFrame({k: np.concatenate(v) for k, v in zip(("open", "high", "low", "close"), out)})
    res["ts"] = d["ts"].to_numpy()
    res["day"] = d["day"].to_numpy()
    return res


def _atr(h, l, c, n):
    h, l, c = (pd.Series(x, dtype=float) for x in (h, l, c))
    tr = pd.concat([h - l, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean().to_numpy()


def run_trade(o, h, l, side, entry_i, entry, stop, exit_i):
    risk = side * (entry - stop)
    for k in range(entry_i + 1, exit_i):
        if (side > 0 and l[k] <= stop) or (side < 0 and h[k] >= stop):
            fill = min(stop, o[k]) if side > 0 else max(stop, o[k])      # a candle that opens beyond the stop fills at its open
            return side * (fill - entry) / risk, risk
    return side * (o[exit_i] - entry) / risk, risk


def signals(df: pd.DataFrame, rule: str):
    """Returns (entry_index, exit_index, side, entry, stop) per setup; indices refer to the whole-day frame."""
    d = whole_days(df)
    o, h, l, c = (d[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    n_days = len(d) // 24
    O, H, L, C = (x.reshape(n_days, 24) for x in (o, h, l, c))
    dh, dl, dc = H.max(axis=1), L.min(axis=1), C[:, -1]
    datr = _atr(dh, dl, dc, 14)
    hatr = _atr(h, l, c, 14)
    out = []
    if rule == "judas":
        for t in range(4, n_days):
            a = datr[t - 1]
            if not np.isfinite(a) or a <= 0:
                continue
            swing_hi = dh[t - 2] > dh[t - 3] and dh[t - 2] > dh[t - 1]
            swing_lo = dl[t - 2] < dl[t - 3] and dl[t - 2] < dl[t - 1]
            if swing_hi == swing_lo:
                continue
            side = -1 if swing_hi else 1
            day_open = O[t, 0]
            ext, pushed = (H[t, 0], False) if side < 0 else (L[t, 0], False)
            for hr in range(12):
                ext = max(ext, H[t, hr]) if side < 0 else min(ext, L[t, hr])
                pushed = pushed or ((ext - day_open) >= JUDAS_ATR * a if side < 0 else (day_open - ext) >= JUDAS_ATR * a)
                back = C[t, hr] < day_open if side < 0 else C[t, hr] > day_open
                if pushed and back:
                    stop = ext + JUDAS_PAD_ATR * a if side < 0 else ext - JUDAS_PAD_ATR * a
                    entry = C[t, hr]
                    if 0 < side * (entry - stop) <= MAX_STOP_ATR * a:
                        out.append((t * 24 + hr, t * 24 + EXIT_HOUR, side, entry, stop))
                    break
    else:
        hh = pd.Series(h).rolling(WR_LEN).max().to_numpy()
        ll = pd.Series(l).rolling(WR_LEN).min().to_numpy()
        wr = -100.0 * (hh - c) / np.where(hh - ll == 0, np.nan, hh - ll)
        for t in range(1, n_days):
            i = t * 24 + 7
            a = hatr[i - 1]
            if not np.isfinite(a) or a <= 0 or not np.isfinite(wr[i]):
                continue
            alo, ahi = L[t, 0:7].min(), H[t, 0:7].max()
            if l[i] < alo and wr[i] <= WR_OS:
                side, stop = 1, l[i] - WR_PAD_ATR * a
            elif h[i] > ahi and wr[i] >= WR_OB:
                side, stop = -1, h[i] + WR_PAD_ATR * a
            else:
                continue
            entry = c[i]
            if 0 < side * (entry - stop) <= MAX_STOP_ATR * a:
                out.append((i, t * 24 + EXIT_HOUR, side, entry, stop))
    return d, out


def trades(df: pd.DataFrame, rule: str, cost: float) -> np.ndarray:
    d, sigs = signals(df, rule)
    o, h, l = (d[x].to_numpy(float) for x in ("open", "high", "low"))
    rs = []
    for ei, xi, side, entry, stop in sigs:
        r, risk = run_trade(o, h, l, side, ei, entry, stop, xi)
        rs.append(r - cost * entry / risk)
    return np.array(rs)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"])
    p.add_argument("--download", action="store_true")
    p.add_argument("--null-runs", type=int, default=100)
    p.add_argument("--seed", type=int, default=9)
    a = p.parse_args()
    frames = {}
    for s in a.symbols:
        if a.download or load(s) is None:
            print(f"downloading {s} ...", flush=True)
            download(s)
        f = load(s)
        if f is not None and len(f) > 24 * 400:
            frames[s] = f
            print(f"{s}: {len(f)} hourly candles, {f['ts'].iloc[0].date()} to {f['ts'].iloc[-1].date()}")
    print(f"\nGross = zero cost. Net = {NET_COST * 100:.1f}% round trip. Shuffles permute whole days, at zero cost.\n")
    for rule in RULES:
        g_all, n_all, f1, f2, pos = [], [], [], [], 0
        for s, f in frames.items():
            g, n = trades(f, rule, 0.0), trades(f, rule, NET_COST)
            if len(g) == 0:
                continue
            h = len(g) // 2
            g_all.append(g); n_all.append(n); f1.append(g[:h]); f2.append(g[h:])
            pos += g.mean() > 0
            print(f"  {rule} {s}: {len(g)} trades, gross {g.mean():+.3f}R, win rate {(g > 0).mean():.0%}")
        if not g_all:
            print(f"=== {rule}: no trades ===\n"); continue
        g, n = np.concatenate(g_all), np.concatenate(n_all)
        se = g.std() / np.sqrt(len(g)) if len(g) > 1 else float("nan")
        print(f"=== {rule} ===\n{len(g)} trades | win rate {(g > 0).mean():.0%} | gross {g.mean():+.3f}R ({g.mean() / se:+.1f} std errors) | net {n.mean():+.3f}R")
        print(f"first halves {np.concatenate(f1).mean():+.3f}R, second halves {np.concatenate(f2).mean():+.3f}R | coins positive: {pos} of {len(g_all)}")
        rng = np.random.default_rng(a.seed)
        null = []
        for _ in range(a.null_runs):
            rs = [trades(day_shuffle(f, rng), rule, 0.0) for f in frames.values()]
            rs = [x for x in rs if len(x)]
            null.append(np.concatenate(rs).mean() if rs else np.nan)
        null = np.array(null)
        luck = (np.nansum(null >= g.mean()) + 1) / (np.isfinite(null).sum() + 1)
        print(f"day-shuffled prices: average {np.nanmean(null):+.3f}R, best {np.nanmax(null):+.3f}R | chance of matching the real gross by luck: {luck:.2f}\n")
    print("Count a rule only if: gross beats its shuffles (luck chance about 0.02 or below), positive in both halves and in most coins, and positive net.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
