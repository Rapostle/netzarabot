from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


TASK_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = TASK_ROOT / "outputs/monitor_overview.md"
HTML_OUTPUT = TASK_ROOT / "outputs/monitor_dashboard.html"
ALERT_OUTPUT = TASK_ROOT / "outputs/monitor_alerts.md"
DECISION_BRIEF_OUTPUT = TASK_ROOT / "outputs/decision_brief.md"
PAIR_SIGNAL_REPORT = TASK_ROOT / "outputs/pair_candidate_signal_frequency_report.md"


MONITORS = [
    {
        "name": "Original stable rules",
        "status": TASK_ROOT / "outputs/paper_stable_status.csv",
        "journal": TASK_ROOT / "outputs/paper_stable_rules_journal.csv",
        "readiness": TASK_ROOT / "outputs/paper_stable_go_live_readiness.md",
        "dashboard": TASK_ROOT / "outputs/paper_stable_dashboard.md",
        "runner": "work/run_paper_monitor.sh",
        "role": "Conservative approved rules currently used as the main paper baseline.",
    },
    {
        "name": "Experimental pair candidates",
        "status": TASK_ROOT / "outputs/pair_candidate_status.csv",
        "journal": TASK_ROOT / "outputs/pair_candidate_paper_journal.csv",
        "readiness": TASK_ROOT / "outputs/pair_candidate_go_live_readiness.md",
        "dashboard": TASK_ROOT / "outputs/pair_candidate_dashboard.md",
        "runner": "work/run_pair_candidate_paper_monitor.sh",
        "role": "Separate experimental paper track for the 10 stronger two-condition candidates.",
    },
    {
        "name": "Advanced sniper candidates",
        "status": TASK_ROOT / "outputs/advanced_sniper_status.csv",
        "journal": TASK_ROOT / "outputs/advanced_sniper_paper_journal.csv",
        "readiness": TASK_ROOT / "outputs/advanced_sniper_go_live_readiness.md",
        "dashboard": TASK_ROOT / "outputs/advanced_sniper_dashboard.md",
        "runner": "work/run_advanced_sniper_paper_local.sh",
        "role": "Separate offline-gated sniper track using regime, spike, score, exit, walk-forward, and risk filters.",
    },
    {
        "name": "Boom/Crash expansion candidates",
        "status": TASK_ROOT / "outputs/boom_crash_expansion_status.csv",
        "journal": TASK_ROOT / "outputs/boom_crash_expansion_paper_journal.csv",
        "readiness": TASK_ROOT / "outputs/boom_crash_expansion_go_live_readiness.md",
        "dashboard": TASK_ROOT / "outputs/boom_crash_expansion_dashboard.md",
        "runner": "work/run_boom_crash_expansion_paper_monitor.sh",
        "role": "Separate wider Boom/Crash paper track for expansion candidates across more instruments and timeframes.",
    },
]


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def metric(df: pd.DataFrame, key: str, default: str = "") -> str:
    if df.empty or "metric" not in df.columns or "value" not in df.columns:
        return default
    rows = df[df["metric"] == key]
    if rows.empty:
        return default
    value = rows.iloc[-1]["value"]
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def readiness_verdict(path: Path) -> str:
    if not path.exists():
        return "missing"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("Verdict:"):
            return line.replace("Verdict:", "").strip()
    return "unknown"


def paper_order_rows(journal: pd.DataFrame) -> int:
    if journal.empty or "decision" not in journal.columns:
        return 0
    return int((journal["decision"] == "paper_order").sum())


def age_minutes(timestamp: str) -> str:
    if not timestamp or timestamp == "not run":
        return "unknown"
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return "unknown"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    minutes = max((datetime.now(timezone.utc) - parsed).total_seconds() / 60.0, 0.0)
    return f"{minutes:.1f}"


def markdown_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    if not rows:
        return "No monitor rows available."
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(str(row.get(column, "")) for column in columns) + " |" for row in rows]
    return "\n".join([header, divider, *body])


def pair_signal_drought_note() -> str:
    if not PAIR_SIGNAL_REPORT.exists():
        return "Experimental pair signal report is missing, so no-trade detail is unavailable."
    text = PAIR_SIGNAL_REPORT.read_text(encoding="utf-8")
    exact = "unknown"
    near = "unknown"
    relaxed = "unknown"
    for line in text.splitlines():
        if line.startswith("- Exact rule matches right now:"):
            exact = line.split(":", 1)[1].strip()
        elif line.startswith("- Near misses right now:"):
            near = line.split(":", 1)[1].strip()
        elif line.startswith("- Research-only relaxed candidates passing floor:"):
            relaxed = line.split(":", 1)[1].strip()
    if exact == "0":
        return (
            "Experimental pair is not frozen: it has 0 exact matches right now, "
            f"{near} near miss(es), and {relaxed} relaxed research candidate(s). "
            "It is probably too selective for fast evidence because it only watches BOOM300N/CRASH300N on 15m."
        )
    return (
        f"Experimental pair signal check: {exact} exact match(es), {near} near miss(es), "
        f"and {relaxed} relaxed research candidate(s)."
    )


