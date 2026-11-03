from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import websockets

# Deriv retired the legacy endpoint (wss://ws.derivws.com/websockets/v3?app_id=...,
# now answers HTTP 520). Public market data (candles) comes from the new public
# options endpoint, which needs no app id and no login.
PUBLIC_WS_URL = "wss://api.derivws.com/trading/v1/options/ws/public"
FALLBACK_COUNT = 1000


@dataclass(frozen=True)
class DerivDownloadRequest:
    symbol: str
    granularity: int
    output: str | Path
    count: int = 5000
    app_id: int | str = 1089  # kept for compatibility; the public endpoint ignores it


class DerivDataDownloader:
    def __init__(self, app_id: int | str = 1089) -> None:
        self.app_id = str(app_id)

    async def _fetch_candles(self, url: str, symbol: str, granularity: int, count: int) -> dict:
        payload = {
            "ticks_history": symbol,
            "count": int(count),
            "end": "latest",
            "granularity": int(granularity),
            "style": "candles",
        }
        async with websockets.connect(url, ping_interval=20, close_timeout=10) as ws:
            await ws.send(json.dumps(payload))
            message = await asyncio.wait_for(ws.recv(), timeout=45)
        return json.loads(message)

    async def _download_async(self, request: DerivDownloadRequest) -> pd.DataFrame:
        url = os.environ.get("DERIV_WS_URL") or PUBLIC_WS_URL
        response = await self._fetch_candles(url, request.symbol, request.granularity, request.count)
        if "error" in response and int(request.count) > FALLBACK_COUNT:
            # The new API may cap how many candles one request can return.
            response = await self._fetch_candles(url, request.symbol, request.granularity, FALLBACK_COUNT)
        if "error" in response:
            error = response["error"]
            raise RuntimeError(f"Deriv download failed for {request.symbol}: {error.get('message', error)}")
        candles = response.get("candles")
        if not candles:
            raise RuntimeError(f"Deriv returned no candles for {request.symbol}")
        df = pd.DataFrame(candles)
        df = df.rename(columns={"epoch": "timestamp"})
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
        for column in ["open", "high", "low", "close"]:
            df[column] = pd.to_numeric(df[column], errors="coerce")
        if "volume" not in df.columns:
            df["volume"] = 0.0
        else:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0.0)
        df = df[["timestamp", "open", "high", "low", "close", "volume"]].dropna()
        if df.empty:
            raise RuntimeError(f"Deriv candle response was empty after parsing for {request.symbol}")
        output = Path(request.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output, index=False)
        return df

    def download(self, request: DerivDownloadRequest) -> pd.DataFrame:
        return asyncio.run(self._download_async(request))
