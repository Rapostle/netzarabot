from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


BOT_ROOT = Path("/Users/ocmix/Documents/Codex/2026-07-09/can-you-help-implement-in-the")
TASK_ROOT = Path("/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot")
DEFAULT_RULES = TASK_ROOT / "outputs/crash_boom_execution_approved_stable_rules_15m_30m.csv"
DEFAULT_DATA_DIR = TASK_ROOT / "outputs/paper_refreshed_data"
DEFAULT_NEAR_MISS = TASK_ROOT / "outputs/stable_rules_near_misses.csv"
DEFAULT_RELAXED = TASK_ROOT / "outputs/stable_rules_relaxed_research_candidates.csv"
DEFAULT_RELAXED_RULES = TASK_ROOT / "outputs/stable_rules_relaxed_promoted_research_rules.csv"
DEFAULT_REPORT = TASK_ROOT / "outputs/stable_rules_signal_frequency_report.md"

sys.path.insert(0, str(BOT_ROOT))

from trading_bot.data.loader import load_ohlcv_csv  # noqa: E402
from trading_bot.indicators.technical import add_indicators  # noqa: E402
from trading_bot.research.signal_discovery import condition_frame, forward_returns  # noqa: E402


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
    features = feature.split("+")
    values = condition.split(" & ")
    if len(features) != len(values):
        return pd.Series(False, index=conditions.index)
    mask = pd.Series(True, index=conditions.index)
    for name, value in zip(features, values):
        if name not in conditions.columns:
            return pd.Series(False, index=conditions.index)
        mask &= conditions[name].astype(str) == value
    return mask


def score_mask(df: pd.DataFrame, mask: pd.Series, side: str, horizon: int) -> dict[str, float | int]:
    returns = forward_returns(df, horizon).dropna()
    aligned = mask.reindex(returns.index).fillna(False)
    selected = returns[aligned]
    if side == "sell":
        selected = -selected
    trades = len(selected)
    if trades == 0:
        return {"trades": 0, "win_rate": 0.0, "profit_factor": 0.0, "expectancy": 0.0, "total_return": 0.0}
    return {
        "trades": trades,
        "win_rate": float((selected > 0).mean()),
        "profit_factor": profit_factor(selected),
        "expectancy": float(selected.mean()),
        "total_return": float(selected.sum()),
    }


def analyze(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    rules = pd.read_csv(args.rules_csv)
    near_rows = []
    relaxed_rows = []

    for (symbol, timeframe), symbol_rules in rules.groupby(["symbol", "timeframe"], sort=True):
        path = data_path(Path(args.data_dir), str(symbol), str(timeframe))
        if not path.exists():
            continue

        df = add_indicators(load_ohlcv_csv(path)).tail(args.max_rows)
        if len(df) < 260:
            continue
        conditions = condition_frame(df).astype(str)
        latest = conditions.iloc[-1]
        latest_time = df.index[-1].isoformat()
        recent_conditions = conditions.tail(args.recent_bars)

        for _, rule in symbol_rules.sort_values(["symbol_rule_rank", "profit_factor"], ascending=[True, False]).iterrows():
            features = str(rule["feature"]).split("+")
            values = str(rule["condition"]).split(" & ")
            pairs = list(zip(features, values))
            matched = [name for name, value in pairs if str(latest.get(name, "")) == value]
            missing = [f"{name}={value} (now {latest.get(name, '')})" for name, value in pairs if str(latest.get(name, "")) != value]

            exact = rule_mask(conditions, str(rule["feature"]), str(rule["condition"]))
            recent_exact = int(exact.tail(args.recent_bars).sum())
            recent_partial = 0
            if len(pairs) > 1:
                part_counts = pd.Series(0, index=recent_conditions.index)
                for name, value in pairs:
                    part_counts += (recent_conditions[name].astype(str) == value).astype(int)
                recent_partial = int((part_counts == len(pairs) - 1).sum())

            near_rows.append(
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "rule_id": rule["rule_id"],
                    "side": rule["suggested_side"],
                    "rank": int(rule["symbol_rule_rank"]),
                    "feature": rule["feature"],
                    "condition": rule["condition"],
                    "latest_time": latest_time,
                    "latest_match_parts": len(matched),
                    "required_parts": len(pairs),
                    "latest_status": "exact_match" if len(matched) == len(pairs) else "near_miss" if matched else "blocked",
                    "matched_features": ", ".join(matched) if matched else "",
                    "missing_features": "; ".join(missing) if missing else "",
                    "recent_exact_matches": recent_exact,
                    "recent_one_missing_matches": recent_partial,
                    "approved_trades": int(rule["trades"]),
                    "approved_win_rate": float(rule["win_rate"]),
                    "approved_profit_factor": float(rule["profit_factor"]),
                }
            )

            for name, value in pairs:
                single_mask = conditions[name].astype(str) == value
                scores = score_mask(df, single_mask, str(rule["suggested_side"]), args.horizon)
                relaxed_rows.append(
                    {
                        "rule_id": f"RELAXED_{rule['rule_id']}_{name}",
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "source_rule_id": rule["rule_id"],
                        "suggested_side": rule["suggested_side"],
                        "relaxed_feature": name,
                        "relaxed_condition": value,
                        "feature": name,
                        "condition": value,
                        **scores,
                        "passes_research_floor": bool(
                            scores["trades"] >= args.min_trades
                            and scores["profit_factor"] >= args.min_profit_factor
                            and scores["expectancy"] > 0
                        ),
                    }
                )

    near = pd.DataFrame(near_rows)
    relaxed = pd.DataFrame(relaxed_rows)
    if not relaxed.empty:
        relaxed = relaxed.sort_values(
            ["passes_research_floor", "profit_factor", "expectancy", "trades"],
            ascending=[False, False, False, False],
        )
    return near, relaxed