def html_escape(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_rows() -> list[dict[str, str]]:
    rows = []
    for monitor in MONITORS:
        status = load_csv(monitor["status"])
        journal = load_csv(monitor["journal"])
        last_run = metric(status, "last_run_utc", "not run")
        rows.append(
            {
                "monitor": monitor["name"],
                "last_run_utc": last_run,
                "age_minutes": age_minutes(last_run),
                "latest_decisions": metric(status, "latest_decisions", "none"),
                "latest_paper_orders": metric(status, "latest_paper_orders", "0"),
                "latest_blocked_signals": metric(status, "latest_blocked_signals", "0"),
                "journal_rows": metric(status, "journal_rows", str(0 if journal.empty else len(journal))),
                "paper_orders": str(paper_order_rows(journal)),
                "open_positions": metric(status, "open_positions", "0"),
                "closed_trades": metric(status, "closed_trades", "0"),
                "closed_pnl": metric(status, "closed_pnl", "0"),
                "readiness": readiness_verdict(monitor["readiness"]),
            }
        )
    return rows


def as_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: str, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def track_verdict(row: dict[str, str]) -> str:
    pnl = as_float(row["closed_pnl"])
    closed_trades = as_int(row["closed_trades"])
    open_positions = as_int(row["open_positions"])
    if row["monitor"] == "Original stable rules" and pnl <= -60:
        return "QUARANTINED"
    if row["readiness"] == "READY FOR TINY LIVE PILOT":
        return "REVIEW BEFORE TINY PILOT"
    if closed_trades < 10:
        return "KEEP PAPER TESTING"
    if pnl <= 0:
        return "REJECT FOR NOW"
    if open_positions > 0:
        return "WAIT FOR OPEN TRADE"
    return "PROMISING, NEED REVIEW"


def write_decision_brief(rows: list[dict[str, str]]) -> str:
    stable = next((row for row in rows if row["monitor"] == "Original stable rules"), None)
    pair = next((row for row in rows if row["monitor"] == "Experimental pair candidates"), None)

    stable_verdict = track_verdict(stable) if stable else "UNKNOWN"
    pair_verdict = track_verdict(pair) if pair else "UNKNOWN"

    if stable and as_float(stable["closed_pnl"]) <= -60:
        headline = "Do not use the original stable rules live. They are quarantined."
    else:
        headline = "Keep monitoring. No track is live-ready yet."

    advanced = next((row for row in rows if row["monitor"] == "Advanced sniper candidates"), None)

    if advanced and as_int(advanced["open_positions"]) > 0:
        next_action = "Let the advanced sniper paper trade close before judging that track."
    elif pair and as_float(pair["closed_pnl"]) > 0 and as_int(pair["closed_trades"]) < 10:
        next_action = "Let the experimental pair track reach at least 10 closed paper trades before judging it."
    elif pair and as_int(pair["closed_trades"]) >= 10 and as_float(pair["closed_pnl"]) > 0:
        next_action = "Review the experimental pair track manually for drawdown, win rate, and repeated behavior."
    else:
        next_action = "Keep the monitor running and wait for more experimental pair trades."

    lines = [
        "# Trading Bot Decision Brief",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"Main answer: {headline}",
        "",
        "## Track Verdicts",
        "",
        markdown_table(
            [
                {
                    "track": row["monitor"],
                    "verdict": track_verdict(row),
                    "closed_trades": row["closed_trades"],
                    "closed_pnl": row["closed_pnl"],
                    "open_positions": row["open_positions"],
                    "opened_this_run": row["latest_paper_orders"],
                    "blocked_this_run": row["latest_blocked_signals"],
                    "latest_decisions": row["latest_decisions"],
                }
                for row in rows
            ],
            [
                "track",
                "verdict",
                "closed_trades",
                "closed_pnl",
                "open_positions",
                "opened_this_run",
                "blocked_this_run",
                "latest_decisions",
            ],
        ),
        "",
        "## What This Means",
        "",
        f"- Original stable rules: {stable_verdict}. Keep them blocked from new entries while the loss remains beyond the safety limit.",
        f"- Experimental pair candidates: {pair_verdict}. This is still useful, but it needs more closed paper trades.",
        f"- Experimental pair signal drought: {pair_signal_drought_note()}",
        f"- Advanced sniper candidates: {track_verdict(advanced) if advanced else 'UNKNOWN'}. This is the stricter research track built from the 10 accuracy layers.",
        "- Real-money trading: NOT READY.",
        "",
        "## Next Checkpoint",
        "",
        next_action,
        "",
        "Stop conditions:",
        "",
        "- Stop considering any track that drops below the loss limit.",
        "- Do not promote a track with fewer than 10 closed paper trades.",
        "- Do not promote while any paper trade is still open.",
        "- Do not promote if closed paper PnL is negative.",
        "",
    ]
    DECISION_BRIEF_OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    return next_action


def status_class(row: dict[str, str]) -> str:
    if int(row["latest_paper_orders"]) > 0 or int(float(row["open_positions"])) > 0:
        return "active"
    if row["readiness"] == "READY FOR TINY LIVE PILOT":
        return "ready"
    try:
        if float(row["age_minutes"]) > 20:
            return "stale"
    except ValueError:
        return "stale"
    return "waiting"


def write_html_dashboard(rows: list[dict[str, str]], next_action: str) -> None:
    cards = []
    for row in rows:
        cls = status_class(row)
        cards.append(
            f"""
            <section class="card {cls}">
              <div class="card-top">
                <h2>{html_escape(row['monitor'])}</h2>
                <span class="badge">{html_escape(row['readiness'])}</span>
              </div>
              <p class="decision">{html_escape(row['latest_decisions'])}</p>
              <div class="metrics">
                <div><strong>{html_escape(row['journal_rows'])}</strong><span>Journal rows</span></div>
                <div><strong>{html_escape(row['paper_orders'])}</strong><span>Paper orders</span></div>
                <div><strong>{html_escape(row['open_positions'])}</strong><span>Open positions</span></div>
                <div><strong>{html_escape(row['closed_trades'])}</strong><span>Closed trades</span></div>
                <div><strong>{html_escape(row['closed_pnl'])}</strong><span>Closed PnL</span></div>
              </div>
              <p class="timestamp">Last run: {html_escape(row['last_run_utc'])}</p>
              <p class="timestamp">Freshness: {html_escape(row['age_minutes'])} minutes old</p>
            </section>
            """
        )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="60">
  <title>Trading Bot Monitor</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --ink: #1f2933;
      --muted: #657282;
      --line: #d8dee7;
      --panel: #ffffff;
      --waiting: #7c5f00;
      --waiting-bg: #fff6d8;
      --active: #075985;
      --active-bg: #e0f2fe;
      --ready: #166534;
      --ready-bg: #dcfce7;
      --stale: #991b1b;
      --stale-bg: #fee2e2;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--ink);
    }}
    main {{
      width: min(1120px, calc(100% - 32px));
      margin: 0 auto;
      padding: 32px 0;
    }}
    header {{
      margin-bottom: 24px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 32px;
      line-height: 1.1;
    }}
    .subtle {{
      margin: 0;
      color: var(--muted);
      line-height: 1.5;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
    }}
    .card-top {{
      display: flex;
      gap: 12px;
      align-items: start;
      justify-content: space-between;
      margin-bottom: 12px;
    }}
    h2 {{
      margin: 0;
      font-size: 20px;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      text-align: center;
      white-space: nowrap;
    }}
    .waiting .badge {{ background: var(--waiting-bg); color: var(--waiting); }}
    .active .badge {{ background: var(--active-bg); color: var(--active); }}
    .ready .badge {{ background: var(--ready-bg); color: var(--ready); }}
    .stale .badge {{ background: var(--stale-bg); color: var(--stale); }}
    .decision {{
      margin: 0 0 16px;
      color: var(--muted);
      overflow-wrap: anywhere;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }}
    .metrics div {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      min-width: 0;
    }}
    strong {{
      display: block;
      font-size: 20px;
      line-height: 1.1;
      overflow-wrap: anywhere;
    }}
    span {{
      display: block;
      margin-top: 4px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.25;
    }}
    .timestamp {{
      margin: 0;
      color: var(--muted);
      font-size: 13px;
      overflow-wrap: anywhere;
    }}
    .next {{
      margin-top: 16px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
    }}
    code {{
      display: inline-block;
      margin-top: 6px;
      padding: 4px 6px;
      background: #eef2f7;
      border-radius: 6px;
      font-size: 13px;
      overflow-wrap: anywhere;
    }}
    @media (max-width: 780px) {{
      main {{ width: min(100% - 20px, 1120px); padding: 20px 0; }}
      .grid {{ grid-template-columns: 1fr; }}
      .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .card-top {{ flex-direction: column; }}
      .badge {{ white-space: normal; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Trading Bot Monitor</h1>
      <p class="subtle">Updated {html_escape(datetime.now(timezone.utc).isoformat())}. Paper monitoring only; no real trades are placed.</p>
    </header>
    <div class="grid">
      {''.join(cards)}
    </div>
    <section class="next">
      <h2>Next Action</h2>
      <p>{html_escape(next_action)}</p>
      <p>This browser page refreshes itself every 60 seconds. The data changes when the Terminal monitor completes a cycle.</p>
      <p>Keep the combined monitor running:</p>
      <code>work/run_combined_paper_monitor.sh</code>
      <p>Read the no-trade explainers:</p>
      <code>outputs/stable_rules_signal_frequency_report.md</code>
      <code>outputs/pair_candidate_signal_frequency_report.md</code>
    </section>
  </main>
</body>
</html>
"""
    HTML_OUTPUT.write_text(html, encoding="utf-8")


def write_alerts(rows: list[dict[str, str]]) -> None:
    alerts = []
    for row in rows:
        monitor = row["monitor"]
        try:
            if float(row["age_minutes"]) > 20:
                alerts.append(f"- {monitor}: monitor data is stale ({row['age_minutes']} minutes old).")
        except ValueError:
            alerts.append(f"- {monitor}: monitor has not produced a valid timestamp yet.")
        if int(row["latest_paper_orders"]) > 0:
            alerts.append(f"- {monitor}: fresh paper order signal detected. Check open positions and readiness before doing anything else.")
        if int(row["latest_blocked_signals"]) > 0:
            alerts.append(f"- {monitor}: {row['latest_blocked_signals']} fresh signal(s) blocked by quarantine.")
        if int(row["open_positions"]) > 0:
            alerts.append(f"- {monitor}: open paper position detected.")
        if row["readiness"] == "READY FOR TINY LIVE PILOT":
            alerts.append(f"- {monitor}: readiness changed to READY FOR TINY LIVE PILOT. Review manually before any live step.")
        if monitor == "Experimental pair candidates" and int(row["latest_paper_orders"]) == 0 and int(row["open_positions"]) == 0:
            alerts.append(f"- {monitor}: {pair_signal_drought_note()}")

    if not alerts:
        alerts = ["- No attention items right now. Keep the combined monitor running."]

    lines = [
        "# Trading Bot Monitor Alerts",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        *alerts,
        "",
    ]
    ALERT_OUTPUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    rows = build_rows()
    any_orders = any(int(row["paper_orders"]) > 0 for row in rows)
    next_action = write_decision_brief(rows)
    if not any_orders:
        next_action = "Keep both monitors running; neither track has produced a paper order yet."

    lines = [
        "# Trading Bot Monitor Overview",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This is the single summary for the paper tracks. None of these tracks places real trades.",
        "",
        "## Monitor Comparison",
        "",
        markdown_table(
            rows,
            [
                "monitor",
                "last_run_utc",
                "age_minutes",
                "latest_decisions",
                "journal_rows",
                "paper_orders",
                "open_positions",
                "closed_trades",
                "closed_pnl",
                "readiness",
            ],
        ),
        "",
        "## What Each Track Means",
        "",
        *[f"- {monitor['name']}: {monitor['role']}" for monitor in MONITORS],
        "",
        "## Experimental Pair No-Trade Check",
        "",
        pair_signal_drought_note(),
        "",
        "## Next Action",
        "",
        next_action,
        "",
        "Use this one command to run all paper tracks and refresh this overview:",
        "",
        "- Combined monitor: `work/run_combined_paper_monitor.sh`",
        "- One-time combined check: `work/run_all_paper_checks.sh`",
        "",
        "The older individual runners still work if you ever want to inspect one track by itself:",
        "",
        "- Original stable only: `work/run_paper_monitor.sh`",
        "- Experimental pair only: `work/run_pair_candidate_paper_monitor.sh`",
        "",
        "Useful files:",
        "",
        "- Original dashboard: `outputs/paper_stable_dashboard.md`",
        "- Experimental dashboard: `outputs/pair_candidate_dashboard.md`",
        "- Advanced sniper dashboard: `outputs/advanced_sniper_dashboard.md`",
        "- Original no-trade explainer: `outputs/stable_rules_signal_frequency_report.md`",
        "- Experimental no-trade explainer: `outputs/pair_candidate_signal_frequency_report.md`",
        "- Plain decision brief: `outputs/decision_brief.md`",
        "- Advanced accuracy report: `outputs/advanced_accuracy_report.md`",
        "- Paper performance report: `outputs/paper_performance_report.md`",
        "- Pair validation report: `outputs/stable_rules_pair_validation_report.md`",
        "- Go-live readiness files stay NOT READY until paper orders and closed trades exist.",
        "",
    ]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    write_html_dashboard(rows, next_action)
    write_alerts(rows)
    print(f"Saved monitor overview to {OUTPUT}")
    print(f"Saved monitor dashboard to {HTML_OUTPUT}")
    print(f"Saved monitor alerts to {ALERT_OUTPUT}")
    print(f"Saved decision brief to {DECISION_BRIEF_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
