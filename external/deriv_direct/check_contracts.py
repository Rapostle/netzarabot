#!/usr/bin/env python3
"""Read-only check: which contract types does Deriv offer on BOOM300N / CRASH300N?

Run this on the VPS (the Deriv WebSocket must be reachable). It never buys
anything and never needs the real-money consent flags.

    python3 external/deriv_direct/check_contracts.py
    DERIV_API_TOKEN=xxxx python3 external/deriv_direct/check_contracts.py   # offerings for YOUR account

Without a token you see the public offering. With a token (demo or real) the
`contracts_for` answer reflects what your account type may actually trade,
which is what ticket #55954 is asking Deriv about. The token is only used to
authorize and is never printed or saved.

Output: a readable summary on screen and a JSON file with the raw answers
(default: outputs/deriv_contracts_check.json) to send to Deriv support or to me.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import websockets

SYMBOLS = ("BOOM300N", "CRASH300N")
INTERESTING = ("MULTUP", "MULTDOWN", "ACCU", "CALL", "PUT", "ONETOUCH", "NOTOUCH", "DIGITOVER", "DIGITUNDER")


class DerivSession:
    def __init__(self, ws):
        self.ws = ws
        self._req_id = 0

    async def call(self, payload: dict, timeout: float = 20.0) -> dict:
        self._req_id += 1
        payload = dict(payload, req_id=self._req_id)
        await self.ws.send(json.dumps(payload))
        while True:
            raw = await asyncio.wait_for(self.ws.recv(), timeout=timeout)
            message = json.loads(raw)
            if message.get("req_id") == self._req_id:
                return message


def summarize_contracts(answer: dict) -> list[dict]:
    available = (answer.get("contracts_for") or {}).get("available") or []
    by_type: dict[str, dict] = {}
    for item in available:
        ctype = item.get("contract_type", "?")
        entry = by_type.setdefault(
            ctype,
            {
                "contract_type": ctype,
                "category": item.get("contract_category_display", ""),
                "min_duration": item.get("min_contract_duration", ""),
                "max_duration": item.get("max_contract_duration", ""),
                "multiplier_range": item.get("multiplier_range"),
                "growth_rate_range": item.get("growth_rate_range"),
                "barriers": item.get("barriers"),
            },
        )
        if entry["min_duration"] == "" and item.get("min_contract_duration"):
            entry["min_duration"] = item["min_contract_duration"]
    return sorted(by_type.values(), key=lambda e: e["contract_type"])


async def run(app_id: str, token: str | None, out_path: Path) -> int:
    url = os.environ.get("DERIV_WS_URL") or f"wss://ws.derivws.com/websockets/v3?app_id={app_id}"
    report: dict = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "app_id": app_id,
        "authorized": False,
        "account": {},
        "symbols": {},
    }
    try:
        async with websockets.connect(url, open_timeout=20) as ws:
            session = DerivSession(ws)

            if token:
                auth = await session.call({"authorize": token})
                if auth.get("error"):
                    print(f"authorize failed: {auth['error'].get('code')}: {auth['error'].get('message')}")
                    report["authorize_error"] = auth["error"]
                else:
                    info = auth.get("authorize", {})
                    report["authorized"] = True
                    report["account"] = {
                        "loginid": info.get("loginid"),
                        "is_virtual": info.get("is_virtual"),
                        "currency": info.get("currency"),
                        "landing_company_name": info.get("landing_company_name"),
                        "country": info.get("country"),
                    }

            active = await session.call({"active_symbols": "brief", "product_type": "basic"})
            listed = {s.get("symbol"): s for s in active.get("active_symbols", [])}

            for symbol in SYMBOLS:
                entry: dict = {"listed_in_active_symbols": symbol in listed}
                if symbol in listed:
                    entry["market_open"] = listed[symbol].get("exchange_is_open")
                    entry["submarket"] = listed[symbol].get("submarket_display_name")
                answer = await session.call({"contracts_for": symbol, "currency": report["account"].get("currency") or "USD"})
                if answer.get("error"):
                    entry["error"] = answer["error"]
                else:
                    entry["contracts"] = summarize_contracts(answer)
                report["symbols"][symbol] = entry
    except (OSError, asyncio.TimeoutError, websockets.exceptions.WebSocketException) as exc:
        print(f"Could not reach Deriv: {type(exc).__name__}: {exc}")
        print("Run this on the VPS, where the WebSocket is reachable.")
        return 2

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2))

    print(f"Deriv offerings check ({report['checked_at_utc']})")
    if report["authorized"]:
        acct = report["account"]
        kind = "demo" if acct.get("is_virtual") else "REAL"
        print(f"Account: {acct.get('loginid')} ({kind}, {acct.get('currency')}, {acct.get('landing_company_name')})")
    else:
        print("Account: not authorized (public offering only; set DERIV_API_TOKEN to see your account's offering)")
    for symbol, entry in report["symbols"].items():
        print(f"\n== {symbol} ==")
        if not entry.get("listed_in_active_symbols"):
            print("  not listed in active_symbols for this app/account")
        if entry.get("error"):
            err = entry["error"]
            print(f"  contracts_for error: {err.get('code')}: {err.get('message')}")
            continue
        contracts = entry.get("contracts", [])
        if not contracts:
            print("  no contracts offered")
            continue
        for c in contracts:
            flag = "  <-- " if c["contract_type"] in INTERESTING else "      "
            extra = ""
            if c.get("multiplier_range"):
                extra = f" multipliers {c['multiplier_range']}"
            if c.get("growth_rate_range"):
                extra += f" growth {c['growth_rate_range']}"
            print(f"{flag}{c['contract_type']:<10} {c['category']:<14} {c['min_duration']}..{c['max_duration']}{extra}")
    print(f"\nRaw answers saved to {out_path}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--app-id", default=os.environ.get("DERIV_APP_ID", "1089"))
    parser.add_argument("--out", default="outputs/deriv_contracts_check.json")
    args = parser.parse_args()
    token = os.environ.get("DERIV_API_TOKEN") or None
    sys.exit(asyncio.run(run(args.app_id, token, Path(args.out))))


if __name__ == "__main__":
    main()
