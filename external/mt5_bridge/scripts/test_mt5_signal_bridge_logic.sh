#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

python3 - <<'PY'
from pathlib import Path
from external.mt5_bridge.bridge.mt5_signal_server import load_symbol_map, select_signal, text_signal

root = Path.cwd()
symbol_map = load_symbol_map(root / "external/mt5_bridge/config/mt5_symbol_map.csv")
signal = select_signal(
    root / "external/mt5_bridge/tests/sample_decisions.csv",
    symbol_map,
    "Boom 300 Index",
    99999999,
)
line = text_signal(signal)
print(line, end="")
if not line.startswith("SIGNAL|"):
    raise SystemExit("Expected SIGNAL response")
if "Boom 300 Index|buy|960.25|950.25|978.25" not in line:
    raise SystemExit("Signal payload did not match expected MT5 format")
PY
