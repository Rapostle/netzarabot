from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


TASK_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = TASK_ROOT / "outputs"

SELF_HEAL_OUTPUT = OUTPUT_DIR / "self_healing_monitor_check.md"
EXPANSION_GUARD_OUTPUT = OUTPUT_DIR / "expansion_monitor_health_guard.md"
LEADERBOARD_OUTPUT = OUTPUT_DIR / "best_track_leaderboard.md"
REPLAY_OUTPUT = OUTPUT_DIR / "trade_replay_report.md"
KILL_SWITCH_OUTPUT = OUTPUT_DIR / "rule_kill_switch_report.md"
KILL_SWITCH_BLOCKLIST_OUTPUT = OUTPUT_DIR / "rule_kill_switch_blocklist.csv"
PROMOTION_QUEUE_OUTPUT = OUTPUT_DIR / "candidate_promotion_queue.md"
DAILY_OUTPUT = OUTPUT_DIR / "daily_summary_report.md"
SUMMARY_OUTPUT = OUTPUT_DIR / "supervision_tools_summary.md"

STALE_AFTER_MINUTES = 25.0

TRACKS = [
    {
        "name": "Original stable rules",
        "short": "original",
        "status": OUTPUT_DIR / "paper_stable_status.csv",
        "decisions": OUTPUT_DIR / "paper_stable_rules_decisions.csv",
        "open": OUTPUT_DIR / "paper_stable_open_positions.csv",
        "closed": OUTPUT_DIR / "paper_stable_closed_trades.csv",
        "loss_limit": -60.0,
        "can_promote": False,
    },
    {
        "name": "Experimental pair candidates",
        "short": "experimental",
        "status": OUTPUT_DIR / "pair_candidate_status.csv",
        "decisions": OUTPUT_DIR / "pair_candidate_paper_decisions.csv",
        "open": OUTPUT_DIR / "pair_candidate_open_positions.csv",
        "closed": OUTPUT_DIR / "pair_candidate_closed_trades.csv",
        "loss_limit": -60.0,
        "can_promote": True,
    },
    {
        "name": "Advanced sniper candidates",
        "short": "sniper",
        "status": OUTPUT_DIR / "advanced_sniper_status.csv",
        "decisions": OUTPUT_DIR / "advanced_sniper_paper_decisions.csv",
        "open": OUTPUT_DIR / "advanced_sniper_open_positions.csv",
        "closed": OUTPUT_DIR / "advanced_sniper_closed_trades.csv",
        "loss_limit": -60.0,
        "can_promote": True,
    },
    {
        "name": "Boom/Crash expansion candidates",
        "short": "expansion",
        "status": OUTPUT_DIR / "boom_crash_expansion_status.csv",
        "decisions": OUTPUT_DIR / "boom_crash_expansion_paper_decisions.csv",
        "open": OUTPUT_DIR / "boom_crash_expansion_open_positions.csv",
        "closed": OUTPUT_DIR / "boom_crash_expansion_closed_trades.csv",
        "loss_limit": -60.0,
        "can_promote": False,
    },
]


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def as_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def metric(df: pd.DataFrame, key: str, default: str = "0") -> str:
    if df.empty or "metric" not in df.columns or "value" not in df.columns:
        return default
    rows = df[df["metric"] == key]
    if rows.empty:
        return default
    return str(rows.iloc[-1]["value"])


def markdown_table(rows: list[dict[str, object]], columns: list[str], empty: str) -> str:
    if not rows:
        return empty
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(str(row.get(column, "")) for column in columns) + " |" for row in rows]
    return "\n".join([header, divider, *body])


def parse_utc(value: object) -> pd.Timestamp | None:
    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed


def age_minutes(value: object) -> float | None:
    parsed = parse_utc(value)
    if parsed is None:
        return None
    now = pd.Timestamp.now(tz="UTC")
    return max(0.0, (now - parsed).total_seconds() / 60.0)


