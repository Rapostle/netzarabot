from __future__ import annotations

import argparse
import csv
import json
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
    max_lot: float = 0.01
    signal_lot: float = 0.0
    risk_amount: float = 0.0


@dataclass
class ControlState:
    trading_enabled: bool = False
    emergency_stop: bool = False
    mode: str = "live"
    max_lot: float = 0.01
    lot_mode: str = "fixed"
    fixed_lot: float = 0.01
    min_lot: float = 0.01
    risk_percent: float = 0.5
    allowed_symbols: list[str] | None = None
    stop_mode: str = "signal"
    override_sl_points: float = 0.0
    override_tp_points: float = 0.0
    breakeven_enabled: bool = False
    breakeven_trigger_points: float = 0.0
    breakeven_offset_points: float = 0.0
    trailing_enabled: bool = False
    trailing_start_points: float = 0.0
    trailing_distance_points: float = 0.0
    close_after_minutes: float = 0.0
    updated_at: str = ""
    updated_by: str = "system"

    def normalized_symbols(self) -> list[str]:
        return [item.strip() for item in (self.allowed_symbols or []) if item.strip()]


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


def safe_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value in ("", None):
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def normalized_stop_mode(value: object) -> str:
    mode = str(value or "signal").strip().lower()
    if mode not in {"signal", "override_points", "none"}:
        return "signal"
    return mode


def normalized_lot_mode(value: object) -> str:
    mode = str(value or "fixed").strip().lower()
    if mode not in {"fixed", "signal_quantity", "risk_percent"}:
        return "fixed"
    return mode


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


def default_control() -> ControlState:
    return ControlState(
        trading_enabled=False,
        emergency_stop=False,
        mode="live",
        max_lot=0.01,
        lot_mode="fixed",
        fixed_lot=0.01,
        min_lot=0.01,
        risk_percent=0.5,
        allowed_symbols=[],
        stop_mode="signal",
        override_sl_points=0.0,
        override_tp_points=0.0,
        breakeven_enabled=False,
        breakeven_trigger_points=0.0,
        breakeven_offset_points=0.0,
        trailing_enabled=False,
        trailing_start_points=0.0,
        trailing_distance_points=0.0,
        close_after_minutes=0.0,
        updated_at=datetime.now(timezone.utc).isoformat(),
        updated_by="default",
    )


def load_control(path: Path) -> ControlState:
    if not path.exists() or path.stat().st_size == 0:
        control = default_control()
        save_control(path, control)
        return control
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        control = default_control()
        control.emergency_stop = True
        control.updated_by = "invalid_control_file"
        return control
    return ControlState(
        trading_enabled=safe_bool(raw.get("trading_enabled"), False),
        emergency_stop=safe_bool(raw.get("emergency_stop"), False),
        mode=str(raw.get("mode") or "live"),
        max_lot=max(safe_float(raw.get("max_lot"), 0.01), 0.0),
        lot_mode=normalized_lot_mode(raw.get("lot_mode")),
        fixed_lot=max(safe_float(raw.get("fixed_lot"), 0.01), 0.0),
        min_lot=max(safe_float(raw.get("min_lot"), 0.01), 0.0),
        risk_percent=max(safe_float(raw.get("risk_percent"), 0.5), 0.0),
        allowed_symbols=list(raw.get("allowed_symbols") or []),
        stop_mode=normalized_stop_mode(raw.get("stop_mode")),
        override_sl_points=max(safe_float(raw.get("override_sl_points"), 0.0), 0.0),
        override_tp_points=max(safe_float(raw.get("override_tp_points"), 0.0), 0.0),
        breakeven_enabled=safe_bool(raw.get("breakeven_enabled"), False),
        breakeven_trigger_points=max(safe_float(raw.get("breakeven_trigger_points"), 0.0), 0.0),
        breakeven_offset_points=max(safe_float(raw.get("breakeven_offset_points"), 0.0), 0.0),
        trailing_enabled=safe_bool(raw.get("trailing_enabled"), False),
        trailing_start_points=max(safe_float(raw.get("trailing_start_points"), 0.0), 0.0),
        trailing_distance_points=max(safe_float(raw.get("trailing_distance_points"), 0.0), 0.0),
        close_after_minutes=max(safe_float(raw.get("close_after_minutes"), 0.0), 0.0),
        updated_at=str(raw.get("updated_at") or ""),
        updated_by=str(raw.get("updated_by") or ""),
    )


