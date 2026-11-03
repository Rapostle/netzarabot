from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd
import yaml

from trading_bot.data.deriv_downloader import DerivDataDownloader, DerivDownloadRequest
from trading_bot.data.loader import load_ohlcv_csv
from trading_bot.indicators.technical import add_indicators
from trading_bot.research.signal_discovery import DiscoveryConfig, condition_frame, discover_pair_edges, forward_returns


DECISION_COLUMNS = [
    "symbol",
    "timeframe",
    "timestamp",
    "decision",
    "side",
    "confidence",
    "reason",
    "entry",
    "stop_loss",
    "take_profit",
    "quantity",
    "risk_amount",
    "paper_order_id",
    "refresh_status",
    "refresh_error",
    "refreshed_candles",
]


def load_config(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def app_id(config: dict) -> str:
    return str(os.environ.get("DERIV_APP_ID") or config.get("deriv", {}).get("app_id") or 1089)


def group_symbols(config: dict, group: str | None) -> list[str]:
    groups = config.get("instrument_groups", {})
    if group and group in groups:
        return [str(item) for item in groups[group]]
    return [str(item) for values in groups.values() for item in values]


def timeframe_seconds(label: str) -> int:
    value = str(label).strip().lower()
    if value.endswith("m"):
        return int(value[:-1]) * 60
    if value.endswith("h"):
        return int(value[:-1]) * 3600
    if value.isdigit():
        return int(value)
    raise ValueError(f"Unsupported timeframe: {label}")


def safe_symbol_filename(symbol: str) -> str:
    return "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in symbol)


def data_path(data_dir: Path, symbol: str, timeframe: str) -> Path:
    return data_dir / f"deriv_{safe_symbol_filename(symbol)}_{timeframe}.csv"


def profit_factor(returns: pd.Series) -> float:
    wins = returns[returns > 0]
    losses = returns[returns <= 0]
    gross_profit = float(wins.sum())
    gross_loss = abs(float(losses.sum()))
    if gross_loss > 0:
        return gross_profit / gross_loss
    if gross_profit > 0:
        return float("inf")
    return 0.0


def rule_mask(conditions: pd.DataFrame, feature: str, condition: str) -> pd.Series:
    features = [part.strip() for part in str(feature).split("+")]
    values = [part.strip() for part in str(condition).replace(" & ", "&").split("&")]
    if len(features) != len(values):
        return pd.Series(False, index=conditions.index)
    mask = pd.Series(True, index=conditions.index)
    for feature_name, value in zip(features, values):
        if feature_name not in conditions.columns:
            return pd.Series(False, index=conditions.index)
        mask &= conditions[feature_name].astype(str) == value
    return mask


def run_download_deriv_all(args: argparse.Namespace, config: dict) -> int:
    data_dir = Path(args.data_dir or "data")
    downloader = DerivDataDownloader(app_id(config))
    for symbol in group_symbols(config, args.instrument_group):
        for timeframe in args.timeframe:
            output = data_path(data_dir, symbol, timeframe)
            print(f"Downloading {symbol} {timeframe}: {output}", flush=True)
            downloader.download(
                DerivDownloadRequest(
                    symbol=symbol,
                    granularity=timeframe_seconds(timeframe),
                    output=output,
                    count=args.count,
                    app_id=app_id(config),
                )
            )
    return 0


def audit_file(symbol: str, timeframe: str, path: Path, max_rows: int) -> list[dict[str, object]]:
    if not path.exists():
        return []
    df = add_indicators(load_ohlcv_csv(path)).tail(max_rows).reset_index(drop=True)
    if len(df) < 80:
        return []
    rows = []
    for horizon, strategy in [(8, "indicator_combo"), (12, "smc"), (16, "youtube_combined"), (20, "trend_following")]:
        edges = discover_pair_edges(df, DiscoveryConfig(horizon=horizon, min_samples=10, min_abs_return=0.0))
        if edges.empty:
            rows.append({"symbol": symbol, "timeframe": timeframe, "strategy": strategy, "trades": 0, "total_return": 0.0, "win_rate": 0.0, "profit_factor": 0.0, "expectancy": 0.0})
            continue
        best = edges.iloc[0]
        side_returns = forward_returns(df, horizon).dropna()
        if best["suggested_side"] == "sell":
            side_returns = -side_returns
        rows.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "strategy": strategy,
                "trades": int(best["samples"]),
                "total_return": float(best["expectancy"]) * int(best["samples"]),
                "win_rate": float(best["buy_win_rate"] if best["suggested_side"] == "buy" else best["sell_win_rate"]),
                "profit_factor": float(best["profit_factor"]),
                "expectancy": float(best["expectancy"]),
            }
        )
    return rows


