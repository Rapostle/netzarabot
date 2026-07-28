# NetzaraBot Live Execution Status

Current live-money execution routes:

- **MT5 / CFD bridge**
- **Deriv-direct WebSocket engine**

## Enabled Route

Use this route for Deriv MT5/CFD accounts:

```text
external/mt5_bridge/
```

Important files:

```text
external/mt5_bridge/bridge/mt5_signal_server.py
external/mt5_bridge/ea/NetzaraBotBridgeEA.mq5
external/mt5_bridge/config/control_state.json
external/mt5_bridge/config/mt5_symbol_map.csv
```

The MT5 EA contains the real order calls:

```text
trade.Buy(...)
trade.Sell(...)
```

The bridge is live-enabled when:

- `external/mt5_bridge/config/control_state.json` has `trading_enabled=true`
- the MT5 EA input `EnableLiveTrading=true`
- MT5 Algo Trading is enabled
- the bridge is running
- a fresh buy/sell signal exists

## Deriv-Direct Route

Use this route for Deriv API contract trading:

```text
external/deriv_direct/deriv_direct_executor.py
work/run_deriv_direct_dry_run.sh
work/run_deriv_direct_live_once.sh
live_candidate/config/deriv_direct_live_config.json
```

The engine uses Deriv WebSocket calls:

```text
authorize
portfolio
proposal
buy
balance
```

Real buys require:

- `live_candidate/config/ALLOW_REAL_LIVE_TRADING.txt`
- `DERIV_API_TOKEN`
- `ALLOW_REAL_DERIV_DIRECT=true`
- `DERIV_DIRECT_CONSENT=I_UNDERSTAND_REAL_MONEY_TRADING`

## Legacy Status Script

This script now reports the direct-engine status:

```text
live_candidate/work/live_order_blocker.py
```

Do not use it as the execution engine. The execution engine is `external/deriv_direct/deriv_direct_executor.py`.
