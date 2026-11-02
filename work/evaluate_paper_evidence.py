#!/usr/bin/env python3
"""Honest evaluation of NetzaraBot paper-trading evidence.

Why this exists: the live gate in deriv_direct_executor.py passes a track at
>=65% win rate over >=15 closed trades. That is easy to pass by luck, and the
same entry can appear in several tracks, so the effective sample is smaller
than the row count. This script:

  1. Loads every *_closed_trades.csv and de-duplicates identical entries
     (same symbol + opened_at + side) that were taken by more than one track.
  2. Computes win rate with a Wilson 95% interval, the break-even win rate
     implied by the actual average win / average loss, profit factor,
     expectancy per trade, max drawdown, and a bootstrap interval on the
     mean PnL per trade.
  3. Splits trades chronologically (first 60% / last 40%) so later trades
     act as a rough out-of-sample check.
  4. Marks a group QUALIFIED only when it has enough independent trades AND
     the lower Wilson bound clears break-even AND the bootstrap lower bound
     on mean PnL is above zero AND the later split is not losing.

Standard library only. Read-only: it never touches any Deriv API or token.

Usage:
    python3 work/evaluate_paper_evidence.py [--root PATH] [--min-trades 30]
                                            [--out reports/paper_evidence_report.md]
"""
from __future__ import annotations

import argparse
import csv
import math
import random
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

TRACK_FILES = {
    "Experimental pair candidates": "outputs/pair_candidate_closed_trades.csv",
    "Advanced sniper candidates": "outputs/advanced_sniper_closed_trades.csv",
    "Boom/Crash expansion candidates": "outputs/boom_crash_expansion_closed_trades.csv",
    "Original stable rules": "outputs/paper_stable_closed_trades.csv",
    "Strict research candidates": "outputs/strict_research_closed_trades.csv",
}

RULE_RE = re.compile(r"rule\s+([A-Za-z]+\d+)")


def parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_trades(root: Path) -> list[dict]:
    trades: list[dict] = []
    for track, rel in TRACK_FILES.items():
        path = root / rel
        if not path.exists():
            continue
        with path.open(newline="") as handle:
            for row in csv.DictReader(handle):
                try:
                    pnl = float(row["paper_pnl"])
                except (KeyError, ValueError):
                    continue
                match = RULE_RE.search(row.get("reason", ""))
                trades.append(
                    {
                        "track": track,
                        "symbol": row.get("symbol", ""),
                        "side": row.get("side", ""),
                        "opened_at": parse_time(row.get("opened_at", "")),
                        "opened_raw": row.get("opened_at", ""),
                        "pnl": pnl,
                        "rule": match.group(1) if match else "unknown",
                        "exit_reason": row.get("exit_reason", ""),
                    }
                )
    return trades


def dedupe(trades: list[dict]) -> tuple[list[dict], int]:
    """Collapse the same entry taken by several tracks into one trade.

    The same entry can close differently in different tracks (different exit
    rules), so the pooled trade uses the average PnL across the tracks that
    took it, rather than an arbitrary one of them.
    """
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for trade in sorted(trades, key=lambda t: t["opened_at"]):
        groups[(trade["symbol"], trade["opened_raw"], trade["side"])].append(trade)
    unique = []
    for members in groups.values():
        merged = dict(members[0])
        merged["pnl"] = sum(m["pnl"] for m in members) / len(members)
        merged["tracks"] = {m["track"] for m in members}
        unique.append(merged)
    unique.sort(key=lambda t: t["opened_at"])
    return unique, len(trades) - len(unique)


def per_track_pnl(trades: list[dict], track: str) -> list[float]:
    """A track's own trades, in time order, using that track's own PnL."""
    own = sorted((t for t in trades if t["track"] == track), key=lambda t: t["opened_at"])
    return [t["pnl"] for t in own]


