"""DEMO ONLY: buy one $1 BOOM300N multiplier on the demo account, look at it, then close it.
Prints Deriv's raw answers so the open/close message formats are known. Refuses to run unless demo."""
import asyncio, json, os, sys
from pathlib import Path
import websockets
sys.path.insert(0, str(Path(__file__).resolve().parent))
import deriv_direct_executor_v2 as ex

ex.load_env_file()
root = Path(__file__).resolve().parents[2]
config = ex.load_config(root / "live_candidate/config/deriv_direct_demo_config.json", root)
assert config.account_mode == "demo", "refusing: config is not demo"
sig = ex.CandidateSignal("demo-test", "BOOM300N", "15m", "2026-11-03T00:00:00Z", "buy", "buy", 0.8, "demo test", 100.0, 99.0, 102.0, 1, 1, "demo1")
plan = ex.plan_order(sig, config)
trader = ex.DerivDirectTrader(config, os.environ.get("DERIV_PAT", ""), os.environ.get("DERIV_APP_ID", ""))


def show(label, data):
    print(f"\n== {label} ==")
    print(json.dumps(data, indent=1)[:1500])


async def main():
    url = trader.ws_url()  # raises unless this is the demo endpoint
    async with websockets.connect(url, ping_interval=20, close_timeout=10) as ws:
        multiplier, proposal = await trader.proposal_with_smallest_multiplier(ws, plan)
        buy = await trader.buy(ws, proposal["proposal"]["id"], plan.stake, plan.signal)
        show("BUY answer", buy)
        contract_id = (buy.get("buy") or {}).get("contract_id")
        if not contract_id:
            print("No contract id; stopping."); return
        await asyncio.sleep(2)
        try:
            show("OPEN CONTRACT", await trader.call(ws, {"proposal_open_contract": 1, "contract_id": contract_id}))
        except RuntimeError as exc:
            print("open-contract lookup failed:", exc)
        try:
            show("PORTFOLIO", await trader.portfolio(ws))
        except RuntimeError as exc:
            print("portfolio failed:", exc)
        try:
            show("SELL (close now)", await trader.call(ws, {"sell": contract_id, "price": 0}))
        except RuntimeError as exc:
            print("SELL FAILED:", exc, "\nThe demo position stays open; it has a stop-loss and can be closed on Deriv's demo site.")
        show("BALANCE after", await trader.balance(ws))


asyncio.run(main())
