"""Sam's sniper entry, second and LAST look: same rule, wider stop room and a nearer target. Fixed before running.

Only three numbers differ from work/sniper_test.py: the stop sits 0.5 ATR beyond the zone (was 0.25), stops up to 6 ATR
away are allowed (was 3), and the target is 1.5 times the stop distance (was 3). Entry, 4h direction, touch and candle
confirmation are untouched. Research only: it never trades.

    python work/sniper_retest.py --data-dir outputs/history --symbols CRASH300N R_75 --timeframe 5m
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sniper_test as st  # noqa: E402

STOP_PAD_ATR = 0.5
MAX_STOP_ATR = 6.0
REWARD_R = 1.5


def apply_settings() -> None:
    st.STOP_PAD_ATR, st.MAX_STOP_ATR, st.REWARD_R = STOP_PAD_ATR, MAX_STOP_ATR, REWARD_R


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data-dir", default="outputs/history")
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--timeframe", default="5m")
    parser.add_argument("--null-runs", type=int, default=100)
    parser.add_argument("--min-bars", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=9)
    args = parser.parse_args()
    apply_settings()
    print(f"Sniper entry, second look (stop {STOP_PAD_ATR} ATR beyond the zone, up to {MAX_STOP_ATR} ATR away, target {REWARD_R}R). "
          "Fixed in advance; this is the last variant.\n")
    wf = st.wf
    be = 1 / (1 + REWARD_R)
    tested, pooled, n_all = 0, 0.0, 0
    for sym in args.symbols:
        df = wf.load_history(Path(args.data_dir), sym, args.timeframe)
        if df is None or len(df) < args.min_bars:
            print(f"{sym}: skipped (not enough history)")
            continue
        t = st.evaluate(df)
        if len(t) == 0:
            print(f"{sym}: no trades")
            continue
        tested += 1
        pooled += float(t["r"].sum())
        n_all += len(t)
        wins = int((t["r"] > 0).sum())
        half = len(t) // 2
        p = st.luck_chance(df, float(t["r"].mean()), args.null_runs, args.seed)
        print(f"{sym}: {len(t)} trades ({int((t['side'] > 0).sum())} buys, {int((t['side'] < 0).sum())} sells), win rate {wins / len(t):.0%} "
              f"(break-even about {be:.0%} before costs), average {t['r'].mean():+.2f}R per trade, total {t['r'].sum():+.1f}R, luck chance {p:.2f}")
        print(f"   first half {t['r'].iloc[:half].mean():+.2f}R | second half {t['r'].iloc[half:].mean():+.2f}R")
    avg = pooled / n_all if n_all else float("nan")
    print(f"\nAll markets together: {n_all} trades, {pooled:+.1f}R in total, {avg:+.2f}R per trade. Markets with trades: {tested}.")
    print("The pooled line is the one to judge. With that many markets, one at 0.05 is expected by chance. This is the last variant; no more tuning.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
