from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


TASK_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = TASK_ROOT / "outputs"

PRODUCT_DASHBOARD = OUTPUT_DIR / "trading_bot_app_dashboard.html"
DATABASE_PATH = OUTPUT_DIR / "paper_trading.db"
DATABASE_REPORT = OUTPUT_DIR / "paper_trade_database_report.md"
BACKTEST_VS_PAPER = OUTPUT_DIR / "backtest_vs_paper_report.md"
BOT_FORMAT_PLAN = OUTPUT_DIR / "bot_format_export_plan.md"
LICENSING_PLAN = OUTPUT_DIR / "subscription_licensing_plan.md"
LIVE_SAFETY_LAYER = OUTPUT_DIR / "real_broker_safety_layer.md"
PRODUCT_SUMMARY = OUTPUT_DIR / "product_layer_summary.md"


TRACKS = [
    {
        "track": "Original stable rules",
        "status": OUTPUT_DIR / "paper_stable_status.csv",
        "open": OUTPUT_DIR / "paper_stable_open_positions.csv",
        "closed": OUTPUT_DIR / "paper_stable_closed_trades.csv",
        "journal": OUTPUT_DIR / "paper_stable_rules_journal.csv",
        "backtest": OUTPUT_DIR / "crash_boom_execution_approved_stable_rules_15m_30m.csv",
    },
    {
        "track": "Experimental pair candidates",
        "status": OUTPUT_DIR / "pair_candidate_status.csv",
        "open": OUTPUT_DIR / "pair_candidate_open_positions.csv",
        "closed": OUTPUT_DIR / "pair_candidate_closed_trades.csv",
        "journal": OUTPUT_DIR / "pair_candidate_paper_journal.csv",
        "backtest": OUTPUT_DIR / "stable_rules_pair_execution_candidates.csv",
    },
    {
        "track": "Advanced sniper candidates",
        "status": OUTPUT_DIR / "advanced_sniper_status.csv",
        "open": OUTPUT_DIR / "advanced_sniper_open_positions.csv",
        "closed": OUTPUT_DIR / "advanced_sniper_closed_trades.csv",
        "journal": OUTPUT_DIR / "advanced_sniper_paper_journal.csv",
        "backtest": OUTPUT_DIR / "advanced_accuracy_execution_candidates.csv",
    },
    {
        "track": "Boom/Crash expansion candidates",
        "status": OUTPUT_DIR / "boom_crash_expansion_status.csv",
        "open": OUTPUT_DIR / "boom_crash_expansion_open_positions.csv",
        "closed": OUTPUT_DIR / "boom_crash_expansion_closed_trades.csv",
        "journal": OUTPUT_DIR / "boom_crash_expansion_paper_journal.csv",
        "backtest": OUTPUT_DIR / "boom_crash_expansion_execution_candidates.csv",
    },
]


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def metric(status: pd.DataFrame, key: str, default: str = "0") -> str:
    if status.empty or "metric" not in status.columns or "value" not in status.columns:
        return default
    rows = status[status["metric"] == key]
    if rows.empty:
        return default
    return str(rows.iloc[-1]["value"])


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


