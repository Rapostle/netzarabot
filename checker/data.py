"""Daily candles for the coins the checker supports (public sources, cached for the day)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "work"))
import download_long_daily as dl  # noqa: E402

# display name -> (binance code, yahoo code)
COINS = {
    "BTC": ("BTCUSDT", "BTC-USD"), "ETH": ("ETHUSDT", "ETH-USD"), "BNB": ("BNBUSDT", "BNB-USD"),
    "SOL": ("SOLUSDT", "SOL-USD"), "XRP": ("XRPUSDT", "XRP-USD"), "ADA": ("ADAUSDT", "ADA-USD"),
    "DOGE": ("DOGEUSDT", "DOGE-USD"), "LTC": ("LTCUSDT", "LTC-USD"), "TRX": ("TRXUSDT", "TRX-USD"),
    "LINK": ("LINKUSDT", "LINK-USD"),
}


def fetch_close(coin: str, years: int = 12, cache_dir: str = "checker_cache", max_age_hours: float = 20.0) -> pd.Series:
    coin = coin.upper()
    if coin not in COINS:
        raise KeyError(coin)
    cache = Path(cache_dir) / f"{coin}_1d.csv"
    if not (cache.exists() and time.time() - cache.stat().st_mtime < max_age_hours * 3600):
        binance, yahoo = COINS[coin]
        rows, problems = [], []
        for label, call in (("binance", lambda: dl.fetch_binance(binance, years)), ("yahoo", lambda: dl.fetch_yahoo(yahoo, years))):
            try:
                rows = call()
            except Exception as exc:  # fall through to the next source
                problems.append(f"{label}: {exc}")
                continue
            if len(rows) >= 200:
                break
        if len(rows) < 200:
            if cache.exists():  # stale data beats no data, but it is still the same days
                return _read(cache)
            raise RuntimeError("no price source reachable: " + "; ".join(problems))
        cache.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(sorted({r[0]: r for r in rows}.values()), columns=["timestamp", "open", "high", "low", "close"])
        df.to_csv(cache, index=False)
    return _read(cache)


def _read(path: Path) -> pd.Series:
    df = pd.read_csv(path)
    idx = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    close = pd.Series(df["close"].astype(float).to_numpy(), index=idx)
    return close[~close.index.duplicated(keep="last")].sort_index()


def fetch_ohlc(coin: str, years: int = 12, cache_dir: str = "checker_cache") -> pd.DataFrame:
    """Daily open/high/low/close indexed by UTC time (refreshes the cache like fetch_close)."""
    fetch_close(coin, years=years, cache_dir=cache_dir)
    df = pd.read_csv(Path(cache_dir) / f"{coin.upper()}_1d.csv")
    df.index = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df[["open", "high", "low", "close"]].astype(float)