def markdown_table(df: pd.DataFrame, columns: list[str], empty_message: str, limit: int | None = None) -> str:
    if df.empty:
        return empty_message
    if limit is not None:
        df = df.head(limit)
    available = [column for column in columns if column in df.columns]
    view = df[available].fillna("").astype(str)
    header = "| " + " | ".join(available) + " |"
    divider = "| " + " | ".join("---" for _ in available) + " |"
    rows = ["| " + " | ".join(row) + " |" for row in view.to_numpy()]
    return "\n".join([header, divider, *rows])


def write_report(path: Path, near: pd.DataFrame, relaxed: pd.DataFrame, label: str) -> None:
    exact_now = int((near["latest_status"] == "exact_match").sum()) if not near.empty else 0
    near_now = int((near["latest_status"] == "near_miss").sum()) if not near.empty else 0
    viable_relaxed = relaxed[relaxed["passes_research_floor"] == True] if not relaxed.empty else relaxed
    lines = [
        f"# {label} Signal Frequency Report",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This report explains why the paper rules are not firing often. Relaxed candidates are research-only.",
        "",
        "## Current Signal State",
        "",
        f"- Exact rule matches right now: {exact_now}",
        f"- Near misses right now: {near_now}",
        f"- Research-only relaxed candidates passing floor: {0 if viable_relaxed.empty else len(viable_relaxed)}",
        "",
        "## Latest Near Misses",
        "",
        markdown_table(
            near.sort_values(["latest_match_parts", "recent_one_missing_matches", "recent_exact_matches"], ascending=False),
            [
                "symbol",
                "timeframe",
                "rule_id",
                "side",
                "latest_status",
                "latest_match_parts",
                "required_parts",
                "missing_features",
                "recent_exact_matches",
                "recent_one_missing_matches",
            ],
            "No near-miss rows available.",
            limit=12,
        ),
        "",
        "## Best Relaxed Research Candidates",
        "",
        markdown_table(
            viable_relaxed,
            [
                "symbol",
                "timeframe",
                "source_rule_id",
                "suggested_side",
                "relaxed_feature",
                "relaxed_condition",
                "trades",
                "win_rate",
                "profit_factor",
                "expectancy",
                "total_return",
            ],
            "No relaxed candidate passed the research floor.",
            limit=12,
        ),
        "",
        "## What This Means",
        "",
        "- If near misses are common but exact matches are rare, the approved rules are probably too strict for frequent paper signals.",
        "- Relaxed candidates must be re-tested with backtest and walk-forward before promotion.",
        "- Nothing in this report changes live or paper trading rules automatically.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Explain stable-rule no-trade decisions and research safe relaxations.")
    parser.add_argument("--rules-csv", default=str(DEFAULT_RULES))
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--near-miss-output", default=str(DEFAULT_NEAR_MISS))
    parser.add_argument("--relaxed-output", default=str(DEFAULT_RELAXED))
    parser.add_argument("--relaxed-rules-output", default=str(DEFAULT_RELAXED_RULES))
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT))
    parser.add_argument("--label", default="Stable Rules")
    parser.add_argument("--max-rows", type=int, default=5000)
    parser.add_argument("--recent-bars", type=int, default=96)
    parser.add_argument("--horizon", type=int, default=12)
    parser.add_argument("--min-trades", type=int, default=30)
    parser.add_argument("--min-profit-factor", type=float, default=1.2)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    near, relaxed = analyze(args)
    near_path = Path(args.near_miss_output)
    relaxed_path = Path(args.relaxed_output)
    relaxed_rules_path = Path(args.relaxed_rules_output)
    report_path = Path(args.report_output)

    near_path.parent.mkdir(parents=True, exist_ok=True)
    near.to_csv(near_path, index=False)
    relaxed.to_csv(relaxed_path, index=False)
    relaxed_rules = relaxed[relaxed["passes_research_floor"] == True].copy() if not relaxed.empty else relaxed
    if not relaxed_rules.empty:
        relaxed_rules = relaxed_rules.drop_duplicates(["symbol", "timeframe", "suggested_side", "feature", "condition"])
        relaxed_rules["symbol_rule_rank"] = relaxed_rules.groupby(["symbol", "timeframe", "suggested_side"]).cumcount() + 1
        relaxed_rules["promotion_status"] = "research_relaxed"
        relaxed_rules = relaxed_rules[
            [
                "rule_id",
                "symbol",
                "timeframe",
                "suggested_side",
                "feature",
                "condition",
                "trades",
                "total_return",
                "win_rate",
                "profit_factor",
                "expectancy",
                "symbol_rule_rank",
                "promotion_status",
                "source_rule_id",
            ]
        ]
    relaxed_rules.to_csv(relaxed_rules_path, index=False)
    write_report(report_path, near, relaxed, args.label)

    print(f"Saved near-miss detail to {near_path}")
    print(f"Saved relaxed research candidates to {relaxed_path}")
    print(f"Saved relaxed research rules to {relaxed_rules_path}")
    print(f"Saved signal frequency report to {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
