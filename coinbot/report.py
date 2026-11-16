"""Weekly plain-language comparison of the two coin paper books (pretend money)."""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

MIN_TRADES_FOR_VERDICT = 30


def _journal(outputs: Path, name: str) -> list[dict]:
    path = outputs / f"coin_paper_{name}_journal.csv"
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _state(outputs: Path, name: str) -> dict:
    path = outputs / f"coin_paper_{name}_state.json"
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {"positions": {}, "closed": 0, "wins": 0, "realized": 0.0}


def last_prices(cache_dir: Path, markets: set[str]) -> dict[str, float]:
    out = {}
    for market in markets:
        path = cache_dir / f"{market}_1d.csv"
        try:
            df = pd.read_csv(path)
            out[market] = float(df["close"].iloc[-2])  # the last row can be an unfinished candle
        except (OSError, ValueError, KeyError, IndexError):
            continue
    return out


def book_stats(outputs: Path, name: str, prices: dict[str, float], notional: float = 100.0, cost: float = 0.002) -> dict:
    state = _state(outputs, name)
    unreal = sum(p["side"] * (prices[k.split("|")[0]] / p["entry"] - 1.0) * notional
                 for k, p in state["positions"].items() if k.split("|")[0] in prices)
    rows = [r for r in _journal(outputs, name) if r["action"] in ("close", "stop", "target") and r["pnl"] not in ("", None)]
    nets = [float(r["pnl"]) - notional * cost / 2 for r in rows]  # charge the opening half-cost to each closed trade
    by_rule: dict[str, list[float]] = {}
    for r, n in zip(rows, nets):
        by_rule.setdefault(r["rule"], []).append(n)
    return {"name": name, "open": len(state["positions"]), "closed": len(rows),
            "wins": sum(1 for n in nets if n > 0), "net_closed": sum(nets), "avg": (sum(nets) / len(nets)) if nets else 0.0,
            "realized_state": float(state.get("realized", 0.0)), "unrealized": unreal,
            "by_rule": {k: (len(v), sum(v)) for k, v in by_rule.items()}}


def _line(s: dict) -> str:
    wr = f"{s['wins'] / s['closed']:.0%}" if s["closed"] else "n/a"
    return (f"{s['name']}: {s['closed']} closed, win rate {wr}, average {s['avg']:+.2f} USD per trade, "
            f"{s['open']} open (unrealized {s['unrealized']:+.2f}), total incl. open {s['realized_state'] + s['unrealized']:+.2f} USD")


def build_weekly(outputs: Path, cache_dir: Path, now: datetime) -> str:
    markets = {k.split("|")[0] for k in _state(outputs, "gated")["positions"]}
    prices = last_prices(cache_dir, markets)
    g = book_stats(outputs, "gated", prices)
    exits: dict[str, int] = {}
    for r in _journal(outputs, "gated"):
        if r["action"] in ("close", "stop", "target"):
            exits[r["action"]] = exits.get(r["action"], 0) + 1
    lines = [f"Coin paper bot, weekly report (PRETEND money), {now:%d %b %Y}", "", _line(g)]
    if exits:
        lines.append("How trades ended: " + ", ".join(f"{n} by {'rule flip' if k == 'close' else k + (' hit' if k != 'target' else ' hit')}" for k, n in sorted(exits.items())))
    lines.append("")
    if g["closed"] < MIN_TRADES_FOR_VERDICT:
        lines.append(f"Verdict: too early. {g['closed']} closed trades so far; we need {MIN_TRADES_FOR_VERDICT} before judging.")
    elif g["avg"] > 0:
        lines.append(f"Verdict: ahead so far, {g['avg']:+.2f} USD per trade on pretend money. Treat it as ONE experiment: the bets overlap "
                     "(many rules and coins move together), so it is weaker evidence than the trade count suggests.")
    else:
        lines.append(f"Verdict: not working so far, {g['avg']:+.2f} USD per trade on pretend money.")
    ranked = sorted(g["by_rule"].items(), key=lambda kv: kv[1][1])
    if ranked:
        worst, best = ranked[:2], ranked[-2:][::-1]
        lines += ["", "By rule (closed trades / net USD): best " + ", ".join(f"{k} {n} / {t:+.2f}" for k, (n, t) in best)
                  + "; worst " + ", ".join(f"{k} {n} / {t:+.2f}" for k, (n, t) in worst)]
    lines += ["", "Short positions ignore funding fees, so shorts look slightly better than they would be live.",
              "Real-money trading: DISARMED"]
    return "\n".join(lines)
