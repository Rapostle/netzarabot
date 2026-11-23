"""Strategy Honesty Checker: the engine.

Answers one question about one built-in rule on one market's daily history:
"is this result distinguishable from luck, after costs?"

It never trades and never predicts. It reuses the rules and the shuffled-data method of
work/daily_trend_test.py (position = yesterday's signal; costs on every position change).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "work"))
import daily_trend_test as dtt  # noqa: E402
from checker import layers as lay  # noqa: E402

RULE_NAMES = tuple(dtt.RULES)
MIN_DAYS = 500            # below this the engine refuses: too little data to say anything
STRONG_DAYS = 365 * 3     # below this a pass is downgraded to "inconclusive"
MIN_NULL_RUNS_FOR_PASS = 500
PASS_P = 0.05
MAYBE_P = 0.10

VERDICT_NONE = "no evidence of an edge"
VERDICT_MAYBE = "inconclusive"
VERDICT_PASS = "passes the tests (this is not a promise of profit)"
VERDICT_REFUSED = "not enough history to judge"


@dataclass
class CheckResult:
    rule: str
    market: str
    days: int
    years: float
    trades: int
    net_sharpe: float
    first_half_sharpe: float
    second_half_sharpe: float
    total_return_pct: float
    buy_hold_return_pct: float
    buy_hold_sharpe: float
    p_luck: float             # chance a shuffled copy of the same market does at least as well
    p_adjusted: float         # p_luck corrected for how many combinations were tried
    tests_counted: int
    null_runs: int
    cost_round_trip: float
    verdict: str
    notes: list[str] = field(default_factory=list)
    layers: str = "plain"
    gross_return_pct: float = 0.0          # same rule, same market, at zero cost
    break_even_cost: float | None = None   # round-trip cost at which total return reaches zero; None = no gross profit or no trades

    def as_dict(self) -> dict:
        return asdict(self)


def _returns(close: pd.Series, rule: str, cost_one_way: float, hold_cost: float, layers: "lay.Layers | None") -> pd.Series:
    if layers is None:
        return dtt.strategy_returns(close, rule, cost_one_way, hold_cost)
    return lay.layered_returns(close, dtt.RULES[rule](close), cost_one_way, hold_cost, layers)


def _count_trades(close: pd.Series, rule: str, layers: "lay.Layers | None" = None) -> int:
    position = lay.filtered_signal(close, dtt.RULES[rule](close), layers).shift(1).fillna(0.0)
    return int(position.diff().abs().fillna(position.abs()).sum() // 2 + (1 if position.iloc[-1] != 0 else 0))


def break_even_round_trip(close: pd.Series, rule: str, cost_round_trip: float, hold_cost: float,
                          layers: "lay.Layers | None", net: pd.Series) -> tuple[float, float | None]:
    """Gross total return (%) and the round-trip cost at which the total return falls to zero.
    Costs act almost linearly on log growth, so one probe at a known cost is enough."""
    gross_series = _returns(close, rule, 0.0, 0.0, layers)
    gross = float((1 + gross_series).prod() - 1)
    probe = cost_round_trip if cost_round_trip > 0 else 0.002
    probe_net = net if cost_round_trip > 0 else _returns(close, rule, probe / 2, hold_cost, layers)
    if gross <= 0 or probe_net.empty:
        return gross * 100, None
    lg, ln = np.log1p(gross), np.log1p(max(float((1 + probe_net).prod() - 1), -0.999999))
    drag = (lg - ln) / probe
    return gross * 100, (float(lg / drag) if drag > 1e-12 else None)


def run_check(close: pd.Series, rule: str, market: str = "", cost_round_trip: float = 0.002,
              hold_cost: float = 0.0, null_runs: int = 1000, seed: int = 11, tests_counted: int = 1,
              layers: "lay.Layers | None" = None) -> CheckResult:
    """Run one rule on one daily close series. `tests_counted` is how many market/rule
    combinations were tried in the same period (the correction for trying many)."""
    if rule not in dtt.RULES:
        raise ValueError(f"unknown rule {rule!r}; choose from {', '.join(RULE_NAMES)}")
    close = close[close > 0].dropna().sort_index()
    days = len(close)
    years = (close.index[-1] - close.index[0]).days / 365.25 if days > 1 else 0.0
    notes: list[str] = []
    if days < MIN_DAYS:
        return CheckResult(rule, market, days, round(years, 1), 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0,
                           tests_counted, 0, cost_round_trip, VERDICT_REFUSED,
                           [f"Only {days} daily candles; at least {MIN_DAYS} are needed."])

    ppy = days / years if years > 0 else 365.0
    half = days // 2
    net = _returns(close, rule, cost_round_trip / 2, hold_cost, layers)
    real = dtt.sharpe(net, ppy)
    rng = np.random.default_rng(seed)
    beaten = 0
    for _ in range(null_runs):
        fake = dtt.shuffled_close(close, rng)
        if dtt.sharpe(_returns(fake, rule, cost_round_trip / 2, hold_cost, layers), ppy) >= real:
            beaten += 1
    p = (beaten + 1) / (null_runs + 1)
    p_adj = min(1.0, p * max(1, tests_counted))
    first, second = dtt.sharpe(net.iloc[:half], ppy), dtt.sharpe(net.iloc[half:], ppy)
    hold_ret = float(close.iloc[-1] / close.iloc[0] - 1) * 100
    total_ret = float((1 + net).prod() - 1) * 100
    trades = _count_trades(close, rule, layers)
    gross_ret, break_even = break_even_round_trip(close, rule, cost_round_trip, hold_cost, layers, net)
    persistent = first > 0 and second > 0 and real > 0

    if null_runs < MIN_NULL_RUNS_FOR_PASS:
        notes.append(f"Only {null_runs} shuffled copies were used, too few to call a pass.")
    if years < STRONG_DAYS / 365:
        notes.append(f"Only {years:.1f} years of history; short history can hide or fake an edge.")
    if trades < 20:
        notes.append(f"Only {trades} trades; too few to be sure of anything.")
    if real > 0 and total_ret < hold_ret:
        notes.append("It earned less than simply holding the coin over the same period.")

    if p_adj <= PASS_P and persistent and null_runs >= MIN_NULL_RUNS_FOR_PASS:
        verdict = VERDICT_PASS
        if days < STRONG_DAYS or trades < 20:
            verdict = VERDICT_MAYBE
        elif total_ret < hold_ret:
            verdict = VERDICT_MAYBE
            notes.append("A pass is downgraded when the rule did not beat holding.")
    elif p <= MAYBE_P and real > 0:
        verdict = VERDICT_MAYBE
    else:
        verdict = VERDICT_NONE
    return CheckResult(rule, market, days, round(years, 1), trades, round(real, 2), round(first, 2), round(second, 2),
                       round(total_ret, 1), round(hold_ret, 1), round(dtt.sharpe(close.pct_change().fillna(0.0), ppy), 2),
                       round(p, 4), round(p_adj, 4), tests_counted, null_runs, cost_round_trip, verdict, notes, layers.label() if layers else "plain",
                       round(gross_ret, 1), None if break_even is None else round(break_even, 5))
