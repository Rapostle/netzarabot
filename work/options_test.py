"""Options honesty test: can any simple rule beat the house on Deriv-style option contracts? Research only; it places no orders.

A fixed-payout option pays back (1 - margin) / p0 times the stake on a win, where p0 is how often that contract wins with NO signal at all
(counted on the same data) and margin is the house's cut (default 5%, an assumption; pass --margin). With no signal the average result is
exactly -margin per $1 staked. A rule only helps if it wins MORE often than p0 by more than the margin.
Headline number: the BREAK-EVEN MARGIN = 1 - p0 / win rate. If Deriv's real margin is above it, the rule loses money.

Contracts, modelled on candles (entries only every N candles so trades do not overlap; decided at a candle close):
  rise_fall   win if the price N candles later is on our side of the entry (a tie loses)
  higher_lower  win if the price N candles later is beyond entry +/- 0.5 ATR on our side
  touch       win if the price touches entry +/- 1 ATR on our side within N candles
  no_touch    win if it does NOT touch entry +/- 1 ATR on the chosen side within N candles
  band        accumulator-style: win if the price stays within entry +/- 1 ATR for N candles (rules: always, after big candle, after quiet candle)
  turbo       leveraged 20x position held N candles, knocked out at -5%; fee 0.0005 of the stake x 20 each way (an assumption). Result = real pnl per $1.
Rules (fixed in advance): follow/fade the last 1, 3 or 12 candles, fade RSI(14) extremes (70/30), follow/fade a 20-candle close breakout.
Judge: the same rules on shuffled candles (whole candles in random order, same sizes and shapes, so any pattern is destroyed). For each contract
and N the BEST rule is compared with the best rule of each shuffle, so trying many rules cannot manufacture a pass.

    .venv/bin/python work/options_test.py --data-dir outputs/history --timeframe 5m --null-runs 60
    .venv/bin/python work/options_test.py --digits BOOM500 CRASH500 R_75       # digit contracts, needs the 'websockets' package
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

BOT_ROOT = Path(os.environ.get("TRADING_BOT_ROOT", str(Path(__file__).resolve().parent.parent / "external" / "trading_bot")))
sys.path.insert(0, str(BOT_ROOT))

DURATIONS = (1, 3, 12)
MARGIN = 0.05
BARRIER_HL, BARRIER_TOUCH, BAND = 0.5, 1.0, 1.0
TURBO_X, TURBO_FEE = 20, 0.0005
DIR_RULES = ("follow_1", "fade_1", "follow_3", "fade_3", "follow_12", "fade_12", "rsi_fade", "breakout_follow", "breakout_fade")
VOL_RULES = ("always", "after_big", "after_quiet")
FAMILIES = {"rise_fall": DIR_RULES, "higher_lower": DIR_RULES, "touch": DIR_RULES, "no_touch": DIR_RULES, "band": VOL_RULES, "turbo": DIR_RULES}
MIN_TRADES = 200


def shuffle_candles(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Whole candles in random order, each keeping its own shape relative to the previous close; prices stay continuous."""
    c = df["close"].to_numpy(float)
    prev = np.r_[c[0], c[:-1]][1:]
    rel = np.column_stack([df[k].to_numpy(float)[1:] / prev for k in ("open", "high", "low", "close")])
    rel = rel[rng.permutation(len(rel))]
    close = c[0] * np.cumprod(rel[:, 3])
    pc = np.r_[c[0], close[:-1]]
    return pd.DataFrame({"open": rel[:, 0] * pc, "high": rel[:, 1] * pc, "low": rel[:, 2] * pc, "close": close})


def atr(df: pd.DataFrame, n: int = 14) -> np.ndarray:
    h, l, c = (df[k].to_numpy(float) for k in ("high", "low", "close"))
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    return pd.Series(tr).rolling(n).mean().to_numpy()


def rsi(c: np.ndarray, n: int = 14) -> np.ndarray:
    d = pd.Series(c).diff()
    up, dn = d.clip(lower=0).rolling(n).mean(), (-d.clip(upper=0)).rolling(n).mean()
    return (100 - 100 / (1 + up / dn.replace(0, np.nan))).to_numpy()