def track_state(track: dict[str, object]) -> dict[str, object]:
    status = load_csv(Path(track["status"]))
    open_positions = load_csv(Path(track["open"]))
    closed = load_csv(Path(track["closed"]))
    decisions = load_csv(Path(track["decisions"]))
    closed_pnl = as_float(metric(status, "closed_pnl", "0"))
    closed_trades = as_int(metric(status, "closed_trades", str(len(closed))))
    open_count = as_int(metric(status, "open_positions", str(len(open_positions))))
    paper_orders = int((decisions.get("decision", pd.Series(dtype=str)) == "paper_order").sum()) if not decisions.empty else 0
    pnl_series = pd.to_numeric(closed.get("paper_pnl", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    wins = int((pnl_series > 0).sum())
    losses = int((pnl_series < 0).sum())
    win_rate = (wins / closed_trades * 100.0) if closed_trades else 0.0
    last_run = metric(status, "last_run_utc", "not run")
    age = age_minutes(last_run)
    return {
        "name": track["name"],
        "short": track["short"],
        "last_run_utc": last_run,
        "age_minutes": age,
        "latest_decisions": metric(status, "latest_decisions", "none"),
        "latest_paper_orders": as_int(metric(status, "latest_paper_orders", "0")),
        "latest_blocked_signals": as_int(metric(status, "latest_blocked_signals", "0")),
        "journal_rows": as_int(metric(status, "journal_rows", "0")),
        "paper_orders_seen": paper_orders,
        "open_positions": open_count,
        "closed_trades": closed_trades,
        "closed_pnl": closed_pnl,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "loss_limit": float(track["loss_limit"]),
        "can_promote": bool(track["can_promote"]),
        "missing_files": [
            str(path.relative_to(TASK_ROOT))
            for path in [Path(track["status"]), Path(track["decisions"]), Path(track["open"])]
            if not path.exists()
        ],
    }


def gate_decision(state: dict[str, object]) -> tuple[str, str]:
    if state["missing_files"]:
        return "CHECK FILES", "One or more tracking files are missing."
    if state["age_minutes"] is None:
        return "RESTART MONITOR", "This track has no valid last-run time."
    if float(state["age_minutes"]) > STALE_AFTER_MINUTES:
        return "RESTART MONITOR", "This track is stale."
    if float(state["closed_pnl"]) <= float(state["loss_limit"]):
        return "QUARANTINE", "Closed paper PnL has breached the loss limit."
    if int(state["open_positions"]) > 0:
        return "WAIT FOR CLOSE", "There is an open paper trade."
    if int(state["closed_trades"]) < 10:
        return "KEEP PAPER TESTING", "Sample size is still too small."
    if float(state["closed_pnl"]) <= 0:
        return "REJECT FOR NOW", "Closed paper PnL is not positive."
    if not state["can_promote"]:
        return "DO NOT PROMOTE", "This track is treated as legacy research only."
    return "MANUAL REVIEW", "Positive enough for human review, still not live-ready."


def write_self_healing(states: list[dict[str, object]]) -> None:
    rows = []
    for state in states:
        decision, reason = gate_decision(state)
        rows.append(
            {
                "track": state["name"],
                "health": decision,
                "why": reason,
                "age_min": "unknown" if state["age_minutes"] is None else f"{state['age_minutes']:.1f}",
                "open": state["open_positions"],
                "closed_pnl": f"{state['closed_pnl']:.2f}",
            }
        )
    lines = [
        "# Self-Healing Monitor Check",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This is the monitor's own health check. It does not place trades.",
        "",
        markdown_table(rows, ["track", "health", "why", "age_min", "open", "closed_pnl"], "No monitor tracks found."),
        "",
        "If any row says `RESTART MONITOR`, stop the old Terminal loop with Ctrl+C, then start it again with:",
        "",
        "`work/run_combined_paper_monitor.sh`",
        "",
    ]
    SELF_HEAL_OUTPUT.write_text("\n".join(lines), encoding="utf-8")


def write_leaderboard(states: list[dict[str, object]]) -> None:
    rows = []
    for state in states:
        decision, _ = gate_decision(state)
        score = float(state["closed_pnl"]) + int(state["closed_trades"]) * 2.0 - int(state["open_positions"]) * 10.0
        if "QUARANTINE" in decision or "REJECT" in decision:
            score -= 500.0
        rows.append(
            {
                "track": state["name"],
                "rank_score": f"{score:.2f}",
                "status": decision,
                "closed_pnl": f"{state['closed_pnl']:.2f}",
                "closed": state["closed_trades"],
                "wins": state["wins"],
                "losses": state["losses"],
                "win_rate": f"{state['win_rate']:.1f}%",
            }
        )
    rows.sort(key=lambda row: as_float(row["rank_score"]), reverse=True)
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    lines = [
        "# Best Track Leaderboard",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This ranks the current paper tracks. It is paper-only and should not be treated as live approval.",
        "",
        markdown_table(rows, ["rank", "track", "status", "closed_pnl", "closed", "wins", "losses", "win_rate"], "No tracks found."),
        "",
    ]
    LEADERBOARD_OUTPUT.write_text("\n".join(lines), encoding="utf-8")


def clean_rule_id(reason: object) -> str:
    text = str(reason)
    match = re.search(r"\b(SR\d+|PAIR\d+|BCX\d+)\b", text)
    if match:
        return match.group(1)
    return "unknown_rule"


def trade_r_multiple(row: pd.Series) -> float:
    pnl = as_float(row.get("paper_pnl", 0.0))
    risk = abs(as_float(row.get("risk_amount", 0.0)))
    if risk <= 0:
        return 0.0
    return pnl / risk


def write_trade_replay() -> None:
    rows = []
    for track in TRACKS:
        closed = load_csv(Path(track["closed"]))
        if closed.empty:
            continue
        for _, trade in closed.tail(8).iterrows():
            pnl = as_float(trade.get("paper_pnl", 0.0))
            verdict = "helped the account" if pnl > 0 else "hurt the account" if pnl < 0 else "flat"
            rows.append(
                {
                    "track": track["name"],
                    "closed_at": trade.get("closed_at", ""),
                    "symbol": trade.get("symbol", ""),
                    "side": trade.get("side", ""),
                    "rule": clean_rule_id(trade.get("reason", "")),
                    "entry": f"{as_float(trade.get('entry', 0.0)):.3f}",
                    "exit": f"{as_float(trade.get('exit_price', 0.0)):.3f}",
                    "pnl": f"{pnl:.2f}",
                    "r": f"{trade_r_multiple(trade):.2f}R",
                    "read": f"{trade.get('exit_reason', '')}; {verdict}",
                }
            )
    rows.sort(key=lambda row: str(row.get("closed_at", "")), reverse=True)
    rows = rows[:20]
    lines = [
        "# Trade Replay Report",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This replays recent closed paper trades in plain language.",
        "",
        markdown_table(rows, ["track", "closed_at", "symbol", "side", "rule", "entry", "exit", "pnl", "r", "read"], "No closed paper trades found."),
        "",
    ]
    REPLAY_OUTPUT.write_text("\n".join(lines), encoding="utf-8")


def write_kill_switch() -> None:
    trade_rows = []
    for track in TRACKS:
        closed = load_csv(Path(track["closed"]))
        if closed.empty:
            continue
        closed = closed.copy()
        closed["track"] = str(track["name"])
        closed["rule_id"] = closed["reason"].map(clean_rule_id) if "reason" in closed else "unknown_rule"
        closed["pnl_num"] = pd.to_numeric(closed.get("paper_pnl", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
        trade_rows.append(closed)
    if trade_rows:
        all_trades = pd.concat(trade_rows, ignore_index=True)
    else:
        all_trades = pd.DataFrame()

    rows = []
    if not all_trades.empty:
        for (track, rule_id), group in all_trades.groupby(["track", "rule_id"], dropna=False):
            pnl = group["pnl_num"]
            losses = int((pnl < 0).sum())
            wins = int((pnl > 0).sum())
            total = float(pnl.sum())
            avg = float(pnl.mean())
            trades = int(len(group))
            win_rate = wins / trades if trades else 0.0
            stop_losses = 0
            if "exit_reason" in group.columns:
                stop_losses = int(group["exit_reason"].astype(str).str.contains("stop", case=False, na=False).sum())
            recent = group.tail(3)
            recent_pnl = recent["pnl_num"]
            recent_losses = int((recent_pnl < 0).sum())
            recent_stop_losses = 0
            if "exit_reason" in recent.columns:
                recent_stop_losses = int(recent["exit_reason"].astype(str).str.contains("stop", case=False, na=False).sum())

            if trades >= 3 and (total < 0 or win_rate < 0.60 or losses >= 2):
                action = "KILL NOW"
                reason = "Strict accuracy gate: enough paper evidence and rule is hurting quality."
            elif trades >= 2 and (total <= 0 or win_rate < 0.70 or losses >= 2):
                action = "FREEZE"
                reason = "Strict accuracy gate: rule is below 70% paper win rate or not net-positive."
            elif trades >= 2 and recent_losses >= 1 and win_rate < 0.80:
                action = "FREEZE"
                reason = "Strict accuracy gate: recent loss and below 80% target accuracy."
            elif stop_losses >= 1 and trades >= 2 and win_rate < 0.80:
                action = "FREEZE"
                reason = "Strict accuracy gate: stop-loss pattern below 80% target accuracy."
            elif recent_stop_losses >= 1:
                action = "WATCH"
                reason = "Recent stop loss; keep watching before allowing promotion."
            elif total < 0:
                action = "WATCH"
                reason = "Negative, but sample is still small."
            else:
                action = "KEEP PAPER"
                reason = "No kill signal yet."
            rows.append(
                {
                    "track": track,
                    "rule": rule_id,
                    "action": action,
                    "trades": trades,
                    "wins": wins,
                    "losses": losses,
                    "win_rate": f"{win_rate:.1%}",
                    "stop_losses": stop_losses,
                    "pnl": f"{total:.2f}",
                    "avg": f"{avg:.2f}",
                    "why": reason,
                }
            )
    order = {"KILL NOW": 0, "FREEZE": 1, "WATCH": 2, "KEEP PAPER": 3}
    rows.sort(key=lambda row: (order.get(str(row["action"]), 9), as_float(row["pnl"])))
    blocklist = [row for row in rows if row["action"] in {"KILL NOW", "FREEZE"} and row["rule"] != "unknown_rule"]
    pd.DataFrame(
        blocklist,
        columns=["track", "rule", "action", "trades", "wins", "losses", "win_rate", "stop_losses", "pnl", "avg", "why"],
    ).to_csv(
        KILL_SWITCH_BLOCKLIST_OUTPUT,
        index=False,
    )
    lines = [
        "# Rule Kill-Switch Report",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This recommends which paper rules should be frozen or killed. The matching blocklist is used by paper monitoring.",
        "",
        "Strict mode is active: paper rules below 70% win rate, net-negative rules, and rules with weak stop-loss patterns are blocked from new entries.",
        "",
        markdown_table(
            rows,
            ["track", "rule", "action", "trades", "wins", "losses", "win_rate", "stop_losses", "pnl", "avg", "why"],
            "No closed paper trades found.",
        ),
        "",
        f"Machine-readable blocklist: `{KILL_SWITCH_BLOCKLIST_OUTPUT}`",
        "",
    ]
    KILL_SWITCH_OUTPUT.write_text("\n".join(lines), encoding="utf-8")


def candidate_rows_from(path: Path, source: str, limit: int = 12) -> list[dict[str, object]]:
    df = load_csv(path)
    if df.empty:
        return []
    for column in ["profit_factor", "total_return", "expectancy", "trades", "win_rate"]:
        if column in df:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    sort_cols = [column for column in ["profit_factor", "total_return", "expectancy"] if column in df]
    if sort_cols:
        df = df.sort_values(sort_cols, ascending=False)
    rows = []
    for _, row in df.head(limit).iterrows():
        rows.append(
            {
                "source": source,
                "rule": row.get("rule_id", ""),
                "symbol": row.get("symbol", ""),
                "tf": row.get("timeframe", ""),
                "side": row.get("suggested_side", ""),
                "trades": as_int(row.get("trades", 0)),
                "win_rate": f"{as_float(row.get('win_rate', 0.0)) * 100.0:.1f}%" if as_float(row.get("win_rate", 0.0)) <= 1.0 else f"{as_float(row.get('win_rate', 0.0)):.1f}%",
                "pf": f"{as_float(row.get('profit_factor', 0.0)):.2f}",
                "next_step": "paper test separately",
            }
        )
    return rows


def write_promotion_queue(states: list[dict[str, object]]) -> None:
    track_rows = []
    for state in states:
        decision, reason = gate_decision(state)
        track_rows.append(
            {
                "candidate": state["name"],
                "queue_status": decision,
                "closed": state["closed_trades"],
                "closed_pnl": f"{state['closed_pnl']:.2f}",
                "next_step": reason,
            }
        )
    research_rows = []
    research_rows.extend(candidate_rows_from(OUTPUT_DIR / "advanced_accuracy_execution_candidates.csv", "advanced sniper"))
    research_rows.extend(candidate_rows_from(OUTPUT_DIR / "boom_crash_expansion_execution_candidates.csv", "Boom/Crash expansion"))
    lines = [
        "# Candidate Promotion Queue",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Nothing here is live-approved. This only organizes what should be watched next.",
        "",
        "## Paper Tracks",
        "",
        markdown_table(track_rows, ["candidate", "queue_status", "closed", "closed_pnl", "next_step"], "No paper tracks found."),
        "",
        "## Research Candidates Waiting For Paper Testing",
        "",
        markdown_table(research_rows, ["source", "rule", "symbol", "tf", "side", "trades", "win_rate", "pf", "next_step"], "No research candidates found."),
        "",
    ]
    PROMOTION_QUEUE_OUTPUT.write_text("\n".join(lines), encoding="utf-8")


def write_expansion_guard(states: list[dict[str, object]]) -> None:
    expansion = load_csv(OUTPUT_DIR / "boom_crash_expansion_execution_candidates.csv")
    open_total = sum(int(state["open_positions"]) for state in states)
    stale_tracks = [state["name"] for state in states if state["age_minutes"] is None or float(state["age_minutes"]) > STALE_AFTER_MINUTES]
    original = next((state for state in states if state["name"] == "Original stable rules"), None)
    original_quarantined = bool(original and float(original["closed_pnl"]) <= float(original["loss_limit"]))
    ready = not expansion.empty and open_total == 0 and not stale_tracks and original_quarantined
    rows = [
        {"check": "Expansion candidates exist", "result": "yes" if not expansion.empty else "no"},
        {"check": "No open current paper trades", "result": "yes" if open_total == 0 else f"no, {open_total} open"},
        {"check": "Current monitor is fresh", "result": "yes" if not stale_tracks else ", ".join(stale_tracks)},
        {"check": "Losing original rules quarantined", "result": "yes" if original_quarantined else "no"},
    ]
    lines = [
        "# Expansion Monitor Health Guard",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This decides whether it is sensible to start a separate expansion paper monitor.",
        "",
        markdown_table(rows, ["check", "result"], "No checks found."),
        "",
        f"Decision: {'READY FOR SEPARATE EXPANSION PAPER TEST' if ready else 'WAIT'}",
        "",
        "Important: expansion testing must use separate ledgers so it does not mix with the current paper results.",
        "",
    ]
    EXPANSION_GUARD_OUTPUT.write_text("\n".join(lines), encoding="utf-8")


def write_daily_summary(states: list[dict[str, object]]) -> None:
    now = pd.Timestamp.now(tz="UTC")
    cutoff = now - pd.Timedelta(hours=24)
    rows = []
    for track in TRACKS:
        closed = load_csv(Path(track["closed"]))
        if closed.empty or "closed_at" not in closed:
            rows.append(
                {
                    "track": track["name"],
                    "closed_24h": 0,
                    "wins_24h": 0,
                    "losses_24h": 0,
                    "pnl_24h": "0.00",
                    "current_open": next((s["open_positions"] for s in states if s["name"] == track["name"]), 0),
                }
            )
            continue
        closed = closed.copy()
        closed["closed_at_dt"] = pd.to_datetime(closed["closed_at"], utc=True, errors="coerce")
        closed["pnl_num"] = pd.to_numeric(closed.get("paper_pnl", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
        recent = closed[closed["closed_at_dt"] >= cutoff]
        pnl = recent["pnl_num"] if not recent.empty else pd.Series(dtype=float)
        rows.append(
            {
                "track": track["name"],
                "closed_24h": len(recent),
                "wins_24h": int((pnl > 0).sum()),
                "losses_24h": int((pnl < 0).sum()),
                "pnl_24h": f"{float(pnl.sum()) if not pnl.empty else 0.0:.2f}",
                "current_open": next((s["open_positions"] for s in states if s["name"] == track["name"]), 0),
            }
        )
    lines = [
        "# Daily Summary Report",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This summarizes paper activity from the last 24 hours.",
        "",
        markdown_table(rows, ["track", "closed_24h", "wins_24h", "losses_24h", "pnl_24h", "current_open"], "No daily data found."),
        "",
    ]
    DAILY_OUTPUT.write_text("\n".join(lines), encoding="utf-8")


def write_summary(states: list[dict[str, object]]) -> None:
    actions = []
    for state in states:
        decision, reason = gate_decision(state)
        actions.append(f"- {state['name']}: {decision} ({reason})")
    lines = [
        "# Supervision Tools Summary",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Built the eight supervision tools:",
        "",
        "- Self-healing monitor check: `outputs/self_healing_monitor_check.md`",
        "- One-click status command: `work/check_bot_status.sh`",
        "- Expansion monitor health guard: `outputs/expansion_monitor_health_guard.md`",
        "- Best track leaderboard: `outputs/best_track_leaderboard.md`",
        "- Trade replay report: `outputs/trade_replay_report.md`",
        "- Rule kill-switch report: `outputs/rule_kill_switch_report.md`",
        "- Rule kill-switch blocklist: `outputs/rule_kill_switch_blocklist.csv`",
        "- Candidate promotion queue: `outputs/candidate_promotion_queue.md`",
        "- Daily summary report: `outputs/daily_summary_report.md`",
        "",
        "Current action read:",
        "",
        *actions,
        "",
        "This is still paper monitoring only. No live trades are approved.",
        "",
    ]
    SUMMARY_OUTPUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    states = [track_state(track) for track in TRACKS]
    write_self_healing(states)
    write_expansion_guard(states)
    write_leaderboard(states)
    write_trade_replay()
    write_kill_switch()
    write_promotion_queue(states)
    write_daily_summary(states)
    write_summary(states)
    print(f"Saved self-healing monitor check to {SELF_HEAL_OUTPUT}")
    print(f"Saved expansion monitor health guard to {EXPANSION_GUARD_OUTPUT}")
    print(f"Saved best track leaderboard to {LEADERBOARD_OUTPUT}")
    print(f"Saved trade replay report to {REPLAY_OUTPUT}")
    print(f"Saved rule kill-switch report to {KILL_SWITCH_OUTPUT}")
    print(f"Saved candidate promotion queue to {PROMOTION_QUEUE_OUTPUT}")
    print(f"Saved daily summary report to {DAILY_OUTPUT}")
    print(f"Saved supervision tools summary to {SUMMARY_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
