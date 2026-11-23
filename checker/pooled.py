"""Pooled daily check: one rule applied to several markets at once as an equal-weight bundle.

Used when each market has too little history on its own (Deriv gives only about a year of daily candles per index).
Every shuffled copy scrambles each market separately and rebuilds the bundle, so the luck test matches the real test.
A short history can never earn a pass: the best verdict here is 'inconclusive'.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import engine
from .engine import CheckResult, VERDICT_MAYBE, VERDICT_NONE, VERDICT_REFUSED, dtt

MIN_POOL_DAYS = 250
MIN_MARKETS = 3


def _bundle(closes: dict[str, pd.Series], rule: str, cost_one_way: float) -> pd.Series:
    cols = {k: engine._returns(c, rule, cost_one_way, 0.0, None) for k, c in closes.items()}
    return pd.DataFrame(cols).mean(axis=1, skipna=True).dropna()


def run_pool_check(closes: dict[str, pd.Series], rule: str, market: str = "", cost_round_trip: float = 0.001,
                   null_runs: int = 200, seed: int = 11, tests_counted: int = 1) -> CheckResult:
    if rule not in dtt.RULES:
        raise ValueError(f"unknown rule {rule!r}")
    closes = {k: c[c > 0].dropna().sort_index() for k, c in closes.items()}
    closes = {k: c for k, c in closes.items() if len(c) > 30}
    market = market or f"{len(closes)} markets pooled"
    days = max((len(c) for c in closes.values()), default=0)
    if len(closes) < MIN_MARKETS or days < MIN_POOL_DAYS:
        return CheckResult(rule, market, days, 0.0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, tests_counted, 0, cost_round_trip,
                           VERDICT_REFUSED, [f"Need at least {MIN_MARKETS} markets and {MIN_POOL_DAYS} days; have {len(closes)} markets, {days} days."])
    idx = sorted(set().union(*[set(c.index) for c in closes.values()]))
    years = (idx[-1] - idx[0]).days / 365.25
    ppy = len(idx) / years if years > 0 else 365.0
    net = _bundle(closes, rule, cost_round_trip / 2)
    gross = _bundle(closes, rule, 0.0)
    real = dtt.sharpe(net, ppy)
    rng = np.random.default_rng(seed)
    beaten = 0
    for _ in range(null_runs):
        fake = {k: dtt.shuffled_close(c, rng) for k, c in closes.items()}
        if dtt.sharpe(_bundle(fake, rule, cost_round_trip / 2), ppy) >= real:
            beaten += 1
    p = (beaten + 1) / (null_runs + 1)
    p_adj = min(1.0, p * max(1, tests_counted))
    half = len(net) // 2
    first, second = dtt.sharpe(net.iloc[:half], ppy), dtt.sharpe(net.iloc[half:], ppy)
    hold = pd.DataFrame({k: c.pct_change() for k, c in closes.items()}).mean(axis=1, skipna=True).dropna()
    total_ret = float((1 + net).prod() - 1) * 100
    gross_ret = float((1 + gross).prod() - 1) * 100
    hold_ret = float((1 + hold).prod() - 1) * 100
    break_even = None
    if gross_ret > 0 and cost_round_trip > 0:
        lg, ln = np.log1p(gross_ret / 100), np.log1p(max(total_ret / 100, -0.999999))
        drag = (lg - ln) / cost_round_trip
        break_even = float(lg / drag) if drag > 1e-12 else None
    trades = sum(engine._count_trades(c, rule) for c in closes.values())
    notes = [f"Only {years:.1f} years of history; short history can hide or fake an edge, so the best possible verdict is 'inconclusive'.",
             f"{len(closes)} markets were bundled with equal weight; a bundle is judged against bundles of scrambled markets."]
    if real > 0 and total_ret < hold_ret:
        notes.append("It earned less than simply holding the same bundle.")
    verdict = VERDICT_MAYBE if (p <= engine.MAYBE_P and real > 0 and p_adj <= 0.5) else VERDICT_NONE
    return CheckResult(rule, market, len(idx), round(years, 1), trades, round(real, 2), round(first, 2), round(second, 2),
                       round(total_ret, 1), round(hold_ret, 1), round(dtt.sharpe(hold, ppy), 2), round(p, 4), round(p_adj, 4),
                       tests_counted, null_runs, cost_round_trip, verdict, notes, "plain", round(gross_ret, 1),
                       None if break_even is None else round(break_even, 5))
