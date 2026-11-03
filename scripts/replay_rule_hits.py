#!/usr/bin/env python3
"""How often would the paper rules have fired on the candles we hold now?

Read-only. For every rule in a rules CSV it replays the stored candles (the same indicators and
the same matching the paper track uses) and counts the candles where the rule would have matched.
Also counts how often each half of every rule is true on its own, so a rule that never fires
can be traced to the half that never happens.

Usage (on the server, from the project folder):
  .venv/bin/python scripts/replay_rule_hits.py \
      --rules outputs/advanced_accuracy_execution_candidates.csv \
      --data-dir outputs/pair_candidate_refreshed_data
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "external" / "trading_bot"))

from trading_bot.data.loader import load_ohlcv_csv  # noqa: E402
from trading_bot.indicators.technical import add_indicators  # noqa: E402
from trading_bot.research.signal_discovery import condition_frame  # noqa: E402

WARMUP = 240  # rolling-rank features need this much history before they mean anything


def candle_file(data_dir: Path, symbol: str, timeframe: str) -> Path:
    return data_dir / f"deriv_{symbol}_{timeframe}.csv"


def split_rule(rule: pd.Series) -> list[tuple[str, str]]:
    features = [part.strip() for part in str(rule["feature"]).split("+")]
    values = [part.strip() for part in str(rule["condition"]).replace(" & ", "&").split("&")]
    return list(zip(features, values)) if len(features) == len(values) else []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rules", required=True)
    parser.add_argument("--data-dir", required=True)
    args = parser.parse_args()
    rules = pd.read_csv(args.rules)
    data_dir = Path(args.data_dir)
    frames: dict[tuple[str, str], pd.DataFrame] = {}
    for symbol, timeframe in rules[["symbol", "timeframe"]].drop_duplicates().itertuples(index=False):
        path = candle_file(data_dir, str(symbol), str(timeframe))
        if not path.exists():
            print(f"{symbol} {timeframe}: no candle file at {path}")
            continue
        df = add_indicators(load_ohlcv_csv(path)).reset_index(drop=True)
        conditions = condition_frame(df).astype(str)
        frames[(str(symbol), str(timeframe))] = pd.concat([df[["timestamp", "close"]], conditions], axis=1)
        span_days = (df["timestamp"].iloc[-1] - df["timestamp"].iloc[WARMUP]).total_seconds() / 86400 if len(df) > WARMUP else 0
        print(f"{symbol} {timeframe}: {len(df)} candles, {max(len(df) - WARMUP, 0)} usable after warm-up (~{span_days:.1f} days), "
              f"last close {df['close'].iloc[-1]:.3f}, newest candle {df['timestamp'].iloc[-1]}")
    print()
    any_hit = False
    for _, rule in rules.sort_values(["symbol", "symbol_rule_rank"]).iterrows():
        key = (str(rule["symbol"]), str(rule["timeframe"]))
        frame = frames.get(key)
        parts = split_rule(rule)
        if frame is None or not parts or len(frame) <= WARMUP:
            continue
        usable = frame.iloc[WARMUP:]
        masks = []
        for feature, value in parts:
            masks.append((usable[feature] == value) if feature in usable.columns else pd.Series(False, index=usable.index))
        both = masks[0]
        for mask in masks[1:]:
            both = both & mask
        days = (usable["timestamp"].iloc[-1] - usable["timestamp"].iloc[0]).total_seconds() / 86400
        hits = int(both.sum())
        any_hit = any_hit or hits > 0
        halves = ", ".join(f"{feature}={value}: {int(mask.sum())}" for (feature, value), mask in zip(parts, masks))
        last = usable.loc[both, "timestamp"].iloc[-1] if hits else "never"
        print(f"{rule['rule_id']} {key[0]} {rule['suggested_side']:4s} fired {hits:3d}x in {days:.1f} days "
              f"(~{hits / max(days, 0.01) * 7:.1f}/week), last: {last}\n      halves -> {halves}")
    print()
    print("RESULT:", "rules do fire on the candles we hold" if any_hit else "NO rule fires on the candles we hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
