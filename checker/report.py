"""Turns an engine result into the plain-language Telegram message."""
from __future__ import annotations

from .engine import CheckResult, VERDICT_NONE, VERDICT_MAYBE, VERDICT_PASS, VERDICT_REFUSED

DISCLAIMER = "Past data cannot promise future profit. This is not financial advice and not a signal."

RULE_TEXT = {
    "momentum_20": "buy when the last 20 days were up, sell when down",
    "momentum_60": "buy when the last 60 days were up, sell when down",
    "momentum_120": "buy when the last 120 days were up, sell when down",
    "momentum_250": "buy when the last year was up, sell when down",
    "ma_cross_20_100": "buy when the 20-day average is above the 100-day average",
    "ma_cross_50_200": "buy when the 50-day average is above the 200-day average",
    "breakout_20": "buy a new 20-day high, sell a new 20-day low",
    "breakout_55": "buy a new 55-day high, sell a new 55-day low",
    "mean_reversion_5": "bet against sharp 5-day moves",
}

VERDICT_LINE = {
    VERDICT_NONE: "NO EVIDENCE OF AN EDGE. What it earned is what luck alone often produces.",
    VERDICT_MAYBE: "INCONCLUSIVE. Some signs, but not strong or long enough to trust.",
    VERDICT_PASS: "PASSES THE TESTS. It beat luck after costs. That is not a promise of profit.",
    VERDICT_REFUSED: "NOT ENOUGH HISTORY TO JUDGE.",
}


def luck_sentence(p: float, null_runs: int) -> str:
    if null_runs <= 0:
        return "Luck test not run."
    return f"In {null_runs:,} scrambled copies of this market, {p:.1%} did at least as well. That is the luck chance."


def format_report(res: CheckResult) -> str:
    title = f"Check: {RULE_TEXT.get(res.rule, res.rule)} on {res.market or 'this market'}"
    lines = [title, ""]
    lines.append(VERDICT_LINE.get(res.verdict, res.verdict))
    if res.verdict == VERDICT_REFUSED:
        lines += [""] + res.notes + ["", DISCLAIMER]
        return "\n".join(lines)
    lines += [
        "",
        f"History used: {res.years} years ({res.days:,} daily candles), {res.trades} trades.",
        f"Result after costs: {res.total_return_pct:+.1f}% in total. Simply holding earned {res.buy_hold_return_pct:+.1f}%.",
        f"First half of history: Sharpe {res.first_half_sharpe:+.2f}. Second half: {res.second_half_sharpe:+.2f}. (Above about 0.5 is decent.)",
        luck_sentence(res.p_luck, res.null_runs),
    ]
    if res.tests_counted > 1:
        lines.append(f"Today {res.tests_counted} combinations were tried in this service, so the luck chance is raised to {res.p_adjusted:.1%} to be fair.")
    lines.append(f"Costs assumed: {res.cost_round_trip:.2%} per round trip.")
    if res.notes:
        lines += ["", "Cautions:"] + [f"- {n}" for n in res.notes]
    lines += ["", DISCLAIMER]
    return "\n".join(lines)
