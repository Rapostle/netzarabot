# Live Candidate Export Layer

This folder turns the paper-tested candidate bot into formats you can use outside this research workspace.

Current status: **signals and paper monitoring only**.

## Formats Included

1. **MT5 Signal Bridge EA**
   - File: `mt5/LiveCandidateSignalBridgeEA.mq5`
   - Reads `live_candidate_signals.csv` from the MT5 `MQL5/Files` folder.
   - Default: live execution is OFF.

2. **MT5 Signal Exporter**
   - File: `signal_bridge/export_signal_for_mt5.py`
   - Converts the latest candidate decision into an MT5-readable CSV.

3. **Telegram Status Bot**
   - File: `telegram/telegram_bot.py`
   - Commands: `/status`, `/signals`, `/readiness`, `/help`
   - It reports status and signals. It does not place trades.

4. **Universal Integration Payload**
   - File: `webhook/export_payload.py`
   - Creates `latest_payload.json` for future Discord, WhatsApp, website, email, webhook, or automation integrations.

## Export Latest MT5 Signal

Run:

```bash
cd /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot
live_candidate/exports/signal_bridge/run_export_mt5_signal.sh
```

Then copy this file into your MT5 `MQL5/Files` folder:

```text
/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/live_candidate/exports/mt5/live_candidate_signals.csv
```

## Install The MT5 EA

1. Open MT5.
2. Open MetaEditor.
3. Copy `LiveCandidateSignalBridgeEA.mq5` into `MQL5/Experts`.
4. Compile it.
5. Attach it to the matching chart, for example `CRASH300N` on `15m`.
6. Leave `EnableLiveTrading=false` until the bot has passed live-readiness.

## Run Telegram Bot

Create a Telegram bot with BotFather, then run:

```bash
cd /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot
export TELEGRAM_BOT_TOKEN='paste_token_here'
live_candidate/exports/telegram/run_telegram_bot.sh
```

Optional: lock it to your chat only:

```bash
export TELEGRAM_CHAT_ID='your_chat_id'
```

## Safety

The MT5 EA has live trading disabled by default. Telegram is status-only. This package is meant to prove signal delivery first, then later become a tiny live pilot after readiness passes.

## Export Universal Payload

Run:

```bash
cd /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot
live_candidate/exports/webhook/run_export_payload.sh
```

This creates:

```text
live_candidate/exports/webhook/latest_payload.json
```
