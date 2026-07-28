from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


DECISION_ORDER = {"paper_order": 0, "live_order": 0}


@dataclass
class Signal:
    ok: bool
    status: str
    signal_id: str = ""
    bot_symbol: str = ""
    mt5_symbol: str = ""
    timeframe: str = ""
    side: str = ""
    entry: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    confidence: float = 0.0
    reason: str = ""
    timestamp: str = ""
    age_minutes: float = 0.0


def parse_time(value: str) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value in ("", None):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def load_symbol_map(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["bot_symbol"].strip(): row["mt5_symbol"].strip() for row in csv.DictReader(handle) if row.get("bot_symbol")}


def load_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def select_signal(decisions_csv: Path, symbol_map: dict[str, str], requested_symbol: str, max_age_minutes: float) -> Signal:
    rows = load_rows(decisions_csv)
    if not rows:
        return Signal(ok=False, status="no_decision_rows")

    candidates: list[tuple[datetime, dict[str, str]]] = []
    now = datetime.now(timezone.utc)
    for row in rows:
        decision = (row.get("decision") or "").strip()
        side = (row.get("side") or "").strip().lower()
        bot_symbol = (row.get("symbol") or "").strip()
        mt5_symbol = symbol_map.get(bot_symbol, bot_symbol)
        if decision not in DECISION_ORDER or side not in {"buy", "sell"}:
            continue
        if requested_symbol and requested_symbol not in {bot_symbol, mt5_symbol}:
            continue
        signal_time = parse_time(row.get("timestamp") or "")
        if signal_time is None:
            continue
        age_minutes = max((now - signal_time).total_seconds() / 60.0, 0.0)
        if max_age_minutes > 0 and age_minutes > max_age_minutes:
            continue
        candidates.append((signal_time, row))

    if not candidates:
        return Signal(ok=False, status="no_fresh_signal")

    signal_time, row = sorted(candidates, key=lambda item: item[0], reverse=True)[0]
    bot_symbol = (row.get("symbol") or "").strip()
    mt5_symbol = symbol_map.get(bot_symbol, bot_symbol)
    signal_id = "~".join(
        [
            bot_symbol,
            row.get("timeframe", ""),
            row.get("side", ""),
            row.get("timestamp", ""),
            row.get("paper_order_id", ""),
        ]
    )
    return Signal(
        ok=True,
        status="signal",
        signal_id=signal_id,
        bot_symbol=bot_symbol,
        mt5_symbol=mt5_symbol,
        timeframe=row.get("timeframe", ""),
        side=(row.get("side") or "").strip().lower(),
        entry=safe_float(row.get("entry")),
        stop_loss=safe_float(row.get("stop_loss")),
        take_profit=safe_float(row.get("take_profit")),
        confidence=safe_float(row.get("confidence")),
        reason=row.get("reason", ""),
        timestamp=signal_time.isoformat(),
        age_minutes=round(max((datetime.now(timezone.utc) - signal_time).total_seconds() / 60.0, 0.0), 2),
    )


def text_signal(signal: Signal) -> str:
    if not signal.ok:
        return f"NO_SIGNAL|{signal.status}\n"
    return (
        "SIGNAL|"
        f"{signal.signal_id}|{signal.mt5_symbol}|{signal.side}|{signal.entry}|"
        f"{signal.stop_loss}|{signal.take_profit}|{signal.confidence}|{signal.timestamp}|{signal.reason}"
        "\n"
    )


def make_handler(args: argparse.Namespace):
    decisions_csv = Path(args.decisions_csv)
    symbol_map_path = Path(args.symbol_map)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *values: object) -> None:
            print(f"{datetime.now(timezone.utc).isoformat()} {self.address_string()} {fmt % values}")

        def send_json(self, payload: object, status: int = 200) -> None:
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def send_text(self, body_text: str, status: int = 200) -> None:
            body = body_text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            requested_symbol = (query.get("symbol") or [""])[0]
            symbol_map = load_symbol_map(symbol_map_path)
            if parsed.path == "/health":
                self.send_json(
                    {
                        "ok": True,
                        "service": "netzarabot-mt5-signal-bridge",
                        "time": datetime.now(timezone.utc).isoformat(),
                        "decisions_csv": str(decisions_csv),
                        "decisions_exists": decisions_csv.exists(),
                        "symbol_map": str(symbol_map_path),
                    }
                )
                return
            if parsed.path == "/signals.json":
                signal = select_signal(decisions_csv, symbol_map, requested_symbol, args.max_signal_age_minutes)
                self.send_json(asdict(signal))
                return
            if parsed.path == "/signal":
                signal = select_signal(decisions_csv, symbol_map, requested_symbol, args.max_signal_age_minutes)
                self.send_text(text_signal(signal))
                return
            self.send_json({"ok": False, "error": "Use /health, /signal, or /signals.json"}, status=404)

    return Handler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Expose NetzaraBot decisions to an MT5 Expert Advisor.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--decisions-csv", required=True)
    parser.add_argument("--symbol-map", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--max-signal-age-minutes", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(args))
    print(f"NetzaraBot MT5 signal bridge running at http://{args.host}:{args.port}")
    print(f"Reading decisions from {args.decisions_csv}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping MT5 signal bridge.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
