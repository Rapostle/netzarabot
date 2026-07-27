from __future__ import annotations

import argparse
import csv
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


TASK_ROOT = Path("/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot")
STABLE_STATUS = TASK_ROOT / "outputs/paper_stable_status.csv"


def status_metric(path: Path, key: str, default: str = "0") -> str:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("metric") == key:
                return row.get("value", default)
    return default


def stable_track_is_quarantined(loss_limit: float) -> bool:
    try:
        closed_pnl = float(status_metric(STABLE_STATUS, "closed_pnl", "0"))
    except ValueError:
        closed_pnl = 0.0
    return closed_pnl <= -abs(loss_limit)


def run_step(label: str, command: list[str]) -> int:
    print(f"\n[{datetime.now(timezone.utc).isoformat()}] {label}", flush=True)
    result = subprocess.run(command, cwd=TASK_ROOT, check=False)
    if result.returncode != 0:
        print(f"{label} failed with exit code {result.returncode}", flush=True)
    return result.returncode


def run_cycle(skip_download: bool, stable_loss_limit: float) -> int:
    stable_cmd = [str(TASK_ROOT / "work/run_paper_refresh.sh")]
    pair_cmd = [str(TASK_ROOT / "work/run_pair_candidate_paper_refresh.sh")]
    if skip_download:
        stable_cmd = [str(TASK_ROOT / "work/run_paper_local.sh")]
    if stable_track_is_quarantined(stable_loss_limit):
        stable_cmd = [str(TASK_ROOT / "work/run_paper_guarded.sh")]
        print(
            f"Original stable track is in guarded mode after paper loss limit {stable_loss_limit:.2f}. "
            "Existing positions are tracked, but no new paper positions are added.",
            flush=True,
        )

    steps = [
        ("Pre-trade strict rule filter refresh", [str(TASK_ROOT / "work/run_monitor_overview.sh")]),
        ("Original stable paper check", stable_cmd),
        ("Experimental pair paper check", pair_cmd),
        ("Advanced sniper paper check", [str(TASK_ROOT / "work/run_advanced_sniper_paper_local.sh")]),
        ("Strict research paper check", [str(TASK_ROOT / "work/run_strict_research_paper_refresh.sh")]),
        ("Signal explainer refresh", [str(TASK_ROOT / "work/run_signal_explainers.sh")]),
        ("Monitor overview refresh", [str(TASK_ROOT / "work/run_monitor_overview.sh")]),
    ]
    for label, command in steps:
        code = run_step(label, command)
        if code != 0:
            return code
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run both paper tracks and update the combined overview.")
    parser.add_argument("--repeat", action="store_true", help="Keep running both paper tracks on a timer.")
    parser.add_argument("--interval-minutes", type=float, default=15.0, help="Minutes between repeated cycles.")
    parser.add_argument("--max-runs", type=int, help="Stop after this many cycles.")
    parser.add_argument("--skip-download", action="store_true", help="Use local copied data for the original stable track.")
    parser.add_argument("--stable-loss-limit", type=float, default=60.0, help="Guard original stable track after this closed paper loss.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_number = 0
    while True:
        run_number += 1
        print(f"\nCombined paper monitor cycle {run_number} started.", flush=True)
        result = run_cycle(skip_download=args.skip_download, stable_loss_limit=args.stable_loss_limit)
        if result != 0:
            return result
        if not args.repeat:
            return 0
        if args.max_runs is not None and run_number >= args.max_runs:
            print(f"Combined paper monitor finished after {run_number} cycle(s).", flush=True)
            return 0
        print(f"Next combined cycle in {args.interval_minutes:g} minute(s). Press Ctrl+C to stop.", flush=True)
        try:
            time.sleep(max(args.interval_minutes * 60.0, 1.0))
        except KeyboardInterrupt:
            print("\nCombined paper monitor stopped by user.", flush=True)
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
