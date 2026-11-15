"""Download a long candle history from Deriv's public endpoint by paging backwards.

The paper bot only keeps about 1,000 candles (10 days of 15m). A fair rule search needs months.
Uses only the standard library and `websockets`, so the system python3 on the VPS can run it.

    python3 work/download_history.py --symbols CRASH300N BOOM300N --days 150
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import time
from pathlib import Path

import websockets

PUBLIC_WS_URL = "wss://api.derivws.com/trading/v1/options/ws/public"
GRANULARITY = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400}


async def _request(ws, payload: dict) -> dict:
    await ws.send(json.dumps(payload))
    return json.loads(await asyncio.wait_for(ws.recv(), timeout=45))


async def download_history(url: str, symbol: str, granularity: int, days: float, count: int = 1000, max_pages: int = 80) -> tuple[list[dict], str]:
    """Return (candles oldest-first, note). Stops quietly at the first problem and keeps what it has."""
    wanted_from = time.time() - days * 86400
    by_epoch: dict[int, dict] = {}
    note = "reached requested depth"
    end: int | str = "latest"
    async with websockets.connect(url, ping_interval=20, close_timeout=10) as ws:
        for _page in range(max_pages):
            payload = {"ticks_history": symbol, "count": count, "end": end, "granularity": granularity, "style": "candles"}
            response = await _request(ws, payload)
            if "error" in response:
                message = response["error"].get("message", response["error"]) if isinstance(response["error"], dict) else response["error"]
                note = f"stopped by the server: {message}"
                break
            candles = response.get("candles") or []
            if not candles:
                note = "no older candles available"
                break
            before = len(by_epoch)
            for candle in candles:
                by_epoch[int(candle["epoch"])] = candle
            oldest = min(int(c["epoch"]) for c in candles)
            if len(by_epoch) == before:
                note = "no progress (same candles returned)"
                break
            if oldest <= wanted_from:
                break
            end = oldest - 1
        else:
            note = f"stopped after {max_pages} pages"
    rows = [by_epoch[key] for key in sorted(by_epoch)]
    rows = [row for row in rows if int(row["epoch"]) >= wanted_from]
    return rows, note


def save_csv(path: Path, candles: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for c in candles:
            writer.writerow([int(c["epoch"]), c["open"], c["high"], c["low"], c["close"], c.get("volume", 0)])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--symbols", nargs="+", default=["CRASH300N", "BOOM300N"])
    parser.add_argument("--timeframe", default="15m", choices=sorted(GRANULARITY))
    parser.add_argument("--days", type=float, default=150)
    parser.add_argument("--out-dir", default="outputs/history")
    parser.add_argument("--count", type=int, default=1000)
    args = parser.parse_args()
    url = os.environ.get("DERIV_WS_URL") or PUBLIC_WS_URL
    status = 0
    for symbol in args.symbols:
        try:
            candles, note = asyncio.run(download_history(url, symbol, GRANULARITY[args.timeframe], args.days, args.count))
        except Exception as exc:  # network or protocol problems must not hide the other symbols
            print(f"{symbol}: failed ({exc})")
            status = 1
            continue
        if not candles:
            print(f"{symbol}: no candles ({note})")
            status = 1
            continue
        save_csv(Path(args.out_dir) / f"deriv_{symbol}_{args.timeframe}.csv", candles)
        span = (candles[-1]["epoch"] - candles[0]["epoch"]) / 86400
        print(f"{symbol}: {len(candles)} candles, {span:.0f} days ({note})")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
