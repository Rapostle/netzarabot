#!/usr/bin/env python3
"""Read-only: multiplier/limit-order details and candle history on Deriv's NEW public API.
No token, never buys. Saves raw answers to outputs/deriv_new_api_details.json
"""
import asyncio, json, os, sys
from pathlib import Path
import websockets

URL = os.environ.get("DERIV_WS_URL", "wss://api.derivws.com/trading/v1/options/ws/public")
OUT = Path("outputs/deriv_new_api_details.json")


async def ask(ws, n, payload):
    await ws.send(json.dumps(dict(payload, req_id=n)))
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), 20))
        if msg.get("req_id") == n:
            return msg


async def main():
    raw = {}
    async with websockets.connect(URL, open_timeout=20) as ws:
        for n, sym in enumerate(("BOOM300N", "CRASH300N"), start=1):
            ans = await ask(ws, n, {"contracts_for": sym})
            raw[f"contracts_for_{sym}"] = ans
            print(f"\n== {sym}: offerings ==")
            for a in (ans.get("contracts_for") or {}).get("available") or []:
                print(json.dumps(a))
        for n, sym in enumerate(("BOOM300N", "CRASH300N"), start=10):
            ans = await ask(ws, n, {"ticks_history": sym, "style": "candles", "granularity": 900, "count": 3, "end": "latest"})
            raw[f"candles_{sym}"] = ans
            print(f"\n== {sym}: last 3 x 15m candles ==")
            print(json.dumps(ans.get("error") or ans.get("candles"))[:600])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(raw, indent=2))
    print(f"\nRaw answers saved to {OUT}")


try:
    asyncio.run(main())
except Exception as exc:
    print(f"Failed: {type(exc).__name__}: {exc}")
    sys.exit(2)
