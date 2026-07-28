# Live Candidate Bot

This is a separate candidate bot package. It lets one focused bot run beside the main research/backtesting system.

Current status: **DEMO / PAPER ONLY for Deriv-direct API**

This package does not place real Deriv API trades.

The real-money route currently built in this repo is the MT5/CFD bridge:

```text
external/mt5_bridge
```

Use that route for Deriv MT5/CFD accounts.

## What It Trades In Demo

Primary demo:

- CRASH300N
- 15m
- buy only
- PAIR017

Watchlist demo:

- CRASH300N 15m PAIR017
- BOOM300N 15m PAIR006

## Why These Rules

Current paper evidence from the main monitor:

- Experimental pair: +161.69 paper PnL, 23 closed trades, 65.2% win rate
- Advanced sniper: +153.61 paper PnL, 19 closed trades, 68.4% win rate
- PAIR017: 4 wins / 0 losses on both main candidate tracks
- PAIR006: 2 wins / 0 losses on Experimental pair

This is promising, but still not enough for real money.

## Run Primary Demo

Paste this in a new Terminal:

```bash
cd /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot
live_candidate/work/run_primary_demo_monitor.sh
```

Leave it running when it says:

```text
Next live-candidate demo check in 15 minutes. Press Ctrl+C to stop.
```

## Check Status

In another Terminal:

```bash
cd /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot
live_candidate/work/check_status.sh
```

## Run Watchlist Demo

Use this only if you want PAIR017 and PAIR006 watched together:

```bash
cd /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot
live_candidate/work/run_watchlist_demo_monitor.sh
```

## Real Live Mode

Deriv-direct real live mode is intentionally blocked in this `live_candidate`
package because it has no Deriv API order sender.

This command proves that Deriv-direct live trading is blocked:

```bash
cd /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot
live_candidate/work/run_real_live_blocked.sh
```

## Rule

Keep the main research bot running separately. This candidate package collects separate paper evidence for a future tiny live pilot.

## Current Live Execution Route

For real-money CFD testing, use:

```text
external/mt5_bridge/ea/NetzaraBotBridgeEA.mq5
external/mt5_bridge/bridge/mt5_signal_server.py
external/mt5_bridge/config/control_state.json
```

That route has the live switch, TP/SL controls, flexible lot sizing, and emergency stop controls.

## MT5 And Telegram

Export tools are now included in:

```text
live_candidate/exports
```

They include:

- MT5 Signal Bridge EA
- MT5 signal CSV exporter
- Telegram status and alert bot
- Universal JSON payload for future webhooks and apps

Start with:

```bash
cd /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot
live_candidate/exports/signal_bridge/run_export_mt5_signal.sh
```

Then read:

```text
live_candidate/exports/README.md
```
