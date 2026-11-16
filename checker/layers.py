"""Optional risk layers on top of any rule, fixed in advance (never tuned on results).

1. Trend-strength filter: stay flat while the market is choppy (Kaufman efficiency ratio below a floor).
2. Volatility sizing: smaller positions when the market is wild (size = target / recent volatility, between a floor and 1).
Size is set when a position opens and held until it changes, so the checker and the paper bot use the same arithmetic.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Layers:
    er_min: float = 0.15      # 0 turns the choppy-market filter off
    er_n: int = 30
    target_vol: float = 0.03  # target daily volatility; 0 turns sizing off
    vol_n: int = 20
    size_floor: float = 0.25

    def label(self) -> str:
        parts = []
        if self.er_min > 0:
            parts.append(f"skips choppy markets (efficiency ratio under {self.er_min:g} over {self.er_n} days)")
        if self.target_vol > 0:
            parts.append(f"sizes down in wild markets (target {self.target_vol:.0%} daily volatility, size {self.size_floor:g} to 1)")
        return "; ".join(parts) or "plain"


def efficiency_ratio(close: pd.Series, n: int) -> pd.Series:
    """1 = a straight line, near 0 = going nowhere. Net move over n days divided by the path travelled."""
    net = (close - close.shift(n)).abs()
    path = close.diff().abs().rolling(n).sum()
    return net / path.replace(0, np.nan)


def filtered_signal(close: pd.Series, signal: pd.Series, layers: Layers | None) -> pd.Series:
    if layers is None or layers.er_min <= 0:
        return signal
    ok = efficiency_ratio(close, layers.er_n) >= layers.er_min  # NaN compares False: no trade during warm-up
    return signal.where(ok, 0.0)


def raw_size(close: pd.Series, layers: Layers | None) -> pd.Series:
    if layers is None or layers.target_vol <= 0:
        return pd.Series(1.0, index=close.index)
    vol = close.pct_change().rolling(layers.vol_n).std()
    return (layers.target_vol / vol).clip(layers.size_floor, 1.0).fillna(layers.size_floor)


def held_size(close: pd.Series, signal: pd.Series, layers: Layers | None) -> pd.Series:
    """Size fixed on the day the signal changes, then carried until it changes again."""
    size = raw_size(close, layers)
    changed = signal != signal.shift(1)
    return size.where(changed).ffill().fillna(size.iloc[0] if len(size) else 1.0)


def layered_returns(close: pd.Series, signal: pd.Series, cost_one_way: float, hold_cost: float, layers: Layers | None) -> pd.Series:
    """Daily net return of: yesterday's (filtered) signal, sized at entry, with costs on every change of exposure."""
    sig = filtered_signal(close, signal, layers)
    exposure = (sig * held_size(close, sig, layers)).shift(1).fillna(0.0)
    daily = close.pct_change().fillna(0.0)
    turnover = exposure.diff().abs().fillna(exposure.abs())
    return exposure * daily - turnover * cost_one_way - exposure.abs() * hold_cost


def latest_signal_and_size(close: pd.Series, signal: pd.Series, layers: Layers | None) -> tuple[int, float]:
    """What the paper bot needs on the newest closed candle: the filtered signal and the size it would open with."""
    sig = filtered_signal(close, signal, layers)
    return int(sig.iloc[-1]), float(raw_size(close, layers).iloc[-1])
