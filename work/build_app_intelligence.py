from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


TASK_ROOT = Path("/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot")
OUTPUT_DIR = TASK_ROOT / "outputs"

PROMOTION_OUTPUT = OUTPUT_DIR / "auto_promotion_gate.md"
TRADE_EXPLAINER_OUTPUT = OUTPUT_DIR / "trade_explainer.md"
SHADOW_OUTPUT = OUTPUT_DIR / "shadow_retest_report.md"
LOSS_OUTPUT = OUTPUT_DIR / "loss_pattern_report.md"
EXIT_OUTPUT = OUTPUT_DIR / "paper_exit_optimizer.md"
EXPANSION_OUTPUT = OUTPUT_DIR / "instrument_expansion_plan.md"
CONTROL_PANEL_OUTPUT = OUTPUT_DIR / "control_panel.html"
APP_INTELLIGENCE_OUTPUT = OUTPUT_DIR / "app_intelligence_summary.md"


TRACKS = [
    {
        "name": "Original stable rules",
        "short": "original",
        "status": OUTPUT_DIR / "paper_stable_status.csv",
        "decisions": OUTPUT_DIR / "paper_stable_rules_decisions.csv",
        "open": OUTPUT_DIR / "paper_stable_open_positions.csv",
        "closed": OUTPUT_DIR / "paper_stable_closed_trades.csv",
        "dashboard": OUTPUT_DIR / "paper_stable_dashboard.md",
        "data_dir": OUTPUT_DIR / "paper_refreshed_data",
        "loss_limit": -60.0,
    },
    {
        "name": "Experimental pair candidates",
        "short": "experimental",
        "status": OUTPUT_DIR / "pair_candidate_status.csv",
        "decisions": OUTPUT_DIR / "pair_candidate_paper_decisions.csv",
        "open": OUTPUT_DIR / "pair_candidate_open_positions.csv",
        "closed": OUTPUT_DIR / "pair_candidate_closed_trades.csv",
        "dashboard": OUTPUT_DIR / "pair_candidate_dashboard.md",
        "data_dir": OUTPUT_DIR / "pair_candidate_refreshed_data",
        "loss_limit": -60.0,
    },
    {
        "name": "Advanced sniper candidates",
        "short": "sniper",
        "status": OUTPUT_DIR / "advanced_sniper_status.csv",
        "decisions": OUTPUT_DIR / "advanced_sniper_paper_decisions.csv",
        "open": OUTPUT_DIR / "advanced_sniper_open_positions.csv",
        "closed": OUTPUT_DIR / "advanced_sniper_closed_trades.csv",
        "dashboard": OUTPUT_DIR / "advanced_sniper_dashboard.md",
        "data_dir": OUTPUT_DIR / "pair_candidate_refreshed_data",
        "loss_limit": -60.0,
    },
]


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def metric(df: pd.DataFrame, key: str, default: str = "0") -> str:
    if df.empty or "metric" not in df.columns or "value" not in df.columns:
        return default
    rows = df[df["metric"] == key]
    if rows.empty:
        return default
    value = rows.iloc[-1]["value"]
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def as_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def markdown_table(rows: list[dict[str, object]], columns: list[str], empty: str) -> str:
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


def data_path(data_dir: Path, symbol: str, timeframe: str) -> Path:
    safe = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in str(symbol))
    return data_dir / f"deriv_{safe}_{timeframe}.csv"


def track_state(track: dict[str, object]) -> dict[str, object]:
    status = load_csv(Path(track["status"]))
    open_positions = load_csv(Path(track["open"]))
    closed = load_csv(Path(track["closed"]))
    decisions = load_csv(Path(track["decisions"]))
    closed_pnl = as_float(metric(status, "closed_pnl", "0"))
    closed_trades = as_int(metric(status, "closed_trades", str(0 if closed.empty else len(closed))))
    open_count = as_int(metric(status, "open_positions", str(0 if open_positions.empty else len(open_positions))))
    latest_orders = as_int(metric(status, "latest_paper_orders", "0"))
    blocked = as_int(metric(status, "latest_blocked_signals", "0"))
    paper_orders = int((decisions["decision"] == "paper_order").sum()) if not decisions.empty and "decision" in decisions else 0
    wins = 0
    losses = 0
    if not closed.empty and "paper_pnl" in closed:
        pnl = pd.to_numeric(closed["paper_pnl"], errors="coerce").fillna(0.0)
        wins = int((pnl > 0).sum())
        losses = int((pnl < 0).sum())
    return {
        "track": track["name"],
        "short": track["short"],
        "last_run_utc": metric(status, "last_run_utc", "not run"),
        "latest_decisions": metric(status, "latest_decisions", "none"),
        "latest_orders": latest_orders,
        "blocked_signals": blocked,
        "paper_orders_seen": paper_orders,
        "open_positions": open_count,
        "closed_trades": closed_trades,
        "closed_pnl": closed_pnl,
        "wins": wins,
        "losses": losses,
        "loss_limit": float(track["loss_limit"]),
    }


