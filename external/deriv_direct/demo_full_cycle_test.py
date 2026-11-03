"""DEMO ONLY: executor buys one $1 trade, the position manager closes it by the time rule (1 minute).
Tagged track_name 'demo-cycle-test' so the trade can be ignored in any evidence report."""
import asyncio, os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import deriv_direct_executor_v2 as ex
except ImportError:
    import deriv_direct_executor as ex
import deriv_position_manager as mgr

ex.load_env_file()
root = Path(__file__).resolve().parents[2]
config = ex.load_config(root / "live_candidate/config/deriv_direct_demo_config.json", root)
assert config.account_mode == "demo", "refusing: config is not demo"
sig = ex.CandidateSignal("demo-cycle-test", "BOOM300N", "1m", "2026-11-03T00:00:00Z", "buy", "buy", 0.8, "demo cycle", 100.0, 99.0, 102.0, 1, 1, "cycle1")
plan = ex.plan_order(sig, config)
trader = ex.DerivDirectTrader(config, os.environ.get("DERIV_PAT", ""), os.environ.get("DERIV_APP_ID", ""))

result = asyncio.run(trader.execute(plan, False))
print("bought:", result["status"], "contract", result["buy"].get("contract_id"), "limits", result["proposal_payload"]["limit_order"])
ex.record_open_position(config, plan, result)
positions = ex.load_open_positions(ex.open_positions_path(config))
positions[-1]["max_bars"] = 1          # 1 candle of 1m = 60 seconds, so the time exit fires soon
ex.save_open_positions(ex.open_positions_path(config), positions)

print("manager check right away (should keep it open):")
print("  ", asyncio.run(mgr.manage_once(config, trader, 0)  # 0 = profit lock off, so only the time rule can fire))
print("waiting 65 seconds for the time exit...")
time.sleep(65)
print("manager check after 65s (should close it):")
print("  ", asyncio.run(mgr.manage_once(config, trader, 0)  # 0 = profit lock off, so only the time rule can fire))
print("closed-trades file:")
for row in ex.read_rows(mgr.closed_path(config))[-1:]:
    print("  ", {k: row[k] for k in ("contract_id", "exit_reason", "buy_price", "sell_price", "pnl")})
print("still open:", len(ex.load_open_positions(ex.open_positions_path(config))))
