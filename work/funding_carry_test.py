"""Funding-rate carry on crypto perpetual futures, tested on the real funding history. Research only; it never trades.

Carry: hold 1 unit of the coin in spot and short 1 unit of its perpetual. Price moves cancel, so the result is the funding payments
(short side RECEIVES the rate when it is positive and PAYS it when negative, every 8 hours) minus trading costs.
This is not a price prediction rule, so the test is different from the shuffled-price tests: what matters is how much was earned after costs,
how long and how deep the bad stretches were, and whether switching on and off adds anything beyond always holding.

always_on  Enter once at the start, never leave. Costs: one round trip (spot and perp, in and out).
switch     Hold only while the average of the previous 9 funding payments (3 days) is above zero; every change of state costs half a round trip.
           The 9-payment window and the zero threshold are fixed in advance.
Shuffle    The switch rule is run on 200 reshuffled copies of the same payments (same payments, random order, persistence destroyed); a switch
           rule counts only if it beats those.

What the numbers leave out, on purpose: basis moves between spot and perp, the margin needed for the short (capital is about double the notional,
so return on capital is about half the return on notional), liquidation risk on the short if the coin spikes, exchange and withdrawal risk, and
the chance that funding turns negative for long stretches (shown below as the worst 30 days).

    python work/funding_carry_test.py --download --symbols BTCUSDT ETHUSDT SOLUSDT BNBUSDT
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path("outputs/funding")
BINANCE = "https://fapi.binance.com/fapi/v1/fundingRate"
BYBIT = "https://api.bybit.com/v5/market/funding/history"
START_MS = int(pd.Timestamp("2019-09-01", tz="UTC").timestamp() * 1000)
PERIODS_PER_YEAR = 3 * 365
ROUND_TRIP = 0.003            # spot taker 0.1% + perp taker 0.05%, in and out
SWITCH_WINDOW = 9
WINDOW_30D = 90


def _get(url: str):
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "research-script"})
            return json.loads(urllib.request.urlopen(req, timeout=40).read())
        except Exception as exc:
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(str(last))


def fetch_binance(symbol: str) -> list[tuple[int, float]]:
    rows, cursor = [], START_MS
    while True:
        data = _get(f"{BINANCE}?symbol={symbol}&limit=1000&startTime={cursor}")
        if not data:
            break
        rows += [(int(d["fundingTime"]), float(d["fundingRate"])) for d in data]
        cursor = int(data[-1]["fundingTime"]) + 1
        if len(data) < 1000:
            break
    return rows


def fetch_bybit(symbol: str) -> list[tuple[int, float]]:
    rows, end = [], int(time.time() * 1000)
    while end > START_MS:
        data = _get(f"{BYBIT}?category=linear&symbol={symbol}&limit=200&endTime={end}")
        items = (data.get("result") or {}).get("list") or []
        if not items:
            break
        rows += [(int(d["fundingRateTimestamp"]), float(d["fundingRate"])) for d in items]
        end = min(int(d["fundingRateTimestamp"]) for d in items) - 1
        if len(items) < 200:
            break
    return rows


def download(symbol: str, directory: Path = DATA_DIR) -> tuple[Path, str]:
    directory.mkdir(parents=True, exist_ok=True)
    errors = []
    for name, fn in (("Binance", fetch_binance), ("Bybit", fetch_bybit)):
        try:
            rows = fn(symbol)
            if len(rows) > 500:
                df = pd.DataFrame(rows, columns=["time_ms", "rate"]).drop_duplicates("time_ms").sort_values("time_ms")
                path = directory / f"{symbol}_funding.csv"
                df.to_csv(path, index=False)
                return path, name
            errors.append(f"{name}: only {len(rows)} rows")
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    raise RuntimeError(f"could not download {symbol}: " + " | ".join(errors))


def load(symbol: str, directory: Path = DATA_DIR) -> np.ndarray | None:
    path = directory / f"{symbol}_funding.csv"
    if not path.exists():
        return None
    return pd.read_csv(path)["rate"].to_numpy(float)


def always_on(rates: np.ndarray, round_trip: float = ROUND_TRIP) -> np.ndarray:
    """Per-payment result on 1 unit of notional; the single round trip is taken off the first payment."""
    out = rates.copy()
    if len(out):
        out[0] -= round_trip
    return out


def switch(rates: np.ndarray, round_trip: float = ROUND_TRIP, window: int = SWITCH_WINDOW) -> np.ndarray:
    out = np.zeros(len(rates))
    held = False
    for k in range(window, len(rates)):
        want = rates[k - window:k].mean() > 0.0          # only payments already made
        if want != held:
            out[k] -= round_trip / 2.0
            held = want
        if held:
            out[k] += rates[k]
    if held and len(out):
        out[-1] -= round_trip / 2.0                       # close at the end so the cost is counted
    return out


def stats(x: np.ndarray) -> dict:
    cum = np.cumsum(x)
    years = len(x) / PERIODS_PER_YEAR
    peak = np.maximum.accumulate(cum)
    w = pd.Series(x).rolling(WINDOW_30D).sum()
    return {
        "years": years, "total": cum[-1], "annual": cum[-1] / years if years else np.nan,
        "max_dd": float((peak - cum).max()), "worst30": float(w.min()) if w.notna().any() else np.nan,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"])
    p.add_argument("--download", action="store_true")
    p.add_argument("--null-runs", type=int, default=200)
    p.add_argument("--seed", type=int, default=9)
    a = p.parse_args()
    data = {}
    for s in a.symbols:
        if a.download or load(s) is None:
            path, src = download(s)
            print(f"{s}: downloaded from {src}", flush=True)
        r = load(s)
        if r is not None and len(r) > 500:
            data[s] = r
    rng = np.random.default_rng(a.seed)
    print(f"\n{len(data)} coins. All figures are per 1 unit of spot held and perp shorted (return on notional). Return on capital is about half.\n")
    pooled_on, pooled_sw = [], []
    for s, r in data.items():
        on, sw = stats(always_on(r)), stats(switch(r))
        neg = (r < 0).mean()
        print(f"=== {s} === {on['years']:.1f} years | average funding {r.mean() * PERIODS_PER_YEAR * 100:+.1f}% a year | payments negative {neg:.0%}")
        print(f"  always_on: net {on['annual'] * 100:+.1f}% a year on notional | worst drawdown {on['max_dd'] * 100:.1f}% | worst 30 days {on['worst30'] * 100:+.2f}%")
        print(f"  switch:    net {sw['annual'] * 100:+.1f}% a year on notional | worst drawdown {sw['max_dd'] * 100:.1f}% | worst 30 days {sw['worst30'] * 100:+.2f}%")
        null = [stats(switch(rng.permutation(r)))["annual"] for _ in range(a.null_runs)]
        luck = (np.sum(np.array(null) >= sw["annual"]) + 1) / (len(null) + 1)
        print(f"  switch on shuffled payments: average {np.mean(null) * 100:+.1f}% a year | chance of matching the real switch result by luck: {luck:.2f}\n")
        pooled_on.append(on["annual"]); pooled_sw.append(sw["annual"])
    if pooled_on:
        print(f"Average over coins: always_on {np.mean(pooled_on) * 100:+.1f}% a year, switch {np.mean(pooled_sw) * 100:+.1f}% a year (on notional).")
    print("Read it as income with risk, not as a prediction edge: judge the worst drawdown and worst 30 days, and remember margin, liquidation and exchange risk are not in these numbers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
