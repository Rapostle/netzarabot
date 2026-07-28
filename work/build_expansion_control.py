from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


TASK_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = TASK_ROOT / "outputs"

EXPANSION_DASHBOARD = OUTPUT_DIR / "expansion_control_dashboard.html"
OPEN_WATCHDOG = OUTPUT_DIR / "open_trade_watchdog.md"
EXPANSION_KILL_SWITCH = OUTPUT_DIR / "expansion_kill_switch.md"
EXPANSION_BLOCKLIST = OUTPUT_DIR / "expansion_kill_switch_blocklist.csv"
RULE_SCORECARD = OUTPUT_DIR / "rule_scorecard.md"
TRADE_AGING = OUTPUT_DIR / "trade_aging_protection.md"
RISK_PROFILES = OUTPUT_DIR / "family_risk_profiles.md"
AUTO_DAILY = OUTPUT_DIR / "auto_daily_report.md"
LIVE_CHECKLIST = OUTPUT_DIR / "live_readiness_checklist.md"
PROTECTION_REPORT = OUTPUT_DIR / "paper_protection_bundle_report.md"
PROMOTION_PACK = OUTPUT_DIR / "promotion_pack.md"
PILOT_PACKAGE = OUTPUT_DIR / "pilot_readiness_package.md"
SUMMARY = OUTPUT_DIR / "expansion_control_summary.md"

ALL_BLOCKLIST = OUTPUT_DIR / "rule_kill_switch_blocklist.csv"


