"""How do the rules the bot actually trades hold up on 5 months of candles?

Replays every rule in a rules CSV over a long candle history with the same simulator as the
walk-forward search (entry at the close, stop 1.4 x ATR, target 1.8 x ATR, exit after 12
candles, costs and stop slippage charged) and reports it in 30-day slices, next to what
buying (or selling) on every candle earned in the same slice.

    .venv/bin/python work/evaluate_existing_rules.py --rules-csv outputs/advanced_accuracy_execution_candidates.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import walk_forward_rule_search as wf


def rule_mask(conditions: pd.DataFrame, feature: str, condition: str) -> np.ndarray:
    features = [part.strip() for part in feature.split("+")]
    values = [part.strip() for part in condition.replace(" & ", "&").split("&")]
    if len(features) != len(values) or any(name not in conditions.columns for name in features):
        return np.zeros(len(conditions), dtype=bool)
    mask = np.ones(len(conditions), dtype=bool)
    for name, value in zip(features, values):
        mask &= (conditions[name] == value).to_numpy()
    return mask


def evaluate(df: pd.DataFrame, rules: pd.DataFrame, cfg: wf.SearchConfig, slice_days: int = 30) -> pd.DataFrame:
    df = wf.add_indicators(df).reset_index(drop=True)
    trades = wf.simulate_trades(df, cfg)
    conditions = wf.condition_frame(df).astype(str)
    usable = (np.arange(len(df)) >= wf.WARMUP_BARS)
    stamps = pd.to_datetime(df["timestamp"], utc=True)
    age_days = ((stamps.iloc[-1] - stamps).dt.total_seconds() / 86400).to_numpy()
    slice_id = (age_days // slice_days).astype(int)  # 0 = most recent slice
    rows = []
    for _, rule in rules.iterrows():
        side = str(rule["suggested_side"]).lower()
        mask = rule_mask(conditions, str(rule["feature"]), str(rule["condition"])) & usable
        ret = trades[f"{side}_ret"].to_numpy()
        for label, select in [("all", np.ones(len(df), dtype=bool))] + [(f"{k * slice_days}-{(k + 1) * slice_days}d ago", slice_id == k) for k in range(int(slice_id.max()) + 1)]:
            hits = wf.segment_stats(ret[mask & select & usable])
            base = float(np.nanmean(ret[select & usable])) if (select & usable).any() else 0.0
            rows.append({"rule_id": rule["rule_id"], "symbol": rule["symbol"], "side": side, "period": label, "trades": hits["n"],
                         "win_rate": round(hits["win_rate"], 3), "net_per_trade_pct": round(hits["expectancy"] * 100, 3),
                         "buy_every_candle_pct": round(base * 100, 3)})
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--rules-csv", default="outputs/advanced_accuracy_execution_candidates.csv")
    parser.add_argument("--rule-ids", nargs="*", default=["PAIR017", "PAIR029"])
    parser.add_argument("--data-dir", default="outputs/history")
    parser.add_argument("--timeframe", default="15m")
    args = parser.parse_args()
    rules = pd.read_csv(args.rules_csv)
    if args.rule_ids:
        rules = rules[rules["rule_id"].isin(args.rule_ids)]
    cfg = wf.SearchConfig()
    pd.set_option("display.width", 200)
    for symbol, group in rules.groupby("symbol"):
        df = wf.load_history(Path(args.data_dir), str(symbol), args.timeframe)
        if df is None:
            print(f"{symbol}: no history file in {args.data_dir}")
            continue
        table = evaluate(df, group, cfg)
        print(f"\n{symbol} {args.timeframe}: {len(df)} candles. net_per_trade_pct is after costs; "
              f"buy_every_candle_pct is what doing the same side on every candle earned.")
        print(table.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