def promotion_decision(state: dict[str, object]) -> tuple[str, str]:
    pnl = float(state["closed_pnl"])
    closed = int(state["closed_trades"])
    open_count = int(state["open_positions"])
    if state["track"] == "Original stable rules" and pnl <= state["loss_limit"]:
        return "REJECT / QUARANTINE", "Closed paper PnL is beyond the loss limit."
    if pnl <= state["loss_limit"]:
        return "REJECT / QUARANTINE", "Closed paper PnL is beyond the loss limit."
    if open_count > 0:
        return "WAIT", "There is still an open paper trade."
    if closed < 10:
        return "KEEP PAPER TESTING", "There are fewer than 10 closed paper trades."
    if pnl <= 0:
        return "REJECT FOR NOW", "Closed paper PnL is not positive."
    if closed >= 20 and pnl > 0:
        return "ELIGIBLE FOR MANUAL REVIEW", "Enough trades and positive paper PnL, but manual review is still required."
    return "KEEP PAPER TESTING", "Needs a larger paper sample before any live step."


def write_auto_promotion_gate(states: list[dict[str, object]]) -> None:
    rows = []
    for state in states:
        decision, reason = promotion_decision(state)
        rows.append(
            {
                "track": state["track"],
                "decision": decision,
                "reason": reason,
                "closed_trades": state["closed_trades"],
                "closed_pnl": f"{state['closed_pnl']:.2f}",
                "open_positions": state["open_positions"],
            }
        )
    lines = [
        "# Auto-Promotion Gate",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This file decides what each paper track is allowed to become. It does not place trades.",
        "",
        markdown_table(rows, ["track", "decision", "reason", "closed_trades", "closed_pnl", "open_positions"], "No tracks found."),
        "",
        "Rules:",
        "",
        "- Losing tracks are quarantined.",
        "- Tracks with open paper trades must wait.",
        "- Tracks with fewer than 10 closed paper trades stay in paper testing.",
        "- No track can move toward live trading with negative closed paper PnL.",
        "",
    ]
    PROMOTION_OUTPUT.write_text("\n".join(lines), encoding="utf-8")


def explain_decision(row: pd.Series, track_name: str) -> dict[str, object]:
    decision = str(row.get("decision", ""))
    side = str(row.get("side", ""))
    reason = str(row.get("reason", ""))
    if decision == "paper_order":
        plain = f"{track_name} saw a {side.upper()} setup because {reason}."
        action = "Paper-only. Watch whether the stop, target, or time exit closes it better."
    else:
        plain = f"{track_name} did not trade this symbol. Reason: {reason}."
        action = "No action needed."
    return {
        "track": track_name,
        "symbol": row.get("symbol", ""),
        "timeframe": row.get("timeframe", ""),
        "decision": decision,
        "side": side,
        "plain_explanation": plain,
        "what_to_watch": action,
    }


def write_trade_explainer() -> None:
    rows = []
    for track in TRACKS:
        decisions = load_csv(Path(track["decisions"]))
        if decisions.empty:
            continue
        for _, row in decisions.iterrows():
            rows.append(explain_decision(row, str(track["name"])))

    open_rows = []
    for track in TRACKS:
        open_positions = load_csv(Path(track["open"]))
        if open_positions.empty:
            continue
        for _, row in open_positions.iterrows():
            open_rows.append(
                {
                    "track": track["name"],
                    "symbol": row.get("symbol", ""),
                    "side": row.get("side", ""),
                    "entry": row.get("entry", ""),
                    "stop_loss": row.get("stop_loss", ""),
                    "take_profit": row.get("take_profit", ""),
                    "explanation": f"Open paper {row.get('side', '')} on {row.get('symbol', '')}; risk is controlled by its stop loss and it must close before promotion.",
                }
            )

    lines = [
        "# Trade Explainer",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Latest Decisions",
        "",
        markdown_table(rows, ["track", "symbol", "timeframe", "decision", "side", "plain_explanation", "what_to_watch"], "No decisions found."),
        "",
        "## Open Paper Trades",
        "",
        markdown_table(open_rows, ["track", "symbol", "side", "entry", "stop_loss", "take_profit", "explanation"], "No open paper trades."),
        "",
    ]
    TRADE_EXPLAINER_OUTPUT.write_text("\n".join(lines), encoding="utf-8")