TRACKS = [
    {
        "name": "Original stable rules",
        "family": "Boom/Crash baseline",
        "status": OUTPUT_DIR / "paper_stable_status.csv",
        "open": OUTPUT_DIR / "paper_stable_open_positions.csv",
        "closed": OUTPUT_DIR / "paper_stable_closed_trades.csv",
        "journal": OUTPUT_DIR / "paper_stable_rules_journal.csv",
        "data_dir": OUTPUT_DIR / "paper_refreshed_data",
        "can_live": False,
    },
    {
        "name": "Experimental pair candidates",
        "family": "Boom/Crash pair",
        "status": OUTPUT_DIR / "pair_candidate_status.csv",
        "open": OUTPUT_DIR / "pair_candidate_open_positions.csv",
        "closed": OUTPUT_DIR / "pair_candidate_closed_trades.csv",
        "journal": OUTPUT_DIR / "pair_candidate_paper_journal.csv",
        "data_dir": OUTPUT_DIR / "pair_candidate_refreshed_data",
        "can_live": False,
    },
    {
        "name": "Advanced sniper candidates",
        "family": "Boom/Crash sniper",
        "status": OUTPUT_DIR / "advanced_sniper_status.csv",
        "open": OUTPUT_DIR / "advanced_sniper_open_positions.csv",
        "closed": OUTPUT_DIR / "advanced_sniper_closed_trades.csv",
        "journal": OUTPUT_DIR / "advanced_sniper_paper_journal.csv",
        "data_dir": OUTPUT_DIR / "pair_candidate_refreshed_data",
        "can_live": False,
    },
    {
        "name": "Boom/Crash expansion candidates",
        "family": "Boom/Crash expansion",
        "status": OUTPUT_DIR / "boom_crash_expansion_status.csv",
        "open": OUTPUT_DIR / "boom_crash_expansion_open_positions.csv",
        "closed": OUTPUT_DIR / "boom_crash_expansion_closed_trades.csv",
        "journal": OUTPUT_DIR / "boom_crash_expansion_paper_journal.csv",
        "data_dir": OUTPUT_DIR / "boom_crash_expansion_refreshed_data",
        "can_live": False,
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


def metric(status: pd.DataFrame, key: str, default: str = "0") -> str:
    if status.empty or "metric" not in status.columns or "value" not in status.columns:
        return default
    rows = status[status["metric"] == key]
    if rows.empty:
        return default
    return str(rows.iloc[-1]["value"])


def md_table(rows: list[dict[str, object]], columns: list[str], empty: str) -> str:
    if not rows:
        return empty
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(str(row.get(column, "")) for column in columns) + " |" for row in rows]
    return "\n".join([header, divider, *body])


def html_escape(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def rule_id(reason: object) -> str:
    match = re.search(r"\b(SR\d+|PAIR\d+|BCX\d+)\b", str(reason))
    return match.group(1) if match else "unknown_rule"


def safe_symbol(symbol: str) -> str:
    return "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in str(symbol))


def candle_path(track: dict[str, object], symbol: str, timeframe: str) -> Path:
    return Path(track["data_dir"]) / f"deriv_{safe_symbol(symbol)}_{timeframe}.csv"


def latest_price(track: dict[str, object], symbol: str, timeframe: str) -> tuple[float | None, pd.Timestamp | None]:
    df = load_csv(candle_path(track, symbol, timeframe))
    if df.empty or "close" not in df:
        return None, None
    timestamp = pd.to_datetime(df.iloc[-1].get("timestamp", ""), utc=True, errors="coerce")
    if pd.isna(timestamp):
        timestamp = None
    return as_float(df.iloc[-1]["close"], None), timestamp


def track_state(track: dict[str, object]) -> dict[str, object]:
    status = load_csv(Path(track["status"]))
    closed = load_csv(Path(track["closed"]))
    open_positions = load_csv(Path(track["open"]))
    journal = load_csv(Path(track["journal"]))
    pnl = pd.to_numeric(closed.get("paper_pnl", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    wins = int((pnl > 0).sum())
    losses = int((pnl < 0).sum())
    closed_count = as_int(metric(status, "closed_trades", str(len(closed))))
    return {
        "track": track["name"],
        "family": track["family"],
        "last_run": metric(status, "last_run_utc", "not run"),
        "latest_orders": as_int(metric(status, "latest_paper_orders", "0")),
        "blocked": as_int(metric(status, "latest_blocked_signals", "0")),
        "journal_rows": as_int(metric(status, "journal_rows", str(len(journal)))),
        "open": as_int(metric(status, "open_positions", str(len(open_positions)))),
        "closed": closed_count,
        "closed_pnl": as_float(metric(status, "closed_pnl", str(float(pnl.sum()) if not pnl.empty else 0.0))),
        "wins": wins,
        "losses": losses,
        "win_rate": wins / closed_count * 100.0 if closed_count else 0.0,
    }


def open_trade_rows() -> list[dict[str, object]]:
    rows = []
    now = pd.Timestamp.now(tz="UTC")
    for track in TRACKS:
        open_positions = load_csv(Path(track["open"]))
        if open_positions.empty:
            continue
        for _, row in open_positions.iterrows():
            symbol = str(row.get("symbol", ""))
            timeframe = str(row.get("timeframe", ""))
            side = str(row.get("side", ""))
            entry = as_float(row.get("entry", 0.0))
            stop = as_float(row.get("stop_loss", 0.0))
            target = as_float(row.get("take_profit", 0.0))
            opened_at = pd.to_datetime(row.get("opened_at", ""), utc=True, errors="coerce")
            age_hours = 0.0 if pd.isna(opened_at) else max((now - opened_at).total_seconds() / 3600.0, 0.0)
            price, candle_time = latest_price(track, symbol, timeframe)
            price_value = price if price is not None else entry
            risk = abs(entry - stop)
            if risk > 0:
                if side == "buy":
                    progress_r = (price_value - entry) / risk
                    stop_gap_r = (price_value - stop) / risk
                    target_gap_r = (target - price_value) / risk
                else:
                    progress_r = (entry - price_value) / risk
                    stop_gap_r = (stop - price_value) / risk
                    target_gap_r = (price_value - target) / risk
            else:
                progress_r = stop_gap_r = target_gap_r = 0.0

            timeframe_minutes = timeframe_to_minutes(timeframe)
            age_candles = age_hours * 60.0 / timeframe_minutes if timeframe_minutes else 0.0
            if progress_r <= -0.75:
                health = "near stop"
            elif progress_r >= 0.75:
                health = "moving well"
            elif age_candles >= 12 and progress_r < 0.25:
                health = "stuck"
            else:
                health = "watch"

            rows.append(
                {
                    "track": track["name"],
                    "id": row.get("paper_order_id", ""),
                    "symbol": symbol,
                    "tf": timeframe,
                    "side": side,
                    "rule": rule_id(row.get("reason", "")),
                    "entry": f"{entry:.5f}",
                    "latest": "missing" if price is None else f"{price:.5f}",
                    "progress_r": f"{progress_r:.2f}",
                    "stop_gap_r": f"{stop_gap_r:.2f}",
                    "target_gap_r": f"{target_gap_r:.2f}",
                    "age_candles": f"{age_candles:.1f}",
                    "health": health,
                    "candle_time": "" if candle_time is None else candle_time.isoformat(),
                }
            )
    return rows


def timeframe_to_minutes(label: str) -> float:
    label = str(label).strip().lower()
    if label.endswith("m"):
        return max(as_float(label[:-1], 1.0), 1.0)
    if label.endswith("h"):
        return max(as_float(label[:-1], 1.0) * 60.0, 1.0)
    return 15.0


def write_expansion_dashboard(states: list[dict[str, object]], open_rows: list[dict[str, object]]) -> None:
    cards = []
    for state in states:
        status = "active" if int(state["open"]) else "waiting"
        if state["track"] == "Original stable rules" and float(state["closed_pnl"]) < -60:
            status = "danger"
        cards.append(
            f"""
            <section class="card {status}">
              <h2>{html_escape(state['track'])}</h2>
              <div class="metrics">
                <div><strong>{state['open']}</strong><small>Open</small></div>
                <div><strong>{state['closed']}</strong><small>Closed</small></div>
                <div><strong>{state['closed_pnl']:.2f}</strong><small>Closed PnL</small></div>
                <div><strong>{state['win_rate']:.1f}%</strong><small>Win rate</small></div>
              </div>
              <p>Last run: {html_escape(state['last_run'])}</p>
            </section>
            """
        )
    trade_rows = "".join(
        f"<tr><td>{html_escape(row['track'])}</td><td>{html_escape(row['symbol'])}</td><td>{html_escape(row['tf'])}</td><td>{html_escape(row['side'])}</td><td>{html_escape(row['rule'])}</td><td>{html_escape(row['progress_r'])}</td><td>{html_escape(row['health'])}</td></tr>"
        for row in open_rows
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="60">
  <title>Expansion Control Dashboard</title>
  <style>
    :root {{ --bg:#f7f8fb; --panel:#fff; --ink:#162033; --muted:#667085; --line:#d8dee8; --ok:#075985; --warn:#92400e; --bad:#991b1b; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:var(--bg); color:var(--ink); }}
    main {{ width:min(1200px,calc(100% - 28px)); margin:0 auto; padding:28px 0; }}
    h1 {{ margin:0 0 6px; font-size:30px; }}
    p {{ color:var(--muted); }}
    .banner {{ border:1px solid var(--bad); color:var(--bad); background:#fee2e2; border-radius:8px; padding:12px; font-weight:800; margin:16px 0; }}
    .grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }}
    .card {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:14px; }}
    .card h2 {{ margin:0 0 12px; font-size:17px; }}
    .active {{ border-color:var(--ok); }}
    .danger {{ border-color:var(--bad); }}
    .metrics {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; }}
    .metrics div {{ border:1px solid var(--line); border-radius:8px; padding:8px; }}
    strong {{ display:block; font-size:21px; }}
    small {{ color:var(--muted); }}
    table {{ width:100%; border-collapse:collapse; background:var(--panel); border:1px solid var(--line); border-radius:8px; overflow:hidden; margin-top:16px; }}
    th,td {{ text-align:left; border-bottom:1px solid var(--line); padding:9px; font-size:14px; }}
    th {{ background:#edf1f7; }}
    @media(max-width:950px) {{ .grid {{ grid-template-columns:1fr; }} table {{ display:block; overflow-x:auto; }} }}
  </style>
</head>
<body>
  <main>
    <h1>Expansion Control Dashboard</h1>
    <p>Updated {html_escape(datetime.now(timezone.utc).isoformat())}. Paper monitoring only.</p>
    <div class="banner">No live trading yet. Open paper trades must close and pass readiness first.</div>
    <div class="grid">{''.join(cards)}</div>
    <h2>Open Paper Trades</h2>
    <table>
      <thead><tr><th>Track</th><th>Symbol</th><th>TF</th><th>Side</th><th>Rule</th><th>Progress R</th><th>Health</th></tr></thead>
      <tbody>{trade_rows or '<tr><td colspan="7">No open paper trades.</td></tr>'}</tbody>
    </table>
  </main>
</body>
</html>
"""
    EXPANSION_DASHBOARD.write_text(html, encoding="utf-8")


def write_open_watchdog(open_rows: list[dict[str, object]]) -> None:
    lines = [
        "# Open Trade Watchdog",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This watches open paper trades for progress toward target, stop pressure, and stuck behavior.",
        "",
        md_table(
            open_rows,
            ["track", "id", "symbol", "tf", "side", "rule", "entry", "latest", "progress_r", "stop_gap_r", "target_gap_r", "age_candles", "health"],
            "No open paper trades.",
        ),
        "",
        "Paper action rule: only force-close in research if a trade stays `stuck` for many cycles or moves near stop repeatedly.",
        "",
    ]
    OPEN_WATCHDOG.write_text("\n".join(lines), encoding="utf-8")


def write_expansion_kill_switch() -> None:
    closed = load_csv(OUTPUT_DIR / "boom_crash_expansion_closed_trades.csv")
    rows = []
    if not closed.empty and "paper_pnl" in closed:
        closed = closed.copy()
        closed["rule"] = closed["reason"].map(rule_id) if "reason" in closed else "unknown_rule"
        closed["pnl"] = pd.to_numeric(closed["paper_pnl"], errors="coerce").fillna(0.0)
        for rule, group in closed.groupby("rule"):
            pnl = group["pnl"]
            wins = int((pnl > 0).sum())
            losses = int((pnl < 0).sum())
            total = float(pnl.sum())
            if len(group) >= 3 and total < -30:
                action = "KILL NOW"
            elif losses >= 2 and wins == 0:
                action = "FREEZE"
            elif total < 0:
                action = "WATCH"
            else:
                action = "KEEP PAPER"
            rows.append(
                {
                    "track": "Boom/Crash expansion candidates",
                    "rule": rule,
                    "action": action,
                    "trades": len(group),
                    "wins": wins,
                    "losses": losses,
                    "pnl": f"{total:.2f}",
                    "avg": f"{float(pnl.mean()):.2f}",
                }
            )
    blocklist = [row for row in rows if row["action"] in {"KILL NOW", "FREEZE"} and row["rule"] != "unknown_rule"]
    pd.DataFrame(blocklist, columns=["track", "rule", "action", "trades", "wins", "losses", "pnl", "avg"]).to_csv(
        EXPANSION_BLOCKLIST,
        index=False,
    )
    merge_blocklists()
    lines = [
        "# Expansion Kill-Switch",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This is the BCX-specific kill-switch for Boom/Crash expansion rules.",
        "",
        md_table(rows, ["rule", "action", "trades", "wins", "losses", "pnl", "avg"], "No closed expansion trades yet. Waiting for paper trades to close."),
        "",
        f"Machine-readable expansion blocklist: `{EXPANSION_BLOCKLIST}`",
        "",
    ]
    EXPANSION_KILL_SWITCH.write_text("\n".join(lines), encoding="utf-8")


def merge_blocklists() -> None:
    base = load_csv(ALL_BLOCKLIST)
    expansion = load_csv(EXPANSION_BLOCKLIST)
    frames = [df for df in [base, expansion] if not df.empty]
    if not frames:
        return
    merged = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["track", "rule", "action"], keep="last")
    merged.to_csv(ALL_BLOCKLIST, index=False)


def write_rule_scorecard() -> None:
    rows = []
    for track in TRACKS:
        closed = load_csv(Path(track["closed"]))
        journal = load_csv(Path(track["journal"]))
        opened = pd.DataFrame()
        if not journal.empty and "decision" in journal:
            opened = journal[journal["decision"] == "paper_order"].copy()
            opened["rule"] = opened["reason"].map(rule_id) if "reason" in opened else "unknown_rule"
        if not closed.empty and "paper_pnl" in closed:
            closed = closed.copy()
            closed["rule"] = closed["reason"].map(rule_id) if "reason" in closed else "unknown_rule"
            closed["pnl"] = pd.to_numeric(closed["paper_pnl"], errors="coerce").fillna(0.0)
            for rule, group in closed.groupby("rule"):
                pnl = group["pnl"]
                wins = pnl[pnl > 0].sum()
                losses = abs(pnl[pnl < 0].sum())
                pf = float("inf") if losses == 0 and wins > 0 else (float(wins / losses) if losses > 0 else 0.0)
                rows.append(
                    {
                        "track": track["name"],
                        "rule": rule,
                        "opens": int((opened["rule"] == rule).sum()) if not opened.empty else len(group),
                        "closed": len(group),
                        "wins": int((pnl > 0).sum()),
                        "losses": int((pnl < 0).sum()),
                        "pnl": f"{float(pnl.sum()):.2f}",
                        "avg_r": f"{avg_r(group):.2f}",
                        "profit_factor": "inf" if math.isinf(pf) else f"{pf:.2f}",
                    }
                )
        elif not opened.empty:
            for rule, group in opened.groupby("rule"):
                rows.append(
                    {
                        "track": track["name"],
                        "rule": rule,
                        "opens": len(group),
                        "closed": 0,
                        "wins": 0,
                        "losses": 0,
                        "pnl": "0.00",
                        "avg_r": "0.00",
                        "profit_factor": "0.00",
                    }
                )
    rows.sort(key=lambda row: (as_float(row["pnl"]), as_int(row["closed"])), reverse=True)
    lines = [
        "# Rule Scorecard",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This ranks rules by actual paper behavior, not only backtests.",
        "",
        md_table(rows, ["track", "rule", "opens", "closed", "wins", "losses", "pnl", "avg_r", "profit_factor"], "No rule activity yet."),
        "",
    ]
    RULE_SCORECARD.write_text("\n".join(lines), encoding="utf-8")


def avg_r(group: pd.DataFrame) -> float:
    if group.empty:
        return 0.0
    pnl = pd.to_numeric(group.get("paper_pnl", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    risk = pd.to_numeric(group.get("risk_amount", pd.Series(dtype=float)), errors="coerce").abs().replace(0, pd.NA)
    r = (pnl / risk).dropna()
    return float(r.mean()) if not r.empty else 0.0


def write_trade_aging(open_rows: list[dict[str, object]]) -> None:
    rows = []
    for row in open_rows:
        age = as_float(row["age_candles"])
        progress = as_float(row["progress_r"])
        if age >= 16 and progress < 0.25:
            action = "paper force-close review"
        elif age >= 10 and progress < 0:
            action = "tight watch"
        elif progress <= -0.75:
            action = "near stop"
        else:
            action = "normal watch"
        rows.append({**row, "aging_action": action})
    lines = [
        "# Trade Aging / Stuck Trade Protection",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This flags paper trades that are taking too long or failing to move.",
        "",
        md_table(rows, ["track", "id", "symbol", "tf", "side", "rule", "progress_r", "age_candles", "health", "aging_action"], "No open paper trades."),
        "",
    ]
    TRADE_AGING.write_text("\n".join(lines), encoding="utf-8")


def write_risk_profiles() -> None:
    rows = [
        {"family": "Boom/Crash 1m", "paper_risk": "0.15%-0.25%", "max_open": 1, "time_stop": "8 candles", "notes": "Fastest and noisiest. Require spike and spread guard."},
        {"family": "Boom/Crash 5m", "paper_risk": "0.25%-0.40%", "max_open": 2, "time_stop": "10 candles", "notes": "Good for expansion, but kill losers quickly."},
        {"family": "Boom/Crash 15m", "paper_risk": "0.30%-0.50%", "max_open": 2, "time_stop": "12 candles", "notes": "Current main testing zone."},
        {"family": "Boom/Crash 30m", "paper_risk": "0.30%-0.50%", "max_open": 2, "time_stop": "10 candles", "notes": "Needs patience but avoid stale trades."},
        {"family": "Volatility indices", "paper_risk": "0.20%-0.35%", "max_open": 1, "time_stop": "12 candles", "notes": "Separate profile; do not share Boom/Crash rules blindly."},
        {"family": "Forex", "paper_risk": "0.25%-0.50%", "max_open": 2, "time_stop": "session-based", "notes": "Needs session, spread, and news filters."},
        {"family": "Crypto", "paper_risk": "0.15%-0.30%", "max_open": 1, "time_stop": "volatility-based", "notes": "Use wider volatility guard and weekend rules."},
    ]
    lines = [
        "# Family-Specific Risk Profiles",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "These are paper risk profiles. They are not live-money settings yet.",
        "",
        md_table(rows, ["family", "paper_risk", "max_open", "time_stop", "notes"], "No profiles."),
        "",
    ]
    RISK_PROFILES.write_text("\n".join(lines), encoding="utf-8")


def write_auto_daily(states: list[dict[str, object]], open_rows: list[dict[str, object]]) -> None:
    rows = []
    for track in TRACKS:
        closed = load_csv(Path(track["closed"]))
        cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=24)
        if not closed.empty and "closed_at" in closed:
            closed = closed.copy()
            closed["closed_at_dt"] = pd.to_datetime(closed["closed_at"], utc=True, errors="coerce")
            closed["pnl"] = pd.to_numeric(closed.get("paper_pnl", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
            recent = closed[closed["closed_at_dt"] >= cutoff]
            pnl = recent["pnl"]
        else:
            recent = pd.DataFrame()
            pnl = pd.Series(dtype=float)
        state = next((item for item in states if item["track"] == track["name"]), {})
        rows.append(
            {
                "track": track["name"],
                "closed_24h": len(recent),
                "wins_24h": int((pnl > 0).sum()),
                "losses_24h": int((pnl < 0).sum()),
                "pnl_24h": f"{float(pnl.sum()) if not pnl.empty else 0.0:.2f}",
                "open_now": state.get("open", 0),
            }
        )
    lines = [
        "# Auto Daily Report",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Daily Paper Summary",
        "",
        md_table(rows, ["track", "closed_24h", "wins_24h", "losses_24h", "pnl_24h", "open_now"], "No daily rows."),
        "",
        "## Open Trade Notes",
        "",
        md_table(open_rows, ["track", "symbol", "tf", "side", "rule", "progress_r", "health"], "No open paper trades."),
        "",
        "## Decision",
        "",
        "Keep paper monitoring. No track is live-ready.",
        "",
    ]
    AUTO_DAILY.write_text("\n".join(lines), encoding="utf-8")


def write_live_checklist(states: list[dict[str, object]]) -> None:
    rows = []
    for state in states:
        checks = [
            ("at least 30 monitor runs", int(state["journal_rows"]) >= 30),
            ("at least 10 closed trades", int(state["closed"]) >= 10),
            ("positive closed PnL", float(state["closed_pnl"]) > 0),
            ("no open trades", int(state["open"]) == 0),
            ("not quarantined", not (state["track"] == "Original stable rules" and float(state["closed_pnl"]) <= -60)),
            ("manual review still required", False),
        ]
        passed = sum(1 for _, ok in checks if ok)
        rows.append(
            {
                "track": state["track"],
                "passed": f"{passed}/{len(checks)}",
                "live_status": "NOT READY",
                "missing": ", ".join(label for label, ok in checks if not ok),
            }
        )
    lines = [
        "# Live-Readiness Checklist",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This is the final gate. It intentionally blocks live trading until the paper evidence is strong.",
        "",
        md_table(rows, ["track", "passed", "live_status", "missing"], "No tracks found."),
        "",
        "Hard rule: no real Deriv token and no real-money trading until this checklist stops saying `NOT READY` and a manual review is done.",
        "",
    ]
    LIVE_CHECKLIST.write_text("\n".join(lines), encoding="utf-8")


def write_protection_report(open_rows: list[dict[str, object]]) -> None:
    rows = [
        {"guard": "Emergency paper stop enforcer", "status": "active", "what_it_does": "Closes paper trades when latest candles breach stop or take-profit."},
        {"guard": "Duplicate trade guard", "status": "active", "what_it_does": "Blocks another open paper trade on the same symbol/timeframe."},
        {"guard": "Max open trades limit", "status": "active", "what_it_does": "Caps each paper track at 4 open positions by default."},
        {"guard": "Rule cooldown", "status": "active", "what_it_does": "Blocks a rule after recent closed losses."},
        {"guard": "Instrument exposure guard", "status": "active", "what_it_does": "Limits stacked Boom/Crash exposure in the same direction."},
        {"guard": "Fresh candle guard", "status": "active", "what_it_does": "Blocks entries when local candle data is too stale."},
        {"guard": "Paper slippage/spread simulation", "status": "active", "what_it_does": "Charges paper exits a small cost so results are less optimistic."},
        {"guard": "Promotion pack generator", "status": "active", "what_it_does": "Builds a paper-evidence package for promising rules."},
    ]
    alert_rows = []
    for row in open_rows:
        if row.get("health") in {"near stop", "stuck"}:
            alert_rows.append(
                {
                    "symbol": row["symbol"],
                    "tf": row["tf"],
                    "rule": row["rule"],
                    "health": row["health"],
                    "progress_r": row["progress_r"],
                    "action": "watch next cycle; emergency enforcer should close if stop is confirmed",
                }
            )
    lines = [
        "# Paper Protection Bundle Report",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "These protections run before new paper entries are added or when open paper positions are updated.",
        "",
        md_table(rows, ["guard", "status", "what_it_does"], "No guards found."),
        "",
        "## Current Protection Alerts",
        "",
        md_table(alert_rows, ["symbol", "tf", "rule", "health", "progress_r", "action"], "No current protection alerts."),
        "",
    ]
    PROTECTION_REPORT.write_text("\n".join(lines), encoding="utf-8")


def write_promotion_pack() -> None:
    scorecard = []
    for track in TRACKS:
        closed = load_csv(Path(track["closed"]))
        if closed.empty or "paper_pnl" not in closed:
            continue
        closed = closed.copy()
        closed["rule"] = closed["reason"].map(rule_id) if "reason" in closed else "unknown_rule"
        closed["pnl"] = pd.to_numeric(closed["paper_pnl"], errors="coerce").fillna(0.0)
        for rule, group in closed.groupby("rule"):
            pnl = group["pnl"]
            wins = int((pnl > 0).sum())
            losses = int((pnl < 0).sum())
            total = float(pnl.sum())
            candidate = len(group) >= 10 and total > 0 and losses <= wins
            scorecard.append(
                {
                    "track": track["name"],
                    "rule": rule,
                    "closed": len(group),
                    "wins": wins,
                    "losses": losses,
                    "pnl": f"{total:.2f}",
                    "promotion_status": "candidate" if candidate else "not enough paper evidence",
                }
            )
    scorecard.sort(key=lambda row: (row["promotion_status"] == "candidate", as_float(row["pnl"]), as_int(row["closed"])), reverse=True)
    lines = [
        "# Promotion Pack Generator",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This package is for deciding what deserves more testing. It does not approve live trading.",
        "",
        md_table(scorecard, ["track", "rule", "closed", "wins", "losses", "pnl", "promotion_status"], "No closed paper trades yet."),
        "",
        "Promotion rule: a rule needs at least 10 closed paper trades, positive PnL, acceptable losses, no open positions, and manual review.",
        "",
    ]
    PROMOTION_PACK.write_text("\n".join(lines), encoding="utf-8")


def write_pilot_package(states: list[dict[str, object]]) -> None:
    rows = []
    for state in states:
        blockers = []
        if int(state["closed"]) < 10:
            blockers.append("needs 10+ closed paper trades")
        if float(state["closed_pnl"]) <= 0:
            blockers.append("needs positive closed paper PnL")
        if int(state["open"]) > 0:
            blockers.append("open paper trades must close")
        if state["track"] == "Original stable rules" and float(state["closed_pnl"]) <= -60:
            blockers.append("track is quarantined")
        blockers.append("manual review required")
        rows.append(
            {
                "track": state["track"],
                "pilot_status": "NOT READY",
                "closed": state["closed"],
                "closed_pnl": f"{state['closed_pnl']:.2f}",
                "open": state["open"],
                "blockers": ", ".join(blockers),
            }
        )
    lines = [
        "# Pilot Readiness Package",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This is the final packaging step before even considering a tiny live pilot.",
        "",
        md_table(rows, ["track", "pilot_status", "closed", "closed_pnl", "open", "blockers"], "No tracks found."),
        "",
        "No live pilot is allowed while any row says `NOT READY`.",
        "",
    ]
    PILOT_PACKAGE.write_text("\n".join(lines), encoding="utf-8")


def write_summary() -> None:
    lines = [
        "# Expansion Control Summary",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Built 8 control layers:",
        "",
        "- Expansion control dashboard: `outputs/expansion_control_dashboard.html`",
        "- Open trade watchdog: `outputs/open_trade_watchdog.md`",
        "- Expansion kill-switch: `outputs/expansion_kill_switch.md`",
        "- Rule scorecard: `outputs/rule_scorecard.md`",
        "- Trade aging protection: `outputs/trade_aging_protection.md`",
        "- Family risk profiles: `outputs/family_risk_profiles.md`",
        "- Auto daily report: `outputs/auto_daily_report.md`",
        "- Live-readiness checklist: `outputs/live_readiness_checklist.md`",
        "- Paper protection bundle report: `outputs/paper_protection_bundle_report.md`",
        "- Promotion pack generator: `outputs/promotion_pack.md`",
        "- Pilot readiness package: `outputs/pilot_readiness_package.md`",
        "",
        "All are paper/research only.",
        "",
    ]
    SUMMARY.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    states = [track_state(track) for track in TRACKS]
    open_rows = open_trade_rows()
    write_expansion_dashboard(states, open_rows)
    write_open_watchdog(open_rows)
    write_expansion_kill_switch()
    write_rule_scorecard()
    write_trade_aging(open_rows)
    write_risk_profiles()
    write_auto_daily(states, open_rows)
    write_live_checklist(states)
    write_protection_report(open_rows)
    write_promotion_pack()
    write_pilot_package(states)
    write_summary()
    print(f"Saved expansion control dashboard to {EXPANSION_DASHBOARD}")
    print(f"Saved open trade watchdog to {OPEN_WATCHDOG}")
    print(f"Saved expansion kill-switch to {EXPANSION_KILL_SWITCH}")
    print(f"Saved rule scorecard to {RULE_SCORECARD}")
    print(f"Saved trade aging protection to {TRADE_AGING}")
    print(f"Saved family risk profiles to {RISK_PROFILES}")
    print(f"Saved auto daily report to {AUTO_DAILY}")
    print(f"Saved live-readiness checklist to {LIVE_CHECKLIST}")
    print(f"Saved paper protection bundle report to {PROTECTION_REPORT}")
    print(f"Saved promotion pack to {PROMOTION_PACK}")
    print(f"Saved pilot readiness package to {PILOT_PACKAGE}")
    print(f"Saved expansion control summary to {SUMMARY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
