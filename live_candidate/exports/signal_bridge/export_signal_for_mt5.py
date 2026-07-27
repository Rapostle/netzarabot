#!/usr/bin/env python3
"""Export the latest live-candidate decision into an MT5-readable signal file."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


FIELDNAMES = [
    "timestamp",
    "symbol",
    "timeframe",
    "side",
    "rule_id",
    "entry",
    "stop_loss",
    "take_profit",
    "confidence",
    "mode",
    "status",
    "reason",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def latest_row(path: Path) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"Missing candidate decision file: {path}")

    rows = list(csv.DictReader(path.open("r", newline="", encoding="utf-8")))
    if not rows:
        raise ValueError(f"No decisions found in {path}")
    return rows[-1]


def normalize_signal(row: dict[str, str], mode: str) -> dict[str, str]:
    decision = (row.get("decision") or "").strip().lower()
    side = (row.get("side") or "hold").strip().lower()
    status = "active_signal" if decision in {"paper_order", "signal", "trade"} and side in {"buy", "sell"} else "no_trade"

    return {
        "timestamp": row.get("timestamp", ""),
        "symbol": row.get("symbol", ""),
        "timeframe": row.get("timeframe", ""),
        "side": side,
        "rule_id": row.get("paper_order_id") or row.get("rule_id") or "candidate_rule",
        "entry": row.get("entry", ""),
        "stop_loss": row.get("stop_loss", ""),
        "take_profit": row.get("take_profit", ""),
        "confidence": row.get("confidence", ""),
        "mode": mode,
        "status": status,
        "reason": row.get("reason", ""),
    }


def write_signal(path: Path, signal: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerow(signal)


def main() -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default=str(root / "live_candidate" / "outputs" / "primary_decisions.csv"),
        help="Candidate decisions CSV to export.",
    )
    parser.add_argument(
        "--output",
        default=str(root / "live_candidate" / "exports" / "mt5" / "live_candidate_signals.csv"),
        help="MT5 signal CSV output path.",
    )
    parser.add_argument("--mode", default="primary_demo", help="Signal mode label.")
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    signal = normalize_signal(latest_row(source), args.mode)
    write_signal(output, signal)

    print(f"Exported MT5 signal file: {output}")
    print(f"Latest decision: {signal['symbol']} {signal['timeframe']} {signal['status']} {signal['side']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
