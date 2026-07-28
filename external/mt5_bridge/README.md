# NetzaraBot MT5/CFD Bridge

This folder is for Deriv MT5 / CFD live execution.

The Deriv web API route is for Deriv Options/DTrader accounts. If an account only
shows CFDs, use this bridge instead:

1. The Python bridge runs on the VPS and reads the bot's decision CSV.
2. The MT5 Expert Advisor polls the bridge with MT5 WebRequest.
3. The EA places the CFD trade inside Deriv MT5.

## Files

- `bridge/mt5_signal_server.py` - lightweight HTTP signal server.
- `ea/NetzaraBotBridgeEA.mq5` - MT5 Expert Advisor.
- `config/mt5_symbol_map.csv` - maps bot symbols to Deriv MT5 symbols.
- `config/control_state.json` - mobile/VPS start-stop control state.
- `scripts/run_mt5_signal_bridge.sh` - starts the bridge locally/VPS.

## Start The Bridge

From the repo root:

```bash
external/mt5_bridge/scripts/run_mt5_signal_bridge.sh
```

Default signal source:

```text
outputs/pair_candidate_paper_decisions.csv
```

Default URL:

```text
http://127.0.0.1:8765
```

Mobile control page:

```text
http://127.0.0.1:8765/control
```

The mobile page can start/stop trading and control TP/SL behavior:

- Use the bot signal's TP/SL.
- Override TP/SL with fixed MT5 points.
- Move SL to break-even after a chosen profit distance.
- Trail winning positions.
- Close bridge-managed trades after a time limit.
- Choose flexible lot sizing: fixed lot, bot signal quantity, or risk percent of account equity.
- Limit min lot, max lot, and allowed MT5 symbols.

If you expose the bridge beyond the VPS, set a control token first:

```bash
export NETZARABOT_CONTROL_TOKEN="choose-a-long-private-password"
external/mt5_bridge/scripts/run_mt5_signal_bridge.sh
```

## MT5 Setup

1. Open MT5.
2. Copy `ea/NetzaraBotBridgeEA.mq5` into `MQL5/Experts/`.
3. Compile it in MetaEditor.
4. In MT5, open Tools > Options > Expert Advisors.
5. Tick `Allow WebRequest for listed URL`.
6. Add your bridge URL, for example:

```text
http://127.0.0.1:8765
```

7. Attach `NetzaraBotBridgeEA` to the Deriv MT5 symbol chart.
8. Set `EnableLiveTrading=true` only when you want MT5 to place real CFD orders.
9. Use the mobile control page to start/stop trading remotely.

For the first real-money test, use `Lot mode=Fixed lot`, keep `Fixed lot=0.01`,
keep `Max lot cap=0.01`, keep stop mode on `Use bot signal TP/SL`, and leave
break-even/trailing off until you confirm the Deriv MT5 point size for that
symbol.

## Important MT5 Symbol Mapping

Deriv MT5 symbols may not exactly match the bot CSV symbols.

Edit:

```text
external/mt5_bridge/config/mt5_symbol_map.csv
```

Example:

```text
BOOM300N,Boom 300 Index
CRASH300N,Crash 300 Index
```

Use the exact symbol names shown in your Deriv MT5 Market Watch.
