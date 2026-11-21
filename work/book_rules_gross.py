"""Cost check for the book rules: the same trades with costs on and off.
Shows how big the stop is as a share of price and how much of the loss is cost, not the rule.
Usage: python work/book_rules_gross.py --symbols A B C --timeframe 5m
"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import book_rules_test as b  # noqa: E402
import walk_forward_rule_search as wf  # noqa: E402


def run(df, rule, cost, slip):
    b.COST, b.SLIP = cost, slip
    return b.evaluate(df, rule)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", default="outputs/history")
    p.add_argument("--symbols", nargs="+", required=True)
    p.add_argument("--timeframe", default="5m")
    p.add_argument("--min-bars", type=int, default=5000)
    a = p.parse_args()
    print("Per rule over all markets: net = with costs (as tested), gross = zero cost and zero slippage.\n")
    for rule in b.RULES:
        net, gross, risk_pct, n = [], [], [], 0
        for sym in a.symbols:
            df = wf.load_history(Path(a.data_dir), sym, a.timeframe)
            if df is None or len(df) < a.min_bars:
                continue
            df = df.reset_index(drop=True)
            sig = b.find_signals(df, rule)
            risk_pct += [abs(e - s) / e * 100 for _, _, e, s, _ in sig]
            net.append(run(df, rule, 0.001, 0.2)["r"].to_numpy())
            gross.append(run(df, rule, 0.0, 0.0)["r"].to_numpy())
        net, gross = np.concatenate(net), np.concatenate(gross)
        print(f"{rule}: {len(net)} trades | net {net.mean():+.2f}R | gross {gross.mean():+.2f}R "
              f"| gross win rate {(gross > 0).mean():.0%} | median stop size {np.median(risk_pct):.3f}% of price")
    print("\nIf gross is near zero or negative, the rule has nothing before costs. If gross is positive but net is negative, costs are eating a thin edge.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
