from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


TASK_ROOT = Path("/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot")
OUTPUT = TASK_ROOT / "outputs/paper_performance_report.md"


TRACKS = [
    {
        "name": "Original stable rules",
        "closed_trades": TASK_ROOT / "outputs/paper_stable_closed_trades.csv",
        "open_positions": TASK_ROOT / "outputs/paper_stable_open_positions.csv",
    },
    {
        "name": "Experimental pair candidates",
        "closed_trades": TASK_ROOT / "outputs/pair_candidate_closed_trades.csv",
        "open_positions": TASK_ROOT / "outputs/pair_candidate_open_positions.csv",
    },
    {
        "name": "Advanced sniper candidates",
        "closed_trades": TASK_ROOT / "outputs/advanced_sniper_closed_trades.csv",
        "open_positions": TASK_ROOT / "outputs/advanced_sniper_open_positions.csv",
    },
]


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def markdown_table(rows: list[dict[str, object]], columns: list[str], empty: str) -> str:
    if not rows:
        return empty
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(str(row.get(column, "")) for column in columns) + " |" for row in rows]
    return "\n".join([header, divider, *body])


def summarize_track(track: dict[str, object]) -> dict[str, object]:
    closed = load_csv(Path(track["closed_trades"]))
    open_positions = load_csv(Path(track["open_positions"]))
    if closed.empty or "paper_pnl" not in closed.columns:
        return {
            "track": track["name"],
            "closed_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": "0.0%",
            "closed_pnl": "0.00",
            "avg_win": "0.00",
            "avg_loss": "0.00",
            "worst_trade": "0.00",
            "open_positions": 0 if open_positions.empty else len(open_positions),
            "verdict": "NO EVIDENCE YET",
        }

    pnl = pd.to_numeric(closed["paper_pnl"], errors="coerce").fillna(0.0)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    closed_count = int(len(pnl))
    closed_pnl = float(pnl.sum())
    win_rate = len(wins) / closed_count if closed_count else 0.0
    avg_win = float(wins.mean()) if not wins.empty else 0.0
    avg_loss = float(losses.mean()) if not losses.empty else 0.0
    worst_trade = float(pnl.min()) if not pnl.empty else 0.0
    open_count = 0 if open_positions.empty else len(open_positions)

    if closed_pnl <= -60:
        verdict = "QUARANTINE"
    elif closed_count < 10:
        verdict = "NEEDS MORE PAPER TRADES"
    elif closed_pnl <= 0:
        verdict = "REJECT FOR NOW"
    elif open_count > 0:
        verdict = "WAIT FOR OPEN TRADE"
    else:
        verdict = "PROMISING, REVIEW MANUALLY"

    return {
        "track": track["name"],
        "closed_trades": closed_count,
        "wins": int(len(wins)),
        "losses": int(len(losses)),
        "win_rate": f"{win_rate:.1%}",
        "closed_pnl": f"{closed_pnl:.2f}",
        "avg_win": f"{avg_win:.2f}",
        "avg_loss": f"{avg_loss:.2f}",
        "worst_trade": f"{worst_trade:.2f}",
        "open_positions": open_count,
        "verdict": verdict,
    }


def recent_trades(track: dict[str, object], limit: int = 5) -> list[dict[str, object]]:
    closed = load_csv(Path(track["closed_trades"]))
    if closed.empty:
        return []
    columns = ["symbol", "timeframe", "side", "closed_at", "paper_pnl", "exit_reason"]
    rows = []
    for _, trade in closed.tail(limit).iterrows():
        rows.append(
            {
                "track": track["name"],
                "symbol": trade.get("symbol", ""),
                "timeframe": trade.get("timeframe", ""),
                "side": trade.get("side", ""),
                "closed_at": trade.get("closed_at", ""),
                "paper_pnl": f"{float(trade.get('paper_pnl', 0.0)):.2f}",
                "exit_reason": trade.get("exit_reason", ""),
            }
        )
    return rows


def main() -> int:
    summary_rows = [summarize_track(track) for track in TRACKS]
    trade_rows = []
    for track in TRACKS:
        trade_rows.extend(recent_trades(track))

    lines = [
        "# Paper Performance Report",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This report summarizes paper trades only. It is not live trading performance.",
        "",
        "## Scoreboard",
        "",
        markdown_table(
            summary_rows,
            [
                "track",
                "verdict",
                "closed_trades",
                "wins",
                "losses",
                "win_rate",
                "closed_pnl",
                "avg_win",
                "avg_loss",
                "worst_trade",
                "open_positions",
            ],
            "No paper performance data yet.",
        ),
        "",
        "## Recent Closed Paper Trades",
        "",
        markdown_table(
            trade_rows,
            ["track", "symbol", "timeframe", "side", "closed_at", "paper_pnl", "exit_reason"],
            "No closed paper trades yet.",
        ),
        "",
        "## Reading This",
        "",
        "- A track with negative closed PnL stays out of live trading.",
        "- A track with fewer than 10 closed paper trades is still too early to judge.",
        "- Average loss being much bigger than average win is a warning sign.",
        "- Open paper trades must close before any promotion decision.",
        "",
    ]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved paper performance report to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