def save_control(path: Path, control: ControlState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    control.updated_at = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(asdict(control), indent=2) + "\n", encoding="utf-8")


def control_blocks_signal(control: ControlState, mt5_symbol: str) -> str:
    if control.emergency_stop:
        return "emergency_stop"
    if not control.trading_enabled:
        return "trading_stopped"
    allowed = control.normalized_symbols()
    if allowed and mt5_symbol not in allowed:
        return "symbol_not_allowed"
    if control.max_lot <= 0:
        return "max_lot_zero"
    return ""


def select_signal(decisions_csv: Path, symbol_map: dict[str, str], requested_symbol: str, max_age_minutes: float, control: ControlState | None = None) -> Signal:
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
        if control is not None:
            block_reason = control_blocks_signal(control, mt5_symbol)
            if block_reason:
                return Signal(ok=False, status=block_reason, mt5_symbol=mt5_symbol, max_lot=control.max_lot)
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
        max_lot=control.max_lot if control is not None else 0.01,
        signal_lot=safe_float(row.get("quantity")),
        risk_amount=safe_float(row.get("risk_amount")),
    )


def text_signal(signal: Signal) -> str:
    if not signal.ok:
        return f"NO_SIGNAL|{signal.status}\n"
    reason = signal.reason.replace("|", "/").replace("\r", " ").replace("\n", " ")
    return (
        "SIGNAL|"
        f"{signal.signal_id}|{signal.mt5_symbol}|{signal.side}|{signal.entry}|"
        f"{signal.stop_loss}|{signal.take_profit}|{signal.confidence}|{signal.timestamp}|{reason}|"
        f"{signal.max_lot}|{signal.signal_lot}|{signal.risk_amount}"
        "\n"
    )


def control_text(control: ControlState) -> str:
    allowed = ",".join(control.normalized_symbols())
    return (
        "CONTROL|"
        f"{str(control.trading_enabled).lower()}|{str(control.emergency_stop).lower()}|"
        f"{control.mode}|{control.max_lot}|{allowed}|{control.updated_at}|"
        f"{control.stop_mode}|{control.override_sl_points}|{control.override_tp_points}|"
        f"{str(control.breakeven_enabled).lower()}|{control.breakeven_trigger_points}|"
        f"{control.breakeven_offset_points}|{str(control.trailing_enabled).lower()}|"
        f"{control.trailing_start_points}|{control.trailing_distance_points}|{control.close_after_minutes}|"
        f"{control.lot_mode}|{control.fixed_lot}|{control.min_lot}|{control.risk_percent}"
        "\n"
    )


