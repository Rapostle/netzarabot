#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

python3 "$ROOT/external/mt5_bridge/bridge/mt5_signal_server.py" \
  --repo-root "$ROOT" \
  --decisions-csv "$ROOT/outputs/pair_candidate_paper_decisions.csv" \
  --symbol-map "$ROOT/external/mt5_bridge/config/mt5_symbol_map.csv" \
  --host 127.0.0.1 \
  --port 8765 \
  --max-signal-age-minutes 30