def write_shadow_retest() -> None:
    latest = []
    for track in TRACKS:
        decisions = load_csv(Path(track["decisions"]))
        if decisions.empty:
            continue
        for _, row in decisions.iterrows():
            latest.append(
                {
                    "track": track["name"],
                    "symbol": row.get("symbol", ""),
                    "timeframe": row.get("timeframe", ""),
                    "decision": row.get("decision", ""),
                    "side": row.get("side", ""),
                    "reason": row.get("reason", ""),
                }
            )
    df = pd.DataFrame(latest)
    rows = []
    if not df.empty:
        for (symbol, timeframe), group in df.groupby(["symbol", "timeframe"]):
            orders = group[group["decision"] == "paper_order"]
            rows.append(
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "tracks_compared": len(group),
                    "tracks_with_orders": len(orders),
                    "order_tracks": ", ".join(orders["track"].astype(str).tolist()) if not orders.empty else "none",
                    "sides": ", ".join(orders["side"].astype(str).tolist()) if not orders.empty else "none",
                    "shadow_read": "agreement" if len(set(orders["side"].astype(str))) == 1 and len(orders) > 1 else "mixed/no signal",
                }
            )

    lines = [
        "# Shadow Re-Test Report",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This compares what each track would do on the latest candles.",
        "",
        markdown_table(rows, ["symbol", "timeframe", "tracks_compared", "tracks_with_orders", "order_tracks", "sides", "shadow_read"], "No latest decisions found."),
        "",
        "Use this to see whether the stricter sniper layer agrees with or improves on the older tracks.",
        "",
    ]
    SHADOW_OUTPUT.write_text("\n".join(lines), encoding="utf-8")


def classify_loss(row: pd.Series) -> str:
    reason = str(row.get("exit_reason", "")).lower()
    pnl = as_float(row.get("paper_pnl", 0.0))
    if pnl >= 0:
        return "not a loss"
    if "stop" in reason:
        return "stop hit: entry timing or direction likely wrong"
    if "time" in reason:
        return "time exit loss: trade did not move fast enough"
    return "loss: needs manual review"


def write_loss_pattern_report() -> None:
    rows = []
    grouped = []
    for track in TRACKS:
        closed = load_csv(Path(track["closed"]))
        if closed.empty or "paper_pnl" not in closed:
            continue
        closed = closed.copy()
        closed["paper_pnl_num"] = pd.to_numeric(closed["paper_pnl"], errors="coerce").fillna(0.0)
        losses = closed[closed["paper_pnl_num"] < 0]
        for _, row in losses.tail(10).iterrows():
            rows.append(
                {
                    "track": track["name"],
                    "symbol": row.get("symbol", ""),
                    "side": row.get("side", ""),
                    "paper_pnl": f"{as_float(row.get('paper_pnl', 0.0)):.2f}",
                    "exit_reason": row.get("exit_reason", ""),
                    "pattern": classify_loss(row),
                }
            )
        if not losses.empty:
            grouped.append(
                {
                    "track": track["name"],
                    "losses": len(losses),
                    "stop_losses": int(losses["exit_reason"].fillna("").str.contains("stop", case=False).sum()),
                    "time_exit_losses": int(losses["exit_reason"].fillna("").str.contains("time", case=False).sum()),
                    "avg_loss": f"{float(losses['paper_pnl_num'].mean()):.2f}",
                }
            )

    lines = [
        "# Loss Pattern Analyzer",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Loss Summary",
        "",
        markdown_table(grouped, ["track", "losses", "stop_losses", "time_exit_losses", "avg_loss"], "No closed losses found."),
        "",
        "## Recent Loss Explanations",
        "",
        markdown_table(rows, ["track", "symbol", "side", "paper_pnl", "exit_reason", "pattern"], "No recent losses found."),
        "",
    ]
    LOSS_OUTPUT.write_text("\n".join(lines), encoding="utf-8")


