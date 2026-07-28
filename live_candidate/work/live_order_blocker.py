from __future__ import annotations

from pathlib import Path


TASK_ROOT = Path(__file__).resolve().parent.parent.parent
ARMING_FILE = TASK_ROOT / "live_candidate/config/ALLOW_REAL_LIVE_TRADING.txt"


def main() -> int:
    print("DERIV DIRECT LIVE TRADING BLOCKED")
    print()
    print("This live-candidate Deriv-direct package is demo/paper-only.")
    print("It does not place real Deriv API orders and does not read a real token.")
    print()
    print("The real-money route currently built for this repo is the MT5/CFD bridge:")
    print("- external/mt5_bridge/bridge/mt5_signal_server.py")
    print("- external/mt5_bridge/ea/NetzaraBotBridgeEA.mq5")
    print()
    print("That MT5 bridge places CFD trades inside MT5 when all are true:")
    print("- the bridge is running")
    print("- external/mt5_bridge/config/control_state.json has trading_enabled=true")
    print("- the MT5 EA input EnableLiveTrading=true")
    print("- MT5 Algo Trading is enabled")
    print("- a fresh buy/sell signal exists")
    print()
    print(f"Required future arming file would be: {ARMING_FILE}")
    print("That file is intentionally absent because this Deriv-direct path has no order sender.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
