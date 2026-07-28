from __future__ import annotations

import numpy as np
import pandas as pd


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False, min_periods=max(2, span // 3)).mean()


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gains = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    losses = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = gains / losses.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    true_range = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def _supertrend_direction(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.Series:
    atr = df["atr_14"] if "atr_14" in df else _atr(df, period)
    hl2 = (df["high"] + df["low"]) / 2
    upper = hl2 + multiplier * atr
    lower = hl2 - multiplier * atr
    direction = pd.Series(1, index=df.index, dtype="int64")
    trend = pd.Series(np.nan, index=df.index, dtype="float64")
    for i in range(len(df)):
        if i == 0 or pd.isna(atr.iloc[i]):
            trend.iloc[i] = lower.iloc[i]
            direction.iloc[i] = 1
            continue
        prev_trend = trend.iloc[i - 1]
        prev_dir = direction.iloc[i - 1]
        close = df["close"].iloc[i]
        if prev_dir > 0:
            trend.iloc[i] = max(lower.iloc[i], prev_trend)
            direction.iloc[i] = -1 if close < trend.iloc[i] else 1
        else:
            trend.iloc[i] = min(upper.iloc[i], prev_trend)
            direction.iloc[i] = 1 if close > trend.iloc[i] else -1
    return direction


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add numeric indicators and rule condition labels used by the workspace."""
    out = df.copy()
    if "timestamp" in out.columns:
        out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")
    for column in ["open", "high", "low", "close", "volume"]:
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    out = out.sort_values("timestamp") if "timestamp" in out.columns else out

    close = out["close"]
    out["ema_20"] = _ema(close, 20)
    out["ema_50"] = _ema(close, 50)
    out["ema_200"] = _ema(close, 200)
    out["atr_14"] = _atr(out, 14)
    out["atr_pct"] = out["atr_14"] / close.replace(0, pd.NA)
    out["rsi_14"] = _rsi(close, 14)

    middle = close.rolling(20, min_periods=10).mean()
    std = close.rolling(20, min_periods=10).std()
    out["bb_middle"] = middle
    out["bb_upper"] = middle + 2 * std
    out["bb_lower"] = middle - 2 * std
    out["bb_width"] = (out["bb_upper"] - out["bb_lower"]) / close.replace(0, pd.NA)
    out["bb_width_atr"] = (out["bb_upper"] - out["bb_lower"]) / out["atr_14"].replace(0, pd.NA)

    ema12 = _ema(close, 12)
    ema26 = _ema(close, 26)
    out["macd"] = ema12 - ema26
    out["macd_signal"] = _ema(out["macd"], 9)
    out["macd_hist"] = out["macd"] - out["macd_signal"]
    out["macd_hist_delta"] = out["macd_hist"].diff()
    out["supertrend_direction"] = _supertrend_direction(out)

    body = out["close"] - out["open"]
    candle_range = (out["high"] - out["low"]).replace(0, pd.NA)
    atr = out["atr_14"].replace(0, pd.NA)
    out["body_atr"] = body / atr
    out["body_range"] = body.abs() / candle_range
    out["upper_wick_atr"] = (out["high"] - out[["open", "close"]].max(axis=1)) / atr
    out["lower_wick_atr"] = (out[["open", "close"]].min(axis=1) - out["low"]) / atr

    trend_strength = (out["ema_50"] - out["ema_200"]) / atr
    out["trend_zone"] = "flat_trend"
    out.loc[trend_strength >= 1.0, "trend_zone"] = "strong_uptrend"
    out.loc[(trend_strength >= 0.25) & (trend_strength < 1.0), "trend_zone"] = "uptrend"
    out.loc[trend_strength <= -1.0, "trend_zone"] = "strong_downtrend"
    out.loc[(trend_strength <= -0.25) & (trend_strength > -1.0), "trend_zone"] = "downtrend"

    atr_q = out["atr_pct"].rolling(240, min_periods=40).rank(pct=True)
    out["atr_regime"] = "atr_mid_low"
    out.loc[atr_q <= 0.2, "atr_regime"] = "atr_low"
    out.loc[(atr_q > 0.2) & (atr_q <= 0.45), "atr_regime"] = "atr_mid_low"
    out.loc[(atr_q > 0.45) & (atr_q <= 0.75), "atr_regime"] = "atr_mid_high"
    out.loc[atr_q > 0.75, "atr_regime"] = "atr_high"

    out["bb_position"] = "middle_band_area"
    bb_span = (out["bb_upper"] - out["bb_lower"]).replace(0, pd.NA)
    bb_pct = (close - out["bb_lower"]) / bb_span
    out.loc[bb_pct < -0.05, "bb_position"] = "below_lower_band_area"
    out.loc[(bb_pct >= -0.05) & (bb_pct < 0.25), "bb_position"] = "lower_band_area"
    out.loc[(bb_pct >= 0.25) & (bb_pct <= 0.75), "bb_position"] = "middle_band_area"
    out.loc[(bb_pct > 0.75) & (bb_pct <= 1.05), "bb_position"] = "upper_band_area"
    out.loc[bb_pct > 1.05, "bb_position"] = "above_upper_band_area"

    width_q = out["bb_width"].rolling(240, min_periods=40).rank(pct=True)
    out["bb_width_regime"] = "bb_normal_low"
    out.loc[width_q <= 0.2, "bb_width_regime"] = "bb_compressed"
    out.loc[(width_q > 0.2) & (width_q <= 0.5), "bb_width_regime"] = "bb_normal_low"
    out.loc[(width_q > 0.5) & (width_q <= 0.8), "bb_width_regime"] = "bb_normal_high"
    out.loc[width_q > 0.8, "bb_width_regime"] = "bb_expanded"

    out["rsi_zone"] = "rsi_mid"
    out.loc[out["rsi_14"] <= 30, "rsi_zone"] = "rsi_oversold"
    out.loc[(out["rsi_14"] > 30) & (out["rsi_14"] <= 45), "rsi_zone"] = "rsi_low"
    out.loc[(out["rsi_14"] > 45) & (out["rsi_14"] < 55), "rsi_zone"] = "rsi_mid"
    out.loc[(out["rsi_14"] >= 55) & (out["rsi_14"] < 70), "rsi_zone"] = "rsi_high"
    out.loc[out["rsi_14"] >= 70, "rsi_zone"] = "rsi_overbought"

    out["macd_hist_sign"] = "macd_negative"
    out.loc[out["macd_hist"] >= 0, "macd_hist_sign"] = "macd_positive"
    out["macd_hist_slope"] = "macd_falling"
    out.loc[out["macd_hist_delta"] >= 0, "macd_hist_slope"] = "macd_rising"
    out["supertrend_side"] = "supertrend_down"
    out.loc[out["supertrend_direction"] >= 0, "supertrend_side"] = "supertrend_up"

    out["candle_body"] = "small_body"
    out.loc[(out["body_atr"] > 0.15) & (out["body_atr"] <= 0.75), "candle_body"] = "bull_body"
    out.loc[(out["body_atr"] < -0.15) & (out["body_atr"] >= -0.75), "candle_body"] = "bear_body"
    out.loc[out["body_atr"] > 0.75, "candle_body"] = "large_bull_body"
    out.loc[out["body_atr"] < -0.75, "candle_body"] = "large_bear_body"

    out["upper_wick"] = "small_upper_wick"
    out.loc[(out["upper_wick_atr"] >= 0.25) & (out["upper_wick_atr"] < 0.75), "upper_wick"] = "medium_upper_wick"
    out.loc[out["upper_wick_atr"] >= 0.75, "upper_wick"] = "large_upper_wick"
    out["lower_wick"] = "small_lower_wick"
    out.loc[(out["lower_wick_atr"] >= 0.25) & (out["lower_wick_atr"] < 0.75), "lower_wick"] = "medium_lower_wick"
    out.loc[out["lower_wick_atr"] >= 0.75, "lower_wick"] = "large_lower_wick"

    return out.reset_index(drop=True)
