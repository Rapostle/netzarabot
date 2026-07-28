from __future__ import annotations
import os

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


BOT_ROOT = Path(os.environ.get("TRADING_BOT_ROOT", str(Path(__file__).resolve().parent.parent / "external" / "trading_bot")))
TASK_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_APPROVED_RULES = TASK_ROOT / "outputs/crash_boom_execution_approved_stable_rules_15m_30m.csv"
DEFAULT_DATA_DIR = TASK_ROOT / "outputs/paper_refreshed_data"
DEFAULT_CANDIDATES = TASK_ROOT / "outputs/stable_rules_pair_research_candidates.csv"
DEFAULT_RULES = TASK_ROOT / "outputs/stable_rules_pair_promoted_research_rules.csv"
DEFAULT_REPORT = TASK_ROOT / "outputs/stable_rules_pair_research_report.md"

sys.path.insert(0, str(BOT_ROOT))

from trading_bot.data.loader import load_ohlcv_csv  # noqa: E402
from trading_bot.indicators.technical import add_indicators  # noqa: E402
from trading_bot.research.signal_discovery import DiscoveryConfig, discover_pair_edges  # noqa: E402


def safe_symbol_filename(symbol: str) -> str:
    return "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in symbol)


def data_path(data_dir: Path, symbol: str, timeframe: str) -> Path:
    return data_dir / f"deriv_{safe_symbol_filename(symbol)}_{timeframe}.csv"


def mine_candidates(args: argparse.Namespace) -> pd.DataFrame:
    approved = pd.read_csv(args.approved_rules_csv)
    existing = set(zip(approved["symbol"], approved["timeframe"], approved["suggested_side"], approved["feature"], approved["condition"]))
    rows = []
    cfg = DiscoveryConfig(horizon=args.horizon, min_samples=args.min_samples, min_abs_return=args.min_abs_return)

    for symbol, timeframe in approved[["symbol", "timeframe"]].drop_duplicates().itertuples(index=False):
        path = data_path(Path(args.data_dir), str(symbol), str(timeframe))
        if not path.exists():
            continue
        df = add_indicators(load_ohlcv_csv(path)).tail(args.max_rows)
        if len(df) < 260:
            continue

        edges = discover_pair_edges(df, cfg)
        if edges.empty:
            continue
        edges = edges[edges["suggested_side"].isin(["buy", "sell"])].copy()
        edges = edges[
            (edges["samples"] >= args.min_samples)
            & (edges["profit_factor"] >= args.min_profit_factor)
            & (edges["expectancy"] > args.min_expectancy)
        ]
        if edges.empty:
            continue
        edges["symbol"] = symbol
        edges["timeframe"] = timeframe
        edges["total_return"] = edges["expectancy"] * edges["samples"]
        edges["win_rate"] = edges.apply(
            lambda row: row["buy_win_rate"] if row["suggested_side"] == "buy" else row["sell_win_rate"],
            axis=1,
        )
        edges = edges[
            ~edges.apply(
                lambda row: (row["symbol"], row["timeframe"], row["suggested_side"], row["feature"], row["condition"]) in existing,
                axis=1,
            )
        ]
        edges = edges.sort_values(["profit_factor", "expectancy", "samples"], ascending=False)
        edges = edges.groupby(["symbol", "timeframe", "suggested_side"], group_keys=False).head(args.top_per_side)
        rows.extend(edges.to_dict("records"))

    candidates = pd.DataFrame(rows)
    if candidates.empty:
        return pd.DataFrame(
            columns=[
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
            ]
        )

    candidates = candidates.sort_values(["symbol", "timeframe", "suggested_side", "profit_factor", "expectancy"], ascending=[True, True, True, False, False])
    candidates["trades"] = candidates["samples"].astype(int)
    candidates["symbol_rule_rank"] = candidates.groupby(["symbol", "timeframe", "suggested_side"]).cumcount() + 1
    candidates["rule_id"] = [f"PAIR{idx:03d}" for idx in range(1, len(candidates) + 1)]
    candidates["promotion_status"] = "research_pair"
    return candidates


def write_rules(candidates: pd.DataFrame, output: Path) -> pd.DataFrame:
    columns = [
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
    ]
    rules = candidates[columns].copy() if not candidates.empty else pd.DataFrame(columns=columns)
    output.parent.mkdir(parents=True, exist_ok=True)
    rules.to_csv(output, index=False)
    return rules


def markdown_table(df: pd.DataFrame, columns: list[str], empty_message: str, limit: int = 12) -> str:
    if df.empty:
        return empty_message
    view = df.head(limit)
    available = [column for column in columns if column in view.columns]
    view = view[available].fillna("").astype(str)
    header = "| " + " | ".join(available) + " |"
    divider = "| " + " | ".join("---" for _ in available) + " |"
    rows = ["| " + " | ".join(row) + " |" for row in view.to_numpy()]
    return "\n".join([header, divider, *rows])


def write_report(path: Path, candidates: pd.DataFrame, rules: pd.DataFrame) -> None:
    lines = [
        "# Stable Pair Research Candidates",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "These are research-only two-condition rules mined from current paper data. They still require simulator validation.",
        "",
        f"- Raw candidates: {len(candidates)}",
        f"- Backtest-ready rules: {len(rules)}",
        "",
        "## Top Candidates",
        "",
        markdown_table(
            candidates.sort_values(["profit_factor", "expectancy", "trades"], ascending=False) if not candidates.empty else candidates,
            ["rule_id", "symbol", "timeframe", "suggested_side", "feature", "condition", "trades", "win_rate", "profit_factor", "expectancy"],
            "No pair candidates passed the research floor.",
        ),
        "",
        "## Required Next Step",
        "",
        "Run the promoted-rule backtest and walk-forward checks before adding any candidate to paper trading.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mine two-condition stable-rule research candidates.")
    parser.add_argument("--approved-rules-csv", default=str(DEFAULT_APPROVED_RULES))
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--candidates-output", default=str(DEFAULT_CANDIDATES))
    parser.add_argument("--rules-output", default=str(DEFAULT_RULES))
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT))
    parser.add_argument("--max-rows", type=int, default=5000)
    parser.add_argument("--horizon", type=int, default=12)
    parser.add_argument("--min-samples", type=int, default=30)
    parser.add_argument("--min-abs-return", type=float, default=0.001)
    parser.add_argument("--min-profit-factor", type=float, default=1.35)
    parser.add_argument("--min-expectancy", type=float, default=0.0005)
    parser.add_argument("--top-per-side", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    candidates = mine_candidates(args)
    candidates_path = Path(args.candidates_output)
    rules_path = Path(args.rules_output)
    report_path = Path(args.report_output)

    candidates_path.parent.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(candidates_path, index=False)
    rules = write_rules(candidates, rules_path)
    write_report(report_path, candidates, rules)

    print(f"Saved pair candidates to {candidates_path}")
    print(f"Saved pair research rules to {rules_path}")
    print(f"Saved pair research report to {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