def rule_sides(df: pd.DataFrame, a: np.ndarray) -> dict[str, np.ndarray]:
    """Decided at each candle close from data up to and including that candle. +1 = bet up, -1 = bet down, 0 = no bet."""
    c, h, l = (df[k].to_numpy(float) for k in ("close", "high", "low"))
    out = {}
    for n in (1, 3, 12):
        past = np.r_[np.full(n, np.nan), c[:-n]]
        s = np.sign(c - past)
        s = np.nan_to_num(s)
        out[f"follow_{n}"], out[f"fade_{n}"] = s, -s
    r = rsi(c)
    out["rsi_fade"] = np.where(r >= 70, -1.0, np.where(r <= 30, 1.0, 0.0))
    hi = pd.Series(c).shift(1).rolling(20).max().to_numpy()
    lo = pd.Series(c).shift(1).rolling(20).min().to_numpy()
    b = np.where(c > hi, 1.0, np.where(c < lo, -1.0, 0.0))
    out["breakout_follow"], out["breakout_fade"] = b, -b
    rng_ = (h - l)
    out["always"] = np.ones(len(c))
    out["after_big"] = np.where(rng_ > 2 * a, 1.0, 0.0)
    out["after_quiet"] = np.where(rng_ < 0.5 * a, 1.0, 0.0)
    return out


def outcomes(df: pd.DataFrame, a: np.ndarray, family: str, n: int):
    """For each entry candle t (on the N-grid): returns (valid mask, win array for side +1, win array for side -1). For turbo: pnl arrays."""
    c, h, l = (df[k].to_numpy(float) for k in ("close", "high", "low"))
    m = len(c)
    t = np.arange(m)
    ok = (t % n == 0) & (t + n < m) & np.isfinite(a) & (t >= 20)
    end = np.where(ok, t + n, 0)
    fwd_c = c[end]
    idx = t[:, None] + np.arange(1, n + 1)[None, :]
    idx = np.minimum(idx, m - 1)
    fmax, fmin = h[idx].max(axis=1), l[idx].min(axis=1)
    if family == "rise_fall":
        up, dn = fwd_c > c, fwd_c < c
    elif family == "higher_lower":
        up, dn = fwd_c > c + BARRIER_HL * a, fwd_c < c - BARRIER_HL * a
    elif family == "touch":
        up, dn = fmax >= c + BARRIER_TOUCH * a, fmin <= c - BARRIER_TOUCH * a
    elif family == "no_touch":      # side +1 = bet it will not touch the UPPER barrier; side -1 = not touch the LOWER one
        up, dn = ~(fmax >= c + BARRIER_TOUCH * a), ~(fmin <= c - BARRIER_TOUCH * a)
    elif family == "band":
        inside = (fmax <= c + BAND * a) & (fmin >= c - BAND * a)
        up = dn = inside
    elif family == "turbo":
        ret_up = fwd_c / c - 1
        stop_up = (fmin / c - 1) <= -1 / TURBO_X
        stop_dn = (fmax / c - 1) >= 1 / TURBO_X
        up = np.where(stop_up, -1.0, np.clip(TURBO_X * ret_up, -1, None)) - TURBO_X * TURBO_FEE * 2
        dn = np.where(stop_dn, -1.0, np.clip(-TURBO_X * ret_up, -1, None)) - TURBO_X * TURBO_FEE * 2
        return ok, up, dn
    return ok, up.astype(float), dn.astype(float)


def market_stats(df: pd.DataFrame, margin: float, families=FAMILIES) -> dict[tuple, tuple[float, int]]:
    """{(family, rule, n): (sum of pnl per $1, trades)} for one market's candles."""
    a = atr(df)
    sides = rule_sides(df, a)
    res = {}
    for fam, rules in families.items():
        for n in DURATIONS:
            ok, up, dn = outcomes(df, a, fam, n)
            if fam == "turbo":
                pu, pd_ = up, dn
            else:
                p0u, p0d = up[ok].mean(), dn[ok].mean()
                pu = up * (1 - margin) / max(p0u, 1e-9) - 1
                pd_ = dn * (1 - margin) / max(p0d, 1e-9) - 1
            for rule in rules:
                s = sides[rule]
                take_up, take_dn = ok & (s > 0), ok & (s < 0)
                if fam == "band":
                    take_up, take_dn = ok & (s != 0), np.zeros_like(ok)
                tot = float(pu[take_up].sum() + pd_[take_dn].sum())
                cnt = int(take_up.sum() + take_dn.sum())
                res[(fam, rule, n)] = (tot, cnt)
    return res


