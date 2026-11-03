#!/usr/bin/env python3
"""Read-only probe of Deriv's NEW public options API for Boom/Crash offerings.
Never buys anything, needs no token. Saves raw answers to outputs/deriv_new_api_probe.json
"""
import asyncio, json, os, sys
from pathlib import Path
import websockets

URL = os.environ.get("DERIV_WS_URL", "wss://api.derivws.com/trading/v1/options/ws/public")
OUT = Path("outputs/deriv_new_api_probe.json")


async def ask(ws, n, payload):
    await ws.send(json.dumps(dict(payload, req_id=n)))
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), 20))
        if msg.get("req_id") == n:
            return msg


async def main():
    raw = {}
    async with websockets.connect(URL, open_timeout=20) as ws:
        syms = await ask(ws, 1, {"active_symbols": "brief"})
        raw["active_symbols"] = syms
        items = syms.get("active_symbols") or []
        print(f"{len(items)} symbols listed. Fields on first item: {sorted(items[0]) if items else 'none'}")
        hits = [i for i in items if any(k in json.dumps(i).upper() for k in ("BOOM", "CRASH"))]
        print(f"Boom/Crash entries: {len(hits)}")
        for i in hits:
            print("  ", i.get("underlying_symbol") or i.get("symbol"), "|", i.get("underlying_symbol_name") or i.get("display_name"))
        for n, i in enumerate(hits[:6], start=2):
            sym = i.get("underlying_symbol") or i.get("symbol")
            ans = await ask(ws, n, {"contracts_for": sym})
            raw[f"contracts_for_{sym}"] = ans
            if ans.get("error"):
                print(f"\n{sym}: error {ans['error'].get('code')}: {ans['error'].get('message')}")
                continue
            avail = (ans.get("contracts_for") or {}).get("available") or []
            types = sorted({a.get("contract_type") for a in avail})
            print(f"\n{sym}: {len(avail)} offerings, contract types: {types}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(raw, indent=2))
    print(f"\nRaw answers saved to {OUT}")


try:
    asyncio.run(main())
except Exception as exc:
    print(f"Failed: {type(exc).__name__}: {exc}")
    sys.exit(2)
