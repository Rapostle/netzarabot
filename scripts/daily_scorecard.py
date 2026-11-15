"""Daily NetzaraBot scorecard: honest demo-trading evidence in one Telegram message.

    python3 scripts/daily_scorecard.py --repo-root /root/netzarabot            # print only
    python3 scripts/daily_scorecard.py --repo-root /root/netzarabot --send     # print and send to Telegram

Standard library only. Read-only: it never trades.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ENV_FILE = "/root/.deriv_env"
TEST_TRACKS = {"demo-cycle-test"}
VERDICT_TRADES = 30
RULE_RE = re.compile(r"\brule\s+([A-Za-z0-9_\-]+)|(PAIR\d+)")
STATE_RE = re.compile(r"(PAIR\d+|WF\d+) is (FREEZE|KILL)")


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        return list(csv.DictReader(handle))


def parse_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat((value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def to_float(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def rule_id(reason: str) -> str:
    match = RULE_RE.search(reason or "")
    return (match.group(1) or match.group(2)) if match else "unknown"


def wilson_lower(wins: int, n: int, z: float = 1.64) -> float:
    if n == 0:
        return 0.0
    p = wins / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre - margin) / denom


def demo_summary(rows: list[dict[str, str]]) -> dict:
    trades = [r for r in rows if r.get("track_name") not in TEST_TRACKS and r.get("pnl") not in (None, "")]
    pnls = [to_float(r["pnl"]) for r in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    n = len(pnls)
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0.0
    breakeven = avg_loss / (avg_win + avg_loss) if (avg_win + avg_loss) > 0 else 0.5
    return {"n": n, "wins": len(wins), "losses": len(losses), "net": sum(pnls), "breakeven": breakeven,
            "lower": wilson_lower(len(wins), n), "win_rate": len(wins) / n if n else 0.0}


def verdict(s: dict) -> str:
    if s["n"] < VERDICT_TRADES:
        return f"too early to judge ({s['n']} of {VERDICT_TRADES} trades)"
    if s["lower"] > s["breakeven"] and s["net"] > 0:
        return "demo evidence of an edge (win rate clearly above break-even)"
    if s["win_rate"] < s["breakeven"] or s["net"] <= 0:
        return "no edge shown: results are at or below break-even"
    return "inconclusive: positive but not clearly above break-even"


def frozen_rules(repo_root: Path, now: datetime) -> list[str]:
    states: dict[str, str] = {}
    cutoff = now - timedelta(days=3)
    for path in sorted((repo_root / "outputs").glob("*_paper_journal.csv")):
        for row in read_rows(path):
            when = parse_time(row.get("run_recorded_at_utc", ""))
            if when is None or when < cutoff:
                continue
            for match in STATE_RE.finditer(row.get("reason", "")):
                states[match.group(1)] = match.group(2)
    return sorted(f"{rule} {state.lower()}" for rule, state in states.items())


def live_rules(repo_root: Path, now: datetime) -> dict[str, int]:
    counts: dict[str, int] = {}
    cutoff = now - timedelta(days=14)
    for path in sorted((repo_root / "outputs").glob("*_paper_journal.csv")):
        for row in read_rows(path):
            if row.get("decision") != "paper_order":
                continue
            when = parse_time(row.get("run_recorded_at_utc", ""))
            if when is None or when < cutoff:
                continue
            key = f"{rule_id(row.get('reason', ''))} {row.get('symbol', '')} {row.get('side', '')}"
            counts[key] = counts.get(key, 0) + 1
    return counts


def build_scorecard(repo_root: Path, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    outputs = repo_root / "outputs"
    closed = demo_summary(read_rows(outputs / "deriv_direct_closed_trades.csv"))
    journal = read_rows(outputs / "deriv_direct_order_journal.csv")
    since = now - timedelta(hours=24)
    recent = [r for r in journal if (parse_time(r.get("timestamp", "")) or datetime.min.replace(tzinfo=timezone.utc)) >= since]
    opened = sum(1 for r in recent if r.get("status") == "bought")
    skipped = [r for r in recent if r.get("status") == "skipped"]
    errors = sum(1 for r in recent if r.get("status") == "error")
    try:
        open_now = len(json.loads((outputs / "deriv_direct_open_positions.json").read_text() or "[]"))
    except (OSError, ValueError):
        open_now = 0
    live = live_rules(repo_root, now)
    frozen = frozen_rules(repo_root, now)

    lines = [f"NetzaraBot scorecard (DEMO money only), {now:%d %b %Y}"]
    if closed["n"]:
        lines.append(
            f"Closed demo trades: {closed['n']} ({closed['wins']} wins, {closed['losses']} losses), "
            f"net {closed['net']:+.2f} USD after costs; break-even win rate {closed['breakeven']:.0%}"
        )
    else:
        lines.append("Closed demo trades: 0 so far")
    lines.append(f"Verdict: {verdict(closed)}")
    lines.append(f"Last 24h: {opened} opened, {len(skipped)} skipped, {errors} errors, {open_now} open now")
    for row in skipped[-3:]:
        lines.append(f"  skipped {row.get('symbol', '')} {row.get('side', '')}: {row.get('message', '').replace('skipped: ', '')[:90]}")
    if live:
        lines.append("Rules that produced signals in 14 days: " + ", ".join(f"{k} x{v}" for k, v in sorted(live.items(), key=lambda kv: -kv[1])[:5]))
    else:
        lines.append("Rules that produced signals in 14 days: none")
    if frozen:
        lines.append("Switched off by the kill-switch: " + ", ".join(frozen))
    lines.append("Real-money trading: DISARMED")
    return "\n".join(lines)


def load_env(path: str = ENV_FILE) -> None:
    file = Path(path)
    if not file.exists():
        return
    for line in file.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def send_telegram(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        print("Telegram not configured; nothing sent.")
        return False
    data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data), timeout=20) as response:
            return response.status == 200
    except Exception as exc:  # never let a failed send crash the scheduler
        print(f"Telegram send failed: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--send", action="store_true")
    args = parser.parse_args()
    load_env()
    text = build_scorecard(Path(args.repo_root).resolve())
    print(text)
    if args.send:
        print("sent" if send_telegram(text) else "not sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