def pool(per_market: list[dict]) -> dict[tuple, float]:
    keys = per_market[0].keys()
    out = {}
    for k in keys:
        tot, cnt = sum(m[k][0] for m in per_market), sum(m[k][1] for m in per_market)
        out[k] = (tot / cnt, cnt) if cnt >= MIN_TRADES else (float("nan"), cnt)
    return out


def evaluate(frames: dict[str, pd.DataFrame], margin: float, null_runs: int, seed: int = 9) -> dict:
    real = pool([market_stats(f, margin) for f in frames.values()])
    rng = np.random.default_rng(seed)
    null_best: dict[tuple, list[float]] = {}
    for _ in range(null_runs):
        sh = pool([market_stats(shuffle_candles(f, rng), margin) for f in frames.values()])
        for fam in FAMILIES:
            for n in DURATIONS:
                vals = [v[0] for k, v in sh.items() if k[0] == fam and k[2] == n and np.isfinite(v[0])]
                null_best.setdefault((fam, n), []).append(max(vals) if vals else float("nan"))
    rows = []
    for fam in FAMILIES:
        for n in DURATIONS:
            cand = {k: v for k, v in real.items() if k[0] == fam and k[2] == n and np.isfinite(v[0])}
            if not cand:
                rows.append({"family": fam, "n": n, "rule": None})
                continue
            k = max(cand, key=lambda x: cand[x][0])
            nb = np.array(null_best[(fam, n)], float)
            nb = nb[np.isfinite(nb)]
            rows.append({"family": fam, "n": n, "rule": k[1], "pnl": cand[k][0], "trades": cand[k][1],
                         "null_best": float(nb.mean()) if len(nb) else float("nan"),
                         "luck": float((np.sum(nb >= cand[k][0]) + 1) / (len(nb) + 1)) if len(nb) else float("nan"),
                         "positive_rules": int(sum(v[0] > 0 for v in cand.values())), "rules": len(cand)})
    return {"rows": rows, "markets": len(frames)}


def render(res: dict, margin: float) -> str:
    out = [f"{res['markets']} markets pooled. House margin assumed {margin:.0%}: a rule with no edge averages {-margin * 100:+.1f}c per $1 staked (turbo: fees only).",
           f"{'contract':<13}{'N':>4}{'best rule':>17}{'trades':>8}{'pnl/$1':>9}{'best of shuffles':>18}{'luck':>7}{'rules>0':>9}"]
    for r in res["rows"]:
        if r["rule"] is None:
            out.append(f"{r['family']:<13}{r['n']:>4}{'too few trades':>17}")
            continue
        out.append(f"{r['family']:<13}{r['n']:>4}{r['rule']:>17}{r['trades']:>8}{r['pnl'] * 100:>+8.1f}c{r['null_best'] * 100:>+17.1f}c{r['luck']:>7.2f}{r['positive_rules']:>5}/{r['rules']}")
    wins = [r for r in res["rows"] if r.get("rule") and r["pnl"] > 0 and r["luck"] <= 0.05 / max(1, len(res["rows"]))]
    out += ["", "Rows where the best rule is above zero AND beats the best shuffle at the corrected level: " + (", ".join(f"{w['family']} N={w['n']} ({w['rule']})" for w in wins) if wins else "none"),
            "Past data cannot promise future profit. This is not financial advice."]
    return "\n".join(out)


# ---------------------------------------------------------------- digits
def chi2_sf(x: float, k: int) -> float:
    """P(chi-square with k degrees >= x), by the regularised upper incomplete gamma function (no scipy needed)."""
    a, xx = k / 2.0, x / 2.0
    if xx <= 0:
        return 1.0
    if xx < a + 1:
        term = total = 1.0 / a
        for n in range(1, 500):
            term *= xx / (a + n)
            total += term
            if abs(term) < abs(total) * 1e-12:
                break
        return 1.0 - total * math.exp(-xx + a * math.log(xx) - math.lgamma(a))
    b = xx + 1 - a
    c, d = 1e300, 1.0 / b
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-12:
            break
    return math.exp(-xx + a * math.log(xx) - math.lgamma(a)) * h