def load_candles(track: dict[str, object], symbol: str, timeframe: str) -> pd.DataFrame:
    path = data_path(Path(track["data_dir"]), symbol, timeframe)
    df = load_csv(path)
    if df.empty or "timestamp" not in df:
        return pd.DataFrame()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df.sort_values("timestamp")


def exit_alternatives_for_trade(track: dict[str, object], trade: pd.Series) -> dict[str, object]:
    symbol = str(trade.get("symbol", ""))
    timeframe = str(trade.get("timeframe", ""))
    side = str(trade.get("side", ""))
    entry = as_float(trade.get("entry", 0.0))
    stop = as_float(trade.get("stop_loss", 0.0))
    opened_at = pd.to_datetime(trade.get("opened_at", ""), utc=True, errors="coerce")
    closed_at = pd.to_datetime(trade.get("closed_at", ""), utc=True, errors="coerce")
    quantity = as_float(trade.get("quantity", 0.0))
    base_pnl = as_float(trade.get("paper_pnl", 0.0))
    if entry <= 0 or stop <= 0 or pd.isna(opened_at) or pd.isna(closed_at) or quantity <= 0:
        return {"track": track["name"], "symbol": symbol, "actual_pnl": f"{base_pnl:.2f}", "best_exit": "not enough data"}

    candles = load_candles(track, symbol, timeframe)
    if candles.empty:
        return {"track": track["name"], "symbol": symbol, "actual_pnl": f"{base_pnl:.2f}", "best_exit": "missing candles"}
    future = candles[(candles["timestamp"] > opened_at) & (candles["timestamp"] <= closed_at)]
    if future.empty:
        return {"track": track["name"], "symbol": symbol, "actual_pnl": f"{base_pnl:.2f}", "best_exit": "no future candles"}

    risk_distance = abs(entry - stop)
    candidates = {"actual": base_pnl}
    for label, multiple in {"fixed_1r": 1.0, "fixed_1_5r": 1.5, "fixed_2r": 2.0}.items():
        target = entry + risk_distance * multiple if side == "buy" else entry - risk_distance * multiple
        hit_target = bool((future["high"] >= target).any()) if side == "buy" else bool((future["low"] <= target).any())
        hit_stop = bool((future["low"] <= stop).any()) if side == "buy" else bool((future["high"] >= stop).any())
        if hit_target and not hit_stop:
            pnl = risk_distance * multiple * quantity
        elif hit_stop and not hit_target:
            pnl = -risk_distance * quantity
        elif hit_target and hit_stop:
            pnl = -risk_distance * quantity
        else:
            last = as_float(future["close"].iloc[-1])
            pnl = (last - entry) * quantity
            if side == "sell":
                pnl *= -1
        candidates[label] = pnl

    best_label, best_pnl = max(candidates.items(), key=lambda item: item[1])
    return {
        "track": track["name"],
        "symbol": symbol,
        "side": side,
        "actual_pnl": f"{base_pnl:.2f}",
        "best_exit": best_label,
        "best_pnl": f"{best_pnl:.2f}",
        "difference": f"{best_pnl - base_pnl:.2f}",
    }


def write_exit_optimizer() -> None:
    rows = []
    for track in TRACKS:
        closed = load_csv(Path(track["closed"]))
        if closed.empty:
            continue
        for _, trade in closed.tail(8).iterrows():
            rows.append(exit_alternatives_for_trade(track, trade))

    lines = [
        "# Paper Exit Optimizer",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This checks whether simple fixed-R exits would have beaten the actual paper exit on recent closed trades.",
        "",
        markdown_table(rows, ["track", "symbol", "side", "actual_pnl", "best_exit", "best_pnl", "difference"], "No closed trades available."),
        "",
        "Treat this as research only. Exit changes still need backtesting and paper testing.",
        "",
    ]
    EXIT_OUTPUT.write_text("\n".join(lines), encoding="utf-8")