def wilson(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def bootstrap_mean_lower(pnl: list[float], iterations: int = 4000, seed: int = 7) -> float:
    """5th percentile of the bootstrapped mean PnL per trade."""
    if not pnl:
        return 0.0
    rng = random.Random(seed)
    n = len(pnl)
    means = sorted(sum(rng.choice(pnl) for _ in range(n)) / n for _ in range(iterations))
    return means[int(0.05 * iterations)]


def max_drawdown(pnl: list[float]) -> float:
    peak = equity = worst = 0.0
    for value in pnl:
        equity += value
        peak = max(peak, equity)
        worst = min(worst, equity - peak)
    return worst


def stats(pnl: list[float]) -> dict:
    n = len(pnl)
    wins = [p for p in pnl if p > 0]
    losses = [p for p in pnl if p < 0]
    gross_win = sum(wins)
    gross_loss = -sum(losses)
    avg_win = gross_win / len(wins) if wins else 0.0
    avg_loss = gross_loss / len(losses) if losses else 0.0
    breakeven = avg_loss / (avg_win + avg_loss) if (avg_win + avg_loss) else 0.5
    lo, hi = wilson(len(wins), n)
    return {
        "n": n,
        "wins": len(wins),
        "win_rate": len(wins) / n if n else 0.0,
        "wilson_lo": lo,
        "wilson_hi": hi,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "breakeven": breakeven,
        "profit_factor": gross_win / gross_loss if gross_loss else float("inf"),
        "total": sum(pnl),
        "expectancy": sum(pnl) / n if n else 0.0,
        "boot_lo": bootstrap_mean_lower(pnl),
        "drawdown": max_drawdown(pnl),
    }


def walk_forward(pnl: list[float], train_fraction: float = 0.6) -> tuple[dict, dict]:
    cut = max(1, int(len(pnl) * train_fraction))
    return stats(pnl[:cut]), stats(pnl[cut:])


def verdict(pnl: list[float], min_trades: int) -> tuple[bool, list[str]]:
    s = stats(pnl)
    _, late = walk_forward(pnl)
    reasons = []
    if s["n"] < min_trades:
        reasons.append(f"only {s['n']} independent trades (need {min_trades})")
    if s["wilson_lo"] <= s["breakeven"]:
        reasons.append(
            f"win-rate lower bound {s['wilson_lo']:.0%} does not clear break-even {s['breakeven']:.0%}"
        )
    if s["boot_lo"] <= 0:
        reasons.append(f"mean PnL lower bound {s['boot_lo']:+.2f}/trade is not above zero")
    if late["n"] and late["total"] <= 0:
        reasons.append("the later 40% of trades is not profitable")
    return (not reasons), reasons


def fmt_pf(value: float) -> str:
    return "inf" if math.isinf(value) else f"{value:.2f}"


def row(label: str, pnl: list[float], min_trades: int) -> str:
    s = stats(pnl)
    ok, reasons = verdict(pnl, min_trades)
    status = "QUALIFIED" if ok else "not yet"
    why = "" if ok else "; ".join(reasons)
    return (
        f"| {label} | {s['n']} | {s['win_rate']:.0%} ({s['wilson_lo']:.0%}-{s['wilson_hi']:.0%}) "
        f"| {s['breakeven']:.0%} | {fmt_pf(s['profit_factor'])} | {s['expectancy']:+.2f} "
        f"({s['boot_lo']:+.2f}) | {s['total']:+.2f} | {s['drawdown']:.2f} | {status} | {why} |"
    )


HEADER = (
    "| group | trades | win rate (95% range) | break-even win rate | profit factor "
    "| avg PnL/trade (5% lower bound) | total PnL | max drawdown | verdict | why not |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
)


def build_report(root: Path, min_trades: int) -> str:
    raw = load_trades(root)
    if not raw:
        return "No closed-trade files found. Check --root.\n"
    unique, dupes = dedupe(raw)
    lines: list[str] = []
    lines.append("# Paper Evidence Report")
    lines.append("")
    lines.append(f"Generated UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    lines.append("")
    lines.append(
        f"Closed-trade rows: {len(raw)}. Independent entries after removing overlap between tracks: "
        f"{len(unique)} ({dupes} duplicate rows removed)."
    )
    lines.append(f"Qualification needs at least {min_trades} independent trades.")
    lines.append("")
    lines.append("## All independent trades (pooled)")
    lines.append("")
    lines.append(HEADER)
    pooled = [t["pnl"] for t in unique]
    lines.append(row("Pooled", pooled, min_trades))
    early, late = walk_forward(pooled)
    lines.append("")
    lines.append(
        f"Chronological split: first 60% = {early['n']} trades, {early['total']:+.2f} PnL, "
        f"{early['win_rate']:.0%} wins; last 40% = {late['n']} trades, {late['total']:+.2f} PnL, "
        f"{late['win_rate']:.0%} wins."
    )

    lines.append("")
    lines.append("## By track (each track's own recorded trades and PnL; tracks overlap, so do not add them up)")
    lines.append("")
    lines.append(HEADER)
    for track in TRACK_FILES:
        own = per_track_pnl(raw, track)
        if own:
            lines.append(row(track, own, min_trades))

    lines.append("")
    lines.append("## By symbol")
    lines.append("")
    lines.append(HEADER)
    by_symbol: dict[str, list[float]] = defaultdict(list)
    for t in unique:
        by_symbol[t["symbol"]].append(t["pnl"])
    for symbol, values in sorted(by_symbol.items()):
        lines.append(row(symbol, values, min_trades))

    lines.append("")
    lines.append("## By rule (small samples: treat as leads, not evidence)")
    lines.append("")
    lines.append(HEADER)
    by_rule: dict[str, list[float]] = defaultdict(list)
    for t in unique:
        by_rule[t["rule"]].append(t["pnl"])
    for rule, values in sorted(by_rule.items(), key=lambda kv: -len(kv[1])):
        lines.append(row(rule, values, min_trades))

    lines.append("")
    lines.append("## How to read this")
    lines.append("")
    lines.append(
        "- A win rate only matters relative to break-even: with unequal wins and losses, 60% can lose money."
    )
    lines.append(
        "- The 95% range is how far the true win rate could plausibly sit from what was measured; with 20-40 trades it is wide."
    )
    lines.append(
        "- Backtests on the same data used to choose the rules are optimistic. Only trades recorded after a rule was chosen count."
    )
    lines.append(
        "- Boom/Crash are synthetic indices generated by a random process. Any edge here needs to survive more trades than this before real money."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=".", help="repo root containing outputs/")
    parser.add_argument("--min-trades", type=int, default=30)
    parser.add_argument("--out", default="reports/paper_evidence_report.md")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    report = build_report(root, args.min_trades)
    out = root / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report)
    print(report)
    print(f"Written to {out}")


if __name__ == "__main__":
    main()
