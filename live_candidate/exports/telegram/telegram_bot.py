#!/usr/bin/env python3
"""Small Telegram status bot for the live-candidate trading monitor."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def read_text(path: Path, fallback: str) -> str:
    if not path.exists():
        return fallback
    return path.read_text(encoding="utf-8", errors="replace").strip() or fallback


def short_status(root: Path) -> str:
    status_path = root / "live_candidate" / "outputs" / "primary_status.csv"
    dashboard_path = root / "live_candidate" / "outputs" / "primary_dashboard.md"
    readiness_path = root / "live_candidate" / "outputs" / "primary_readiness.md"

    lines = ["Live Candidate Bot", "Mode: paper/status only"]
    if status_path.exists():
        raw = status_path.read_text(encoding="utf-8", errors="replace").splitlines()[1:]
        values = {}
        for line in raw:
            if "," in line:
                key, value = line.split(",", 1)
                values[key] = value
        lines.extend(
            [
                f"Last run: {values.get('last_run_utc', 'unknown')}",
                f"Decision: {values.get('latest_decisions', 'unknown')}",
                f"Paper orders: {values.get('latest_paper_orders', '0')}",
                f"Open positions: {values.get('open_positions', '0')}",
            ]
        )
    else:
        lines.append("No status file found yet.")

    readiness = read_text(readiness_path, "")
    if "NOT READY" in readiness.upper():
        lines.append("Live readiness: NOT READY")
    elif readiness:
        lines.append("Live readiness: review required")

    if dashboard_path.exists():
        lines.append("Dashboard file is available locally.")
    return "\n".join(lines)


def signal_text(root: Path) -> str:
    path = root / "live_candidate" / "exports" / "mt5" / "live_candidate_signals.csv"
    if not path.exists():
        return "No exported MT5 signal yet. Run the MT5 signal export first."
    return read_text(path, "Signal file is empty.")


def api_call(token: str, method: str, params: dict[str, str]) -> dict:
    data = urllib.parse.urlencode(params).encode("utf-8")
    url = f"https://api.telegram.org/bot{token}/{method}"
    request = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def send_message(token: str, chat_id: str, text: str) -> None:
    api_call(token, "sendMessage", {"chat_id": chat_id, "text": text[:3900]})


def handle_command(root: Path, text: str) -> str:
    command = text.strip().split()[0].lower() if text.strip() else "/status"
    if command in {"/start", "/help"}:
        return (
            "Live Candidate Bot commands:\n"
            "/status - latest paper monitor status\n"
            "/signals - latest exported MT5 signal\n"
            "/readiness - go-live readiness notes\n"
            "/help - show this message"
        )
    if command == "/signals":
        return signal_text(root)
    if command == "/readiness":
        return read_text(root / "live_candidate" / "outputs" / "primary_readiness.md", "No readiness file found.")
    return short_status(root)


def poll(token: str, root: Path, allowed_chat_id: str | None, interval: int) -> None:
    offset = 0
    print("Telegram bot is running. Press Ctrl+C to stop.")
    while True:
        try:
            result = api_call(token, "getUpdates", {"timeout": "25", "offset": str(offset)})
            for update in result.get("result", []):
                offset = max(offset, int(update["update_id"]) + 1)
                message = update.get("message") or {}
                chat = message.get("chat") or {}
                chat_id = str(chat.get("id", ""))
                if not chat_id:
                    continue
                if allowed_chat_id and chat_id != allowed_chat_id:
                    send_message(token, chat_id, "This bot is locked to another chat.")
                    continue
                reply = handle_command(root, str(message.get("text", "/status")))
                send_message(token, chat_id, reply)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"Telegram polling error: {exc}")
            time.sleep(interval)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval", type=int, default=10, help="Retry interval after temporary errors.")
    args = parser.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("Set TELEGRAM_BOT_TOKEN before running this bot.")
        return 2

    poll(token, repo_root(), os.environ.get("TELEGRAM_CHAT_ID"), args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