def write_instrument_expansion_plan() -> None:
    approved = load_csv(OUTPUT_DIR / "advanced_accuracy_execution_candidates.csv")
    rows = []
    if not approved.empty:
        for symbol, group in approved.groupby("symbol"):
            rows.append(
                {
                    "symbol": symbol,
                    "approved_rules": len(group),
                    "best_profit_factor": f"{pd.to_numeric(group['profit_factor'], errors='coerce').max():.2f}",
                    "next_step": "paper-test sniper rules, then test sibling Boom/Crash symbols",
                }
            )
    plan = [
        {"family": "Boom/Crash", "timeframes": "1m, 5m, 15m, 30m", "status": "next expansion target"},
        {"family": "Volatility indices", "timeframes": "5m, 15m, 30m", "status": "after Boom/Crash sniper rules stabilize"},
        {"family": "Forex", "timeframes": "5m, 15m, 1h", "status": "separate profile required"},
        {"family": "Crypto", "timeframes": "5m, 15m, 1h", "status": "separate volatility limits required"},
        {"family": "Commodities", "timeframes": "15m, 1h", "status": "lower priority"},
    ]
    lines = [
        "# Instrument Expansion Plan",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "The app should expand only from rules that survive the sniper gate, not from losing tracks.",
        "",
        "## Current Strong Base",
        "",
        markdown_table(rows, ["symbol", "approved_rules", "best_profit_factor", "next_step"], "No sniper-approved symbols yet."),
        "",
        "## Expansion Queue",
        "",
        markdown_table(plan, ["family", "timeframes", "status"], "No expansion queue."),
        "",
        "## Completed Expansion Research",
        "",
        "- Boom/Crash expansion report: `outputs/boom_crash_expansion_report.md`",
        "- Boom/Crash expansion execution candidates: `outputs/boom_crash_expansion_execution_candidates.csv`",
        "",
        "Instruction: do not mix new instruments into the current paper ledgers. Use separate output files for each expansion batch.",
        "",
    ]
    EXPANSION_OUTPUT.write_text("\n".join(lines), encoding="utf-8")


