"""Telegram front end. `Bot.handle` is pure (no network) so it can be tested; `main` polls Telegram.

    CHECKER_BOT_TOKEN=... python3 -m checker.bot --config checker/config.json
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Callable

import pandas as pd

from . import engine, payments, report
from .data import COINS, fetch_close
from .store import Store

HELP = ("Strategy Honesty Checker\n"
        "I test whether a trading rule beats luck on a coin's history, after costs. I never tell you what to buy.\n\n"
        "/coins - supported coins\n/rules - built-in rules\n/prices - price list\n/buy <pack> - how to pay\n"
        "/paid <pack> <txid> - tell me you paid\n/balance - your checks\n/check <COIN> <rule> - run a check (1 credit)")


class Bot:
    def __init__(self, store: Store, cfg: payments.PaymentConfig, get_close: Callable[[str], pd.Series] = fetch_close,
                 null_runs: int = 1000, today: Callable[[], str] | None = None):
        self.store, self.cfg, self.get_close, self.null_runs = store, cfg, get_close, null_runs
        self.today = today or (lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    def handle(self, user_id: int, text: str) -> list[tuple[int, str]]:
        parts = text.strip().split()
        if not parts:
            return [(user_id, HELP)]
        cmd, args = parts[0].lower().split("@")[0], parts[1:]
        owner = self.store.is_owner(user_id)
        if cmd in ("/start", "/help"):
            return [(user_id, HELP)]
        if cmd == "/coins":
            return [(user_id, "Coins: " + ", ".join(COINS))]
        if cmd == "/rules":
            return [(user_id, "\n".join(f"{k}: {v}" for k, v in report.RULE_TEXT.items()))]
        if cmd == "/prices":
            return [(user_id, "Prices:\n" + payments.price_list(self.cfg))]
        if cmd == "/balance":
            return [(user_id, "You are the owner: checks are free for you." if owner else f"Checks left: {self.store.balance(user_id)}")]
        if cmd == "/buy":
            pack = payments.pack_by_name(self.cfg, args[0]) if args else None
            return [(user_id, payments.payment_instructions(self.cfg, pack) if pack else "Choose a pack:\n" + payments.price_list(self.cfg) + "\nExample: /buy single")]
        if cmd == "/paid":
            pack = payments.pack_by_name(self.cfg, args[0]) if len(args) >= 2 else None
            if not pack:
                return [(user_id, "Use: /paid <pack> <transaction id>")]
            if not self.store.submit_payment(args[1], user_id, pack.usd, pack.credits):
                return [(user_id, "That transaction ID was already submitted.")]
            msgs = [(user_id, "Thanks. Your checks are added once the payment is confirmed.")]
            msgs += [(o, f"Payment waiting: {args[1]} from {user_id}, {pack.name} (${pack.usd:,.2f}). Approve with /approve {args[1]}") for o in self.store.owner_ids]
            return msgs
        if cmd == "/pending" and owner:
            rows = self.store.pending()
            return [(user_id, "\n".join(f"{t} user {u} ${usd:,.2f} -> {c} check(s)" for t, u, usd, c in rows) or "Nothing waiting.")]
        if cmd == "/approve" and owner:
            done = self.store.approve_payment(args[0]) if args else None
            if not done:
                return [(user_id, "Unknown or already approved.")]
            return [(user_id, "Approved."), (done[0], f"Payment confirmed. {done[1]} check(s) added.")]
        if cmd == "/check":
            return self._check(user_id, args)
        return [(user_id, "I did not understand that.\n\n" + HELP)]

    def _check(self, user_id: int, args: list[str]) -> list[tuple[int, str]]:
        if len(args) != 2:
            return [(user_id, "Use: /check <COIN> <rule>, for example /check BTC momentum_60")]
        coin, rule = args[0].upper(), args[1].lower()
        if coin not in COINS:
            return [(user_id, "Unknown coin. Send /coins.")]
        if rule not in engine.RULE_NAMES:
            return [(user_id, "Unknown rule. Send /rules.")]
        day = self.today()
        cached = self.store.cached_report(day, coin, rule)
        if not self.store.spend_credit(user_id):
            return [(user_id, "You have no checks left. Send /prices then /buy.")]
        try:
            if cached:
                res = engine.CheckResult(**cached)
            else:
                res = engine.run_check(self.get_close(coin), rule, market=coin, null_runs=self.null_runs,
                                       tests_counted=self.store.combinations_today(day) + 1)
                self.store.save_report(day, coin, rule, res.as_dict())
        except Exception:
            self.store.refund_credit(user_id)
            return [(user_id, "I could not get the price data right now. Your check was not used. Try again later.")]
        return [(user_id, report.format_report(res))]


def _api(token: str, method: str, **params) -> dict:
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{token}/{method}", data=data), timeout=70) as r:
        return json.loads(r.read())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="checker/config.json")
    parser.add_argument("--db", default="checker.db")
    args = parser.parse_args()
    token = os.environ.get("CHECKER_BOT_TOKEN", "")
    if not token:
        print("Set CHECKER_BOT_TOKEN first.")
        return 1
    cfg = payments.load_config(args.config)
    bot = Bot(Store(args.db, cfg.owner_ids), cfg)
    offset = 0
    while True:
        try:
            for upd in _api(token, "getUpdates", timeout=50, offset=offset).get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or {}
                if msg.get("text") and msg.get("chat", {}).get("type") == "private":
                    for chat, text in bot.handle(msg["from"]["id"], msg["text"]):
                        _api(token, "sendMessage", chat_id=chat, text=text[:4000])
        except Exception as exc:  # network blips must not kill the service
            print("poll error:", exc)
            time.sleep(5)


if __name__ == "__main__":
    raise SystemExit(main())
