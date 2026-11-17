"""Run the coin paper-trading books once (pretend money only; never touches an exchange).

    .venv/bin/python scripts/run_coin_paper.py --repo-root /root/netzarabot
Schedule it once a day shortly after 00:00 UTC, when the daily candle has closed.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from checker import engine  # noqa: E402
from checker.layers import Layers  # noqa: E402
from checker.data import fetch_ohlc  # noqa: E402
from coinbot.paper import Book, Combo, run_cycle, closed_only  # noqa: E402

DEFAULT_COINS = ["BTC", "ETH", "SOL", "BNB"]


def make_gate(cache_path: Path, combos_count: int, now: datetime, null_runs: int = 500, layers: Layers | None = None):
    """Checker verdict per market and rule, recomputed once a week."""
    week = now.strftime("%G-W%V")
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}

    def gate(market: str, rule: str, close) -> str:
        key = f"{market}|{rule}|{week}|{layers.label() if layers else 'plain'}"
        if key not in cache:
            res = engine.run_check(close, rule, market=market, null_runs=null_runs, tests_counted=combos_count, layers=layers)
            cache[key] = res.verdict
            cache_path.write_text(json.dumps(cache, indent=1))
        return cache[key]
    return gate


def migrate_positions(state_path: Path, stop_atr: float, old_stop_atr: float = 3.0) -> int:
    """One-off: open positions made under the old 3-ATR stop get their stop re-set to `stop_atr` ATRs from their entry.
    Positions that already record their ATR are left alone, so this runs once and never loosens anything later."""
    if not state_path.exists() or stop_atr <= 0:
        return 0
    state = json.loads(state_path.read_text())
    changed = 0
    for pos in state.get("positions", {}).values():
        if pos.get("atr") or not pos.get("stop"):
            continue
        atr = abs(pos["entry"] - pos["stop"]) / old_stop_atr
        pos["atr"] = atr
        pos["stop0"] = pos["stop"] = pos["entry"] - pos["side"] * stop_atr * atr
        changed += 1
    if changed:
        state_path.write_text(json.dumps(state, indent=1))
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--coins", nargs="+", default=DEFAULT_COINS)
    parser.add_argument("--rules", nargs="+", default=list(engine.RULE_NAMES))
    parser.add_argument("--notional", type=float, default=100.0)
    parser.add_argument("--no-layers", action="store_true", help="turn off the choppy-market filter and volatility sizing")
    parser.add_argument("--stop-atr", type=float, default=1.0, help="stop-loss distance in daily ATRs (0 turns it off)")
    parser.add_argument("--trail-atr", type=float, default=1.0, help="also run a paired book whose stop trails the best price by this many ATRs (0 = off)")
    parser.add_argument("--take-atr", type=float, default=6.0, help="take-profit distance in daily ATRs (0 turns it off)")
    args = parser.parse_args()
    root = Path(args.repo_root)
    out = root / "outputs"
    out.mkdir(exist_ok=True)
    now = datetime.now(timezone.utc)
    closes, highs, lows, failed = {}, {}, {}, []
    for coin in args.coins:
        try:
            df = fetch_ohlc(coin, cache_dir=str(root / "checker_cache"))
            closes[coin], highs[coin], lows[coin] = df["close"], df["high"], df["low"]
        except Exception as exc:  # one bad coin must not stop the others
            failed.append(f"{coin}: {exc}")
    combos = [Combo(c, r) for c in closes for r in args.rules]
    layers = None if args.no_layers else Layers()
    moved = migrate_positions(out / "coin_paper_gated_state.json", args.stop_atr)
    if moved:
        print(f"re-set the stop on {moved} open positions to {args.stop_atr:g} ATR from their entry")
    books = [Book("gated", "watch", str(out), args.notional, stop_atr=args.stop_atr, take_atr=args.take_atr, layers=layers)]
    if args.trail_atr > 0:
        trail_state = out / "coin_paper_gated_trail_state.json"
        if not trail_state.exists() and (out / "coin_paper_gated_state.json").exists():
            # Start the trailing book from the same open positions as the main book, so the two are a paired comparison.
            src = json.loads((out / "coin_paper_gated_state.json").read_text())
            positions = {k: {**v, "stop0": v.get("stop0", v.get("stop"))} for k, v in src.get("positions", {}).items()}
            trail_state.write_text(json.dumps({"positions": positions, "last_day": src.get("last_day", {}), "realized": 0.0,
                                               "closed": 0, "wins": 0, "cooldown": src.get("cooldown", {})}, indent=1))
        books.append(Book("gated_trail", "watch", str(out), args.notional, stop_atr=args.stop_atr, take_atr=args.take_atr,
                          layers=layers, trail_atr=args.trail_atr))
    gate = make_gate(out / "coin_gate_cache.json", max(1, len(combos)), now, layers=layers)
    result = run_cycle(books, combos, closes, gate, now, highs, lows)
    for name, lines in result.items():
        acted = [l for l in lines if "changed" in l or "hit" in l]
        print(f"{name}: {len(lines)} checked, {len(acted)} changed")
        for line in acted:
            print("  " + line)
    prices = {c: float(closed_only(s, now).iloc[-1]) for c, s in closes.items()}
    for book in books:
        print(book.summary(prices))
    for line in failed:
        print("price data problem:", line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
