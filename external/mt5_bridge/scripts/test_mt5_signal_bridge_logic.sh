#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

python3 - <<'PY'
from pathlib import Path
from external.mt5_bridge.bridge.mt5_signal_server import ControlState, control_text, load_symbol_map, select_signal, text_signal

root = Path.cwd()
symbol_map = load_symbol_map(root / "external/mt5_bridge/config/mt5_symbol_map.csv")
stopped = ControlState(trading_enabled=False, emergency_stop=False, max_lot=0.01, allowed_symbols=[])
blocked = select_signal(
    root / "external/mt5_bridge/tests/sample_decisions.csv",
    symbol_map,
    "Boom 300 Index",
    99999999,
    stopped,
)
if text_signal(blocked) != "NO_SIGNAL|trading_stopped\n":
    raise SystemExit("Expected stopped control to block signals")

running = ControlState(trading_enabled=True, emergency_stop=False, max_lot=0.01, allowed_symbols=["Boom 300 Index"])
running.lot_mode = "risk_percent"
running.fixed_lot = 0.02
running.min_lot = 0.01
running.risk_percent = 0.5
running.stop_mode = "override_points"
running.override_sl_points = 100.0
running.override_tp_points = 180.0
running.breakeven_enabled = True
running.breakeven_trigger_points = 80.0
running.breakeven_offset_points = 5.0
running.trailing_enabled = True
running.trailing_start_points = 120.0
running.trailing_distance_points = 60.0
running.close_after_minutes = 45.0
control_line = control_text(running)
if "CONTROL|true|false|live|0.01|Boom 300 Index|" not in control_line:
    raise SystemExit("Control payload lost the original EA fields")
if "|override_points|100.0|180.0|true|80.0|5.0|true|120.0|60.0|45.0" not in control_line:
    raise SystemExit("Control payload did not include TP/SL management fields")
if "|risk_percent|0.02|0.01|0.5" not in control_line:
    raise SystemExit("Control payload did not include flexible lot sizing fields")
signal = select_signal(
    root / "external/mt5_bridge/tests/sample_decisions.csv",
    symbol_map,
    "Boom 300 Index",
    99999999,
    running,
)
line = text_signal(signal)
print(line, end="")
if not line.startswith("SIGNAL|"):
    raise SystemExit("Expected SIGNAL response")
if "Boom 300 Index|buy|960.25|950.25|978.25" not in line:
    raise SystemExit("Signal payload did not match expected MT5 format")
if not line.rstrip().endswith("|0.01|0.01|1.0"):
    raise SystemExit("Signal payload did not include signal lot and risk amount")
PY
