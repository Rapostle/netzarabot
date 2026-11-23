"""One-screen summary of every rule on one coin: daily rules and the intraday rules side by side."""
from __future__ import annotations

from .engine import CheckResult
from .intraday import IntradayResult
from .report import DISCLAIMER


def _pct(x: float | None) -> str:
    return "-" if x is None else f"{x:.2%}"


def format_summary(coin: str, daily: list[CheckResult], intraday: list[IntradayResult], tries: int | None = None) -> str:
    lines = [f"All rules on {coin}", ""]
    if daily:
        lines.append("Daily rules (total return over the whole history):")
        lines.append(f"{'rule':<17}{'before costs':>13}{'after costs':>12}{'break-even':>11}{'luck':>7}  verdict")
        for r in sorted(daily, key=lambda r: r.p_adjusted):
            if r.verdict.startswith("not enough"):
                lines.append(f"{r.rule:<17}{'not enough history':>43}")
                continue
            lines.append(f"{r.rule:<17}{r.gross_return_pct:>+12.0f}%{r.total_return_pct:>+11.0f}%{_pct(r.break_even_cost):>11}{r.p_adjusted:>7.2f}  {r.verdict.split(' (')[0]}")
        hold = daily[0].buy_hold_return_pct
        lines.append(f"Simply holding {coin} earned {hold:+.0f}%. The luck column is corrected for {tries or len(daily)} tries.")
    if intraday:
        lines += ["", "Intraday rules (average per trade, R = distance to the stop):"]
        lines.append(f"{'rule':<17}{'trades':>7}{'before':>9}{'after':>9}{'break-even':>11}{'luck':>7}  verdict")
        for r in intraday:
            if r.trades < 1 or r.verdict.startswith("not enough"):
                lines.append(f"{r.rule:<17}{'not enough trades':>43}")
                continue
            lines.append(f"{r.rule:<17}{r.trades:>7}{r.gross_r:>+9.3f}{r.net_r:>+9.3f}{_pct(r.break_even_cost):>11}{r.p_luck:>7.2f}  {r.verdict.split(' (')[0]}")
    lines += ["", "'Inconclusive' means it looked good before the correction for trying many rules, and not good enough after it.",
              "A rule only counts if its luck chance is about 0.05 or below, it holds in both halves of the history, and it still earns after costs.", DISCLAIMER]
    return "\n".join(lines)
