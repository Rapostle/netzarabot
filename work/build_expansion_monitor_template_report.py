from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


TASK_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = TASK_ROOT / "outputs/boom_crash_expansion_monitor_template.md"
RULES = TASK_ROOT / "outputs/boom_crash_expansion_execution_candidates.csv"


def load_rules() -> pd.DataFrame:
    if not RULES.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(RULES)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def markdown_table(rows: list[dict[str, object]], columns: list[str], empty: str) -> str:
    if not rows:
        return empty
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(str(row.get(column, "")) for column in columns) + " |" for row in rows]
    return "\n".join([header, divider, *body])


def main() -> int:
    rules = load_rules()
    if rules.empty:
        symbol_rows = []
        total_rules = 0
    else:
        total_rules = len(rules)
        grouped = rules.groupby(["symbol", "timeframe"], as_index=False).agg(
            rules=("rule_id", "count"),
            best_profit_factor=("profit_factor", "max"),
            best_return=("total_return", "max"),
        )
        grouped = grouped.sort_values(["rules", "best_profit_factor", "best_return"], ascending=False).head(20)
        symbol_rows = [
            {
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "rules": int(row["rules"]),
                "best_profit_factor": f"{float(row['best_profit_factor']):.2f}",
                "best_return": f"{float(row['best_return']):.4f}",
            }
            for _, row in grouped.iterrows()
        ]

    lines = [
        "# Boom/Crash Expansion Paper Monitor Template",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Status: PREPARED, NOT RUNNING.",
        "",
        "This template is ready for later. It is intentionally separate from the active paper tracks.",
        "",
        "## Prepared Runners",
        "",
        "- One-time local check: `work/run_boom_crash_expansion_paper_local.sh`",
        "- One-time fresh-data check: `work/run_boom_crash_expansion_paper_refresh.sh`",
        "- Repeating monitor: `work/run_boom_crash_expansion_paper_monitor.sh`",
        "",
        "## Separate Output Files",
        "",
        "- Decisions: `outputs/boom_crash_expansion_paper_decisions.csv`",
        "- Journal: `outputs/boom_crash_expansion_paper_journal.csv`",
        "- Open positions: `outputs/boom_crash_expansion_open_positions.csv`",
        "- Closed trades: `outputs/boom_crash_expansion_closed_trades.csv`",
        "- Dashboard: `outputs/boom_crash_expansion_dashboard.md`",
        "- Readiness: `outputs/boom_crash_expansion_go_live_readiness.md`",
        "",
        "## Candidate Pool",
        "",
        f"- Expansion rules prepared: {total_rules}",
        "",
        markdown_table(
            symbol_rows,
            ["symbol", "timeframe", "rules", "best_profit_factor", "best_return"],
            "No expansion candidates found yet.",
        ),
        "",
        "## When To Start It",
        "",
        "- Start only after the current experimental and advanced sniper paper trades close, or when you deliberately want a separate expansion test.",
        "- Do not add these expansion candidates to the active combined monitor yet.",
        "- Do not use these for live trading. They need their own paper results first.",
        "",
        "## What To Paste Later",
        "",
        "From the project folder, run:",
        "",
        "```bash",
        "work/run_boom_crash_expansion_paper_monitor.sh",
        "```",
        "",
    ]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved expansion monitor template report to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
