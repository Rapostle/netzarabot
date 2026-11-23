"""Run the checker's daily rules on the Deriv Boom and Crash indices found on disk (read-only).

    .venv/bin/python scripts/checker_deriv.py --data-dir outputs/history [--cost 0.001] [--null-runs 300]
The luck chance is corrected for every rule x index tried in this run, so trying many indices cannot manufacture a pass.
Boom/Crash prices have built-in spikes and drift; the shuffled copies keep the same spikes, so the luck test stays fair.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from checker import engine, summary  # noqa: E402
import daily_trend_test as dtt  # noqa: E402


def find_symbols(data_dir: Path) -> list[str]:
    out = []
    for p in sorted(data_dir.glob("deriv_*_1d.csv")):
        sym = p.name[len("deriv_"):-len("_1d.csv")]
        if sym.upper().startswith(("BOOM", "CRASH")):
            out.append(sym)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data-dir", default="outputs/history")
    ap.add_argument("--cost", type=float, default=0.001, help="round-trip cost as a fraction of price (0.001 = 0.1%%)")
    ap.add_argument("--null-runs", type=int, default=300)
    a = ap.parse_args()
    syms = find_symbols(Path(a.data_dir))
    if not syms:
        print(f"No Boom or Crash daily files (deriv_*_1d.csv) in {a.data_dir}.")
        return 1
    counted = len(engine.RULE_NAMES) * len(syms)
    print(f"{len(syms)} indices x {len(engine.RULE_NAMES)} rules = {counted} tries counted. Cost assumed: {a.cost:.2%} per round trip.\n")
    notable = []
    for s in syms:
        close = dtt.load_daily(Path(a.data_dir), s)
        if close is None:
            continue
        res = [engine.run_check(close, r, market=s, cost_round_trip=a.cost, null_runs=a.null_runs, tests_counted=counted) for r in engine.RULE_NAMES]
        print(summary.format_summary(s, res, [], tries=counted).split("\n\nA rule only counts")[0], "\n")
        notable += [f"{r.market} {r.rule}: {r.verdict.split(' (')[0]} (luck {r.p_adjusted:.2f})" for r in res
                    if r.verdict not in (engine.VERDICT_NONE, engine.VERDICT_REFUSED)]
    print("Rules that were not simply 'no evidence': " + ("; ".join(notable) if notable else "none"))
    print("A rule only counts if its corrected luck chance is about 0.05 or below, it holds in both halves, and it still earns after costs.")
    print("Past data cannot promise future profit. This is not financial advice and not a signal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
