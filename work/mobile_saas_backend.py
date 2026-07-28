#!/usr/bin/env python3
"""Build the mobile auto-trading SaaS backend skeleton and reports."""

from __future__ import annotations

import argparse
import csv
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "outputs"
DB_PATH = OUTPUTS / "mobile_saas_app.db"
REPORT_PATH = OUTPUTS / "mobile_saas_backend_report.md"
ADMIN_HTML_PATH = OUTPUTS / "mobile_saas_admin.html"
TRADING_GUIDE_PATH = ROOT / "docs" / "HOW_TO_BEGIN_TRADING.md"


@dataclass(frozen=True)
class ProductGate:
    live_execution_allowed: bool
    reason: str


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    referral_code TEXT NOT NULL UNIQUE,
    referred_by_code TEXT,
    created_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    plan_name TEXT NOT NULL,
    monthly_price_usd REAL NOT NULL,
    status TEXT NOT NULL,
    current_period_start_utc TEXT NOT NULL,
    current_period_end_utc TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS deriv_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    connection_type TEXT NOT NULL,
    deriv_account_id TEXT,
    account_mode TEXT NOT NULL,
    api_scope_summary TEXT NOT NULL,
    partner_signup_embedded INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS auto_trade_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    enabled_requested INTEGER NOT NULL DEFAULT 0,
    live_execution_allowed INTEGER NOT NULL DEFAULT 0,
    strategy_group TEXT NOT NULL,
    max_daily_loss_pct REAL NOT NULL,
    max_open_trades INTEGER NOT NULL,
    max_risk_per_trade_pct REAL NOT NULL,
    emergency_stop_rule TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS referral_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    referrer_user_id INTEGER NOT NULL,
    referred_user_id INTEGER NOT NULL,
    registration_fee_usd REAL NOT NULL,
    referral_percent REAL NOT NULL,
    referral_fee_usd REAL NOT NULL,
    status TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    FOREIGN KEY(referrer_user_id) REFERENCES users(id),
    FOREIGN KEY(referred_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS profit_share_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    period_start_utc TEXT NOT NULL,
    period_end_utc TEXT NOT NULL,
    gross_profit_usd REAL NOT NULL,
    carried_loss_usd REAL NOT NULL,
    net_profit_after_carry_usd REAL NOT NULL,
    performance_fee_percent REAL NOT NULL,
    fee_due_usd REAL NOT NULL,
    status TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS live_trading_gate (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    live_execution_allowed INTEGER NOT NULL,
    gate_reason TEXT NOT NULL,
    checked_at_utc TEXT NOT NULL
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def detect_live_gate() -> ProductGate:
    readiness = read_text(OUTPUTS / "live_readiness_checklist.md").upper()
    manual = read_text(OUTPUTS / "manual_review_package.md").upper()
    if "NOT READY" in readiness:
        return ProductGate(False, "Live-readiness checklist still says NOT READY.")
    if "MANUAL REVIEW PASS" not in manual:
        return ProductGate(False, "Manual review has not approved live execution.")
    return ProductGate(True, "Readiness and manual review appear to pass. Human approval is still required.")


def connect() -> sqlite3.Connection:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def seed_demo(conn: sqlite3.Connection, gate: ProductGate) -> None:
    now = utc_now()
    users = [
        ("founder@example.com", "Founder Admin", "TA-FOUNDER", None),
        ("demo.user@example.com", "Demo Subscriber", "TA-4821", "TA-FOUNDER"),
    ]
    for email, name, code, referred_by in users:
        conn.execute(
            """
            INSERT OR IGNORE INTO users (email, full_name, referral_code, referred_by_code, created_at_utc)
            VALUES (?, ?, ?, ?, ?)
            """,
            (email, name, code, referred_by, now),
        )

    founder_id = conn.execute("SELECT id FROM users WHERE email = ?", ("founder@example.com",)).fetchone()["id"]
    demo_id = conn.execute("SELECT id FROM users WHERE email = ?", ("demo.user@example.com",)).fetchone()["id"]

    conn.execute(
        """
        INSERT OR IGNORE INTO subscriptions
        (user_id, plan_name, monthly_price_usd, status, current_period_start_utc, current_period_end_utc)
        VALUES (?, 'Auto Trader', 50.0, 'demo_active', ?, ?)
        """,
        (demo_id, now, "pending_payment_processor"),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO deriv_connections
        (user_id, connection_type, deriv_account_id, account_mode, api_scope_summary, partner_signup_embedded, status, created_at_utc)
        VALUES (?, 'manual_api_token', 'CR-DEMO-PENDING', 'demo', 'read/trade planned; admin avoided', 1, 'demo_connected_live_locked', ?)
        """,
        (demo_id, now),
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO auto_trade_settings
        (user_id, enabled_requested, live_execution_allowed, strategy_group, max_daily_loss_pct, max_open_trades,
         max_risk_per_trade_pct, emergency_stop_rule, updated_at_utc)
        VALUES (?, 1, ?, 'strict_approved_candidates_only', 2.0, 1, 0.5, 'stop_after_one_live_loss_or_execution_error', ?)
        """,
        (demo_id, int(gate.live_execution_allowed), now),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO referral_ledger
        (referrer_user_id, referred_user_id, registration_fee_usd, referral_percent, referral_fee_usd, status, created_at_utc)
        VALUES (?, ?, 50.0, 5.0, 2.5, 'pending_real_payment', ?)
        """,
        (founder_id, demo_id, now),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO profit_share_ledger
        (user_id, period_start_utc, period_end_utc, gross_profit_usd, carried_loss_usd,
         net_profit_after_carry_usd, performance_fee_percent, fee_due_usd, status, created_at_utc)
        VALUES (?, ?, 'pending_period_close', 0.0, 0.0, 0.0, 20.0, 0.0, 'tracking_only_not_billable', ?)
        """,
        (demo_id, now, now),
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO live_trading_gate (id, live_execution_allowed, gate_reason, checked_at_utc)
        VALUES (1, ?, ?, ?)
        """,
        (int(gate.live_execution_allowed), gate.reason, now),
    )
    conn.commit()


def table_rows(conn: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    return list(conn.execute(f"SELECT * FROM {table} ORDER BY id"))


def write_csv_exports(conn: sqlite3.Connection) -> None:
    for table in [
        "users",
        "subscriptions",
        "deriv_connections",
        "auto_trade_settings",
        "referral_ledger",
        "profit_share_ledger",
        "live_trading_gate",
    ]:
        rows = table_rows(conn, table)
        path = OUTPUTS / f"mobile_saas_{table}.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            if not rows:
                continue
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows([dict(row) for row in rows])


def md_table(rows: list[sqlite3.Row], columns: list[str]) -> str:
    if not rows:
        return "No rows yet.\n"
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row[col]) for col in columns) + " |")
    return "\n".join(lines) + "\n"


def write_report(conn: sqlite3.Connection, gate: ProductGate) -> None:
    users = table_rows(conn, "users")
    subs = table_rows(conn, "subscriptions")
    connections = table_rows(conn, "deriv_connections")
    settings = table_rows(conn, "auto_trade_settings")
    referrals = table_rows(conn, "referral_ledger")
    profit = table_rows(conn, "profit_share_ledger")

    report = f"""# Mobile SaaS Backend Report

Last updated UTC: {utc_now()}

This backend skeleton supports the auto-trading business app. It is still a local prototype.

## Live Trading Gate

- Allowed: **{gate.live_execution_allowed}**
- Reason: {gate.reason}

## Users

{md_table(users, ["id", "email", "full_name", "referral_code", "referred_by_code"])}
## Subscriptions

{md_table(subs, ["id", "user_id", "plan_name", "monthly_price_usd", "status"])}
## Deriv Connections

{md_table(connections, ["id", "user_id", "connection_type", "deriv_account_id", "account_mode", "status"])}
## Auto-Trade Settings

{md_table(settings, ["user_id", "enabled_requested", "live_execution_allowed", "strategy_group", "max_daily_loss_pct", "max_open_trades", "max_risk_per_trade_pct"])}
## Referral Ledger

{md_table(referrals, ["id", "referrer_user_id", "referred_user_id", "registration_fee_usd", "referral_percent", "referral_fee_usd", "status"])}
## Profit-Share Ledger

{md_table(profit, ["id", "user_id", "gross_profit_usd", "carried_loss_usd", "net_profit_after_carry_usd", "performance_fee_percent", "fee_due_usd", "status"])}
## Rule

Real Deriv trading remains blocked until the live-readiness checklist and manual review both approve it.
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def write_admin_html(conn: sqlite3.Connection, gate: ProductGate) -> None:
    rows = {
        "Users": table_rows(conn, "users"),
        "Subscriptions": table_rows(conn, "subscriptions"),
        "Deriv Connections": table_rows(conn, "deriv_connections"),
        "Auto-Trade Settings": table_rows(conn, "auto_trade_settings"),
        "Referral Ledger": table_rows(conn, "referral_ledger"),
        "Profit-Share Ledger": table_rows(conn, "profit_share_ledger"),
    }

    def render_table(items: list[sqlite3.Row]) -> str:
        if not items:
            return "<p>No rows yet.</p>"
        cols = list(items[0].keys())
        head = "".join(f"<th>{col}</th>" for col in cols)
        body = "".join("<tr>" + "".join(f"<td>{row[col]}</td>" for col in cols) + "</tr>" for row in items)
        return f"<div class='table-wrap'><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"

    sections = "\n".join(f"<section class='card'><h2>{name}</h2>{render_table(items)}</section>" for name, items in rows.items())
    gate_class = "ok" if gate.live_execution_allowed else "bad"
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TradePilot Auto Admin</title>
  <style>
    :root {{ --bg:#f5f7fb; --panel:#fff; --ink:#111827; --muted:#64748b; --line:#d8e0ec; --bad:#991b1b; --badbg:#fee2e2; --ok:#166534; --okbg:#dcfce7; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:var(--bg); color:var(--ink); }}
    main {{ max-width:1180px; margin:0 auto; padding:22px 14px; }}
    h1 {{ margin:0 0 6px; }}
    p {{ color:var(--muted); }}
    .gate {{ border-radius:8px; padding:13px; font-weight:900; margin:14px 0; }}
    .bad {{ background:var(--badbg); border:1px solid #fecaca; color:var(--bad); }}
    .ok {{ background:var(--okbg); border:1px solid #bbf7d0; color:var(--ok); }}
    .grid {{ display:grid; gap:12px; }}
    .card {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:14px; overflow:hidden; }}
    .table-wrap {{ overflow:auto; }}
    table {{ width:100%; border-collapse:collapse; min-width:760px; }}
    th,td {{ border-bottom:1px solid var(--line); padding:9px; text-align:left; font-size:13px; vertical-align:top; }}
    th {{ color:var(--muted); }}
  </style>
</head>
<body>
  <main>
    <h1>TradePilot Auto Admin</h1>
    <p>Subscription, Deriv connection, referral, profit-share, and auto-trading records.</p>
    <div class="gate {gate_class}">Live trading allowed: {gate.live_execution_allowed}. {gate.reason}</div>
    <div class="grid">{sections}</div>
  </main>
</body>
</html>
"""
    ADMIN_HTML_PATH.write_text(html, encoding="utf-8")


def write_trading_guide(gate: ProductGate) -> None:
    guide = f"""# How To Begin Trading

Current status: **{"LIVE EXECUTION MAY BE REVIEWED" if gate.live_execution_allowed else "DO NOT TRADE REAL MONEY YET"}**

Reason: {gate.reason}

## Start Safely Now

1. Run the paper monitor.
2. Open the mobile app preview.
3. Use demo mode first.
4. Connect only a demo Deriv account/token while testing.
5. Confirm the bot opens, manages, and closes demo trades correctly.
6. Keep checking the live-readiness checklist.

## Commands

Start the full paper suite:

```bash
cd /path/to/netzarabot
work/start_trading_bot_suite.sh
```

Check status:

```bash
cd /path/to/netzarabot
work/check_bot_status.sh
```

Open the local app:

```bash
cd /path/to/netzarabot
work/start_local_app.sh
```

## Deriv Connection

New user:

- Tap `Create Deriv account`.
- The app opens the embedded partner/signup path.
- The raw affiliate link is not shown on-screen.

Existing user:

- Use Deriv OAuth when available.
- For manual testing, create a Deriv API token in Deriv and paste it into the app.
- Avoid Admin permission.
- Use demo first.

## Before Real Live Trading

Do not use a real-money token until all are true:

- Live-readiness checklist no longer says NOT READY.
- Manual review approves the exact strategy/rule set.
- Auto-trade settings have max daily loss, max open trades, and emergency stop enabled.
- Terms, risk disclosure, subscription agreement, and profit-share agreement are ready.
- You test the same flow on Deriv demo first.

## First Real Pilot When Approved

When approved, start tiny:

- One user account only.
- One strategy only.
- One symbol/timeframe only.
- Smallest possible stake.
- Stop after one loss, one error, or any unexpected order behavior.
"""
    TRADING_GUIDE_PATH.write_text(guide, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-demo", action="store_true", help="Insert demo records if they do not exist.")
    args = parser.parse_args()

    gate = detect_live_gate()
    with connect() as conn:
        if args.seed_demo:
            seed_demo(conn, gate)
        else:
            conn.execute(
                """
                INSERT OR REPLACE INTO live_trading_gate (id, live_execution_allowed, gate_reason, checked_at_utc)
                VALUES (1, ?, ?, ?)
                """,
                (int(gate.live_execution_allowed), gate.reason, utc_now()),
            )
            conn.commit()
        write_csv_exports(conn)
        write_report(conn, gate)
        write_admin_html(conn, gate)
    write_trading_guide(gate)

    print(f"Saved SaaS database: {DB_PATH}")
    print(f"Saved backend report: {REPORT_PATH}")
    print(f"Saved admin dashboard: {ADMIN_HTML_PATH}")
    print(f"Saved trading guide: {TRADING_GUIDE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
