"""How often would the short side of a funding-carry trade have been force-closed? (pretend money, read-only)

Carry = hold the coin (spot) and short the same amount in perpetual futures, collecting funding. The coin and the short cancel each other
out in price, but the exchange does not know about the coin: if the price rises far enough the short account runs out of margin and is
liquidated, and the hedge is gone. This counts, for every possible start day, how often a short opened at that day's close would have
been liquidated within 30, 90 and 365 days, with no top-ups, using each day's HIGH.

    .venv/bin/python work/funding_liquidation.py --coins BTC ETH SOL BNB
Liquidation price used: entry x (1 + 1/leverage - MMR). MMR is the exchange's maintenance margin rate, set to 0.5% for every coin here
(an assumption: the real rate depends on the exchange tier and position size). Funding income and fees are ignored, so this is the pure price risk.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

LEVERAGES = (1, 2, 3, 5, 10)
WINDOWS = (30, 90, 365)
MMR = 0.005


def forward_max_rise(ohlc: pd.DataFrame, window: int) -> pd.Series:
    """For each day: the highest high over the next `window` days, as a rise from that day's close."""
    high = ohlc["high"].to_numpy(float)
    close = ohlc["close"].to_numpy(float)
    n = len(close)
    out = np.full(n, np.nan)
    for i in range(n - window):
        out[i] = high[i + 1:i + 1 + window].max() / close[i] - 1
    return pd.Series(out, index=ohlc.index)


def liquidation_table(ohlc: pd.DataFrame, leverages=LEVERAGES, windows=WINDOWS, mmr: float = MMR) -> dict:
    rises = {w: forward_max_rise(ohlc, w).dropna() for w in windows}
    table = {}
    for lev in leverages:
        trigger = 1 / lev - mmr
        table[lev] = {"trigger": trigger, **{w: (float((rises[w] >= trigger).mean()) if len(rises[w]) else float("nan")) for w in windows}}
    table["worst"] = {w: (float(rises[w].max()) if len(rises[w]) else float("nan")) for w in windows}
    table["starts"] = {w: len(rises[w]) for w in windows}
    return table


def render(coin: str, table: dict, days: int) -> str:
    out = [f"=== {coin}: {days} days of history ===", f"{'leverage':>9}{'liquidated if price rises':>27}" + "".join(f"{f'within {w}d':>12}" for w in WINDOWS)]
    for lev in LEVERAGES:
        row = table[lev]
        out.append(f"{lev:>8}x{row['trigger']:>26.1%}" + "".join(f"{row[w]:>12.0%}" for w in WINDOWS))
    out.append(f"  biggest rise after any start day: " + ", ".join(f"{table['worst'][w]:.0%} in {w}d" for w in WINDOWS))
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--coins", nargs="+", default=["BTC", "ETH", "SOL", "BNB"])
    a = ap.parse_args()
    from checker.data import fetch_ohlc
    for coin in a.coins:
        try:
            ohlc = fetch_ohlc(coin.upper())
        except Exception as exc:
            print(f"{coin}: could not get prices ({exc})\n")
            continue
        print(render(coin.upper(), liquidation_table(ohlc), len(ohlc)), "\n")
    print("Read it as: at 1x a short is only liquidated if the price doubles. Higher leverage frees capital but liquidation gets close.")
    print("Pure price risk only: exchange failure, withdrawal limits, funding turning negative and basis moves are not in these numbers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
