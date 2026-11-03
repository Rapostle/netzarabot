#!/usr/bin/env python3
"""Watches the positions the Deriv executor opened and closes them like the paper bot does.

Deriv itself enforces the stop-loss and take-profit (they are attached to the contract).
This manager adds the two paper-bot exits Deriv cannot do:
  * time exit: close after MAX_HOLD_BARS candles if no level was reached;
  * profit lock: close when the price has moved profit_lock_r times the stop distance.
It also writes every finished trade to outputs/deriv_direct_closed_trades.csv.

Run once:   python3 external/deriv_direct/deriv_position_manager.py --config <config> --once
Run looping: omit --once (default: look every 60 seconds).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import websockets

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import deriv_direct_executor as ex
except ImportError:  # the server keeps the new executor under this name
    import deriv_direct_executor_v2 as ex

CLOSED_FIELDS = [
    "contract_id", "mode", "track_name", "symbol", "timeframe", "side", "opened_at", "closed_at",
    "entry", "stop_loss", "take_profit", "stake", "multiplier", "buy_price", "sell_price",
    "pnl", "exit_reason", "signal_id",
]
TIMEFRAME_SECONDS = {"m": 60, "h": 3600, "d": 86400}


def timeframe_seconds(label: str) -> int:
    label = (label or "").strip().lower()
    if len(label) >= 2 and label[:-1].isdigit() and label[-1] in TIMEFRAME_SECONDS:
        return int(label[:-1]) * TIMEFRAME_SECONDS[label[-1]]
    return 900


def closed_path(config: ex.DerivDirectConfig) -> Path:
    return Path(config.journal_csv).with_name("deriv_direct_closed_trades.csv")


def is_sold(contract: dict[str, Any]) -> bool:
    return bool(contract.get("is_sold")) or str(contract.get("status", "")).lower() in {"sold", "won", "lost"}


def server_exit_reason(position: dict[str, Any], contract: dict[str, Any]) -> str:
    profit = ex.safe_float(contract.get("profit"))
    take = ex.safe_float(position.get("take_profit_amount"))
    stop = ex.safe_float(position.get("stop_loss_amount"))
    if take and profit >= take * 0.95:
        return "deriv take profit"
    if stop and profit <= -stop * 0.95:
        return "deriv stop loss"
    if profit <= -0.85 * ex.safe_float(position.get("stake"), 1.0):
        return "deriv stop out"
    return "closed on Deriv"


def exit_decision(position: dict[str, Any], contract: dict[str, Any], now: datetime, profit_lock_r: float) -> str:
    """Returns an exit reason if the bot should close now, else ''."""
    opened = ex.parse_time(str(position.get("opened_at", "")))
    if opened is not None:
        limit = timeframe_seconds(position.get("timeframe", "")) * int(position.get("max_bars") or ex.MAX_HOLD_BARS)
        if (now - opened).total_seconds() >= limit:
            return "time exit"
    spot = ex.safe_float(contract.get("current_spot"))
    entry = ex.safe_float(position.get("entry"))
    risk = abs(entry - ex.safe_float(position.get("stop_loss")))
    if profit_lock_r > 0 and spot > 0 and risk > 0:
        move = (spot - entry) if position.get("side") == "buy" else (entry - spot)
        if move / risk >= profit_lock_r:
            return f"profit lock {profit_lock_r:g}R"
    return ""


def journal_close(config: ex.DerivDirectConfig, position: dict[str, Any], contract: dict[str, Any], reason: str, sell: dict[str, Any] | None) -> None:
    sell_price = (sell or {}).get("sold_for", contract.get("sell_price", ""))
    buy_price = ex.safe_float(position.get("buy_price"), ex.safe_float(position.get("stake")))
    pnl = contract.get("profit")
    if pnl in (None, "") and sell_price not in (None, ""):
        pnl = ex.safe_float(sell_price) - buy_price
    row = dict(position)
    row.update({"closed_at": ex.utc_now(), "sell_price": sell_price, "pnl": pnl, "exit_reason": reason})
    ex.append_csv_row(closed_path(config), CLOSED_FIELDS, row)


async def manage_once(config: ex.DerivDirectConfig, trader: Any, profit_lock_r: float = 2.0) -> list[str]:
    """Checks every open position once. Returns short log lines."""
    path = ex.open_positions_path(config)
    positions = ex.load_open_positions(path)
    if not positions:
        return ["no open positions"]
    log: list[str] = []
    still_open: list[dict[str, Any]] = []
    url = await asyncio.to_thread(trader.ws_url)
    async with websockets.connect(url, ping_interval=20, close_timeout=10) as ws:
        for position in positions:
            cid = position.get("contract_id")
            try:
                answer = await trader.call(ws, {"proposal_open_contract": 1, "contract_id": cid})
            except RuntimeError as exc:
                log.append(f"{cid}: lookup failed ({exc}); keeping it")
                still_open.append(position)
                continue
            contract = answer.get("proposal_open_contract") or {}
            if is_sold(contract):
                reason = server_exit_reason(position, contract)
                journal_close(config, position, contract, reason, None)
                log.append(f"{cid}: closed by Deriv ({reason}), profit {contract.get('profit')}")
                continue
            reason = exit_decision(position, contract, datetime.now(timezone.utc), profit_lock_r)
            if not reason:
                still_open.append(position)
                log.append(f"{cid}: open, no exit yet")
                continue
            try:
                sell = await trader.call(ws, {"sell": cid, "price": 0})
            except RuntimeError as exc:
                log.append(f"{cid}: wanted to close ({reason}) but sell failed: {exc}; will retry")
                still_open.append(position)
                continue
            journal_close(config, position, contract, reason, sell.get("sell", {}))
            log.append(f"{cid}: closed by bot ({reason}), sold for {sell.get('sell', {}).get('sold_for')}")
    ex.save_open_positions(path, still_open)
    return log


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="live_candidate/config/deriv_direct_demo_config.json")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--profit-lock-r", type=float, default=2.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ex.load_env_file()
    root = Path(args.repo_root).resolve()
    config = ex.load_config(root / args.config, root)
    pat = (os.environ.get("DERIV_PAT") or "").strip()
    ex.validate_live_arming(config, pat, True)  # closing positions must never need the arming switches
    trader = ex.DerivDirectTrader(config, pat, os.environ.get("DERIV_APP_ID", ""))
    while True:
        try:
            for line in asyncio.run(manage_once(config, trader, args.profit_lock_r)):
                print(f"{ex.utc_now()} {line}", flush=True)
        except Exception as exc:  # noqa: BLE001 - keep watching after a network hiccup
            print(f"{ex.utc_now()} manager error: {exc}", flush=True)
        if args.once:
            return 0
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
