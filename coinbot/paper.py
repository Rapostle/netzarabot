"""Coin paper-trading bot: daily rules on BTC, ETH and others with PRETEND money. It never touches an exchange.

One book, "gated": a rule trades only while the honesty checker's verdict allows it (pass or inconclusive).
Signals come only from CLOSED daily candles. Costs are charged on every open and close.
Optional risk layers (see checker/layers.py): skip choppy markets, and size positions down when volatility is high.
Every position also has a stop-loss and a take-profit (in daily ATRs), checked against each day's high and low.
Note: the checker's verdict tests the rule WITHOUT stops, so the stops are an extra risk control, not part of the verdict.
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
from checker import layers as lay  # noqa: E402

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


def atr14(high: pd.Series, low: pd.Series, close: pd.Series) -> float:
    prev = close.shift(1)
    tr = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    return float(tr.rolling(14).mean().iloc[-1])


class Book:
    def __init__(self, name: str, mode: str, directory: str, notional: float = 100.0, cost_round_trip: float = 0.002,
                 stop_atr: float = 3.0, take_atr: float = 6.0, layers: "lay.Layers | None" = None):
        if mode not in GATE_MODES:
            raise ValueError(f"gate mode must be one of {GATE_MODES}")
        self.name, self.mode, self.notional, self.cost = name, mode, float(notional), float(cost_round_trip)
        self.stop_atr, self.take_atr = float(stop_atr), float(take_atr)
        self.layers = layers
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.dir / f"coin_paper_{name}_state.json"
        self.journal_path = self.dir / f"coin_paper_{name}_journal.csv"
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {}
        for key, default in (("positions", {}), ("last_day", {}), ("realized", 0.0), ("closed", 0), ("wins", 0), ("cooldown", {})):
            self.state.setdefault(key, default)

    def _save(self) -> None:
        self.state_path.write_text(json.dumps(self.state, indent=1))

    def _log(self, row: dict) -> None:
        new = not self.journal_path.exists()
        with self.journal_path.open("a", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=JOURNAL_FIELDS)
            if new:
                writer.writeheader()
            writer.writerow({k: row.get(k, "") for k in JOURNAL_FIELDS})

    def _close(self, combo: Combo, held: dict, price: float, action: str, stamp: str, verdict: str) -> float:
        size_usd = float(held.get("notional", self.notional))
        gross = held["side"] * (price / held["entry"] - 1.0) * size_usd
        pnl = gross - size_usd * self.cost / 2
        self.state["realized"] += pnl
        self.state["closed"] += 1
        self.state["wins"] += 1 if pnl > 0 else 0
        del self.state["positions"][combo.key]
        self._log({"time": stamp, "book": self.name, "market": combo.market, "rule": combo.rule, "action": action,
                   "side": held["side"], "price": price, "notional": round(size_usd, 4), "pnl": round(pnl, 4), "gate_verdict": verdict})
        return pnl

    def _levels(self, side: int, price: float, atr: float) -> tuple[float | None, float | None]:
        if not atr or atr != atr:
            return None, None
        stop = price - side * self.stop_atr * atr if self.stop_atr > 0 else None
        target = price + side * self.take_atr * atr if self.take_atr > 0 else None
        return stop, target

    def _hit(self, held: dict, high: pd.Series, low: pd.Series) -> tuple[str, float] | None:
        """First stop or target touched by candles after the position opened (stop wins if both in one candle)."""
        side, stop, target = held["side"], held.get("stop"), held.get("target")
        for ts in high.index:
            if str(ts.date()) <= held["opened"]:
                continue
            hi, lo = float(high[ts]), float(low[ts])
            stop_hit = stop is not None and ((lo <= stop) if side == 1 else (hi >= stop))
            take_hit = target is not None and ((hi >= target) if side == 1 else (lo <= target))
            if stop_hit:
                return "stop", stop
            if take_hit:
                return "target", target
        return None

    def step(self, combo: Combo, close: pd.Series, verdict: str, now: datetime,
             high: pd.Series | None = None, low: pd.Series | None = None) -> str:
        """Act on the latest closed candle once. Returns what happened."""
        dtt = engine.dtt  # the same rules the checker tests
        close = closed_only(close, now)
        if len(close) < engine.MIN_DAYS:
            return "skipped: not enough history"
        day = str(close.index[-1].date())
        if self.state["last_day"].get(combo.key) == day:
            return "skipped: already handled this candle"
        self.state["last_day"][combo.key] = day
        have_ohlc = high is not None and low is not None
        if have_ohlc:
            high, low = closed_only(high, now), closed_only(low, now)
            atr = atr14(high, low, close)
        else:
            atr = float("nan")
        stamp = now.astimezone(timezone.utc).isoformat(timespec="seconds")
        raw = dtt.RULES[combo.rule](close)
        if self.layers is not None:
            signal, size = lay.latest_signal_and_size(close, raw, self.layers)
        else:
            signal, size = int(raw.iloc[-1]), 1.0
        price = float(close.iloc[-1])
        held = self.state["positions"].get(combo.key)
        if held and have_ohlc:
            if "stop" not in held and "target" not in held:  # position opened before stops existed
                held["stop"], held["target"] = self._levels(held["side"], held["entry"], atr)
            hit = self._hit(held, high, low)
            if hit:
                kind, level = hit
                self._close(combo, held, float(level), kind, stamp, verdict)
                self.state["cooldown"][combo.key] = held["side"]  # no re-entry on the same side until the signal changes
                self._save()
                return f"{kind} hit at {level:.4f}, closed"
        allowed = gate_allows(self.mode, verdict)
        cool = self.state["cooldown"].get(combo.key)
        cooling = False
        if cool is not None:
            if signal == cool:
                cooling = True
            else:
                del self.state["cooldown"][combo.key]
        desired = signal if (allowed and not cooling) else 0
        current = held["side"] if held else 0
        note = "gate blocked" if (not allowed and signal != 0) else ("cooling off after stop or target" if cooling else "")
        if desired == current:
            self._save()
            return ("hold" if current else "flat") + (f" ({note})" if note else "")
        if held:
            self._close(combo, held, price, "close", stamp, verdict)
        if desired != 0:
            size_usd = self.notional * size
            self.state["realized"] -= size_usd * self.cost / 2
            stop, target = self._levels(desired, price, atr)
            self.state["positions"][combo.key] = {"side": desired, "entry": price, "opened": day, "stop": stop, "target": target,
                                                  "notional": size_usd}
            self._log({"time": stamp, "book": self.name, "market": combo.market, "rule": combo.rule, "action": "open",
                       "side": desired, "price": price, "notional": round(size_usd, 4), "pnl": "", "gate_verdict": verdict,
                       "note": note or (f"size {size:.2f}" if size < 1 else "")})
        self._save()
        return f"changed {current}->{desired}" + (f" ({note})" if note else "")

    def summary(self, last_prices: dict[str, float]) -> dict:
        unreal = 0.0
        for key, pos in self.state["positions"].items():
            market = key.split("|")[0]
            if market in last_prices:
                unreal += pos["side"] * (last_prices[market] / pos["entry"] - 1.0) * float(pos.get("notional", self.notional))
        closed = self.state["closed"]
        return {"book": self.name, "mode": self.mode, "open": len(self.state["positions"]), "closed": closed,
                "win_rate": round(self.state["wins"] / closed, 3) if closed else 0.0,
                "realized_usd": round(self.state["realized"], 2), "unrealized_usd": round(unreal, 2)}


def run_cycle(books: list[Book], combos: list[Combo], closes: dict[str, pd.Series], gate: Callable[[str, str, pd.Series], str],
              now: datetime | None = None, highs: dict[str, pd.Series] | None = None,
              lows: dict[str, pd.Series] | None = None) -> dict[str, list[str]]:
    now = now or datetime.now(timezone.utc)
    out: dict[str, list[str]] = {b.name: [] for b in books}
    for combo in combos:
        close = closes.get(combo.market)
        if close is None:
            continue
        verdict = gate(combo.market, combo.rule, closed_only(close, now))
        for book in books:
            result = book.step(combo, close, verdict, now, (highs or {}).get(combo.market), (lows or {}).get(combo.market))
            out[book.name].append(f"{combo.key}: {result}")
    return out
