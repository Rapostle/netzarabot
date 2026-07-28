from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_ohlcv_csv(path: str | Path) -> pd.DataFrame:
    """Load a Deriv-style OHLCV CSV and normalize basic column types."""
    csv_path = Path(path)
    df = pd.read_csv(csv_path)
    if df.empty:
        return df

    rename_map = {
        "epoch": "timestamp",
        "time": "timestamp",
        "datetime": "timestamp",
        "date": "timestamp",
        "volume": "volume",
    }
    df = df.rename(columns={key: value for key, value in rename_map.items() if key in df.columns})
    required = ["timestamp", "open", "high", "low", "close"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Missing OHLCV column(s) in {csv_path}: {', '.join(missing)}")

    if pd.api.types.is_numeric_dtype(df["timestamp"]):
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    else:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")

    for column in ["open", "high", "low", "close", "volume"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    if "volume" not in df.columns:
        df["volume"] = 0.0

    df = df.dropna(subset=["timestamp", "open", "high", "low", "close"])
    df = df.sort_values("timestamp").drop_duplicates("timestamp", keep="last")
    return df.reset_index(drop=True)
