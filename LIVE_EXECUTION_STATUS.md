# NetzaraBot Live Execution Status

Current live-money execution route: **MT5 / CFD bridge**.

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

## Blocked Route

This route remains blocked:

```text
live_candidate/work/live_order_blocker.py
```

That script blocks **Deriv-direct API trading**, not MT5 trading. It does not create orders because no Deriv API order sender exists in `live_candidate`.

Do not treat the missing `live_candidate/config/ALLOW_REAL_LIVE_TRADING.txt` file as proof that the MT5 bridge is disabled. It only means the old Deriv-direct API path is not armed.