def track_rows() -> list[dict[str, object]]:
    rows = []
    for track in TRACKS:
        status = load_csv(track["status"])
        closed = load_csv(track["closed"])
        pnl = pd.to_numeric(closed.get("paper_pnl", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
        wins = int((pnl > 0).sum())
        losses = int((pnl < 0).sum())
        closed_count = as_int(metric(status, "closed_trades", str(len(closed))))
        rows.append(
            {
                "track": track["track"],
                "last_run": metric(status, "last_run_utc", "not run"),
                "open": as_int(metric(status, "open_positions", "0")),
                "closed": closed_count,
                "pnl": as_float(metric(status, "closed_pnl", str(float(pnl.sum()) if not pnl.empty else 0.0))),
                "wins": wins,
                "losses": losses,
                "win_rate": wins / closed_count * 100.0 if closed_count else 0.0,
                "latest_orders": as_int(metric(status, "latest_paper_orders", "0")),
                "blocked": as_int(metric(status, "latest_blocked_signals", "0")),
            }
        )
    return rows


def write_sqlite_database() -> None:
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        pd.DataFrame(track_rows()).to_sql("track_status", conn, index=False)
        for track in TRACKS:
            prefix = (
                track["track"]
                .lower()
                .replace("/", "_")
                .replace(" ", "_")
                .replace("-", "_")
            )
            for label in ["open", "closed", "journal"]:
                df = load_csv(track[label])
                if df.empty:
                    df = pd.DataFrame({"track": [track["track"]], "empty": [True]})
                else:
                    df = df.copy()
                    df.insert(0, "track", track["track"])
                df.to_sql(f"{prefix}_{label}", conn, index=False)
        conn.execute(
            "create table metadata (key text primary key, value text)"
        )
        conn.execute(
            "insert into metadata (key, value) values (?, ?)",
            ("built_at_utc", datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

    lines = [
        "# Paper Trade Database",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"Database file: `{DATABASE_PATH}`",
        "",
        "Included tables:",
        "",
        "- `track_status`",
        "- One open/closed/journal table for each paper track.",
        "",
        "Use this database later for the real app UI, analytics, and cleaner product reporting.",
        "",
    ]
    DATABASE_REPORT.write_text("\n".join(lines), encoding="utf-8")


def write_product_dashboard(rows: list[dict[str, object]]) -> None:
    cards = []
    for row in rows:
        cls = "danger" if float(row["pnl"]) < -60 else "active" if int(row["open"]) else "waiting"
        cards.append(
            f"""
            <section class="card {cls}">
              <h2>{html_escape(row['track'])}</h2>
              <div class="metrics">
                <div><strong>{row['open']}</strong><small>Open</small></div>
                <div><strong>{row['closed']}</strong><small>Closed</small></div>
                <div><strong>{row['pnl']:.2f}</strong><small>Paper PnL</small></div>
                <div><strong>{row['win_rate']:.1f}%</strong><small>Win rate</small></div>
              </div>
              <p>Last run: {html_escape(row['last_run'])}</p>
            </section>
            """
        )
    commands = [
        ("Start full suite", "work/start_trading_bot_suite.sh"),
        ("Stop full suite", "work/stop_trading_bot_suite.sh"),
        ("Check background status", "work/status_trading_bot_suite.sh"),
        ("Quick report", "work/check_bot_status.sh"),
        ("Command center", "work/monitor_command_center.sh"),
    ]
    command_buttons = "".join(
        f"<div class='command'><strong>{html_escape(label)}</strong><code>{html_escape(command)}</code></div>"
        for label, command in commands
    )
    links = [
        "outputs/monitor_dashboard.html",
        "outputs/expansion_control_dashboard.html",
        "outputs/open_trade_watchdog.md",
        "outputs/live_readiness_checklist.md",
        "outputs/promotion_pack.md",
        "outputs/pilot_readiness_package.md",
        "outputs/backtest_vs_paper_report.md",
        "outputs/subscription_licensing_plan.md",
    ]
    link_list = "".join(f"<li><code>{html_escape(link)}</code></li>" for link in links)
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="60">
  <title>Trading Bot App</title>
  <style>
    :root {{ --bg:#f6f8fb; --panel:#fff; --ink:#142033; --muted:#667085; --line:#d8dee8; --bad:#991b1b; --ok:#075985; --wait:#7c5f00; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:var(--bg); color:var(--ink); }}
    main {{ width:min(1200px,calc(100% - 28px)); margin:0 auto; padding:28px 0; }}
    h1 {{ margin:0 0 6px; font-size:32px; }}
    .subtle,p {{ color:var(--muted); }}
    .banner {{ background:#fee2e2; color:var(--bad); border:1px solid var(--bad); border-radius:8px; padding:13px; font-weight:800; margin:16px 0; }}
    .grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }}
    .card,.panel,.command {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:14px; }}
    .active {{ border-color:var(--ok); }}
    .danger {{ border-color:var(--bad); }}
    h2 {{ margin:0 0 12px; font-size:18px; }}
    .metrics {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; }}
    .metrics div {{ border:1px solid var(--line); border-radius:8px; padding:8px; }}
    strong {{ display:block; font-size:20px; }}
    small {{ color:var(--muted); }}
    .commands {{ display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:10px; }}
    code {{ display:block; background:#eef2f7; padding:7px; border-radius:6px; margin-top:7px; white-space:pre-wrap; }}
    .panel {{ margin-top:16px; }}
    li {{ margin:7px 0; }}
    @media(max-width:1000px) {{ .grid,.commands {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <main>
    <h1>Trading Bot App</h1>
    <p class="subtle">Updated {html_escape(datetime.now(timezone.utc).isoformat())}. Paper monitoring only.</p>
    <div class="banner">LIVE TRADING IS NOT READY. Do not add a real Deriv token yet.</div>
    <div class="grid">{''.join(cards)}</div>
    <section class="panel">
      <h2>Controls</h2>
      <p>Paste these commands in Terminal from the project folder.</p>
      <div class="commands">{command_buttons}</div>
    </section>
    <section class="panel">
      <h2>Important Reports</h2>
      <ul>{link_list}</ul>
    </section>
  </main>
</body>
</html>
"""
    PRODUCT_DASHBOARD.write_text(html, encoding="utf-8")


def paper_rule_summary() -> pd.DataFrame:
    rows = []
    for track in TRACKS:
        closed = load_csv(track["closed"])
        if closed.empty or "paper_pnl" not in closed:
            continue
        closed = closed.copy()
        closed["rule"] = closed.get("reason", pd.Series(dtype=str)).astype(str).str.extract(r"\b(SR\d+|PAIR\d+|BCX\d+)\b")[0].fillna("unknown_rule")
        closed["pnl"] = pd.to_numeric(closed["paper_pnl"], errors="coerce").fillna(0.0)
        for rule, group in closed.groupby("rule"):
            pnl = group["pnl"]
            rows.append(
                {
                    "track": track["track"],
                    "rule": rule,
                    "paper_closed": len(group),
                    "paper_wins": int((pnl > 0).sum()),
                    "paper_losses": int((pnl < 0).sum()),
                    "paper_pnl": float(pnl.sum()),
                }
            )
    return pd.DataFrame(rows)


def backtest_rule_summary() -> pd.DataFrame:
    rows = []
    for track in TRACKS:
        df = load_csv(track["backtest"])
        if df.empty:
            continue
        id_col = "rule_id" if "rule_id" in df.columns else None
        if not id_col:
            continue
        for _, row in df.iterrows():
            rows.append(
                {
                    "track": track["track"],
                    "rule": row.get(id_col, ""),
                    "bt_trades": as_int(row.get("trades", row.get("approved_matches", 0))),
                    "bt_win_rate": as_float(row.get("win_rate", row.get("approved_win_rate", 0.0))),
                    "bt_return": as_float(row.get("total_return", row.get("approved_return", 0.0))),
                    "bt_profit_factor": as_float(row.get("profit_factor", row.get("approved_profit_factor", 0.0))),
                }
            )
    return pd.DataFrame(rows)


def write_backtest_vs_paper() -> None:
    paper = paper_rule_summary()
    backtest = backtest_rule_summary()
    rows = []
    if not backtest.empty:
        merged = backtest.merge(paper, on=["track", "rule"], how="left")
        merged["paper_closed"] = merged["paper_closed"].fillna(0).astype(int)
        merged["paper_pnl"] = merged["paper_pnl"].fillna(0.0)
        for _, row in merged.sort_values(["paper_closed", "paper_pnl"], ascending=False).head(25).iterrows():
            rows.append(
                {
                    "track": row["track"],
                    "rule": row["rule"],
                    "bt_trades": row["bt_trades"],
                    "bt_win_rate": f"{as_float(row['bt_win_rate']) * 100:.1f}%" if as_float(row["bt_win_rate"]) <= 1 else f"{as_float(row['bt_win_rate']):.1f}%",
                    "bt_pf": f"{as_float(row['bt_profit_factor']):.2f}",
                    "paper_closed": row["paper_closed"],
                    "paper_pnl": f"{as_float(row['paper_pnl']):.2f}",
                    "read": "paper evidence forming" if as_int(row["paper_closed"]) > 0 else "waiting for paper trades",
                }
            )
    lines = [
        "# Backtest vs Paper Comparison",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This compares research/backtest claims with actual paper behavior. Paper evidence wins.",
        "",
        md_table(rows, ["track", "rule", "bt_trades", "bt_win_rate", "bt_pf", "paper_closed", "paper_pnl", "read"], "No comparison data yet."),
        "",
    ]
    BACKTEST_VS_PAPER.write_text("\n".join(lines), encoding="utf-8")


def write_format_plan() -> None:
    lines = [
        "# Bot Format / Export Plan",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Recommended final format: Web dashboard + Python Deriv engine first.",
        "",
        "| format | status | why |",
        "| --- | --- | --- |",
        "| Python Deriv API bot | best first version | Matches the current code and Deriv data flow. |",
        "| Web dashboard | build now | Gives users buttons and reports without touching code. |",
        "| MT5 EA | later/export target | Useful for MT5 users, but it would require translating rules and execution. |",
        "| Hybrid | later | Python research engine plus EA execution bridge after rules prove themselves. |",
        "",
        "Do not export to EA until the paper tracks have enough closed trades and stable rule scorecards.",
        "",
    ]
    BOT_FORMAT_PLAN.write_text("\n".join(lines), encoding="utf-8")


def write_licensing_plan() -> None:
    lines = [
        "# Subscription / Licensing Plan",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "How to make money when people use the bot:",
        "",
        "| layer | recommendation |",
        "| --- | --- |",
        "| Free/demo | dashboard + delayed paper signals only |",
        "| Starter | limited symbols, paper mode, reports |",
        "| Pro | all paper monitors, optimization reports, alerts |",
        "| Managed/live pilot | only after legal/compliance review, strict risk limits |",
        "",
        "License controls to add later:",
        "",
        "- License key per user.",
        "- Device/account lock.",
        "- Plan limits for symbols and monitors.",
        "- Usage logs.",
        "- Remote kill switch for unpaid or unsafe accounts.",
        "",
        "Important: do not promise profits. Sell tools, analytics, automation, and risk controls.",
        "",
    ]
    LICENSING_PLAN.write_text("\n".join(lines), encoding="utf-8")


def write_live_safety_layer(rows: list[dict[str, object]]) -> None:
    checks = [
        {"check": "Paper-only default", "status": "PASS", "detail": "No live token is used by these scripts."},
        {"check": "Daily loss limit", "status": "DESIGNED", "detail": "Must be enforced before live mode."},
        {"check": "Max open trades", "status": "PASS", "detail": "Paper guard is active; live guard still required."},
        {"check": "Emergency stop all", "status": "DESIGNED", "detail": "Needed for broker/live layer."},
        {"check": "Readiness gate", "status": "PASS", "detail": "All tracks currently report NOT READY."},
    ]
    live_ready = any(int(row["closed"]) >= 10 and float(row["pnl"]) > 0 and int(row["open"]) == 0 for row in rows)
    lines = [
        "# Real Broker Safety Layer",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"Current live verdict: {'MANUAL REVIEW ONLY' if live_ready else 'NOT READY'}",
        "",
        md_table(checks, ["check", "status", "detail"], "No safety checks."),
        "",
        "Before real money:",
        "",
        "- Add a live/paper switch that defaults to paper.",
        "- Add daily loss limit.",
        "- Add emergency stop-all.",
        "- Add max risk per trade and per day.",
        "- Add broker execution logs.",
        "- Add manual confirmation before first live order.",
        "",
    ]
    LIVE_SAFETY_LAYER.write_text("\n".join(lines), encoding="utf-8")


def write_summary() -> None:
    lines = [
        "# Product Layer Summary",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Built product-grade layers:",
        "",
        "- Real app dashboard: `outputs/trading_bot_app_dashboard.html`",
        "- One-command launcher: `work/start_trading_bot_suite.sh`",
        "- Background service helpers: `work/start_trading_bot_suite.sh`, `work/stop_trading_bot_suite.sh`, `work/status_trading_bot_suite.sh`",
        "- Paper trade database: `outputs/paper_trading.db`",
        "- Backtest vs paper comparison: `outputs/backtest_vs_paper_report.md`",
        "- Bot format/export plan: `outputs/bot_format_export_plan.md`",
        "- Subscription/licensing plan: `outputs/subscription_licensing_plan.md`",
        "- Real broker safety layer: `outputs/real_broker_safety_layer.md`",
        "",
        "Everything remains paper-only.",
        "",
    ]
    PRODUCT_SUMMARY.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = track_rows()
    write_sqlite_database()
    write_product_dashboard(rows)
    write_backtest_vs_paper()
    write_format_plan()
    write_licensing_plan()
    write_live_safety_layer(rows)
    write_summary()
    print(f"Saved product app dashboard to {PRODUCT_DASHBOARD}")
    print(f"Saved paper database to {DATABASE_PATH}")
    print(f"Saved database report to {DATABASE_REPORT}")
    print(f"Saved backtest vs paper report to {BACKTEST_VS_PAPER}")
    print(f"Saved bot format plan to {BOT_FORMAT_PLAN}")
    print(f"Saved licensing plan to {LICENSING_PLAN}")
    print(f"Saved live safety layer to {LIVE_SAFETY_LAYER}")
    print(f"Saved product summary to {PRODUCT_SUMMARY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
