from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


CONDITION_COLUMNS = [
    "trend_zone",
    "atr_regime",
    "bb_position",
    "bb_width_regime",
    "rsi_zone",
    "macd_hist_sign",
    "macd_hist_slope",
    "supertrend_side",
    "candle_body",
    "upper_wick",
    "lower_wick",
]


@dataclass(frozen=True)
class DiscoveryConfig:
    horizon: int
    min_samples: int
    min_abs_return: float


def condition_frame(df: pd.DataFrame) -> pd.DataFrame:
    existing = [column for column in CONDITION_COLUMNS if column in df.columns]
    return df[existing].copy()


def forward_returns(df: pd.DataFrame, horizon: int) -> pd.Series:
    return df["close"].shift(-horizon) / df["close"] - 1.0


def _profit_factor(returns: pd.Series) -> float:
    wins = returns[returns > 0]
    losses = returns[returns <= 0]
    gross_profit = float(wins.sum())
    gross_loss = abs(float(losses.sum()))
    if gross_loss > 0:
        return gross_profit / gross_loss
    if gross_profit > 0:
        return float("inf")
    return 0.0


def _score_edge(feature: str, condition: str, returns: pd.Series, min_abs_return: float) -> dict[str, object] | None:
    returns = returns.dropna()
    samples = int(len(returns))
    if samples == 0:
        return None
    buy_expectancy = float(returns.mean())
    sell_returns = -returns
    sell_expectancy = float(sell_returns.mean())
    suggested_side = "buy" if buy_expectancy >= sell_expectancy else "sell"
    chosen = returns if suggested_side == "buy" else sell_returns
    expectancy = float(chosen.mean())
    if abs(expectancy) < min_abs_return:
        return None
    return {
        "feature": feature,
        "condition": condition,
        "samples": samples,
        "suggested_side": suggested_side,
        "buy_win_rate": float((returns > 0).mean()),
        "sell_win_rate": float((sell_returns > 0).mean()),
        "buy_expectancy": buy_expectancy,
        "sell_expectancy": sell_expectancy,
        "profit_factor": _profit_factor(chosen),
        "expectancy": expectancy,
    }


def discover_pair_edges(df: pd.DataFrame, config: DiscoveryConfig) -> pd.DataFrame:
    conditions = condition_frame(df).astype(str)
    fwd = forward_returns(df, config.horizon)
    rows: list[dict[str, object]] = []

    for feature in conditions.columns:
        for value in sorted(conditions[feature].dropna().unique()):
            mask = conditions[feature] == value
            if int(mask.sum()) < config.min_samples:
                continue
            scored = _score_edge(feature, str(value), fwd[mask], config.min_abs_return)
            if scored:
                rows.append(scored)

    columns = list(conditions.columns)
    for left_index, left in enumerate(columns):
        for right in columns[left_index + 1 :]:
            pair = conditions[[left, right]].dropna()
            grouped = pair.groupby([left, right], sort=True)
            for (left_value, right_value), index in grouped.groups.items():
                if len(index) < config.min_samples:
                    continue
                feature = f"{left}+{right}"
                condition = f"{left_value} & {right_value}"
                scored = _score_edge(feature, condition, fwd.loc[index], config.min_abs_return)
                if scored:
                    rows.append(scored)

    if not rows:
        return pd.DataFrame(
            columns=[
                "feature",
                "condition",
                "samples",
                "suggested_side",
                "buy_win_rate",
                "sell_win_rate",
                "buy_expectancy",
                "sell_expectancy",
                "profit_factor",
                "expectancy",
            ]
        )
    return pd.DataFrame(rows).sort_values(["profit_factor", "expectancy", "samples"], ascending=False).reset_index(drop=True)
