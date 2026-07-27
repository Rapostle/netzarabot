# How To Begin Trading

Current status: **DO NOT TRADE REAL MONEY YET**

Reason: Live-readiness checklist still says NOT READY.

## Start Safely Now

1. Run the paper monitor.
2. Open the mobile app preview.
3. Use demo mode first.
4. Connect only a demo Deriv account/token while testing.
5. Confirm the bot opens, manages, and closes demo trades correctly.
6. Keep checking the live-readiness checklist.

## Commands

Start the full paper suite:

```bash
cd /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot
work/start_trading_bot_suite.sh
```

Check status:

```bash
cd /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot
work/check_bot_status.sh
```

Open the local app:

```bash
cd /Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot
work/start_local_app.sh
```

## Deriv Connection

New user:

- Tap `Create Deriv account`.
- The app opens the embedded partner/signup path.
- The raw affiliate link is not shown on-screen.

Existing user:

- Use Deriv OAuth when available.
- For manual testing, create a Deriv API token in Deriv and paste it into the app.
- Avoid Admin permission.
- Use demo first.

## Before Real Live Trading

Do not use a real-money token until all are true:

- Live-readiness checklist no longer says NOT READY.
- Manual review approves the exact strategy/rule set.
- Auto-trade settings have max daily loss, max open trades, and emergency stop enabled.
- Terms, risk disclosure, subscription agreement, and profit-share agreement are ready.
- You test the same flow on Deriv demo first.

## First Real Pilot When Approved

When approved, start tiny:

- One user account only.
- One strategy only.
- One symbol/timeframe only.
- Smallest possible stake.
- Stop after one loss, one error, or any unexpected order behavior.
