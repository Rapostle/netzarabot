from __future__ import annotations

from pathlib import Path


TASK_ROOT = Path(__file__).resolve().parent.parent.parent
ARMING_FILE = TASK_ROOT / "live_candidate/config/ALLOW_REAL_LIVE_TRADING.txt"


def main() -> int:
    print("LIVE TRADING BLOCKED")
    print()
    print("This live-candidate package is demo/paper-only.")
    print("It does not place real Deriv orders and does not read a real token.")
    print()
    print("A future real-money pilot must be built as a separate step after:")
    print("- more paper evidence")
    print("- manual review")
    print("- daily loss limit")
    print("- emergency stop-all")
    print("- explicit arming file")
    print()
    print(f"Required future arming file would be: {ARMING_FILE}")
    print("That file is intentionally absent.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