def digits_report(digits: np.ndarray) -> dict:
    d = np.asarray(digits, int)
    n = len(d)
    counts = np.bincount(d, minlength=10)
    chi = float(((counts - n / 10) ** 2 / (n / 10)).sum())
    prev, nxt = d[:-1], d[1:]
    table = np.zeros((10, 10))
    for p_, q in zip(prev, nxt):
        table[p_, q] += 1
    rows = table.sum(axis=1, keepdims=True)
    exp = rows / 10
    z = (table - exp) / np.sqrt(np.maximum(exp * 0.9, 1e-9))
    i, j = np.unravel_index(np.abs(z).argmax(), z.shape)
    repeat = float((prev == nxt).mean())
    zrep = (repeat - 0.1) / math.sqrt(0.1 * 0.9 / (n - 1))
    max_p = min(1.0, 100 * math.erfc(abs(z[i, j]) / math.sqrt(2)))     # two-sided, Bonferroni over 100 cells
    return {"n": n, "chi2": chi, "p_uniform": chi2_sf(chi, 9), "repeat_rate": repeat, "repeat_z": float(zrep),
            "worst_cell": (int(i), int(j)), "worst_z": float(z[i, j]), "p_worst_cell": float(max_p)}


async def _ticks(url: str, symbol: str, count: int = 5000) -> list[float]:
    import websockets
    async with websockets.connect(url, ping_interval=20, close_timeout=10) as ws:
        await ws.send(json.dumps({"ticks_history": symbol, "count": count, "end": "latest", "style": "ticks"}))
        resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=45))
    if "error" in resp:
        raise RuntimeError(str(resp["error"]))
    return [float(x) for x in resp["history"]["prices"]]


def last_digits(prices: list[float]) -> np.ndarray:
    dec = max(len(f"{p:.6f}".rstrip("0").split(".")[1]) if "." in f"{p:.6f}" else 0 for p in prices[:200])
    return np.array([int(round(p * 10 ** dec)) % 10 for p in prices])


def run_digits(symbols: list[str]) -> None:
    url = os.environ.get("DERIV_WS_URL") or "wss://api.derivws.com/trading/v1/options/ws/public"
    for s in symbols:
        try:
            r = digits_report(last_digits(asyncio.run(_ticks(url, s))))
        except Exception as exc:
            print(f"{s}: could not get ticks ({exc})")
            continue
        print(f"{s}: {r['n']} ticks | digits evenly spread? chi-square p {r['p_uniform']:.2f} | next digit equals this one {r['repeat_rate']:.3f} (fair 0.100, z {r['repeat_z']:+.1f}) | "
              f"strangest pair after-{r['worst_cell'][0]}-comes-{r['worst_cell'][1]} z {r['worst_z']:+.1f}, corrected p {r['p_worst_cell']:.2f}")
    print("\nA digit contract is priced at the fair 1-in-10 or 1-in-2 odds minus the house cut. It can only be beaten if the digits are NOT random; p values far above 0.05 mean they look random.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data-dir", default="outputs/history")
    ap.add_argument("--timeframe", default="5m")
    ap.add_argument("--margin", type=float, default=MARGIN)
    ap.add_argument("--null-runs", type=int, default=60)
    ap.add_argument("--max-markets", type=int, default=20)
    ap.add_argument("--digits", nargs="+")
    a = ap.parse_args()
    if a.digits:
        run_digits(a.digits)
        return 0
    from trading_bot.data.loader import load_ohlcv_csv
    frames = {}
    for p in sorted(Path(a.data_dir).glob(f"deriv_*_{a.timeframe}.csv"))[: a.max_markets]:
        df = load_ohlcv_csv(p)
        if len(df) > 2000:
            frames[p.name[len("deriv_"):-len(f"_{a.timeframe}.csv")]] = df[["open", "high", "low", "close"]].astype(float).reset_index(drop=True)
    if not frames:
        print(f"No deriv_*_{a.timeframe}.csv files with enough candles in {a.data_dir}.")
        return 1
    print(f"{len(frames)} markets: {', '.join(frames)}\n")
    print(render(evaluate(frames, a.margin, a.null_runs), a.margin))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
