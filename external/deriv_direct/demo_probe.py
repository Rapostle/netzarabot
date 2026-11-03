#!/usr/bin/env python3
"""DEMO-ONLY, NO-BUY probe of Deriv's new authenticated options API.

Flow: personal access token -> list accounts -> one-time link for the DEMO account
-> WebSocket -> balance -> price quote ("proposal") for a small multiplier contract.
It never sends a buy request and refuses to use any link that is not the demo endpoint.

Env (put in /root/.deriv_env as KEY=VALUE lines, or export):
  DERIV_PAT             personal access token (never printed)
  DERIV_APP_ID          app id of your PAT-type app
  DERIV_DEMO_ACCOUNT_ID optional: use if account listing does not identify the demo account
Saves what Deriv answered (token/otp redacted) to outputs/deriv_demo_probe.json
"""
import asyncio, json, os, re, sys, urllib.request, urllib.error
from pathlib import Path
import websockets

REST = os.environ.get("DERIV_REST_BASE", "https://api.derivws.com/trading/v1/options")
OUT = Path("outputs/deriv_demo_probe.json")
SYMBOL = os.environ.get("PROBE_SYMBOL", "BOOM300N")


def load_env(path="/root/.deriv_env"):
    p = Path(path)
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def redact(text):
    return re.sub(r"(otp=)[^&\"'\s]+", r"\1<redacted>", str(text))


def rest(method, path, pat, app_id, body=None):
    req = urllib.request.Request(REST + path, method=method, data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Authorization", f"Bearer {pat}")
    req.add_header("Deriv-App-ID", app_id)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "netzarabot-probe/1.0")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        text = exc.read().decode(errors="replace")
        try:
            return exc.code, json.loads(text)
        except ValueError:
            return exc.code, {"raw": text[:300]}


def find_demo_account(listing):
    data = listing.get("data", listing)
    items = data if isinstance(data, list) else (data.get("accounts") if isinstance(data, dict) else None) or []
    for item in items:
        kind = str(item.get("account_type") or item.get("type") or "").lower()
        ident = item.get("account_id") or item.get("id") or item.get("loginid")
        if ident and (kind == "demo" or item.get("is_virtual") in (True, 1)):
            return str(ident)
    return None


async def ask(ws, n, payload):
    assert "buy" not in payload, "this probe never buys"
    await ws.send(json.dumps(dict(payload, req_id=n)))
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), 20))
        if msg.get("req_id") == n:
            return msg


async def main():
    load_env()
    pat, app_id = os.environ.get("DERIV_PAT", ""), os.environ.get("DERIV_APP_ID", "")
    if not pat or not app_id:
        print("Missing DERIV_PAT or DERIV_APP_ID (see the docstring)."); return 2
    raw = {}
    status, listing = rest("GET", "/accounts", pat, app_id)
    raw["accounts"] = {"status": status, "body": listing}
    print(f"List accounts: HTTP {status}")
    account = os.environ.get("DERIV_DEMO_ACCOUNT_ID") or find_demo_account(listing)
    if not account:
        print("Could not identify a demo account. Answer was:", redact(json.dumps(listing))[:500])
        print("Set DERIV_DEMO_ACCOUNT_ID in /root/.deriv_env and run again."); OUT.parent.mkdir(exist_ok=True); OUT.write_text(json.dumps(raw, indent=2)); return 3
    print(f"Using demo account: {account}")
    status, otp = rest("POST", f"/accounts/{account}/otp", pat, app_id)
    url = (otp.get("data") or {}).get("url", "")
    raw["otp"] = {"status": status, "body": json.loads(redact(json.dumps(otp)))}
    print(f"One-time link: HTTP {status}")
    if "/ws/demo" not in url:
        print("REFUSING: the link is not the demo endpoint. Nothing was connected."); OUT.parent.mkdir(exist_ok=True); OUT.write_text(json.dumps(raw, indent=2)); return 4
    async with websockets.connect(url, open_timeout=20) as ws:
        bal = await ask(ws, 1, {"balance": 1})
        raw["balance"] = bal
        print("Balance answer:", json.dumps(bal.get("balance") or bal.get("error"))[:300])
        base = {"proposal": 1, "amount": 2, "basis": "stake", "currency": "USD", "contract_type": "MULTUP", "multiplier": 20, "underlying_symbol": SYMBOL}
        variants = {
            "no limits": {},
            "limit_order (stop_loss/take_profit)": {"limit_order": {"stop_loss": 1, "take_profit": 2}},
        }
        for n, (label, extra) in enumerate(variants.items(), start=2):
            ans = await ask(ws, n, dict(base, **extra))
            raw[f"proposal: {label}"] = ans
            print(f"\nProposal [{label}]:", json.dumps(ans.get("error") or ans.get("proposal"))[:500])
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(redact(json.dumps(raw, indent=2)))
    print(f"\nSaved to {OUT} (token and one-time link redacted). Nothing was bought.")
    return 0


try:
    sys.exit(asyncio.run(main()))
except Exception as exc:
    print(f"Failed: {type(exc).__name__}: {redact(exc)}")
    sys.exit(2)