def write_control_panel(states: list[dict[str, object]]) -> None:
    cards = []
    for state in states:
        decision, reason = promotion_decision(state)
        cls = "danger" if "REJECT" in decision or "QUARANTINE" in decision else "active" if state["open_positions"] else "waiting"
        cards.append(
            f"""
            <section class="card {cls}">
              <div class="top">
                <h2>{html_escape(state['track'])}</h2>
                <span>{html_escape(decision)}</span>
              </div>
              <p>{html_escape(reason)}</p>
              <div class="metrics">
                <div><strong>{state['open_positions']}</strong><small>Open paper trades</small></div>
                <div><strong>{state['closed_trades']}</strong><small>Closed trades</small></div>
                <div><strong>{state['closed_pnl']:.2f}</strong><small>Closed PnL</small></div>
                <div><strong>{state['latest_orders']}</strong><small>Opened this run</small></div>
              </div>
            </section>
            """
        )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="60">
  <title>Trading Bot Control Panel</title>
  <style>
    :root {{
      --bg: #f7f8fa;
      --panel: #fff;
      --ink: #17202a;
      --muted: #667085;
      --line: #d9dee7;
      --danger: #991b1b;
      --danger-bg: #fee2e2;
      --active: #075985;
      --active-bg: #e0f2fe;
      --waiting: #7c5f00;
      --waiting-bg: #fff6d8;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--bg); color: var(--ink); }}
    main {{ width: min(1180px, calc(100% - 28px)); margin: 0 auto; padding: 28px 0; }}
    h1 {{ margin: 0 0 8px; font-size: 32px; }}
    .subtle {{ color: var(--muted); margin: 0 0 20px; }}
    .banner {{ border: 1px solid var(--danger); background: var(--danger-bg); color: var(--danger); border-radius: 8px; padding: 14px; font-weight: 700; margin-bottom: 16px; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }}
    .card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; }}
    .top {{ display: flex; justify-content: space-between; gap: 10px; align-items: flex-start; }}
    h2 {{ margin: 0; font-size: 19px; }}
    span {{ border-radius: 999px; padding: 5px 9px; font-size: 12px; font-weight: 800; text-align: center; }}
    .danger span {{ background: var(--danger-bg); color: var(--danger); }}
    .active span {{ background: var(--active-bg); color: var(--active); }}
    .waiting span {{ background: var(--waiting-bg); color: var(--waiting); }}
    p {{ color: var(--muted); line-height: 1.45; }}
    .metrics {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }}
    .metrics div {{ border: 1px solid var(--line); border-radius: 8px; padding: 10px; }}
    strong {{ display: block; font-size: 22px; }}
    small {{ color: var(--muted); }}
    .links {{ margin-top: 16px; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; }}
    code {{ display: block; background: #eef2f7; border-radius: 6px; padding: 6px; margin: 6px 0; overflow-wrap: anywhere; }}
    @media (max-width: 900px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <main>
    <h1>Trading Bot Control Panel</h1>
    <p class="subtle">Updated {html_escape(datetime.now(timezone.utc).isoformat())}. Paper monitoring only.</p>
    <div class="banner">LIVE TRADING IS NOT READY. Do not add real money yet.</div>
    <div class="grid">{''.join(cards)}</div>
    <section class="links">
      <h2>Useful Reports</h2>
      <code>outputs/auto_promotion_gate.md</code>
      <code>outputs/trade_explainer.md</code>
      <code>outputs/loss_pattern_report.md</code>
      <code>outputs/paper_exit_optimizer.md</code>
      <code>outputs/shadow_retest_report.md</code>
      <code>outputs/instrument_expansion_plan.md</code>
      <code>outputs/boom_crash_expansion_report.md</code>
      <code>outputs/boom_crash_expansion_monitor_template.md</code>
      <code>outputs/self_healing_monitor_check.md</code>
      <code>outputs/best_track_leaderboard.md</code>
      <code>outputs/trade_replay_report.md</code>
      <code>outputs/rule_kill_switch_report.md</code>
      <code>outputs/candidate_promotion_queue.md</code>
      <code>outputs/daily_summary_report.md</code>
    </section>
  </main>
</body>
</html>
"""
    CONTROL_PANEL_OUTPUT.write_text(html, encoding="utf-8")


def write_summary() -> None:
    lines = [
        "# App Intelligence Summary",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Built intelligence layers:",
        "",
        "- Auto-promotion gate: `outputs/auto_promotion_gate.md`",
        "- Trade explainer: `outputs/trade_explainer.md`",
        "- Sniper dashboard upgrade / control panel: `outputs/control_panel.html`",
        "- Shadow re-test: `outputs/shadow_retest_report.md`",
        "- Loss pattern analyzer: `outputs/loss_pattern_report.md`",
        "- Paper exit optimizer: `outputs/paper_exit_optimizer.md`",
        "- Instrument expansion plan: `outputs/instrument_expansion_plan.md`",
        "- Boom/Crash expansion lab: `outputs/boom_crash_expansion_report.md`",
        "- Expansion paper monitor template: `outputs/boom_crash_expansion_monitor_template.md`",
        "- Self-healing monitor check: `outputs/self_healing_monitor_check.md`",
        "- Best track leaderboard: `outputs/best_track_leaderboard.md`",
        "- Trade replay report: `outputs/trade_replay_report.md`",
        "- Rule kill-switch report: `outputs/rule_kill_switch_report.md`",
        "- Candidate promotion queue: `outputs/candidate_promotion_queue.md`",
        "- Daily summary report: `outputs/daily_summary_report.md`",
        "- Non-technical control panel: `outputs/control_panel.html`",
        "",
        "All are paper/research only. None places live trades.",
        "",
    ]
    APP_INTELLIGENCE_OUTPUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    states = [track_state(track) for track in TRACKS]
    write_auto_promotion_gate(states)
    write_trade_explainer()
    write_shadow_retest()
    write_loss_pattern_report()
    write_exit_optimizer()
    write_instrument_expansion_plan()
    write_control_panel(states)
    write_summary()
    print(f"Saved auto-promotion gate to {PROMOTION_OUTPUT}")
    print(f"Saved trade explainer to {TRADE_EXPLAINER_OUTPUT}")
    print(f"Saved shadow re-test report to {SHADOW_OUTPUT}")
    print(f"Saved loss pattern report to {LOSS_OUTPUT}")
    print(f"Saved paper exit optimizer to {EXIT_OUTPUT}")
    print(f"Saved instrument expansion plan to {EXPANSION_OUTPUT}")
    print(f"Saved control panel to {CONTROL_PANEL_OUTPUT}")
    print(f"Saved app intelligence summary to {APP_INTELLIGENCE_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
