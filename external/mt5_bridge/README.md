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
