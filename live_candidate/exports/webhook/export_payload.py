#!/usr/bin/env python3
"""Create a generic JSON payload for integrations outside MT5 and Telegram."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def read_latest_csv_row(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    rows = list(csv.DictReader(path.open("r", newline="", encoding="utf-8")))
    return rows[-1] if rows else {}


def build_payload(root: Path, mode: str) -> dict:
    decision = read_latest_csv_row(root / "live_candidate" / "outputs" / "primary_decisions.csv")
    status_rows = {}
    status_path = root / "live_candidate" / "outputs" / "primary_status.csv"
    if status_path.exists():
        for row in csv.DictReader(status_path.open("r", newline="", encoding="utf-8")):
            status_rows[row.get("metric", "")] = row.get("value", "")

    return {
        "source": "live_candidate_bot",
        "mode": mode,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "live_trading_enabled": False,
        "readiness": "not_ready_for_live_trading",
        "latest_status": status_rows,
        "latest_decision": decision,
        "message": {
            "title": "Live Candidate Bot Update",
            "symbol": decision.get("symbol", ""),
            "timeframe": decision.get("timeframe", ""),
            "decision": decision.get("decision", ""),
            "side": decision.get("side", ""),
            "reason": decision.get("reason", ""),
        },
    }


def main() -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=str(root / "live_candidate" / "exports" / "webhook" / "latest_payload.json"),
        help="Output JSON payload path.",
    )
    parser.add_argument("--mode", default="primary_demo")
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload(root, args.mode)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    decision = payload["message"]
    print(f"Exported integration payload: {output}")
    print(f"Latest decision: {decision['symbol']} {decision['timeframe']} {decision['decision']} {decision['side']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
