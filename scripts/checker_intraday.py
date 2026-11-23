"""Run the checker's intraday verdict on hourly crypto data already on disk (read-only).

    .venv/bin/python scripts/checker_intraday.py --symbols BTCUSDT ETHUSDT --rules judas wr
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from checker import intraday, report  # noqa: E402
import power_of_three_test as p3  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT"])
    ap.add_argument("--rules", nargs="+", default=list(intraday.INTRADAY_RULES))
    ap.add_argument("--null-runs", type=int, default=200)
    a = ap.parse_args()
    for s in a.symbols:
        df = p3.load(s)
        if df is None:
            print(f"{s}: no hourly data in {p3.DATA_DIR}\n")
            continue
        for rule in a.rules:
            print(report.format_intraday_report(intraday.run_intraday_check(df, rule, s, null_runs=a.null_runs)), "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
