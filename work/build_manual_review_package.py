from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


TASK_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_MD = TASK_ROOT / "outputs/manual_review_package.md"
OUTPUT_CSV = TASK_ROOT / "outputs/manual_review_detail.csv"
REPORT_MD = TASK_ROOT / "reports/manual_review_package.md"


TRACKS = [
    {
        "name": "Experimental pair candidates",
        "closed_trades": TASK_ROOT / "outputs/pair_candidate_closed_trades.csv",
        "open_positions": TASK_ROOT / "outputs/pair_candidate_open_positions.csv",
        "status": TASK_ROOT / "outputs/pair_candidate_status.csv",
    },
    {
        "name": "Advanced sniper candidates",
        "closed_trades": TASK_ROOT / "outputs/advanced_sniper_closed_trades.csv",
        "open_positions": TASK_ROOT / "outputs/advanced_sniper_open_positions.csv",
        "status": TASK_ROOT / "outputs/advanced_sniper_status.csv",
    },
    {
        "name": "Boom/Crash expansion candidates",
        "closed_trades": TASK_ROOT / "outputs/boom_crash_expansion_closed_trades.csv",
        "open_positions": TASK_ROOT / "outputs/boom_crash_expansion_open_positions.csv",
        "status": TASK_ROOT / "outputs/boom_crash_expansion_status.csv",
    },
]


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def money(value: float) -> str:
    return f"{value:.2f}"


def pct(value: float) -> str:
    return f"{value:.1%}"


def markdown_table(rows: list[dict[str, object]], columns: list[str], empty: str) -> str:
    if not rows:
        return empty
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(str(row.get(column, "")) for column in columns) + " |" for row in rows]
    return "\n".join([header, divider, *body])


def extract_rule_id(reason: object) -> str:
    text = str(reason or "")
    match = re.search(r"\b(?:PAIR|SR|BCX)\d+\b", text)
    return match.group(0) if match else "unknown"


