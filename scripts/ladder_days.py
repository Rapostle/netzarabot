"""Day-by-day view of the coin paper books (pretend money): is a book's profit repeatable, or one market-wide day?

    .venv/bin/python scripts/ladder_days.py --repo-root /root/netzarabot [--book gated_lock]
Read-only: it only reads the journals in outputs/. A day counts as a 'win day' when at least
MIN_CLOSES trades closed that day and at least WIN_DAY_SHARE of them were profitable.
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

BOOKS = ("gated", "gated_trail", "gated_lock")
CLOSE_ACTIONS = ("close", "stop", "trail_stop", "lock_stop", "target")
WIN_DAY_SHARE = 0.8
MIN_CLOSES = 3


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open() as h:
        return [r for r in csv.DictReader(h) if r.get("action") in CLOSE_ACTIONS and r.get("pnl") not in ("", None)]


def by_day(rows: list[dict]) -> list[dict]:
    days: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for r in rows:
        days[r["time"][:10]].append((r["market"], float(r["pnl"])))
    out = []
    for d in sorted(days):
        items = days[d]
        wins = sum(1 for _, p in items if p > 0)
        coins = len({m for m, _ in items})
        out.append({"day": d, "closes": len(items), "wins": wins, "coins": coins, "pnl": sum(p for _, p in items),
                    "market_wide": len(items) >= MIN_CLOSES and wins / len(items) >= WIN_DAY_SHARE})
    return out


def render(name: str, days: list[dict]) -> str:
    if not days:
        return f"=== {name} ===\nno closed trades yet\n"
    lines = [f"=== {name} ==="]
    for d in days:
        tag = "win day" if d["market_wide"] and d["pnl"] > 0 else ""
        lines.append(f"  {d['day']}: {d['closes']} closes ({d['wins']} wins, {d['coins']} coins) ${d['pnl']:+.2f} {tag}".rstrip())
    total = sum(d["pnl"] for d in days)
    quiet = [d for d in days if not (d["market_wide"] and d["pnl"] > 0)]
    quiet_pnl = sum(d["pnl"] for d in quiet)
    lines.append(f"  total ${total:+.2f} over {len(days)} closing days; positive days {sum(1 for d in days if d['pnl'] > 0)}")
    lines.append(f"  on days that were NOT win days: {len(quiet)} days, ${quiet_pnl:+.2f}")
    if quiet and quiet_pnl > 0 and len(quiet) >= 3:
        lines.append("  It also made money on ordinary days. Keep watching: that is what a repeatable result looks like.")
    else:
        lines.append("  Without its win days it has not yet made money. Still one event until that changes.")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--book", choices=BOOKS)
    a = ap.parse_args()
    out = Path(a.repo_root) / "outputs"
    for b in ([a.book] if a.book else BOOKS):
        print(render(b, by_day(read(out / f"coin_paper_{b}_journal.csv"))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
