from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


TASK_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESEARCH_RULES = TASK_ROOT / "outputs/stable_rules_pair_promoted_research_rules.csv"
DEFAULT_BACKTEST_CANDIDATES = TASK_ROOT / "outputs/stable_rules_pair_backtest_rule_candidates.csv"
DEFAULT_WALK_FORWARD_RULES = TASK_ROOT / "outputs/stable_rules_pair_walk_forward_rule_summary.csv"
DEFAULT_OUTPUT = TASK_ROOT / "outputs/stable_rules_pair_execution_candidates.csv"
DEFAULT_REPORT = TASK_ROOT / "outputs/stable_rules_pair_validation_report.md"


def promote(args: argparse.Namespace) -> pd.DataFrame:
    research = pd.read_csv(args.research_rules_csv)
    backtest = pd.read_csv(args.backtest_candidates_csv)
    walk_forward = pd.read_csv(args.walk_forward_rule_summary_csv)

    backtest_ids = set(backtest["rule_id"].astype(str))
    walk_forward = walk_forward[
        (walk_forward["total_return"] > 0)
        & (walk_forward["profit_factor"] >= args.min_walk_forward_profit_factor)
        & (walk_forward["trades"] >= args.min_walk_forward_trades)
    ]
    walk_ids = set(walk_forward["rule_id"].astype(str))
    keep_ids = backtest_ids & walk_ids

    promoted = research[research["rule_id"].astype(str).isin(keep_ids)].copy()
    if promoted.empty:
        return promoted

    promoted = promoted.merge(
        backtest[
            [
                "rule_id",
                "trades",
                "total_return",
                "win_rate",
                "profit_factor",
                "expectancy",
                "max_drawdown",
            ]
        ].rename(
            columns={
                "trades": "backtest_trades",
                "total_return": "backtest_total_return",
                "win_rate": "backtest_win_rate",
                "profit_factor": "backtest_profit_factor",
                "expectancy": "backtest_expectancy",
                "max_drawdown": "backtest_max_drawdown",
            }
        ),
        on="rule_id",
        how="left",
    )
    promoted = promoted.merge(
        walk_forward[
            [
                "rule_id",
                "trades",
                "total_return",
                "win_rate",
                "profit_factor",
                "expectancy",
                "max_drawdown",
            ]
        ].rename(
            columns={
                "trades": "walk_forward_trades",
                "total_return": "walk_forward_total_return",
                "win_rate": "walk_forward_win_rate",
                "profit_factor": "walk_forward_profit_factor",
                "expectancy": "walk_forward_expectancy",
                "max_drawdown": "walk_forward_max_drawdown",
            }
        ),
        on="rule_id",
        how="left",
    )
    promoted = promoted.sort_values(
        ["symbol", "timeframe", "suggested_side", "walk_forward_profit_factor", "backtest_profit_factor"],
        ascending=[True, True, True, False, False],
    )
    promoted["symbol_rule_rank"] = promoted.groupby(["symbol", "timeframe", "suggested_side"]).cumcount() + 1
    promoted["promotion_status"] = "experimental_paper_candidate"
    return promoted


def write_execution_rules(promoted: pd.DataFrame, output: Path) -> pd.DataFrame:
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
    rules = promoted[columns].copy() if not promoted.empty else pd.DataFrame(columns=columns)
    output.parent.mkdir(parents=True, exist_ok=True)
    rules.to_csv(output, index=False)
    return rules


def markdown_table(df: pd.DataFrame, columns: list[str], empty_message: str, limit: int = 20) -> str:
    if df.empty:
        return empty_message
    view = df.head(limit)
    available = [column for column in columns if column in view.columns]
    view = view[available].fillna("").astype(str)
    header = "| " + " | ".join(available) + " |"
    divider = "| " + " | ".join("---" for _ in available) + " |"
    rows = ["| " + " | ".join(row) + " |" for row in view.to_numpy()]
    return "\n".join([header, divider, *rows])


def write_report(path: Path, promoted: pd.DataFrame, rules: pd.DataFrame) -> None:
    lines = [
        "# Stable Pair Validation Report",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Verdict: EXPERIMENTAL PAPER ONLY",
        "",
        "These rules passed the first backtest and walk-forward gates, but they are not live-trading rules yet.",
        "",
        f"- Promoted experimental paper rules: {len(rules)}",
        f"- Symbols: {0 if rules.empty else rules['symbol'].nunique()}",
        "",
        "## Experimental Paper Rules",
        "",
        markdown_table(
            promoted,
            [
                "rule_id",
                "symbol",
                "timeframe",
                "suggested_side",
                "feature",
                "condition",
                "backtest_trades",
                "backtest_profit_factor",
                "walk_forward_trades",
                "walk_forward_profit_factor",
            ],
            "No pair candidate survived both gates.",
        ),
        "",
        "## Decision",
        "",
        "- Use these only in a separate experimental paper monitor.",
        "- Do not mix them into the approved stable execution file yet.",
        "- Promote to the main paper set only after live paper journaling shows real closed-trade performance.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promote pair research candidates that passed backtest and walk-forward checks.")
    parser.add_argument("--research-rules-csv", default=str(DEFAULT_RESEARCH_RULES))
    parser.add_argument("--backtest-candidates-csv", default=str(DEFAULT_BACKTEST_CANDIDATES))
    parser.add_argument("--walk-forward-rule-summary-csv", default=str(DEFAULT_WALK_FORWARD_RULES))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT))
    parser.add_argument("--min-walk-forward-profit-factor", type=float, default=1.2)
    parser.add_argument("--min-walk-forward-trades", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    promoted = promote(args)
    output = Path(args.output)
    report = Path(args.report_output)
    rules = write_execution_rules(promoted, output)
    write_report(report, promoted, rules)
    print(f"Saved experimental pair execution candidates to {output}")
    print(f"Saved pair validation report to {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