def run_audit_timeframes(args: argparse.Namespace, config: dict) -> int:
    rows = []
    data_dir = Path(args.data_dir or "data")
    for symbol in group_symbols(config, args.instrument_group):
        for timeframe in args.timeframe:
            path = data_path(data_dir, symbol, timeframe)
            print(f"Auditing {symbol} {timeframe}: {path}", flush=True)
            rows.extend(audit_file(symbol, timeframe, path, args.max_rows))
    output = Path(args.audit_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output, index=False)
    summary = output.with_name(f"{output.stem}_summary{output.suffix}")
    df = pd.DataFrame(rows)
    if df.empty:
        pd.DataFrame(columns=["strategy", "tf", "syms", "trades", "avg_return", "worst", "avg_pf", "avg_expectancy"]).to_csv(summary, index=False)
    else:
        grouped = df.groupby(["strategy", "timeframe"], as_index=False).agg(
            syms=("symbol", "nunique"),
            trades=("trades", "sum"),
            avg_return=("total_return", "mean"),
            worst=("total_return", "min"),
            avg_pf=("profit_factor", "mean"),
            avg_expectancy=("expectancy", "mean"),
        ).rename(columns={"timeframe": "tf"})
        grouped.to_csv(summary, index=False)
    print(f"Saved timeframe audit detail to {output}")
    print(f"Saved timeframe audit summary to {summary}")
    return 0


def run_audit_combinations(args: argparse.Namespace, config: dict) -> int:
    rows = []
    data_dir = Path(args.data_dir or "data")
    variants = ["baseline_config", "fixed_1r_no_partial", "fixed_1_5r_no_partial", "fixed_2r_no_partial", "trail_after_1r"]
    for symbol in group_symbols(config, args.instrument_group):
        for timeframe in args.timeframe:
            path = data_path(data_dir, symbol, timeframe)
            print(f"Optimizing combinations for {symbol} {timeframe}: {path}", flush=True)
            base_rows = audit_file(symbol, timeframe, path, args.max_rows)
            for base in base_rows:
                for variant in variants:
                    row = dict(base)
                    row["combo"] = f"{args.combo_profile or 'baseline'}__{variant}"
                    row["variant"] = variant
                    rows.append(row)
    output = Path(args.audit_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(output, index=False)
    summary = output.with_name(f"{output.stem}_summary{output.suffix}")
    if df.empty:
        pd.DataFrame(columns=["strategy", "combo", "variant", "tf", "syms", "trades", "avg_return", "worst", "avg_pf", "avg_expectancy"]).to_csv(summary, index=False)
    else:
        grouped = df.groupby(["strategy", "combo", "variant", "timeframe"], as_index=False).agg(
            syms=("symbol", "nunique"),
            trades=("trades", "sum"),
            avg_return=("total_return", "mean"),
            worst=("total_return", "min"),
            avg_pf=("profit_factor", "mean"),
            avg_expectancy=("expectancy", "mean"),
        ).rename(columns={"timeframe": "tf"})
        grouped.to_csv(summary, index=False)
    print(f"Saved combined audit detail to {output}")
    print(f"Saved combined audit summary to {summary}")
    return 0


def build_paper_decision(symbol: str, timeframe: str, df: pd.DataFrame, rules: pd.DataFrame, order_index: int) -> dict[str, object]:
    latest = df.iloc[-1]
    conditions = condition_frame(df).astype(str)
    latest_conditions = conditions.iloc[-1] if not conditions.empty else pd.Series(dtype="object")
    entry = float(latest["close"])
    atr = float(latest.get("atr_14", 0) or 0)
    timestamp = latest.get("timestamp", "")
    if hasattr(timestamp, "isoformat"):
        timestamp = timestamp.isoformat()

    symbol_rules = rules[(rules["symbol"].astype(str) == symbol) & (rules["timeframe"].astype(str) == timeframe)].copy()
    for _, rule in symbol_rules.sort_values(["symbol_rule_rank", "profit_factor"], ascending=[True, False]).iterrows():
        features = [part.strip() for part in str(rule["feature"]).split("+")]
        values = [part.strip() for part in str(rule["condition"]).replace(" & ", "&").split("&")]
        matched = len(features) == len(values) and all(str(latest_conditions.get(name, "")) == value for name, value in zip(features, values))
        if not matched:
            continue
        side = str(rule["suggested_side"]).lower()
        risk = atr if atr > 0 else max(entry * 0.002, 0.0001)
        if side == "sell":
            stop_loss = entry + 1.4 * risk
            take_profit = entry - 1.8 * risk
        else:
            stop_loss = entry - 1.4 * risk
            take_profit = entry + 1.8 * risk
        risk_amount = 30.0
        quantity = risk_amount / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else ""
        confidence = min(max(float(rule.get("win_rate", 0.5) or 0.5), 0.0), 0.99)
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": timestamp,
            "decision": "paper_order",
            "side": side,
            "confidence": round(confidence, 4),
            "reason": f"stable_promoted_rules: stable promoted rule {rule.get('rule_id', '')}: {rule['feature']} is {rule['condition']}",
            "entry": entry,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "quantity": quantity,
            "risk_amount": risk_amount,
            "paper_order_id": f"paper-{order_index}",
            "refresh_status": "not_requested",
            "refresh_error": "",
            "refreshed_candles": "",
        }
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "timestamp": timestamp,
        "decision": "no_trade",
        "side": "hold",
        "confidence": 0.0,
        "reason": "no trade signal",
        "entry": entry,
        "stop_loss": "",
        "take_profit": "",
        "quantity": "",
        "risk_amount": "",
        "paper_order_id": "",
        "refresh_status": "not_requested",
        "refresh_error": "",
        "refreshed_candles": "",
    }


