from __future__ import annotations
import os

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


BOT_ROOT = Path(os.environ.get("TRADING_BOT_ROOT", str(Path(__file__).resolve().parent.parent / "external" / "trading_bot")))
TASK_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = BOT_ROOT / "data"
DEFAULT_CANDIDATES = TASK_ROOT / "outputs/boom_crash_expansion_candidates.csv"
DEFAULT_DETAIL = TASK_ROOT / "outputs/boom_crash_expansion_gate_detail.csv"
DEFAULT_SUMMARY = TASK_ROOT / "outputs/boom_crash_expansion_gate_summary.csv"
DEFAULT_APPROVED = TASK_ROOT / "outputs/boom_crash_expansion_approved_candidates.csv"
DEFAULT_EXECUTION = TASK_ROOT / "outputs/boom_crash_expansion_execution_candidates.csv"
DEFAULT_REPORT = TASK_ROOT / "outputs/boom_crash_expansion_report.md"

sys.path.insert(0, str(BOT_ROOT))
sys.path.insert(0, str(TASK_ROOT / "work"))
from trading_bot.research.signal_discovery import DiscoveryConfig, discover_pair_edges  # noqa: E402
import advanced_accuracy_lab as sniper  # noqa: E402


def markdown_table(rows: list[dict[str, object]], columns: list[str], empty: str) -> str:
    if not rows:
        return empty
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(str(row.get(column, "")) for column in columns) + " |" for row in rows]
    return "\n".join([header, divider, *body])


def parse_symbol_timeframe(path: Path) -> tuple[str, str] | None:
    stem = path.stem
    if not stem.startswith("deriv_"):
        return None
    body = stem.removeprefix("deriv_")
    for timeframe in ("1m", "5m", "15m", "30m"):
        suffix = f"_{timeframe}"
        if body.endswith(suffix):
            return body[: -len(suffix)], timeframe
    return None


def discover_files(data_dir: Path, timeframes: set[str], symbols: set[str]) -> list[tuple[str, str, Path]]:
    rows = []
    for path in sorted(data_dir.glob("deriv_*_*.csv")):
        parsed = parse_symbol_timeframe(path)
        if not parsed:
            continue
        symbol, timeframe = parsed
        upper = symbol.upper()
        if "BOOM" not in upper and "CRASH" not in upper:
            continue
        if timeframe not in timeframes:
            continue
        if symbols and symbol not in symbols:
            continue
        rows.append((symbol, timeframe, path))
    return rows


def timeframe_horizon(timeframe: str) -> int:
    return {
        "1m": 20,
        "5m": 16,
        "15m": 12,
        "30m": 8,
    }.get(timeframe, 12)


def mine_file(
    symbol: str,
    timeframe: str,
    path: Path,
    max_rows: int,
    min_samples: int,
    min_profit_factor: float,
    top_per_side: int,
) -> pd.DataFrame:
    df = sniper.load_indicated(path, max_rows=max_rows)
    if df.empty:
        return pd.DataFrame()
    config = DiscoveryConfig(horizon=timeframe_horizon(timeframe), min_samples=min_samples, min_abs_return=0.0005)
    edges = discover_pair_edges(df, config)
    if edges.empty:
        return pd.DataFrame()
    edges = edges[edges["suggested_side"].isin(["buy", "sell"])].copy()
    edges = edges[pd.to_numeric(edges["profit_factor"], errors="coerce").fillna(0.0) >= min_profit_factor]
    if edges.empty:
        return pd.DataFrame()
    win_col = edges.apply(
        lambda row: row["buy_win_rate"] if row["suggested_side"] == "buy" else row["sell_win_rate"],
        axis=1,
    )
    edges["win_rate"] = win_col
    edges["symbol"] = symbol
    edges["timeframe"] = timeframe
    edges["trades"] = edges["samples"].astype(int)
    edges["total_return"] = edges["expectancy"] * edges["trades"]
    edges = edges.sort_values(["suggested_side", "profit_factor", "expectancy", "samples"], ascending=[True, False, False, False])
    edges = edges.groupby("suggested_side", as_index=False, group_keys=False).head(top_per_side)
    return edges[
        [
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
        ]
    ]


def build_rule_candidates(args: argparse.Namespace) -> pd.DataFrame:
    data_dir = Path(args.data_dir)
    timeframes = {item.strip() for item in args.timeframe if item.strip()}
    symbols = {item.strip() for item in args.symbol if item.strip()}
    parts = []
    files = discover_files(data_dir, timeframes, symbols)
    for symbol, timeframe, path in files:
        print(f"Mining {symbol} {timeframe}: {path}", flush=True)
        mined = mine_file(
            symbol=symbol,
            timeframe=timeframe,
            path=path,
            max_rows=args.max_rows,
            min_samples=args.min_samples,
            min_profit_factor=args.min_profit_factor,
            top_per_side=args.top_per_side,
        )
        if not mined.empty:
            parts.append(mined)

    if not parts:
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

    candidates = pd.concat(parts, ignore_index=True)
    candidates = candidates.sort_values(
        ["symbol", "timeframe", "suggested_side", "profit_factor", "expectancy"],
        ascending=[True, True, True, False, False],
    )
    candidates["symbol_rule_rank"] = candidates.groupby(["symbol", "timeframe", "suggested_side"]).cumcount() + 1
    candidates["rule_id"] = [f"BCX{idx:04d}" for idx in range(1, len(candidates) + 1)]
    candidates["promotion_status"] = "boom_crash_expansion_research"
    return candidates[
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
        ]
    ]


