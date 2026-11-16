"""Coin paper-trading bot: daily rules on BTC, ETH and others with PRETEND money. It never touches an exchange.

Two books run side by side on the same signals:
  ungated : every rule trades
  gated   : a rule trades only while the honesty checker's verdict allows it
so after a few months we can see whether the checker's verdict actually predicted anything.
Signals come only from CLOSED daily candles. Costs are charged on every open and close.
"""
from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from checker import engine  # noqa: E402

GATE_MODES = ("off", "watch", "strict")  # off: always allowed; watch: pass or inconclusive; strict: pass only
JOURNAL_FIELDS = ["time", "book", "market", "rule", "action", "side", "price", "notional", "pnl", "gate_verdict", "note"]


def closed_only(close: pd.Series, now: datetime) -> pd.Series:
    """Drop today's unfinished daily candle (UTC)."""
    today = now.astimezone(timezone.utc).date()
    return close[[d.date() < today for d in close.index]]


def gate_allows(mode: str, verdict: str) -> bool:
    if mode == "off":
        return True
    if mode == "watch":
        return verdict in (engine.VERDICT_PASS, engine.VERDICT_MAYBE)
    return verdict == engine.VERDICT_PASS


@dataclass
class Combo:
    market: str
    rule: str

    @property
    def key(self) -> str:
        return f"{self.market}|{self.rule}"


class Book:
    def __init__(self, name: str, mode: str, directory: str, notional: float = 100.0, cost_round_trip: float = 0.002):
        if mode not in GATE_MODES:
            raise ValueError(f"gate mode must be one of {GATE_MODES}")
        self.name, self.mode, self.notional, self.cost = name, mode, float(notional), float(cost_round_trip)
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.dir / f"coin_paper_{name}_state.json"
        self.journal_path = self.dir / f"coin_paper_{name}_journal.csv"
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {"positions": {}, "last_day": {}, "realized": 0.0, "closed": 0, "wins": 0}

    def _save(self) -> None:
        self.state_path.write_text(json.dumps(self.state, indent=1))

    def _log(self, row: dict) -> None:
        new = not self.journal_path.exists()
        with self.journal_path.open("a", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=JOURNAL_FIELDS)
            if new:
                writer.writeheader()
            writer.writerow({k: row.get(k, "") for k in JOURNAL_FIELDS})

    def step(self, combo: Combo, close: pd.Series, verdict: str, now: datetime) -> str:
        """Act on the latest closed candle once. Returns what happened."""
        dtt = engine.dtt  # the same rules the checker tests
        close = closed_only(close, now)
        if len(close) < engine.MIN_DAYS:
            return "skipped: not enough history"
        day = str(close.index[-1].date())
        if self.state["last_day"].get(combo.key) == day:
            return "skipped: already handled this candle"
        self.state["last_day"][combo.key] = day
        signal = int(dtt.RULES[combo.rule](close).iloc[-1])
        price = float(close.iloc[-1])
        allowed = gate_allows(self.mode, verdict)
        desired = signal if allowed else 0
        held = self.state["positions"].get(combo.key)
        current = held["side"] if held else 0
        note = ""
        if desired == current:
            self._save()
            blocked = " (gate blocked)" if (not allowed and signal != 0) else ""
            return ("hold" if current else "flat") + blocked
        stamp = now.astimezone(timezone.utc).isoformat(timespec="seconds")
        if held:
            gross = held["side"] * (price / held["entry"] - 1.0) * self.notional
            pnl = gross - self.notional * self.cost / 2
            self.state["realized"] += pnl
            self.state["closed"] += 1
            self.state["wins"] += 1 if pnl > 0 else 0
            del self.state["positions"][combo.key]
            self._log({"time": stamp, "book": self.name, "market": combo.market, "rule": combo.rule, "action": "close",
                       "side": held["side"], "price": price, "notional": self.notional, "pnl": round(pnl, 4), "gate_verdict": verdict})
        if desired != 0:
            self.state["realized"] -= self.notional * self.cost / 2
            self.state["positions"][combo.key] = {"side": desired, "entry": price, "opened": day}
            self._log({"time": stamp, "book": self.name, "market": combo.market, "rule": combo.rule, "action": "open",
                       "side": desired, "price": price, "notional": self.notional, "pnl": "", "gate_verdict": verdict,
                       "note": note})
        if not allowed and signal != 0:
            note = "gate blocked"
        self._save()
        return f"changed {current}->{desired}" + (f" ({note})" if note else "")

    def summary(self, last_prices: dict[str, float]) -> dict:
        unreal = 0.0
        for key, pos in self.state["positions"].items():
            market = key.split("|")[0]
            if market in last_prices:
                unreal += pos["side"] * (last_prices[market] / pos["entry"] - 1.0) * self.notional
        closed = self.state["closed"]
        return {"book": self.name, "mode": self.mode, "open": len(self.state["positions"]), "closed": closed,
                "win_rate": round(self.state["wins"] / closed, 3) if closed else 0.0,
                "realized_usd": round(self.state["realized"], 2), "unrealized_usd": round(unreal, 2)}


def run_cycle(books: list[Book], combos: list[Combo], closes: dict[str, pd.Series], gate: Callable[[str, str, pd.Series], str],
              now: datetime | None = None) -> dict[str, list[str]]:
    now = now or datetime.now(timezone.utc)
    out: dict[str, list[str]] = {b.name: [] for b in books}
    for combo in combos:
        close = closes.get(combo.market)
        if close is None:
            continue
        verdict = gate(combo.market, combo.rule, closed_only(close, now))
        for book in books:
            out[book.name].append(f"{combo.key}: {book.step(combo, close, verdict, now)}")
    return out
