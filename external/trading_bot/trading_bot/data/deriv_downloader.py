from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import websockets


@dataclass(frozen=True)
class DerivDownloadRequest:
    symbol: str
    granularity: int
    output: str | Path
    count: int = 5000
    app_id: int | str = 1089


class DerivDataDownloader:
    def __init__(self, app_id: int | str = 1089) -> None:
        self.app_id = str(app_id)

    async def _download_async(self, request: DerivDownloadRequest) -> pd.DataFrame:
        app_id = str(request.app_id or self.app_id)
        url = f"wss://ws.derivws.com/websockets/v3?app_id={app_id}"
        payload = {
            "ticks_history": request.symbol,
            "adjust_start_time": 1,
            "count": int(request.count),
            "end": "latest",
            "granularity": int(request.granularity),
            "style": "candles",
        }
        async with websockets.connect(url, ping_interval=20, close_timeout=10) as ws:
            await ws.send(json.dumps(payload))
            message = await asyncio.wait_for(ws.recv(), timeout=45)
        response = json.loads(message)
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
