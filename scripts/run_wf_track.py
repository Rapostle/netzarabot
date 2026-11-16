"""Live 5-minute paper track for walk-forward rules (feeds the Deriv demo executor like any other track).

Rules are FROZEN in RULES below (chosen in advance, never edited by results). Every run:
  1. closes paper trades whose stop, target or 12-candle time exit has been reached;
  2. looks at the newest CLOSED 5-minute candle and, if a rule's condition holds, writes one paper signal.
It places no orders itself; the demo executor reads the decisions file and applies its own safety gates.

    .venv/bin/python scripts/run_wf_track.py --repo-root /root/netzarabot        # schedule every 5 minutes
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "work"))
BOT_ROOT = Path(os.environ.get("TRADING_BOT_ROOT", str(Path(__file__).resolve().parent.parent / "external" / "trading_bot")))
sys.path.insert(0, str(BOT_ROOT))
import walk_forward_rule_search as wf  # noqa: E402
from evaluate_existing_rules import rule_mask  # noqa: E402

PUBLIC_WS_URL = "wss://api.derivws.com/trading/v1/options/ws/public"
SL_ATR, TP_ATR, MAX_BARS, COST, SL_SLIPPAGE, RISK_USD = 1.4, 1.8, 12, 0.001, 0.2, 30.0
TF_SECONDS = {"5m": 300}
DECISION_FIELDS = ["symbol", "timeframe", "timestamp", "decision", "side", "confidence", "reason", "entry", "stop_loss", "take_profit",
                   "quantity", "risk_amount", "paper_order_id", "refresh_status", "refresh_error", "refreshed_candles"]
CLOSED_FIELDS = ["paper_order_id", "symbol", "timeframe", "opened_at", "recorded_at_utc", "side", "entry", "stop_loss", "take_profit",
                 "quantity", "risk_amount", "reason", "status", "closed_at", "exit_price", "paper_pnl", "exit_reason"]

# Frozen on 2026-11-17 from the 5-minute walk-forward search. Confidence = the win rate on its test quarter.
RULES = [
    {"rule_id": "WF001", "symbol": "CRASH300N", "timeframe": "5m", "side": "buy", "feature": "rsi_zone+upper_wick",
     "condition": "rsi_high & large_upper_wick", "confidence": 0.6786},
]


def fmt_time(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S+00:00")


async def _fetch(symbol: str, seconds: int, count: int) -> list[dict]:
    import websockets
    url = os.environ.get("DERIV_WS_URL") or PUBLIC_WS_URL
    async with websockets.connect(url, ping_interval=20, close_timeout=10) as ws:
        await ws.send(json.dumps({"ticks_history": symbol, "count": count, "end": "latest", "granularity": seconds, "style": "candles"}))
        reply = json.loads(await asyncio.wait_for(ws.recv(), timeout=45))
    if "error" in reply:
        raise RuntimeError(str(reply["error"]))
    return reply.get("candles") or []


def fetch_candles(symbol: str, timeframe: str, count: int = 400) -> pd.DataFrame:
    candles = asyncio.run(_fetch(symbol, TF_SECONDS[timeframe], count))
    df = pd.DataFrame(candles)
    df["epoch"] = df["epoch"].astype(int)
    df["timestamp"] = pd.to_datetime(df["epoch"], unit="s", utc=True)
    for col in ("open", "high", "low", "close"):
        df[col] = df[col].astype(float)
    df["volume"] = 0
    return df[["epoch", "timestamp", "open", "high", "low", "close", "volume"]]


def append_row(path: Path, fields: list[str], row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if new:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in fields})


def reason_text(rule: dict) -> str:
    return f"walk-forward 5m rules: rule {rule['rule_id']}: {rule['feature']} is {rule['condition']}"


def settle(pos: dict, candles: pd.DataFrame, closed_path: Path, now_iso: str) -> bool:
    """Close one paper position if a stop, target or the time limit was reached. True when closed."""
    later = candles[candles["epoch"] > pos["opened_epoch"]].reset_index(drop=True)
    sign = 1.0 if pos["side"] == "buy" else -1.0
    for k, row in enumerate(later.itertuples(index=False), start=1):
        stop_hit = row.low <= pos["stop_loss"] if sign > 0 else row.high >= pos["stop_loss"]
        take_hit = row.high >= pos["take_profit"] if sign > 0 else row.low <= pos["take_profit"]
        if stop_hit:
            exit_price, why = pos["stop_loss"], "paper stop loss"
        elif take_hit:
            exit_price, why = pos["take_profit"], "paper take profit"
        elif k >= MAX_BARS:
            exit_price, why = float(row.close), "paper time exit"
        else:
            continue
        qty, entry = pos["quantity"], pos["entry"]
        pnl = qty * sign * (exit_price - entry) - qty * entry * COST
        if why == "paper stop loss":
            pnl -= SL_SLIPPAGE * abs(entry - pos["stop_loss"]) * qty
        append_row(closed_path, CLOSED_FIELDS, {
            "paper_order_id": pos["paper_order_id"], "symbol": pos["symbol"], "timeframe": pos["timeframe"],
            "opened_at": fmt_time(pos["opened_epoch"]), "recorded_at_utc": now_iso, "side": pos["side"], "entry": entry,
            "stop_loss": pos["stop_loss"], "take_profit": pos["take_profit"], "quantity": qty, "risk_amount": RISK_USD,
            "reason": pos["reason"], "status": "closed", "closed_at": fmt_time(int(row.epoch)), "exit_price": exit_price,
            "paper_pnl": round(pnl, 4), "exit_reason": why})
        return True
    return False


def process(repo_root: Path, fetch=fetch_candles, now: datetime | None = None, rules: list[dict] | None = None, mask_fn=rule_mask) -> list[str]:
    now = now or datetime.now(timezone.utc)
    out = repo_root / "outputs"
    decisions, closed = out / "wf_5m_paper_decisions.csv", out / "wf_5m_closed_trades.csv"
    state_path = out / "wf_5m_state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {"open": [], "last_signal": {}}
    now_epoch, notes = int(now.timestamp()), []
    now_iso = now.isoformat(timespec="seconds")
    for rule in (RULES if rules is None else rules):
        seconds = TF_SECONDS[rule["timeframe"]]
        try:
            df = fetch(rule["symbol"], rule["timeframe"])
        except Exception as exc:  # a data hiccup must not stop the other rules
            notes.append(f"{rule['rule_id']}: no candles ({exc})")
            continue
        df = df[df["epoch"] + seconds <= now_epoch].reset_index(drop=True)  # closed candles only
        if len(df) < wf.WARMUP_BARS + 5:
            notes.append(f"{rule['rule_id']}: not enough candles")
            continue
        still_open = []
        for pos in state["open"]:
            if pos["rule_id"] == rule["rule_id"] and settle(pos, df, closed, now_iso):
                notes.append(f"{rule['rule_id']}: paper trade {pos['paper_order_id']} closed")
            else:
                still_open.append(pos)
        state["open"] = still_open
        ind = wf.add_indicators(df).reset_index(drop=True)
        cond = wf.condition_frame(ind).astype(str)
        mask = mask_fn(cond, rule["feature"], rule["condition"])
        last = len(ind) - 1
        epoch = int(ind["epoch"].iloc[last])
        atr = float(ind["atr_14"].iloc[last])
        if not bool(mask[last]):
            notes.append(f"{rule['rule_id']}: no signal on candle {fmt_time(epoch)}")
            continue
        if state["last_signal"].get(rule["rule_id"]) == epoch:
            notes.append(f"{rule['rule_id']}: already signalled for this candle")
            continue
        if any(p["rule_id"] == rule["rule_id"] for p in state["open"]):
            notes.append(f"{rule['rule_id']}: signal skipped, a paper trade is still open")
            continue
        if not (atr == atr and atr > 0):
            notes.append(f"{rule['rule_id']}: no volatility reading")
            continue
        entry = float(ind["close"].iloc[last])
        sign = 1.0 if rule["side"] == "buy" else -1.0
        stop, target = entry - sign * SL_ATR * atr, entry + sign * TP_ATR * atr
        qty = RISK_USD / abs(entry - stop)
        order_id = f"wf-{rule['rule_id']}-{epoch}"
        append_row(decisions, DECISION_FIELDS, {
            "symbol": rule["symbol"], "timeframe": rule["timeframe"], "timestamp": fmt_time(epoch), "decision": "paper_order",
            "side": rule["side"], "confidence": rule["confidence"], "reason": reason_text(rule), "entry": entry,
            "stop_loss": stop, "take_profit": target, "quantity": qty, "risk_amount": RISK_USD, "paper_order_id": order_id,
            "refresh_status": "ok"})
        state["open"].append({"paper_order_id": order_id, "rule_id": rule["rule_id"], "symbol": rule["symbol"], "timeframe": rule["timeframe"],
                              "side": rule["side"], "entry": entry, "stop_loss": stop, "take_profit": target, "quantity": qty,
                              "opened_epoch": epoch, "reason": reason_text(rule)})
        state["last_signal"][rule["rule_id"]] = epoch
        notes.append(f"{rule['rule_id']}: SIGNAL {rule['side']} {rule['symbol']} at {entry:.3f}, stop {stop:.3f}, target {target:.3f}")
    out.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=1))
    return notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--check", action="store_true", help="fetch candles and print what it sees, writing nothing")
    args = parser.parse_args()
    if args.check:
        for rule in RULES:
            df = fetch_candles(rule["symbol"], rule["timeframe"])
            print(f"{rule['rule_id']}: got {len(df)} candles for {rule['symbol']}, newest {df['timestamp'].iloc[-1]}")
        return 0
    for note in process(Path(args.repo_root).resolve()):
        print(note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