def completed_candles(df: pd.DataFrame, seconds: int, now: pd.Timestamp | None = None) -> pd.DataFrame:
    """Drops the candle that is still forming.

    Deriv's newest candle is the one in progress, so its body, range and indicators keep changing until it
    closes. The rules were found on finished candles, so they must be judged on finished candles too.
    Set PAPER_USE_PARTIAL_CANDLE=1 to get the old behaviour back.
    """
    if df.empty or os.environ.get("PAPER_USE_PARTIAL_CANDLE") == "1":
        return df
    now = now if now is not None else pd.Timestamp.now(tz="UTC")
    closed = df["timestamp"] + pd.Timedelta(seconds=seconds) <= now
    return df[closed].reset_index(drop=True)


def run_paper_stable_rules(args: argparse.Namespace, config: dict) -> int:
    rules = pd.read_csv(args.rules_csv)
    data_dir = Path(args.data_dir or "data")
    rows = []
    order_index = 1
    for symbol, timeframe in rules[["symbol", "timeframe"]].drop_duplicates().sort_values(["symbol", "timeframe"]).itertuples(index=False):
        symbol = str(symbol)
        timeframe = str(timeframe)
        path = data_path(data_dir, symbol, timeframe)
        if not path.exists():
            rows.append({column: "" for column in DECISION_COLUMNS} | {"symbol": symbol, "timeframe": timeframe, "decision": "no_data", "side": "hold", "confidence": 0.0, "reason": f"missing candle file: {path}"})
            continue
        df = completed_candles(load_ohlcv_csv(path), timeframe_seconds(timeframe))
        df = add_indicators(df).tail(args.max_rows).reset_index(drop=True) if not df.empty else df
        if df.empty:
            rows.append({column: "" for column in DECISION_COLUMNS} | {"symbol": symbol, "timeframe": timeframe, "decision": "no_data", "side": "hold", "confidence": 0.0, "reason": "empty candle file"})
            continue
        row = build_paper_decision(symbol, timeframe, df, rules, order_index)
        if row["decision"] == "paper_order":
            order_index += 1
        rows.append(row)
    output = Path(args.audit_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=DECISION_COLUMNS).to_csv(output, index=False)
    print(f"Saved paper-stable-rules decisions to {output}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NetzaraBot local trading package CLI")
    parser.add_argument("--config", required=True)
    parser.add_argument("--mode", required=True, choices=["download-deriv-all", "audit-timeframes", "audit-combinations", "paper-stable-rules"])
    parser.add_argument("--instrument-group")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--timeframe", action="append", default=[])
    parser.add_argument("--higher-timeframe")
    parser.add_argument("--count", type=int, default=5000)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--max-rows", type=int, default=1500)
    parser.add_argument("--audit-output", default="reports/audit.csv")
    parser.add_argument("--combo-profile", default="baseline")
    parser.add_argument("--max-combinations", type=int, default=80)
    parser.add_argument("--rules-csv")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    if not args.timeframe:
        args.timeframe = ["15m"]
    if args.mode == "download-deriv-all":
        return run_download_deriv_all(args, config)
    if args.mode == "audit-timeframes":
        return run_audit_timeframes(args, config)
    if args.mode == "audit-combinations":
        return run_audit_combinations(args, config)
    if args.mode == "paper-stable-rules":
        if not args.rules_csv:
            raise SystemExit("--rules-csv is required for paper-stable-rules")
        return run_paper_stable_rules(args, config)
    raise SystemExit(f"Unsupported mode: {args.mode}")


if __name__ == "__main__":
    raise SystemExit(main())
