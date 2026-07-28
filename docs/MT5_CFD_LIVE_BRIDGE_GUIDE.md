# MT5 / CFD Live Bridge Guide

Use this when the Deriv account only shows CFDs/MT5.

## Why This Is Different

The website Deriv route talks to Deriv Options/DTrader. CFD accounts execute
inside MT5, so the live version needs an MT5 Expert Advisor.

## What Was Built

- VPS signal server: `external/mt5_bridge/bridge/mt5_signal_server.py`
- Start script: `external/mt5_bridge/scripts/run_mt5_signal_bridge.sh`
- MT5 EA: `external/mt5_bridge/ea/NetzaraBotBridgeEA.mq5`
- Symbol map: `external/mt5_bridge/config/mt5_symbol_map.csv`
- Mobile/VPS control state: `external/mt5_bridge/config/control_state.json`

## How To Test

1. Start the bridge:

```bash
external/mt5_bridge/scripts/run_mt5_signal_bridge.sh
```

2. Open this in a browser:

```text
http://127.0.0.1:8765/health
```

3. Check the latest signal:

```text
http://127.0.0.1:8765/signal
```

4. Open the phone/mobile control page:

```text
http://127.0.0.1:8765/control
```

Use this page to:

- Start Trading
- Stop Trading
- Emergency Stop
- Reset Emergency Stop
- Choose whether MT5 should use the bot's TP/SL, override TP/SL by points, or place orders without bridge TP/SL
- Set break-even rules
- Set trailing stop rules
- Close trades automatically after a time limit
- Limit max lot and allowed MT5 symbols

5. In MT5, add this allowed WebRequest URL:

```text
http://127.0.0.1:8765
```

6. Compile and attach `NetzaraBotBridgeEA.mq5`.

7. Set `EnableLiveTrading=true` only when ready for MT5 to place real CFD orders.

8. Tap `Start Trading` from the phone control page.

The EA will not trade unless both are true:

- EA input `EnableLiveTrading=true`
- Phone/VPS control `trading_enabled=true`

Emergency Stop overrides everything.

## TP / SL Controls

The phone control page has a `TP / SL Settings` section.

- `Use bot signal TP/SL`: the EA uses the stop-loss and take-profit that came from the bot signal.
- `Override with fixed points`: the EA ignores the signal TP/SL and calculates fresh SL/TP from the MT5 entry price.
- `No TP/SL from bridge`: the EA sends the trade without bridge-managed TP/SL. Use this only if another MT5 tool manages exits.
- `Move SL to break-even`: once price moves enough points in profit, the EA moves SL to entry plus the extra points you choose.
- `Use trailing stop`: once price moves enough points in profit, the EA trails the SL by your chosen distance.
- `Close trade after minutes`: closes bridge-managed positions that have stayed open too long.

These controls are read by the EA through `/control.txt`. They can be changed from your phone without restarting MT5.

Recommended first live-money test settings:

- Max lot: `0.01`
- Stop mode: `Use bot signal TP/SL`
- Break-even: off until the broker symbol point size is confirmed
- Trailing stop: off until the broker symbol point size is confirmed
- Close after minutes: `0`, unless you specifically want time-based exits

## VPS Notes

If MT5 runs on a Windows VPS, run the bridge on the same VPS and keep
`BridgeUrl=http://127.0.0.1:8765/signal`.

If the bridge runs on another machine, use that machine's URL and allow it in
MT5 WebRequest settings.

If you want to control it from your phone outside the VPS, expose the bridge
through a protected URL and set a control token:

```bash
export NETZARABOT_CONTROL_TOKEN="choose-a-long-private-password"
external/mt5_bridge/scripts/run_mt5_signal_bridge.sh
```

Then open the control URL on your phone and enter that token.

## Symbol Names

Deriv MT5 symbol names must match Market Watch exactly. Edit:

```text
external/mt5_bridge/config/mt5_symbol_map.csv
```

Use the names shown in MT5, for example:

```text
BOOM300N,Boom 300 Index
CRASH300N,Crash 300 Index
```