def max_consecutive(values: list[float], winning: bool) -> int:
    best = 0
    current = 0
    for value in values:
        is_match = value > 0 if winning else value < 0
        if is_match:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def max_drawdown(values: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    worst = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        worst = min(worst, equity - peak)
    return abs(worst)


def top_win_concentration(wins: pd.Series, total_pnl: float, top_n: int = 1) -> float:
    if wins.empty or total_pnl <= 0:
        return 0.0
    return float(wins.sort_values(ascending=False).head(top_n).sum() / total_pnl)


def review_decision(
    closed_count: int,
    total_pnl: float,
    win_rate: float,
    profit_factor: float,
    open_count: int,
    worst_trade: float,
    largest_win_share: float,
) -> tuple[str, str]:
    if open_count > 0:
        return "WAIT", "Open paper trades must close before review."
    if closed_count < 10:
        return "WAIT", "Needs at least 10 closed paper trades."
    if total_pnl <= 0:
        return "REJECT", "Closed paper PnL is not positive."
    if profit_factor < 1.25:
        return "REJECT", "Profit factor is too weak."
    if win_rate < 0.65:
        return "REJECT", "Win rate is below the current accuracy gate."
    if worst_trade <= -45:
        return "CAUTION", "Worst loss is large; reduce risk or improve exits before any pilot."
    if largest_win_share > 0.5:
        return "CAUTION", "Too much profit came from one trade."
    return "MANUAL REVIEW PASS", "Promising on paper; still not approved for real money."


def summarize_track(track: dict[str, object]) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    closed = load_csv(Path(track["closed_trades"]))
    open_positions = load_csv(Path(track["open_positions"]))
    open_count = 0 if open_positions.empty else len(open_positions)

    if closed.empty or "paper_pnl" not in closed.columns:
        summary = {
            "track": track["name"],
            "decision": "WAIT",
            "reason": "No closed paper-trade evidence yet.",
            "closed": 0,
            "pnl": "0.00",
            "wins": 0,
            "losses": 0,
            "win_rate": "0.0%",
            "profit_factor": "0.00",
            "expectancy": "0.00",
            "worst": "0.00",
            "best": "0.00",
            "largest_win_share": "0.0%",
            "max_loss_streak": 0,
            "paper_drawdown": "0.00",
            "open": open_count,
        }
        return summary, [], []

    closed = closed.copy()
    closed["paper_pnl"] = pd.to_numeric(closed["paper_pnl"], errors="coerce").fillna(0.0)
    closed["rule_id"] = closed.get("reason", "").apply(extract_rule_id)

    pnl = closed["paper_pnl"]
    values = [float(value) for value in pnl.tolist()]
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    total_pnl = float(pnl.sum())
    gross_profit = float(wins.sum()) if not wins.empty else 0.0
    gross_loss = abs(float(losses.sum())) if not losses.empty else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss else (float("inf") if gross_profit > 0 else 0.0)
    closed_count = int(len(closed))
    win_rate = len(wins) / closed_count if closed_count else 0.0
    largest_share = top_win_concentration(wins, total_pnl, 1)
    top3_share = top_win_concentration(wins, total_pnl, 3)
    worst = float(pnl.min()) if not pnl.empty else 0.0
    best = float(pnl.max()) if not pnl.empty else 0.0
    decision, reason = review_decision(
        closed_count=closed_count,
        total_pnl=total_pnl,
        win_rate=win_rate,
        profit_factor=profit_factor,
        open_count=open_count,
        worst_trade=worst,
        largest_win_share=largest_share,
    )

    summary = {
        "track": track["name"],
        "decision": decision,
        "reason": reason,
        "closed": closed_count,
        "pnl": money(total_pnl),
        "wins": int(len(wins)),
        "losses": int(len(losses)),
        "win_rate": pct(win_rate),
        "profit_factor": "inf" if profit_factor == float("inf") else f"{profit_factor:.2f}",
        "expectancy": money(float(pnl.mean()) if not pnl.empty else 0.0),
        "worst": money(worst),
        "best": money(best),
        "largest_win_share": pct(largest_share),
        "top3_win_share": pct(top3_share),
        "max_loss_streak": max_consecutive(values, winning=False),
        "max_win_streak": max_consecutive(values, winning=True),
        "paper_drawdown": money(max_drawdown(values)),
        "open": open_count,
    }

    rule_rows: list[dict[str, object]] = []
    for rule_id, group in closed.groupby("rule_id", dropna=False):
        rule_pnl = group["paper_pnl"]
        rule_wins = rule_pnl[rule_pnl > 0]
        rule_losses = rule_pnl[rule_pnl < 0]
        rule_count = int(len(group))
        rule_total = float(rule_pnl.sum())
        rule_rows.append(
            {
                "track": track["name"],
                "rule": rule_id,
                "closed": rule_count,
                "wins": int(len(rule_wins)),
                "losses": int(len(rule_losses)),
                "win_rate": pct(len(rule_wins) / rule_count if rule_count else 0.0),
                "pnl": money(rule_total),
                "avg": money(float(rule_pnl.mean()) if not rule_pnl.empty else 0.0),
                "worst": money(float(rule_pnl.min()) if not rule_pnl.empty else 0.0),
                "best": money(float(rule_pnl.max()) if not rule_pnl.empty else 0.0),
                "review_note": "needs more rule evidence" if rule_count < 10 else "enough rule sample",
            }
        )

    recent_rows: list[dict[str, object]] = []
    for _, trade in closed.tail(6).iterrows():
        recent_rows.append(
            {
                "track": track["name"],
                "rule": trade.get("rule_id", "unknown"),
                "symbol": trade.get("symbol", ""),
                "tf": trade.get("timeframe", ""),
                "closed_at": trade.get("closed_at", ""),
                "pnl": money(float(trade.get("paper_pnl", 0.0))),
                "exit": trade.get("exit_reason", ""),
            }
        )

    return summary, sorted(rule_rows, key=lambda row: float(row["pnl"]), reverse=True), recent_rows


def main() -> int:
    summaries: list[dict[str, object]] = []
    all_rules: list[dict[str, object]] = []
    all_recent: list[dict[str, object]] = []
    for track in TRACKS:
        summary, rules, recent = summarize_track(track)
        summaries.append(summary)
        all_rules.extend(rules)
        all_recent.extend(recent)

    detail = pd.DataFrame(all_rules)
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(OUTPUT_CSV, index=False)

    lines = [
        "# Manual Review Package",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This is the human review gate. It analyzes paper trades only and does not approve real-money trading.",
        "",
        "## Review Decision",
        "",
        markdown_table(
            summaries,
            [
                "track",
                "decision",
                "reason",
                "closed",
                "pnl",
                "wins",
                "losses",
                "win_rate",
                "profit_factor",
                "expectancy",
                "worst",
                "largest_win_share",
                "paper_drawdown",
                "open",
            ],
            "No tracks to review yet.",
        ),
        "",
        "## Rule Quality",
        "",
        markdown_table(
            all_rules,
            ["track", "rule", "closed", "wins", "losses", "win_rate", "pnl", "avg", "worst", "best", "review_note"],
            "No rule-level evidence yet.",
        ),
        "",
        "## Recent Closed Paper Trades",
        "",
        markdown_table(
            all_recent,
            ["track", "rule", "symbol", "tf", "closed_at", "pnl", "exit"],
            "No recent closed paper trades yet.",
        ),
        "",
        "## Manual Review Rules",
        "",
        "- Keep live trading blocked until this report, the live-readiness checklist, and human review all agree.",
        "- Prefer slow, high-quality setups over frequent trades.",
        "- Reject any track where one lucky win creates most of the profit.",
        "- Reject or reduce risk if average losses and worst losses are too large.",
        "- A rule with fewer than 10 closed paper trades is not proven by itself yet.",
        "",
        "## Tiny Pilot Plan",
        "",
        "Status: **DISABLED**",
        "",
        "Use this only after manual review is complete and the live-readiness checklist no longer says NOT READY.",
        "",
        "- Start with the smallest possible stake.",
        "- Trade only the reviewed track and rule set.",
        "- Stop immediately after one daily loss limit, one abnormal error, or unexpected order behavior.",
        "- Keep paper monitoring running beside any future live pilot.",
        "",
    ]

    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved manual review package to {OUTPUT_MD}")
    print(f"Saved manual review detail to {OUTPUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