def evaluate_candidates(candidates: pd.DataFrame, data_dir: Path, max_rows: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    detail_parts = []
    summaries = []
    for _, rule in candidates.iterrows():
        detail, summary = sniper.evaluate_rule(rule, data_dir, max_rows=max_rows)
        if not detail.empty:
            detail_parts.append(detail)
        summaries.append(summary)
    detail = pd.concat(detail_parts, ignore_index=True) if detail_parts else pd.DataFrame()
    summary = pd.DataFrame(summaries)
    approved = summary[summary.get("verdict", "") == "APPROVED_RESEARCH"].copy() if not summary.empty else pd.DataFrame()
    execution = sniper.execution_candidates(approved)
    if not execution.empty:
        execution["promotion_status"] = "boom_crash_expansion_sniper_candidate"
    return detail, summary, approved, execution


def write_report(path: Path, candidates: pd.DataFrame, summary: pd.DataFrame, approved: pd.DataFrame, execution: pd.DataFrame) -> None:
    if summary.empty:
        top_rows = []
    else:
        top_rows = (
            summary.sort_values(
                ["verdict", "walk_forward_pass", "approved_profit_factor", "approved_expectancy", "approved_matches"],
                ascending=[True, False, False, False, False],
            )
            .head(20)
            .to_dict("records")
        )

    symbol_rows = []
    if not approved.empty:
        grouped = approved.groupby(["symbol", "timeframe"], as_index=False).agg(
            approved_rules=("rule_id", "count"),
            best_profit_factor=("approved_profit_factor", "max"),
            avg_score=("avg_sniper_score", "mean"),
            best_return=("approved_return", "max"),
        )
        grouped = grouped.sort_values(["approved_rules", "best_profit_factor", "best_return"], ascending=False)
        for _, row in grouped.iterrows():
            symbol_rows.append(
                {
                    "symbol": row["symbol"],
                    "timeframe": row["timeframe"],
                    "approved_rules": int(row["approved_rules"]),
                    "best_profit_factor": f"{float(row['best_profit_factor']):.2f}",
                    "avg_score": f"{float(row['avg_score']):.1f}",
                    "best_return": f"{float(row['best_return']):.4f}",
                }
            )

    lines = [
        "# Boom/Crash Expansion Lab",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This is a separate research scan. It does not touch current paper trades and does not place live trades.",
        "",
        "## Expansion Summary",
        "",
        f"- Raw expansion candidates mined: {len(candidates)}",
        f"- Sniper-approved research candidates: {len(approved)}",
        f"- Execution candidate rows written: {len(execution)}",
        "",
        "## Strongest Symbols / Timeframes",
        "",
        markdown_table(
            symbol_rows,
            ["symbol", "timeframe", "approved_rules", "best_profit_factor", "avg_score", "best_return"],
            "No symbol/timeframe passed the expansion sniper gate.",
        ),
        "",
        "## Top Approved / Near-Approved Rules",
        "",
        markdown_table(
            top_rows,
            [
                "rule_id",
                "symbol",
                "timeframe",
                "side",
                "verdict",
                "approved_matches",
                "avg_sniper_score",
                "approved_win_rate",
                "approved_return",
                "approved_profit_factor",
                "walk_forward_test_return",
                "walk_forward_test_pf",
                "best_exit_mode",
            ],
            "No rules evaluated.",
        ),
        "",
        "## What To Do With This",
        "",
        "- Keep these separate from the current paper tracks.",
        "- Only paper-test expansion candidates after the current open paper trades close, or in a separate ledger.",
        "- Do not promote any expansion candidate to live trading yet.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mine and score Boom/Crash expansion candidates.")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--timeframe", action="append", default=["1m", "5m", "15m", "30m"])
    parser.add_argument("--symbol", action="append", default=[])
    parser.add_argument("--max-rows", type=int, default=2500)
    parser.add_argument("--min-samples", type=int, default=25)
    parser.add_argument("--min-profit-factor", type=float, default=1.4)
    parser.add_argument("--top-per-side", type=int, default=3)
    parser.add_argument("--candidates-output", default=str(DEFAULT_CANDIDATES))
    parser.add_argument("--detail-output", default=str(DEFAULT_DETAIL))
    parser.add_argument("--summary-output", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--approved-output", default=str(DEFAULT_APPROVED))
    parser.add_argument("--execution-output", default=str(DEFAULT_EXECUTION))
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    candidates = build_rule_candidates(args)
    detail, summary, approved, execution = evaluate_candidates(candidates, Path(args.data_dir), max_rows=args.max_rows)

    outputs = [
        (Path(args.candidates_output), candidates),
        (Path(args.detail_output), detail),
        (Path(args.summary_output), summary),
        (Path(args.approved_output), approved),
        (Path(args.execution_output), execution),
    ]
    for output, frame in outputs:
        output.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(output, index=False)

    write_report(Path(args.report_output), candidates, summary, approved, execution)
    print(f"Saved expansion candidates to {args.candidates_output}")
    print(f"Saved expansion gate detail to {args.detail_output}")
    print(f"Saved expansion gate summary to {args.summary_output}")
    print(f"Saved expansion approved candidates to {args.approved_output}")
    print(f"Saved expansion execution candidates to {args.execution_output}")
    print(f"Saved expansion report to {args.report_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
