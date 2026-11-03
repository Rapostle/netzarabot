#!/usr/bin/env python3
"""Telegram alert when NetzaraBot's price data goes stale (or recovers).

Why: when Deriv retired its old endpoint, data refreshes failed for six weeks and
the only trace was a log line. The paper monitor already refuses to open trades on
old candles, but nobody was told. This watcher tells you.

Checks the newest candle in live_candidate/outputs/refreshed_data/*.csv. Sends one
message when a file turns stale, one when all files are fresh again, and repeats the
stale warning every --repeat-hours while it stays stale. Stdlib only.

Env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID  (use --dry-run to print instead of send)
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "live_candidate" / "outputs" / "refreshed_data"
STATE_FILE = ROOT / "outputs" / "data_freshness_state.json"


def newest_candle_age_minutes(path: Path, now: datetime) -> float | None:
    try:
        lines = [ln for ln in path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
        stamp = lines[-1].split(",", 1)[0]
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max((now - parsed).total_seconds() / 60.0, 0.0)
    except Exception:  # noqa: BLE001 - unreadable or empty file counts as stale
        return None


def check(data_dir: Path, stale_minutes: float, now: datetime) -> dict[str, float | None]:
    ages = {}
    for path in sorted(data_dir.glob("*.csv")):
        age = newest_candle_age_minutes(path, now)
        if age is None or age > stale_minutes:
            ages[path.name] = age
    return ages


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:  # noqa: BLE001
        return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state))


def describe(stale: dict[str, float | None]) -> str:
    parts = []
    for name, age in stale.items():
        parts.append(f"{name}: " + ("no readable candles" if age is None else f"newest candle {age / 60:.1f}h old"))
    return "\n".join(parts)


def send(text: str, dry_run: bool) -> None:
    if dry_run:
        print(f"[dry-run] {text}\n")
        return
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID (or use --dry-run).")
        return
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text[:3900]}).encode()
    request = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
    try:
        urllib.request.urlopen(request, timeout=30).read()
    except Exception as exc:  # noqa: BLE001 - never crash the watcher on a Telegram hiccup
        print(f"Telegram send failed: {exc}")


def run_once(data_dir: Path, stale_minutes: float, repeat_hours: float, dry_run: bool, now: datetime) -> None:
    stale = check(data_dir, stale_minutes, now)
    state = load_state()
    was_stale = bool(state.get("stale"))
    last_alert = float(state.get("last_alert_ts", 0))
    if stale:
        if not was_stale or time.time() - last_alert >= repeat_hours * 3600:
            send("NetzaraBot data is STALE. New paper trades are blocked until it refreshes.\n" + describe(stale), dry_run)
            state = {"stale": True, "last_alert_ts": time.time()}
        else:
            state["stale"] = True
    elif was_stale:
        send("NetzaraBot data is fresh again. Paper monitoring has resumed.", dry_run)
        state = {"stale": False, "last_alert_ts": 0}
    save_state(state)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default=str(DEFAULT_DIR))
    parser.add_argument("--stale-minutes", type=float, default=180.0, help="Same limit the paper monitor uses.")
    parser.add_argument("--interval-minutes", type=float, default=10.0)
    parser.add_argument("--repeat-hours", type=float, default=6.0)
    parser.add_argument("--once", action="store_true", help="Check once and exit.")
    parser.add_argument("--dry-run", action="store_true", help="Print messages instead of sending them.")
    args = parser.parse_args()
    while True:
        run_once(Path(args.data_dir), args.stale_minutes, args.repeat_hours, args.dry_run, datetime.now(timezone.utc))
        if args.once:
            return 0
        time.sleep(args.interval_minutes * 60)


if __name__ == "__main__":
    raise SystemExit(main())