def control_page(control: ControlState) -> str:
    status = "RUNNING" if control.trading_enabled and not control.emergency_stop else "STOPPED"
    if control.emergency_stop:
        status = "EMERGENCY STOP"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>NetzaraBot MT5 Control</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, sans-serif; margin: 0; background: #07111f; color: #f8fafc; }}
    main {{ max-width: 620px; margin: 0 auto; padding: 24px; }}
    .card {{ background: #0f1d32; border: 1px solid #20324f; border-radius: 14px; padding: 18px; margin: 14px 0; }}
    .status {{ font-size: 34px; font-weight: 800; margin: 10px 0; }}
    button {{ width: 100%; padding: 16px; border: 0; border-radius: 12px; margin: 8px 0; font-weight: 800; font-size: 17px; }}
    .start {{ background: #22c55e; color: #04120a; }}
    .stop {{ background: #facc15; color: #1d1600; }}
    .danger {{ background: #ef4444; color: white; }}
    .reset {{ background: #38bdf8; color: #03111a; }}
    input {{ width: 100%; box-sizing: border-box; padding: 13px; border-radius: 10px; border: 1px solid #334155; background: #020617; color: white; margin: 6px 0 12px; }}
    select {{ width: 100%; box-sizing: border-box; padding: 13px; border-radius: 10px; border: 1px solid #334155; background: #020617; color: white; margin: 6px 0 12px; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
    .toggle {{ display: flex; align-items: center; gap: 10px; margin: 8px 0 14px; }}
    .toggle input {{ width: auto; margin: 0; }}
    small {{ color: #aab7cc; }}
  </style>
</head>
<body>
  <main>
    <h1>NetzaraBot MT5 Control</h1>
    <div class="card">
      <small>Status</small>
      <div class="status">{status}</div>
      <p>Mode: {control.mode} · Lot: {control.lot_mode} · Max lot: {control.max_lot}</p>
      <p>Stops: {control.stop_mode} · SL {control.override_sl_points} pts · TP {control.override_tp_points} pts</p>
      <p>Allowed symbols: {", ".join(control.normalized_symbols()) or "all mapped symbols"}</p>
      <small>Updated: {control.updated_at or "not yet"}</small>
    </div>
    <div class="card">
      <label>Control token</label>
      <input id="token" type="password" placeholder="Only needed if bridge token is set" />
      <button class="start" onclick="send('/control/start')">Start Trading</button>
      <button class="stop" onclick="send('/control/stop')">Stop Trading</button>
      <button class="danger" onclick="send('/control/emergency-stop')">Emergency Stop</button>
      <button class="reset" onclick="send('/control/reset-emergency')">Reset Emergency Stop</button>
      <p id="result"></p>
    </div>
    <div class="card">
      <h2>TP / SL Settings</h2>
      <label>Stop mode</label>
      <select id="stop_mode">
        <option value="signal" {"selected" if control.stop_mode == "signal" else ""}>Use bot signal TP/SL</option>
        <option value="override_points" {"selected" if control.stop_mode == "override_points" else ""}>Override with fixed points</option>
        <option value="none" {"selected" if control.stop_mode == "none" else ""}>No TP/SL from bridge</option>
      </select>
      <div class="grid">
        <div>
          <label>Override SL points</label>
          <input id="override_sl_points" type="number" step="0.1" value="{control.override_sl_points}" />
        </div>
        <div>
          <label>Override TP points</label>
          <input id="override_tp_points" type="number" step="0.1" value="{control.override_tp_points}" />
        </div>
      </div>
      <label class="toggle"><input id="breakeven_enabled" type="checkbox" {"checked" if control.breakeven_enabled else ""} /> Move SL to break-even</label>
      <div class="grid">
        <div>
          <label>Break-even trigger points</label>
          <input id="breakeven_trigger_points" type="number" step="0.1" value="{control.breakeven_trigger_points}" />
        </div>
        <div>
          <label>Break-even extra points</label>
          <input id="breakeven_offset_points" type="number" step="0.1" value="{control.breakeven_offset_points}" />
        </div>
      </div>
      <label class="toggle"><input id="trailing_enabled" type="checkbox" {"checked" if control.trailing_enabled else ""} /> Use trailing stop</label>
      <div class="grid">
        <div>
          <label>Trail starts after points</label>
          <input id="trailing_start_points" type="number" step="0.1" value="{control.trailing_start_points}" />
        </div>
        <div>
          <label>Trail distance points</label>
          <input id="trailing_distance_points" type="number" step="0.1" value="{control.trailing_distance_points}" />
        </div>
      </div>
      <label>Close trade after minutes</label>
      <input id="close_after_minutes" type="number" step="1" value="{control.close_after_minutes}" />
      <label>Allowed symbols, comma separated</label>
      <input id="allowed_symbols" value="{", ".join(control.normalized_symbols())}" />
      <button class="reset" onclick="saveSettings()">Save TP/SL Settings</button>
    </div>
    <div class="card">
      <h2>Lot Sizing</h2>
      <label>Lot mode</label>
      <select id="lot_mode">
        <option value="fixed" {"selected" if control.lot_mode == "fixed" else ""}>Fixed lot</option>
        <option value="signal_quantity" {"selected" if control.lot_mode == "signal_quantity" else ""}>Use bot signal quantity</option>
        <option value="risk_percent" {"selected" if control.lot_mode == "risk_percent" else ""}>Risk percent of equity</option>
      </select>
      <div class="grid">
        <div>
          <label>Fixed lot</label>
          <input id="fixed_lot" type="number" step="0.01" value="{control.fixed_lot}" />
        </div>
        <div>
          <label>Max lot cap</label>
          <input id="max_lot" type="number" step="0.01" value="{control.max_lot}" />
        </div>
      </div>
      <div class="grid">
        <div>
          <label>Min lot</label>
          <input id="min_lot" type="number" step="0.01" value="{control.min_lot}" />
        </div>
        <div>
          <label>Risk % of equity</label>
          <input id="risk_percent" type="number" step="0.1" value="{control.risk_percent}" />
        </div>
      </div>
      <small>Max lot is always a hard cap, even when using signal quantity or risk percent.</small>
    </div>
  </main>
  <script>
    async function send(path) {{
      const token = document.getElementById('token').value;
      const res = await fetch(path, {{ method: 'POST', headers: token ? {{ 'X-Control-Token': token }} : {{}} }});
      document.getElementById('result').textContent = await res.text();
      setTimeout(() => location.reload(), 800);
    }}
    async function saveSettings() {{
      const token = document.getElementById('token').value;
      const allowedRaw = document.getElementById('allowed_symbols').value;
      const payload = {{
        stop_mode: document.getElementById('stop_mode').value,
        override_sl_points: Number(document.getElementById('override_sl_points').value || 0),
        override_tp_points: Number(document.getElementById('override_tp_points').value || 0),
        breakeven_enabled: document.getElementById('breakeven_enabled').checked,
        breakeven_trigger_points: Number(document.getElementById('breakeven_trigger_points').value || 0),
        breakeven_offset_points: Number(document.getElementById('breakeven_offset_points').value || 0),
        trailing_enabled: document.getElementById('trailing_enabled').checked,
        trailing_start_points: Number(document.getElementById('trailing_start_points').value || 0),
        trailing_distance_points: Number(document.getElementById('trailing_distance_points').value || 0),
        close_after_minutes: Number(document.getElementById('close_after_minutes').value || 0),
        lot_mode: document.getElementById('lot_mode').value,
        fixed_lot: Number(document.getElementById('fixed_lot').value || 0),
        max_lot: Number(document.getElementById('max_lot').value || 0),
        min_lot: Number(document.getElementById('min_lot').value || 0),
        risk_percent: Number(document.getElementById('risk_percent').value || 0),
        allowed_symbols: allowedRaw.split(',').map((item) => item.trim()).filter(Boolean)
      }};
      const res = await fetch('/control', {{
        method: 'POST',
        headers: Object.assign({{ 'Content-Type': 'application/json' }}, token ? {{ 'X-Control-Token': token }} : {{}}),
        body: JSON.stringify(payload)
      }});
      document.getElementById('result').textContent = await res.text();
      setTimeout(() => location.reload(), 800);
    }}
  </script>
</body>
</html>"""


def make_handler(args: argparse.Namespace):
    decisions_csv = Path(args.decisions_csv)
    symbol_map_path = Path(args.symbol_map)
    control_path = Path(args.control_state)
    control_token = args.control_token or ""

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

        def send_html(self, body_text: str, status: int = 200) -> None:
            body = body_text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def authorized(self) -> bool:
            if not control_token:
                return True
            header = self.headers.get("X-Control-Token", "")
            bearer = self.headers.get("Authorization", "").replace("Bearer ", "")
            query = parse_qs(urlparse(self.path).query)
            supplied = header or bearer or (query.get("token") or [""])[0]
            return supplied == control_token

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            requested_symbol = (query.get("symbol") or [""])[0]
            symbol_map = load_symbol_map(symbol_map_path)
            control = load_control(control_path)
            if parsed.path == "/health":
                self.send_json(
                    {
                        "ok": True,
                        "service": "netzarabot-mt5-signal-bridge",
                        "time": datetime.now(timezone.utc).isoformat(),
                        "decisions_csv": str(decisions_csv),
                        "decisions_exists": decisions_csv.exists(),
                        "symbol_map": str(symbol_map_path),
                        "control_state": str(control_path),
                        "control": asdict(control),
                    }
                )
                return
            if parsed.path == "/control":
                accept = self.headers.get("accept", "")
                if "text/html" in accept:
                    self.send_html(control_page(control))
                else:
                    self.send_json(asdict(control))
                return
            if parsed.path == "/control.txt":
                self.send_text(control_text(control))
                return
            if parsed.path == "/signals.json":
                signal = select_signal(decisions_csv, symbol_map, requested_symbol, args.max_signal_age_minutes, control)
                self.send_json(asdict(signal))
                return
            if parsed.path == "/signal":
                signal = select_signal(decisions_csv, symbol_map, requested_symbol, args.max_signal_age_minutes, control)
                self.send_text(text_signal(signal))
                return
            self.send_json({"ok": False, "error": "Use /health, /control, /control.txt, /signal, or /signals.json"}, status=404)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if not self.authorized():
                self.send_json({"ok": False, "error": "unauthorized"}, status=401)
                return
            control = load_control(control_path)
            action = parsed.path.removeprefix("/control/").strip("/")
            if parsed.path == "/control":
                length = int(self.headers.get("content-length") or 0)
                payload = {}
                if length:
                    payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                for key in [
                    "trading_enabled",
                    "emergency_stop",
                    "mode",
                    "max_lot",
                    "lot_mode",
                    "fixed_lot",
                    "min_lot",
                    "risk_percent",
                    "allowed_symbols",
                    "stop_mode",
                    "override_sl_points",
                    "override_tp_points",
                    "breakeven_enabled",
                    "breakeven_trigger_points",
                    "breakeven_offset_points",
                    "trailing_enabled",
                    "trailing_start_points",
                    "trailing_distance_points",
                    "close_after_minutes",
                ]:
                    if key in payload:
                        setattr(control, key, payload[key])
            elif action == "start":
                control.trading_enabled = True
                control.emergency_stop = False
            elif action == "stop":
                control.trading_enabled = False
            elif action == "emergency-stop":
                control.trading_enabled = False
                control.emergency_stop = True
            elif action == "reset-emergency":
                control.emergency_stop = False
            else:
                self.send_json({"ok": False, "error": "unknown control action"}, status=404)
                return
            control.updated_by = self.client_address[0]
            control.max_lot = max(safe_float(control.max_lot, 0.01), 0.0)
            control.lot_mode = normalized_lot_mode(control.lot_mode)
            control.fixed_lot = max(safe_float(control.fixed_lot, 0.01), 0.0)
            control.min_lot = max(safe_float(control.min_lot, 0.01), 0.0)
            control.risk_percent = max(safe_float(control.risk_percent, 0.5), 0.0)
            control.stop_mode = normalized_stop_mode(control.stop_mode)
            control.override_sl_points = max(safe_float(control.override_sl_points), 0.0)
            control.override_tp_points = max(safe_float(control.override_tp_points), 0.0)
            control.breakeven_enabled = safe_bool(control.breakeven_enabled)
            control.breakeven_trigger_points = max(safe_float(control.breakeven_trigger_points), 0.0)
            control.breakeven_offset_points = max(safe_float(control.breakeven_offset_points), 0.0)
            control.trailing_enabled = safe_bool(control.trailing_enabled)
            control.trailing_start_points = max(safe_float(control.trailing_start_points), 0.0)
            control.trailing_distance_points = max(safe_float(control.trailing_distance_points), 0.0)
            control.close_after_minutes = max(safe_float(control.close_after_minutes), 0.0)
            save_control(control_path, control)
            self.send_json({"ok": True, "control": asdict(control)})

    return Handler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Expose NetzaraBot decisions to an MT5 Expert Advisor.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--decisions-csv", required=True)
    parser.add_argument("--symbol-map", required=True)
    parser.add_argument("--control-state", required=True)
    parser.add_argument("--control-token", default="")
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
