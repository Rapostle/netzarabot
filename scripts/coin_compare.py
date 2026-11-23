"""Compare the three coin paper books side by side (pretend money): how each closed, and how much of the realised profit came from one day.

    .venv/bin/python scripts/coin_compare.py --repo-root /root/netzarabot
Read-only: it only reads the journals in outputs/.
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

BOOKS = ("gated", "gated_trail", "gated_lock")
CLOSE_ACTIONS = ("close", "stop", "trail_stop", "lock_stop", "target")


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open() as h:
        return [r for r in csv.DictReader(h) if r.get("action") in CLOSE_ACTIONS and r.get("pnl") not in ("", None)]


def summarise(rows: list[dict]) -> dict:
    by_action, by_day, by_coin = defaultdict(lambda: [0, 0.0]), defaultdict(float), defaultdict(float)
    for r in rows:
        p = float(r["pnl"])
        by_action[r["action"]][0] += 1
        by_action[r["action"]][1] += p
        by_day[r["time"][:10]] += p
        by_coin[r["market"]] += p
    total = sum(float(r["pnl"]) for r in rows)
    best = max(by_day.items(), key=lambda kv: kv[1]) if by_day else ("", 0.0)
    return {"n": len(rows), "wins": sum(1 for r in rows if float(r["pnl"]) > 0), "total": total, "by_action": dict(by_action),
            "by_day": dict(by_day), "by_coin": dict(by_coin), "best_day": best}


def render(name: str, s: dict) -> str:
    out = [f"=== {name} ===", f"closed {s['n']} (wins {s['wins']}) | realised after costs ${s['total']:+.2f}"]
    for a, (n, p) in sorted(s["by_action"].items()):
        out.append(f"  ended by {a}: {n} trades, ${p:+.2f}")
    days = sorted(s["by_day"].items())
    if days:
        out.append("  realised by closing day: " + ", ".join(f"{d} ${p:+.2f}" for d, p in days))
        day, p = s["best_day"]
        share = (p / s["total"] * 100) if s["total"] > 0 else float("nan")
        out.append(f"  best single day: {day} ${p:+.2f} = {share:.0f}% of the total realised" if s["total"] > 0 else f"  best single day: {day} ${p:+.2f}")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo-root", default=".")
    a = ap.parse_args()
    out = Path(a.repo_root) / "outputs"
    for b in BOOKS:
        print(render(b, summarise(read(out / f"coin_paper_{b}_journal.csv"))), "\n")
    print("A book that earns most of its profit on one day has shown one event, not a repeatable result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
