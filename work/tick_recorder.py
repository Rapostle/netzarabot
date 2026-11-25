"""Tick recorder + pre-registered digit-pair test (pretend money; it never places an order).

Why: a digit pair that looks odd in ticks you already saw (CRASH500: a 2 followed by a 3) can only be judged on ticks recorded AFTER you
fixed the pair. This keeps recording ticks, stores the pair and the start time in advance, and counts only ticks after that.

    python3/.venv python work/tick_recorder.py --record --symbols CRASH500          # runs forever (use pm2); one CSV per symbol in outputs/ticks/
    .venv/bin/python work/tick_recorder.py --register CRASH500 2 3                  # fix the pair NOW; only ticks after this moment count
    .venv/bin/python work/tick_recorder.py --analyze                                # read the verdict any time
Needs the 'websockets' package for --record only. The judgement is made at JUDGE_EVENTS cases of "a 2 just appeared" (about 5-6 hours on a 1-second index).
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import math
import os
import time
from pathlib import Path

URL = "wss://api.derivws.com/trading/v1/options/ws/public"
FAIR = 0.10
BREAK_EVEN = 0.105          # a one-digit 'matches' contract at a 5% margin (an assumption)
JUDGE_EVENTS = 2000
BLOCK_EVENTS = 400
PREREG = "prereg.json"


def parse_tick(msg: dict) -> tuple[str, int, str, int] | None:
    """Deriv tick message -> (symbol, epoch, quote text, last digit), or None. Uses pip_size so a trailing zero is not lost."""
    if msg.get("msg_type") != "tick" or "tick" not in msg:
        return None
    t = msg["tick"]
    try:
        pip = int(t["pip_size"])
        quote = float(t["quote"])
        text = f"{quote:.{pip}f}"
        return str(t["symbol"]), int(t["epoch"]), text, int(text[-1])
    except (KeyError, ValueError, TypeError):
        return None


def append_rows(path: Path, rows: list[tuple]) -> None:
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="") as h:
        w = csv.writer(h)
        if new:
            w.writerow(["epoch", "quote", "digit"])
        w.writerows(rows)


async def record(symbols: list[str], out_dir: Path, url: str) -> None:
    import websockets
    last_epoch: dict[str, int] = {}
    delay = 2
    while True:
        try:
            async with websockets.connect(url, ping_interval=20, close_timeout=10) as ws:
                for s in symbols:
                    await ws.send(json.dumps({"ticks": s, "subscribe": 1}))
                delay, buf = 2, {s: [] for s in symbols}
                async for raw in ws:
                    msg = json.loads(raw)
                    if "error" in msg:
                        print("server said:", msg["error"], flush=True)
                        continue
                    p = parse_tick(msg)
                    if not p:
                        continue
                    sym, epoch, text, digit = p
                    if epoch <= last_epoch.get(sym, 0):
                        continue
                    last_epoch[sym] = epoch
                    buf.setdefault(sym, []).append((epoch, text, digit))
                    if len(buf[sym]) >= 30:
                        append_rows(out_dir / f"{sym}.csv", buf[sym])
                        buf[sym] = []
        except Exception as exc:   # network drops must not end the recorder
            print(f"connection lost ({exc}); retrying in {delay}s", flush=True)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)


def load_prereg(out_dir: Path) -> list[dict]:
    p = out_dir / PREREG
    return json.loads(p.read_text()) if p.exists() else []


def register(out_dir: Path, symbol: str, prev: int, nxt: int, now: float | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    items = load_prereg(out_dir)
    item = {"symbol": symbol.upper(), "prev": prev, "next": nxt, "start_epoch": int(now if now is not None else time.time())}
    if any(i["symbol"] == item["symbol"] and i["prev"] == prev and i["next"] == nxt for i in items):
        raise SystemExit("That pair is already registered; its start time cannot be moved.")
    items.append(item)
    (out_dir / PREREG).write_text(json.dumps(items, indent=1))
    return item


def read_ticks(path: Path, since: int) -> list[tuple[int, int]]:
    if not path.exists():
        return []
    with path.open() as h:
        rows = [(int(r["epoch"]), int(r["digit"])) for r in csv.DictReader(h) if int(r["epoch"]) > since]
    return sorted(set(rows))


def analyze_pair(ticks: list[tuple[int, int]], prev: int, nxt: int) -> dict:
    """Counts only back-to-back ticks (a gap of more than 3x the usual spacing is skipped, so a dropped connection cannot fake a pair)."""
    if len(ticks) < 3:
        return {"events": 0}
    gaps = sorted(b[0] - a[0] for a, b in zip(ticks, ticks[1:]))
    usual = max(1, gaps[len(gaps) // 2])
    hits_flags = [d2 == nxt for (e1, d1), (e2, d2) in zip(ticks, ticks[1:]) if d1 == prev and e2 - e1 <= 3 * usual]
    n = len(hits_flags)
    if n == 0:
        return {"events": 0}
    hits = sum(hits_flags)
    rate = hits / n
    z = (rate - FAIR) / math.sqrt(FAIR * (1 - FAIR) / n)
    blocks = [sum(hits_flags[i:i + BLOCK_EVENTS]) / len(hits_flags[i:i + BLOCK_EVENTS]) for i in range(0, n - BLOCK_EVENTS + 1, BLOCK_EVENTS)]
    return {"events": n, "hits": hits, "rate": rate, "z": z, "p": 0.5 * math.erfc(z / math.sqrt(2)), "blocks": blocks,
            "hours": (ticks[-1][0] - ticks[0][0]) / 3600}


def verdict(r: dict) -> str:
    if not r.get("events"):
        return "no usable ticks yet"
    if r["events"] < JUDGE_EVENTS:
        return f"not judged yet: {r['events']} of {JUDGE_EVENTS} cases"
    if r["p"] <= 0.01 and r["rate"] >= BREAK_EVEN and sum(b > FAIR for b in r["blocks"]) >= max(1, len(r["blocks"]) - 1):
        return "HOLDS on fresh ticks: still needs separate windows and a demo test before anything else"
    return "DOES NOT HOLD on fresh ticks: it was chance"


def analyze(out_dir: Path) -> str:
    items = load_prereg(out_dir)
    if not items:
        return "No pair registered. Register one first: --register CRASH500 2 3"
    lines = []
    for i in items:
        r = analyze_pair(read_ticks(out_dir / f"{i['symbol']}.csv", i["start_epoch"]), i["prev"], i["next"])
        head = f"{i['symbol']}: after a {i['prev']}, next digit {i['next']} (fair {FAIR:.3f}, break-even about {BREAK_EVEN:.3f}), counting ticks after {time.strftime('%d %b %H:%M UTC', time.gmtime(i['start_epoch']))}"
        if not r.get("events"):
            lines.append(head + "\n  " + verdict(r))
            continue
        lines.append(head + f"\n  {r['hits']} of {r['events']} cases = {r['rate']:.3f} | z {r['z']:+.1f} | chance by luck (one pair, chosen in advance) {r['p']:.3f} | {r['hours']:.1f} hours recorded"
                     + (f"\n  by block of {BLOCK_EVENTS} cases: " + ", ".join(f"{b:.2f}" for b in r["blocks"]) if r["blocks"] else "")
                     + "\n  " + verdict(r))
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out-dir", default="outputs/ticks")
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--symbols", nargs="+", default=["CRASH500"])
    ap.add_argument("--register", nargs=3, metavar=("SYMBOL", "PREV", "NEXT"))
    ap.add_argument("--analyze", action="store_true")
    a = ap.parse_args()
    out = Path(a.out_dir)
    if a.register:
        print("registered:", register(out, a.register[0], int(a.register[1]), int(a.register[2])))
    if a.record:
        asyncio.run(record(a.symbols, out, os.environ.get("DERIV_WS_URL") or URL))
    if a.analyze or not (a.register or a.record):
        print(analyze(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
