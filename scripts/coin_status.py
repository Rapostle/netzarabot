"""Read-only status of the coin paper book (pretend money): realised, open (at today's prices), and per-coin totals.

    .venv/bin/python scripts/coin_status.py --repo-root /root/netzarabot
It changes nothing. Open positions are valued at the latest closed daily candle.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# every way a position can end is a close: a signal change, a stop, a trailing stop or a target
CLOSE_ACTIONS = ("close", "stop", "trail_stop", "target")


def compute(state: dict, journal_rows: list[list[str]], prices: dict[str, float], default_notional: float = 100.0, cost_round_trip: float = 0.002) -> dict:
    coins: dict[str, dict] = {}

    def slot(c: str) -> dict:
        return coins.setdefault(c, {"realised": 0.0, "closed": 0, "wins": 0, "unrealised": 0.0, "long": 0, "short": 0, "exposure": 0.0, "entry_costs": 0.0, "exit_costs": 0.0})

    for r in journal_rows:
        if len(r) > 8 and r[4] == "open" and r[7] not in ("", "nan"):
            slot(r[2])["entry_costs"] += float(r[7]) * cost_round_trip / 2   # paid when the position was opened
        if len(r) > 8 and r[4] != "open" and r[4] in CLOSE_ACTIONS and r[8] not in ("", "nan"):
            s, p = slot(r[2]), float(r[8])
            s["realised"] += p
            s["closed"] += 1
            s["wins"] += 1 if p > 0 else 0
    for key, pos in state.get("positions", {}).items():
        coin = key.split("|")[0]
        s = slot(coin)
        n = float(pos.get("notional", default_notional))
        s["long" if pos["side"] > 0 else "short"] += 1
        s["exposure"] += pos["side"] * n
        s["exit_costs"] += n * cost_round_trip / 2                                   # will be paid when it closes
        if coin in prices:
            s["unrealised"] += pos["side"] * (prices[coin] / pos["entry"] - 1.0) * n
    for c in coins.values():
        c["realised_net"] = c["realised"] - c["entry_costs"]
    tot = {k: sum(c[k] for c in coins.values()) for k in ("realised", "closed", "wins", "unrealised", "long", "short", "entry_costs", "exit_costs", "realised_net")}
    return {"coins": coins, "total": tot}


def render(res: dict, as_of: str) -> str:
    t = res["total"]
    lines = [f"Coin paper book (pretend money), prices as of {as_of}", ""]
    lines.append(f"Closed trades: {t['closed']} (wins {t['wins']}, losses {t['closed'] - t['wins']})")
    lines.append(f"Realised after costs paid so far: ${t['realised_net']:+.2f}  (closed trades ${t['realised']:+.2f}, entry costs of all positions -${t['entry_costs']:.2f})")
    lines.append(f"Open positions: {t['long'] + t['short']} (long {t['long']}, short {t['short']}), valued now before exit costs: ${t['unrealised']:+.2f}")
    lines.append(f"Net if everything closed now: ${t['realised_net'] + t['unrealised'] - t['exit_costs']:+.2f}  (after about ${t['exit_costs']:.2f} of exit costs)")
    lines.append("")
    lines.append("Per coin (the open rules on one coin are really one bet):")
    for coin, c in sorted(res["coins"].items()):
        side = "net short" if c["exposure"] < 0 else "net long" if c["exposure"] > 0 else "flat"
        lines.append(f"  {coin}: {c['long'] + c['short']} open ({side}, ${abs(c['exposure']):.0f} exposure), open now ${c['unrealised']:+.2f}, "
                     f"closed {c['closed']} (wins {c['wins']}), realised after costs ${c['realised_net']:+.2f}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--book", default="gated", help="gated (stop and target) or gated_trail (trailing stop)")
    args = parser.parse_args()
    out = Path(args.repo_root) / "outputs"
    state = json.loads((out / f"coin_paper_{args.book}_state.json").read_text())
    with (out / f"coin_paper_{args.book}_journal.csv").open() as h:
        rows = list(csv.reader(h))
    from checker.data import fetch_ohlc
    from coinbot.paper import closed_only
    now = datetime.now(timezone.utc)
    prices = {}
    for coin in sorted({k.split("|")[0] for k in state.get("positions", {})} | {r[2] for r in rows if len(r) > 4 and (r[4] == "open" or r[4] in CLOSE_ACTIONS)}):
        try:
            prices[coin] = float(closed_only(fetch_ohlc(coin, cache_dir=str(Path(args.repo_root) / "checker_cache"))["close"], now).iloc[-1])
        except Exception as exc:
            print(f"(no price for {coin}: {exc})")
    print(render(compute(state, rows, prices), now.strftime("%Y-%m-%d %H:%M UTC")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
