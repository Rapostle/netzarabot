"""Download up to 25 years of DAILY candles from public sources (Deriv itself keeps only about a year).

Sources, tried in order for each market until one works:
  crypto : Binance public market-data mirror, then Yahoo Finance
  others : Yahoo Finance, then Stooq
The files are saved under Deriv's market names (deriv_<name>_1d.csv) so the daily test can read them.
These are the broad market prices, not Deriv's own quotes. That is fine for asking "does this idea work at all".

Standard library only.

    python3 work/download_long_daily.py --symbols frxEURUSD cryBTCUSD
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) research-script"

# our name -> (yahoo code, stooq code, binance code)
MARKETS = {
    "frxEURUSD": ("EURUSD=X", "eurusd", None), "frxGBPUSD": ("GBPUSD=X", "gbpusd", None),
    "frxUSDJPY": ("JPY=X", "usdjpy", None), "frxAUDUSD": ("AUDUSD=X", "audusd", None),
    "frxUSDCAD": ("CAD=X", "usdcad", None), "frxUSDCHF": ("CHF=X", "usdchf", None),
    "frxNZDUSD": ("NZDUSD=X", "nzdusd", None), "frxEURJPY": ("EURJPY=X", "eurjpy", None),
    "frxGBPJPY": ("GBPJPY=X", "gbpjpy", None), "frxXAUUSD": ("GC=F", "xauusd", None),
    "frxXAGUSD": ("SI=F", "xagusd", None), "cryBTCUSD": ("BTC-USD", None, "BTCUSDT"),
    "cryETHUSD": ("ETH-USD", None, "ETHUSDT"), "OTC_SPC": ("^GSPC", "^spx", None),
    "OTC_NDX": ("^NDX", "^ndx", None), "OTC_DJI": ("^DJI", "^dji", None), "OTC_FTSE": ("^FTSE", "^ukx", None),
}


def bases() -> dict[str, str]:
    return {
        "yahoo": os.environ.get("YAHOO_BASE", "https://query1.finance.yahoo.com"),
        "binance": os.environ.get("BINANCE_BASE", "https://data-api.binance.vision"),
        "stooq": os.environ.get("STOOQ_BASE", "https://stooq.com"),
    }


def http_get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=40) as response:
        return response.read()


def parse_yahoo(payload: dict) -> list[tuple[int, float, float, float, float]]:
    result = payload["chart"]["result"][0]
    quote = result["indicators"]["quote"][0]
    rows = []
    for i, epoch in enumerate(result.get("timestamp") or []):
        o, h, l, c = (quote[k][i] for k in ("open", "high", "low", "close"))
        if None in (o, h, l, c) or c <= 0:
            continue
        rows.append((int(epoch), float(o), float(h), float(l), float(c)))
    return rows


def parse_binance(klines: list) -> list[tuple[int, float, float, float, float]]:
    return [(int(k[0]) // 1000, float(k[1]), float(k[2]), float(k[3]), float(k[4])) for k in klines]


def parse_stooq(text: str) -> list[tuple[int, float, float, float, float]]:
    lines = text.strip().splitlines()
    if not lines or not lines[0].lower().startswith("date"):
        raise ValueError("Stooq did not return a CSV (it may now require a key)")
    rows = []
    for rec in csv.DictReader(lines):
        try:
            when = datetime.strptime(rec["Date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            o, h, l, c = (float(rec[k]) for k in ("Open", "High", "Low", "Close"))
        except (KeyError, ValueError):
            continue
        if c > 0:
            rows.append((int(when.timestamp()), o, h, l, c))
    return rows


def fetch_yahoo(code: str, years: int) -> list:
    period1 = int(time.time()) - years * 366 * 86400
    url = f"{bases()['yahoo']}/v8/finance/chart/{urllib.parse.quote(code)}?period1={period1}&period2={int(time.time())}&interval=1d"
    return parse_yahoo(json.loads(http_get(url)))


def fetch_binance(code: str, years: int) -> list:
    start_ms = (int(time.time()) - years * 366 * 86400) * 1000
    rows: list = []
    for _ in range(40):
        url = f"{bases()['binance']}/api/v3/klines?symbol={code}&interval=1d&limit=1000&startTime={start_ms}"
        batch = json.loads(http_get(url))
        if not batch:
            break
        rows.extend(parse_binance(batch))
        next_start = int(batch[-1][0]) + 1
        if next_start <= start_ms or len(batch) < 1000:
            break
        start_ms = next_start
    return rows


def fetch_stooq(code: str, years: int) -> list:
    return parse_stooq(http_get(f"{bases()['stooq']}/q/d/l/?s={urllib.parse.quote(code)}&i=d").decode("utf-8", "replace"))


def get_market(name: str, years: int) -> tuple[list, str, list[str]]:
    yahoo, stooq, binance = MARKETS[name]
    attempts = []
    if binance:
        attempts.append(("binance", lambda: fetch_binance(binance, years)))
    if yahoo:
        attempts.append(("yahoo", lambda: fetch_yahoo(yahoo, years)))
    if stooq:
        attempts.append(("stooq", lambda: fetch_stooq(stooq, years)))
    problems: list[str] = []
    for label, call in attempts:
        try:
            rows = call()
        except Exception as exc:  # any network or format problem moves on to the next source
            problems.append(f"{label}: {exc}")
            continue
        if len(rows) >= 200:
            unique = {row[0]: row for row in rows}
            return [unique[k] for k in sorted(unique)], label, problems
        problems.append(f"{label}: only {len(rows)} candles")
    return [], "", problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--symbols", nargs="+", default=sorted(MARKETS))
    parser.add_argument("--years", type=int, default=12)
    parser.add_argument("--out-dir", default="outputs/history")
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    status = 0
    for name in args.symbols:
        if name not in MARKETS:
            print(f"{name}: unknown market name")
            status = 1
            continue
        rows, source, problems = get_market(name, args.years)
        if not rows:
            print(f"{name}: FAILED ({'; '.join(problems)})")
            status = 1
            continue
        with (out_dir / f"deriv_{name}_1d.csv").open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
            for epoch, o, h, l, c in rows:
                writer.writerow([epoch, o, h, l, c, 0])
        years = (rows[-1][0] - rows[0][0]) / (365.25 * 86400)
        print(f"{name}: {len(rows)} daily candles, {years:.1f} years, from {source}" + (f" (after: {'; '.join(problems)})" if problems else ""))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
