"""One-screen summary of all checker rules on a coin (read-only; fetches daily prices, reads hourly data on disk).

    .venv/bin/python scripts/checker_summary.py --coin BTC [--pool BTC ETH SOL BNB]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from checker import engine, intraday, summary  # noqa: E402
from checker.data import fetch_close  # noqa: E402
import power_of_three_test as p3  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--coin", default="BTC")
    ap.add_argument("--null-runs", type=int, default=300)
    a = ap.parse_args()
    coin = a.coin.upper()
    close = fetch_close(coin)
    daily = [engine.run_check(close, r, market=coin, null_runs=a.null_runs, tests_counted=len(engine.RULE_NAMES)) for r in engine.RULE_NAMES]
    hourly = p3.load(coin + "USDT")
    intra = [intraday.run_intraday_check(hourly, r, coin, null_runs=min(a.null_runs, 200)) for r in intraday.INTRADAY_RULES] if hourly is not None else []
    print(summary.format_summary(coin, daily, intra))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
