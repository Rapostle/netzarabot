"""Forward paper book (pretend money) for the MIRRORED pairs rule. Research only; it never places a real order.

Why it exists: work/pairs_wide_test.py found that buying the "snap back" side of stretched coin ratios LOST money on every kind of
history (-1.9% per trade before costs, both halves negative). The mirror image (trade WITH the stretch) would have won by the same
amount, but that idea came from looking at these results, and the coin list is today's survivors, which flatters coins that kept rising.
The only fair judge is days it has not seen, so this book starts now, with the rule fixed below, and trades only new days.

Rule (exact mirror of work/pairs_test.py, including its exits):
  spread = log(A / B) on closed UTC daily closes; z = (spread - 60-day mean) / 60-day standard deviation.
  Day z >= +2: LONG A, SHORT B (the original rule did the opposite). Day z <= -2: SHORT A, LONG B.
  Exit on the first later day when z has crossed back through 0, or the original rule's "stop" |z| >= 4 on the stretching side
  (here that is a profit-taking exit), or after 30 days. One position per pair; a new entry cannot happen on the exit day.
  Each trade: $100 per leg. Result = change in the spread in our favour x $100, minus costs of 0.4% x $100 per round trip.
Pairs: every pair among the checker's ten coins (45). It starts at the latest closed day and does not backfill history.

    .venv/bin/python work/pairs_trend_paper.py --run        # once a day after 00:10 UTC
    .venv/bin/python work/pairs_trend_paper.py --status
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pairs_test as PT  # noqa: E402

LEG_USD = 100.0
STATE = "pairs_trend_paper_state.json"
JOURNAL = "pairs_trend_paper_journal.csv"
FIELDS = ["time", "pair", "action", "long", "short", "spread", "z", "pnl_usd", "reason"]


def zscores(spread: pd.Series) -> pd.Series:
    return (spread - spread.rolling(PT.WINDOW).mean()) / spread.rolling(PT.WINDOW).std()


def step_day(held: dict | None, spread: pd.Series, z: pd.Series, pos: int) -> tuple[str, dict | None]:
    """Advance one pair by the closed day at integer position `pos`. Returns (event, new_held); event is '', 'open' or 'close:<reason>'."""
    if held is not None:
        entry_pos = held["pos"]
        zk, z0 = float(z.iloc[pos]), held["z"]
        original_side = -float(np.sign(z0))
        reason = None
        if zk * z0 <= 0:
            reason = "crossed"
        elif np.isfinite(zk) and original_side * zk <= -PT.STOP_Z:
            reason = "stretch_target"
        elif pos - entry_pos >= PT.MAX_DAYS:
            reason = "max_days"
        if reason:
            return f"close:{reason}", None
        return "", held
    zt = float(z.iloc[pos])
    if np.isfinite(zt) and abs(zt) >= PT.ENTER_Z:
        side = 1.0 if zt > 0 else -1.0       # +1 = long A, short B (mirror of the original rule)
        return "open", {"pos": pos, "z": zt, "side": side, "entry_spread": float(spread.iloc[pos])}
    return "", None


def replay(spread: pd.Series, start_pos: int = None) -> list[tuple[int, int, float]]:
    """Run the forward engine over a whole history (used by the tests to prove it equals the backtest). Returns (entry, exit, gross) rows."""
    z = zscores(spread)
    held, out = None, []
    for pos in range(PT.WINDOW if start_pos is None else start_pos, len(spread)):
        event, new = step_day(held, spread, z, pos)
        if event.startswith("close"):
            out.append((held["pos"], pos, held["side"] * (float(spread.iloc[pos]) - held["entry_spread"])))
        held = new
    return out


def closed_daily(coin: str) -> pd.Series:
    from checker.data import fetch_close
    close = fetch_close(coin)
    close.index = close.index.tz_convert("UTC").normalize() if close.index.tz is not None else close.index.normalize()
    today = pd.Timestamp(datetime.now(timezone.utc).date(), tz="UTC")
    return close[close.index < today]


def load_state(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {"last_day": None, "held": {}}


def log(path: Path, row: dict) -> None:
    new = not path.exists()
    with path.open("a", newline="") as h:
        w = csv.DictWriter(h, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in FIELDS})


def run(out_dir: Path, closes: dict[str, pd.Series]) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    state_path, journal = out_dir / STATE, out_dir / JOURNAL
    state = load_state(state_path)
    msgs = []
    pairs = {}
    for a, b in itertools.combinations(sorted(closes), 2):
        j = pd.concat([closes[a], closes[b]], axis=1, join="inner").dropna()
        if len(j) > PT.WINDOW + 5:
            pairs[f"{a}/{b}"] = pd.Series(np.log(j.iloc[:, 0].to_numpy() / j.iloc[:, 1].to_numpy()), index=j.index)
    if not pairs:
        return ["no pairs with enough data"]
    latest = min(s.index[-1] for s in pairs.values())
    if state["last_day"] is None:
        state["last_day"] = str(latest.date())
        msgs.append(f"started: watching {len(pairs)} pairs from {state['last_day']}; no history is back-filled")
    last = pd.Timestamp(state["last_day"], tz="UTC")
    new_days = 0
    for name, spread in pairs.items():
        z = zscores(spread)
        held = state["held"].get(name)
        for pos in [p for p in range(len(spread)) if last < spread.index[p] <= latest]:
            if held is not None:
                held["pos"] = int(spread.index.get_loc(pd.Timestamp(held["date"], tz="UTC")))
            event, new = step_day(held, spread, z, pos)
            day = str(spread.index[pos].date())
            a, b = name.split("/")
            if event == "open":
                new["date"] = day
                long_, short_ = (a, b) if new["side"] > 0 else (b, a)
                log(journal, {"time": day, "pair": name, "action": "open", "long": long_, "short": short_, "spread": round(float(spread.iloc[pos]), 5), "z": round(new["z"], 2)})
                msgs.append(f"{day} OPEN {name}: long {long_}, short {short_} (z {new['z']:+.2f})")
                held = new
            elif event.startswith("close"):
                gross = held["side"] * (float(spread.iloc[pos]) - held["entry_spread"])
                pnl = (gross - PT.COST) * LEG_USD
                reason = event.split(":")[1]
                log(journal, {"time": day, "pair": name, "action": "close", "spread": round(float(spread.iloc[pos]), 5), "z": round(float(z.iloc[pos]), 2), "pnl_usd": round(pnl, 2), "reason": reason})
                msgs.append(f"{day} CLOSE {name} ({reason}): ${pnl:+.2f}")
                held = None
        if held is not None:
            held.pop("pos", None)
        state["held"][name] = held
    state["last_day"] = str(latest.date())
    state_path.write_text(json.dumps(state, indent=1))
    msgs.append(f"processed to {state['last_day']}; open positions: {sum(1 for v in state['held'].values() if v)}")
    return msgs


def status(out_dir: Path) -> str:
    journal = out_dir / JOURNAL
    if not journal.exists():
        return "No trades yet (the book only trades days after it started)."
    with journal.open() as h:
        rows = list(csv.DictReader(h))
    closed = [r for r in rows if r["action"] == "close"]
    pnl = [float(r["pnl_usd"]) for r in closed]
    opens = sum(1 for r in rows if r["action"] == "open") - len(closed)
    if not pnl:
        return f"{opens} positions open, none closed yet."
    by_day: dict[str, float] = {}
    for r in closed:
        by_day[r["time"]] = by_day.get(r["time"], 0.0) + float(r["pnl_usd"])
    best = max(by_day.items(), key=lambda kv: kv[1])
    return (f"closed {len(pnl)} (wins {sum(1 for p in pnl if p > 0)}) | realised after costs ${sum(pnl):+.2f} | open {opens}\n"
            f"best single day: {best[0]} ${best[1]:+.2f}. The test is judged at 100 closed trades across many days, not before.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out-dir", default="outputs")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    out = Path(a.out_dir)
    if a.run:
        from checker.data import COINS
        closes = {}
        for c in COINS:
            try:
                closes[c] = closed_daily(c)
            except Exception as exc:
                print(f"{c}: no prices ({exc})")
        print("\n".join(run(out, closes)))
    if a.status or not a.run:
        print(status(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
