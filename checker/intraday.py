"""Strategy Honesty Checker: stop-and-target (intraday) rules on hourly crypto candles.

Judge = the same rule on day-shuffled prices at ZERO cost. Tight stops with timed exits can show a
gross profit on random data, so a rule only counts if it beats its own shuffles. Nothing here trades.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "work"))
import power_of_three_test as p3  # noqa: E402

INTRADAY_RULES = tuple(p3.RULES)       # judas, wr
MIN_TRADES = 100
MIN_NULL_RUNS_FOR_PASS = 100
PASS_P = 0.05

V_NONE = "no evidence of an edge"
V_MAYBE = "inconclusive"
V_PASS = "passes the tests (this is not a promise of profit)"
V_REFUSED = "not enough trades to judge"


@dataclass
class IntradayResult:
    rule: str
    market: str
    trades: int
    gross_r: float            # average result per trade at zero cost, in multiples of the stop distance (R)
    net_r: float
    first_half_r: float
    second_half_r: float
    win_rate: float
    shuffled_avg_r: float
    p_luck: float
    null_runs: int
    cost_round_trip: float
    break_even_cost: float | None
    verdict: str
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def run_intraday_check(df: pd.DataFrame, rule: str, market: str = "", cost_round_trip: float = p3.NET_COST,
                       null_runs: int = 200, seed: int = 9) -> IntradayResult:
    return run_intraday_pool({market or "market": df}, rule, market, cost_round_trip, null_runs, seed)


def run_intraday_pool(frames: dict[str, pd.DataFrame], rule: str, market: str = "", cost_round_trip: float = p3.NET_COST,
                      null_runs: int = 200, seed: int = 9) -> IntradayResult:
    """One verdict over several coins at once: their trades are pooled, and each shuffled copy
    scrambles every coin's days and pools again, so the luck test matches the real test."""
    if rule not in INTRADAY_RULES:
        raise ValueError(f"unknown intraday rule {rule!r}; choose from {', '.join(INTRADAY_RULES)}")
    market = market or "+".join(frames)
    gs, ns, first, second, pos, used = [], [], [], [], 0, 0
    for df in frames.values():
        g = p3.trades(df, rule, 0.0)
        if len(g) == 0:
            continue
        gs.append(g)
        ns.append(p3.trades(df, rule, cost_round_trip))
        h = len(g) // 2
        first.append(g[:h]); second.append(g[h:])
        pos += g.mean() > 0
        used += 1
    total = sum(len(g) for g in gs)
    if total < MIN_TRADES:
        return IntradayResult(rule, market, total, 0, 0, 0, 0, 0, 0, 1.0, 0, cost_round_trip, None, V_REFUSED,
                              [f"Only {total} trades; at least {MIN_TRADES} are needed."])
    g, n = np.concatenate(gs), np.concatenate(ns)
    gm, nm = float(g.mean()), float(n.mean())
    f1, f2 = float(np.concatenate(first).mean()), float(np.concatenate(second).mean())
    rng = np.random.default_rng(seed)
    null = []
    for _ in range(null_runs):
        rs = [p3.trades(p3.day_shuffle(df, rng), rule, 0.0) for df in frames.values()]
        rs = [x for x in rs if len(x)]
        if rs:
            null.append(float(np.concatenate(rs).mean()))
    null_a = np.array(null) if null else np.array([np.nan])
    p = (int(np.nansum(null_a >= gm)) + 1) / (int(np.isfinite(null_a).sum()) + 1)
    drag = gm - nm
    break_even = cost_round_trip * gm / drag if gm > 0 and drag > 1e-12 and cost_round_trip > 0 else None
    notes: list[str] = []
    if null_runs < MIN_NULL_RUNS_FOR_PASS:
        notes.append(f"Only {null_runs} shuffled copies were used, too few to call a pass.")
    if nm <= 0 < gm:
        notes.append("It makes money before costs and loses after them.")
    if len(frames) > 1:
        notes.append(f"Pooled {used} coins; it made money before costs on {pos} of them.")
    persistent = f1 > 0 and f2 > 0
    if p <= PASS_P and persistent and nm > 0 and null_runs >= MIN_NULL_RUNS_FOR_PASS and pos > used / 2:
        verdict = V_PASS
    elif p <= 0.10 and gm > 0:
        verdict = V_MAYBE
    else:
        verdict = V_NONE
    return IntradayResult(rule, market, total, round(gm, 3), round(nm, 3), round(f1, 3), round(f2, 3),
                          round(float((g > 0).mean()), 3), round(float(np.nanmean(null_a)), 3), round(p, 4), null_runs,
                          cost_round_trip, None if break_even is None else round(break_even, 5), verdict, notes)
