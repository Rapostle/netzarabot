from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


TASK_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = TASK_ROOT / "outputs"
APP_DIR = TASK_ROOT / "app"
REPORTS_DIR = TASK_ROOT / "reports"
DATA_DIR = TASK_ROOT / "data"
SCRIPTS_DIR = TASK_ROOT / "scripts"
DOCS_DIR = TASK_ROOT / "docs"
RELEASE_DIR = TASK_ROOT / "releases/v0.1-paper-alpha"

OPERATOR_UI = OUTPUT_DIR / "operator_console.html"
TRADE_TIMELINE = OUTPUT_DIR / "trade_timeline.html"
RULE_INDEX = OUTPUT_DIR / "rule_pages/index.html"
ALERTS = OUTPUT_DIR / "action_alerts.md"
INSTALL_GUIDE = DOCS_DIR / "INSTALL_AND_RUN_GUIDE.md"
DEMO_MODE = OUTPUT_DIR / "client_demo_mode.html"
RELEASE_SUMMARY = OUTPUT_DIR / "release_package_summary.md"


TRACKS = [
    {
        "name": "Original stable rules",
        "status": OUTPUT_DIR / "paper_stable_status.csv",
        "open": OUTPUT_DIR / "paper_stable_open_positions.csv",
        "closed": OUTPUT_DIR / "paper_stable_closed_trades.csv",
        "journal": OUTPUT_DIR / "paper_stable_rules_journal.csv",
    },
    {
        "name": "Experimental pair candidates",
        "status": OUTPUT_DIR / "pair_candidate_status.csv",
        "open": OUTPUT_DIR / "pair_candidate_open_positions.csv",
        "closed": OUTPUT_DIR / "pair_candidate_closed_trades.csv",
        "journal": OUTPUT_DIR / "pair_candidate_paper_journal.csv",
    },
    {
        "name": "Advanced sniper candidates",
        "status": OUTPUT_DIR / "advanced_sniper_status.csv",
        "open": OUTPUT_DIR / "advanced_sniper_open_positions.csv",
        "closed": OUTPUT_DIR / "advanced_sniper_closed_trades.csv",
        "journal": OUTPUT_DIR / "advanced_sniper_paper_journal.csv",
    },
    {
        "name": "Boom/Crash expansion candidates",
        "status": OUTPUT_DIR / "boom_crash_expansion_status.csv",
        "open": OUTPUT_DIR / "boom_crash_expansion_open_positions.csv",
        "closed": OUTPUT_DIR / "boom_crash_expansion_closed_trades.csv",
        "journal": OUTPUT_DIR / "boom_crash_expansion_paper_journal.csv",
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


def html_escape(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def md_table(rows: list[dict[str, object]], columns: list[str], empty: str) -> str:
    if not rows:
        return empty
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(str(row.get(column, "")) for column in columns) + " |" for row in rows]
    return "\n".join([header, divider, *body])


def rule_id(reason: object) -> str:
    match = re.search(r"\b(SR\d+|PAIR\d+|BCX\d+)\b", str(reason))
    return match.group(1) if match else "unknown_rule"


def track_status_rows() -> list[dict[str, object]]:
    rows = []
    for track in TRACKS:
        status = load_csv(track["status"])
        closed = load_csv(track["closed"])
        pnl = pd.to_numeric(closed.get("paper_pnl", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
        closed_count = as_int(metric(status, "closed_trades", str(len(closed))))
        wins = int((pnl > 0).sum())
        rows.append(
            {
                "track": track["name"],
                "open": as_int(metric(status, "open_positions", "0")),
                "closed": closed_count,
                "pnl": as_float(metric(status, "closed_pnl", str(float(pnl.sum()) if not pnl.empty else 0.0))),
                "win_rate": wins / closed_count * 100.0 if closed_count else 0.0,
                "last_run": metric(status, "last_run_utc", "not run"),
            }
        )
    return rows


def all_trades() -> pd.DataFrame:
    frames = []
    for track in TRACKS:
        closed = load_csv(track["closed"])
        if not closed.empty:
            closed = closed.copy()
            closed.insert(0, "track", track["name"])
            closed["event"] = "closed"
            frames.append(closed)
        open_positions = load_csv(track["open"])
        if not open_positions.empty:
            open_positions = open_positions.copy()
            open_positions.insert(0, "track", track["name"])
            open_positions["event"] = "open"
            frames.append(open_positions)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True, sort=False)
    df["rule"] = df.get("reason", pd.Series(dtype=str)).map(rule_id)
    return df


def write_operator_ui() -> None:
    rows = track_status_rows()
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
            </section>
            """
        )
    commands = [
        ("Start", "work/start_trading_bot_suite.sh"),
        ("Stop", "work/stop_trading_bot_suite.sh"),
        ("Status", "work/check_bot_status.sh"),
        ("Service Status", "work/status_trading_bot_suite.sh"),
        ("Command Center", "work/monitor_command_center.sh"),
    ]
    command_cards = "".join(
        f"<button title='{html_escape(cmd)}'><span>{html_escape(label)}</span><code>{html_escape(cmd)}</code></button>"
        for label, cmd in commands
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="60">
  <title>Trading Bot Operator Console</title>
  <style>
    :root {{ --bg:#f6f8fb; --panel:#fff; --ink:#142033; --muted:#667085; --line:#d7deea; --bad:#991b1b; --ok:#075985; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:var(--bg); color:var(--ink); }}
    main {{ width:min(1180px,calc(100% - 28px)); margin:0 auto; padding:28px 0; }}
    h1 {{ margin:0 0 6px; font-size:32px; }}
    p {{ color:var(--muted); }}
    .banner {{ background:#fee2e2; color:var(--bad); border:1px solid var(--bad); border-radius:8px; padding:13px; font-weight:800; margin:16px 0; }}
    .grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }}
    .card,.panel,button {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:14px; }}
    .danger {{ border-color:var(--bad); }}
    .active {{ border-color:var(--ok); }}
    h2 {{ margin:0 0 12px; font-size:18px; }}
    .metrics {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; }}
    .metrics div {{ border:1px solid var(--line); border-radius:8px; padding:8px; }}
    strong {{ display:block; font-size:21px; }}
    small {{ color:var(--muted); }}
    .controls {{ display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:10px; }}
    button {{ text-align:left; cursor:default; }}
    button span {{ font-weight:800; display:block; margin-bottom:8px; }}
    code {{ background:#eef2f7; display:block; padding:7px; border-radius:6px; white-space:pre-wrap; }}
    .panel {{ margin-top:16px; }}
    a {{ color:var(--ok); }}
    @media(max-width:1000px) {{ .grid,.controls {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <main>
    <h1>Trading Bot Operator Console</h1>
    <p>Updated {html_escape(datetime.now(timezone.utc).isoformat())}. Local paper mode.</p>
    <div class="banner">No live trading. These buttons show commands to paste in Terminal.</div>
    <div class="grid">{''.join(cards)}</div>
    <section class="panel">
      <h2>Controls</h2>
      <div class="controls">{command_cards}</div>
    </section>
    <section class="panel">
      <h2>Views</h2>
      <p><a href="trade_timeline.html">Trade Timeline</a> | <a href="rule_pages/index.html">Rule Detail Pages</a> | <a href="client_demo_mode.html">Client Demo Mode</a></p>
    </section>
  </main>
</body>
</html>
"""
    OPERATOR_UI.write_text(html, encoding="utf-8")


def write_trade_timeline() -> None:
    trades = all_trades()
    rows = []
    if not trades.empty:
        sort_col = "closed_at" if "closed_at" in trades.columns else "opened_at"
        trades = trades.sort_values(sort_col, ascending=False, na_position="last")
        for _, row in trades.head(120).iterrows():
            rows.append(
                {
                    "time": row.get("closed_at", row.get("opened_at", "")),
                    "event": row.get("event", ""),
                    "track": row.get("track", ""),
                    "symbol": row.get("symbol", ""),
                    "tf": row.get("timeframe", ""),
                    "side": row.get("side", ""),
                    "rule": row.get("rule", ""),
                    "pnl": "" if pd.isna(row.get("paper_pnl", "")) else f"{as_float(row.get('paper_pnl', 0.0)):.2f}",
                    "reason": row.get("exit_reason", row.get("status", "")),
                }
            )
    table_rows = "".join(
        "<tr>" + "".join(f"<td>{html_escape(row[col])}</td>" for col in ["time", "event", "track", "symbol", "tf", "side", "rule", "pnl", "reason"]) + "</tr>"
        for row in rows
    )
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60"><title>Trade Timeline</title>
<style>body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;margin:0;background:#f6f8fb;color:#142033}}main{{width:min(1200px,calc(100% - 28px));margin:0 auto;padding:28px 0}}table{{width:100%;border-collapse:collapse;background:white;border:1px solid #d7deea;border-radius:8px;overflow:hidden}}th,td{{border-bottom:1px solid #d7deea;padding:8px;text-align:left;font-size:14px}}th{{background:#eef2f7}}a{{color:#075985}}</style></head>
<body><main><h1>Trade Timeline</h1><p><a href="operator_console.html">Back to console</a></p>
<table><thead><tr><th>Time</th><th>Event</th><th>Track</th><th>Symbol</th><th>TF</th><th>Side</th><th>Rule</th><th>PnL</th><th>Reason</th></tr></thead><tbody>{table_rows or '<tr><td colspan="9">No trades yet.</td></tr>'}</tbody></table>
</main></body></html>"""
    TRADE_TIMELINE.write_text(html, encoding="utf-8")


def write_rule_pages() -> None:
    rules_dir = OUTPUT_DIR / "rule_pages"
    rules_dir.mkdir(parents=True, exist_ok=True)
    trades = all_trades()
    links = []
    if not trades.empty:
        for rule, group in trades.groupby("rule"):
            if not rule or rule == "unknown_rule":
                continue
            closed = group[group["event"] == "closed"]
            pnl = pd.to_numeric(closed.get("paper_pnl", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
            rows = []
            for _, row in group.tail(80).iterrows():
                rows.append(
                    {
                        "event": row.get("event", ""),
                        "track": row.get("track", ""),
                        "symbol": row.get("symbol", ""),
                        "tf": row.get("timeframe", ""),
                        "side": row.get("side", ""),
                        "pnl": "" if pd.isna(row.get("paper_pnl", "")) else f"{as_float(row.get('paper_pnl', 0.0)):.2f}",
                        "status": row.get("exit_reason", row.get("status", "")),
                    }
                )
            table = md_table(rows, ["event", "track", "symbol", "tf", "side", "pnl", "status"], "No rule rows.")
            page = [
                f"# Rule {rule}",
                "",
                f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
                "",
                f"- Paper closed trades: {len(closed)}",
                f"- Paper PnL: {float(pnl.sum()) if not pnl.empty else 0.0:.2f}",
                f"- Wins/losses: {int((pnl > 0).sum())}/{int((pnl < 0).sum())}",
                "",
                "## Activity",
                "",
                table,
                "",
            ]
            page_path = rules_dir / f"{rule}.md"
            page_path.write_text("\n".join(page), encoding="utf-8")
            links.append({"rule": rule, "closed": len(closed), "pnl": f"{float(pnl.sum()) if not pnl.empty else 0.0:.2f}", "file": f"{rule}.md"})
    links.sort(key=lambda row: as_float(row["pnl"]), reverse=True)
    body = "".join(f"<tr><td>{html_escape(row['rule'])}</td><td>{row['closed']}</td><td>{row['pnl']}</td><td><a href='{html_escape(row['file'])}'>{html_escape(row['file'])}</a></td></tr>" for row in links)
    empty_rule_rows = "<tr><td colspan='4'>No rules yet.</td></tr>"
    RULE_INDEX.write_text(
        f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>Rule Pages</title><style>body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f6f8fb;color:#142033}}main{{width:min(900px,calc(100% - 28px));margin:0 auto;padding:28px 0}}table{{width:100%;border-collapse:collapse;background:white}}td,th{{border:1px solid #d7deea;padding:8px;text-align:left}}</style></head><body><main><h1>Rule Detail Pages</h1><p><a href='../operator_console.html'>Back to console</a></p><table><thead><tr><th>Rule</th><th>Closed</th><th>PnL</th><th>File</th></tr></thead><tbody>{body or empty_rule_rows}</tbody></table></main></body></html>",
        encoding="utf-8",
    )


def write_alerts() -> None:
    rows = []
    watchdog = (OUTPUT_DIR / "open_trade_watchdog.md").read_text(encoding="utf-8") if (OUTPUT_DIR / "open_trade_watchdog.md").exists() else ""
    if "near stop" in watchdog:
        rows.append({"level": "warning", "alert": "One or more open paper trades are near stop.", "action": "Let emergency paper stop enforcer handle next cycle."})
    if "stuck" in watchdog:
        rows.append({"level": "warning", "alert": "One or more paper trades are stuck.", "action": "Watch next cycle; do not promote affected rule."})
    status_rows = track_status_rows()
    for row in status_rows:
        if float(row["pnl"]) < -60:
            rows.append({"level": "danger", "alert": f"{row['track']} breached loss limit.", "action": "Keep quarantined."})
        if int(row["open"]) > 0:
            rows.append({"level": "info", "alert": f"{row['track']} has {row['open']} open paper trade(s).", "action": "Wait for close before judging."})
    lines = [
        "# Action Alerts",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        md_table(rows, ["level", "alert", "action"], "No alerts right now."),
        "",
    ]
    ALERTS.write_text("\n".join(lines), encoding="utf-8")


def sync_clean_folders() -> None:
    for folder in [APP_DIR, REPORTS_DIR, DATA_DIR, SCRIPTS_DIR, DOCS_DIR]:
        folder.mkdir(parents=True, exist_ok=True)
    for source in [OPERATOR_UI, TRADE_TIMELINE, DEMO_MODE, OUTPUT_DIR / "trading_bot_app_dashboard.html", OUTPUT_DIR / "expansion_control_dashboard.html"]:
        if source.exists():
            shutil.copy2(source, APP_DIR / source.name)
    report_files = [
        ALERTS,
        OUTPUT_DIR / "live_readiness_checklist.md",
        OUTPUT_DIR / "promotion_pack.md",
        OUTPUT_DIR / "pilot_readiness_package.md",
        OUTPUT_DIR / "backtest_vs_paper_report.md",
        OUTPUT_DIR / "paper_protection_bundle_report.md",
        OUTPUT_DIR / "subscription_licensing_plan.md",
    ]
    for source in report_files:
        if source.exists():
            shutil.copy2(source, REPORTS_DIR / source.name)
    if (OUTPUT_DIR / "paper_trading.db").exists():
        shutil.copy2(OUTPUT_DIR / "paper_trading.db", DATA_DIR / "paper_trading.db")
    for source in [
        TASK_ROOT / "work/start_trading_bot_suite.sh",
        TASK_ROOT / "work/stop_trading_bot_suite.sh",
        TASK_ROOT / "work/status_trading_bot_suite.sh",
        TASK_ROOT / "work/check_bot_status.sh",
    ]:
        if source.exists():
            shutil.copy2(source, SCRIPTS_DIR / source.name)


def write_guide_and_demo() -> None:
    guide = [
        "# Install And Run Guide",
        "",
        "This bot is currently paper-only.",
        "",
        "## Start",
        "",
        "From the project folder, run:",
        "",
        "```bash",
        "work/start_trading_bot_suite.sh",
        "```",
        "",
        "## Stop",
        "",
        "```bash",
        "work/stop_trading_bot_suite.sh",
        "```",
        "",
        "## Check Status",
        "",
        "```bash",
        "work/check_bot_status.sh",
        "```",
        "",
        "## Open The App",
        "",
        "Open `outputs/operator_console.html` or `outputs/trading_bot_app_dashboard.html`.",
        "",
        "## Live Trading",
        "",
        "Do not add a real token or trade real money until the readiness reports stop saying NOT READY.",
        "",
    ]
    INSTALL_GUIDE.write_text("\n".join(guide), encoding="utf-8")
    rows = track_status_rows()
    demo_rows = "".join(f"<tr><td>{html_escape(row['track'])}</td><td>{row['open']}</td><td>{row['closed']}</td><td>{row['pnl']:.2f}</td></tr>" for row in rows)
    DEMO_MODE.write_text(
        f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>Client Demo Mode</title><style>body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f6f8fb;color:#142033}}main{{width:min(900px,calc(100% - 28px));margin:0 auto;padding:28px 0}}table{{width:100%;border-collapse:collapse;background:white}}td,th{{border:1px solid #d7deea;padding:8px;text-align:left}}.banner{{background:#eef2f7;border:1px solid #d7deea;border-radius:8px;padding:12px}}</style></head><body><main><h1>Client Demo Mode</h1><div class='banner'>Demo view: strategy internals are hidden. Paper results only.</div><table><thead><tr><th>Track</th><th>Open</th><th>Closed</th><th>Paper PnL</th></tr></thead><tbody>{demo_rows}</tbody></table></main></body></html>",
        encoding="utf-8",
    )


def build_release() -> None:
    if RELEASE_DIR.exists():
        shutil.rmtree(RELEASE_DIR)
    (RELEASE_DIR / "app").mkdir(parents=True, exist_ok=True)
    (RELEASE_DIR / "reports").mkdir(parents=True, exist_ok=True)
    (RELEASE_DIR / "scripts").mkdir(parents=True, exist_ok=True)
    (RELEASE_DIR / "docs").mkdir(parents=True, exist_ok=True)
    for folder, target in [(APP_DIR, "app"), (REPORTS_DIR, "reports"), (SCRIPTS_DIR, "scripts"), (DOCS_DIR, "docs")]:
        if folder.exists():
            for source in folder.iterdir():
                if source.is_file():
                    shutil.copy2(source, RELEASE_DIR / target / source.name)
    readme = [
        "# v0.1 Paper Alpha",
        "",
        "This is a paper-only release package.",
        "",
        "Start with `docs/INSTALL_AND_RUN_GUIDE.md`.",
        "",
        "No live trading is approved in this release.",
        "",
    ]
    (RELEASE_DIR / "README.md").write_text("\n".join(readme), encoding="utf-8")


def write_summary() -> None:
    lines = [
        "# Release Package Summary",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Built polish/release layers:",
        "",
        "- True start/stop operator UI: `outputs/operator_console.html`",
        "- Trade timeline: `outputs/trade_timeline.html`",
        "- Rule detail pages: `outputs/rule_pages/index.html`",
        "- Alert system: `outputs/action_alerts.md`",
        "- Clean app folders: `app/`, `reports/`, `data/`, `scripts/`, `docs/`",
        "- Install/run guide: `docs/INSTALL_AND_RUN_GUIDE.md`",
        "- Client demo mode: `outputs/client_demo_mode.html`",
        "- Versioned release package: `releases/v0.1-paper-alpha/`",
        "",
        "Everything is still paper-only.",
        "",
    ]
    RELEASE_SUMMARY.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    (OUTPUT_DIR / "rule_pages").mkdir(parents=True, exist_ok=True)
    for folder in [APP_DIR, REPORTS_DIR, DATA_DIR, SCRIPTS_DIR, DOCS_DIR]:
        folder.mkdir(parents=True, exist_ok=True)
    write_operator_ui()
    write_trade_timeline()
    write_rule_pages()
    write_alerts()
    write_guide_and_demo()
    sync_clean_folders()
    build_release()
    write_summary()
    print(f"Saved operator console to {OPERATOR_UI}")
    print(f"Saved trade timeline to {TRADE_TIMELINE}")
    print(f"Saved rule pages to {RULE_INDEX}")
    print(f"Saved alerts to {ALERTS}")
    print(f"Saved install guide to {INSTALL_GUIDE}")
    print(f"Saved client demo mode to {DEMO_MODE}")
    print(f"Saved release package to {RELEASE_DIR}")
    print(f"Saved release summary to {RELEASE_SUMMARY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
