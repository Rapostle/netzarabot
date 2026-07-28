from __future__ import annotations

from pathlib import Path


TASK_ROOT = Path(__file__).resolve().parent.parent.parent
ARMING_FILE = TASK_ROOT / "live_candidate/config/ALLOW_REAL_LIVE_TRADING.txt"
DIRECT_ENGINE = TASK_ROOT / "external/deriv_direct/deriv_direct_executor.py"


def main() -> int:
    print("DERIV DIRECT LIVE TRADING STATUS")
    print()
    print("The old live-candidate blocker does not place orders itself.")
    print("Deriv-direct execution is now handled by:")
    print(f"- {DIRECT_ENGINE}")
    print()
    print("The MT5/CFD route also remains available:")
    print("- external/mt5_bridge/bridge/mt5_signal_server.py")
    print("- external/mt5_bridge/ea/NetzaraBotBridgeEA.mq5")
    print()
    print("To run Deriv-direct live once, use:")
    print("- work/run_deriv_direct_live_once.sh")
    print()
    print("Runtime requirements:")
    print("- DERIV_API_TOKEN")
    print("- ALLOW_REAL_DERIV_DIRECT=true")
    print("- DERIV_DIRECT_CONSENT=I_UNDERSTAND_REAL_MONEY_TRADING")
    print("- fresh buy/sell signal")
    print()
    print(f"Arming file: {ARMING_FILE}")
    print(f"Arming file exists: {ARMING_FILE.exists()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
