"""Confirm ONE pre-chosen price-action rule on each market, with no searching (so no hunting for a lucky rule).

The rule is fixed on the command line before looking at any result. For every market it reports:
trades with no overlap (a new trade only after the previous one's 12 candles are over), win rate, average net return per trade,
what buying on every candle earned, the result in each third of history, and the chance that a shuffled copy of the same
market does at least as well with this same rule.

    python work/confirm_rule.py --data-dir checker_cache --symbols BTC ETH BNB SOL --timeframe 1d \
        --feature structure+fvg --condition 'downtrend_lh_ll & bear_fvg_retest' --side buy --cost 0.002 --htf-factor 7
Research only: it never trades.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import walk_forward_rule_search as wf  # noqa: E402
import price_action_features as pa  # noqa: E402
from evaluate_existing_rules import rule_mask  # noqa: E402


def spaced_returns(mask: np.ndarray, ret: np.ndarray, horizon: int, start: int) -> tuple[np.ndarray, np.ndarray]:
    """Take the first signal, then ignore signals until its horizon is over. Returns (indices, net returns)."""
    idx, out, free = [], [], start
    for i in np.flatnonzero(mask):
        if i < free or not np.isfinite(ret[i]):
            continue
        idx.append(i)
        out.append(ret[i])
        free = i + horizon
    return np.array(idx, dtype=int), np.array(out, dtype=float)


def evaluate(df: pd.DataFrame, cfg: wf.SearchConfig, feature: str, condition: str, side: str, htf_factor: int) -> dict:
    ind = wf.add_indicators(df).reset_index(drop=True)
    trades = wf.simulate_trades(ind, cfg)[f"{side}_ret"].to_numpy()
    conds = pa.price_action_conditions(ind, htf_factor).astype(str)
    mask = rule_mask(conds, feature, condition)
    idx, rets = spaced_returns(mask, trades, cfg.horizon, wf.WARMUP_BARS)
    n = len(ind)
    thirds = []
    for k in range(3):
        lo, hi = wf.WARMUP_BARS + (n - wf.WARMUP_BARS) * k // 3, wf.WARMUP_BARS + (n - wf.WARMUP_BARS) * (k + 1) // 3
        sel = rets[(idx >= lo) & (idx < hi)]
        thirds.append((len(sel), float(sel.mean()) if len(sel) else float("nan")))
    base = float(np.nanmean(trades[wf.WARMUP_BARS:]))
    return {"n": len(rets), "win": float((rets > 0).mean()) if len(rets) else float("nan"),
            "mean": float(rets.mean()) if len(rets) else float("nan"), "baseline": base, "thirds": thirds, "rets": rets}


def luck_chance(df: pd.DataFrame, cfg: wf.SearchConfig, feature: str, condition: str, side: str, htf_factor: int,
                real_mean: float, runs: int, seed: int) -> float:
    rng = np.random.default_rng(seed)
    beat = 0
    for _ in range(runs):
        fake = wf.shuffle_bars(df, rng)
        r = evaluate(fake, cfg, feature, condition, side, htf_factor)
        if r["n"] and r["mean"] >= real_mean:
            beat += 1
    return (beat + 1) / (runs + 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data-dir", default="checker_cache")
    parser.add_argument("--symbols", nargs="+", default=["BTC", "ETH", "BNB", "SOL"])
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument("--feature", required=True)
    parser.add_argument("--condition", required=True)
    parser.add_argument("--side", choices=["buy", "sell"], required=True)
    parser.add_argument("--cost", type=float, default=0.002)
    parser.add_argument("--htf-factor", type=int, default=7)
    parser.add_argument("--null-runs", type=int, default=500)
    parser.add_argument("--min-bars", type=int, default=800)
    parser.add_argument("--seed", type=int, default=5)
    args = parser.parse_args()
    cfg = wf.SearchConfig(cost=args.cost)
    print(f"Rule (fixed in advance): {args.side} when {args.feature} is {args.condition}; cost {args.cost:.2%} per trade, "
          f"stop {cfg.sl_atr} ATR, target {cfg.tp_atr} ATR, {cfg.horizon}-candle limit, trades never overlap\n")
    for sym in args.symbols:
        df = wf.load_history(Path(args.data_dir), sym, args.timeframe)
        if df is None or len(df) < args.min_bars:
            print(f"{sym}: skipped (not enough history)")
            continue
        r = evaluate(df, cfg, args.feature, args.condition, args.side, args.htf_factor)
        if r["n"] == 0:
            print(f"{sym}: the rule never fired")
            continue
        p = luck_chance(df, cfg, args.feature, args.condition, args.side, args.htf_factor, r["mean"], args.null_runs, args.seed)
        thirds = " | ".join(f"{n} trades {m:+.2%}" if n else "no trades" for n, m in r["thirds"])
        print(f"{sym}: {len(df)} candles, {r['n']} trades, win rate {r['win']:.0%}, average {r['mean']:+.2%} per trade "
              f"(buying every candle: {r['baseline']:+.2%}), luck chance {p:.2f}")
        print(f"   history in thirds: {thirds}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
