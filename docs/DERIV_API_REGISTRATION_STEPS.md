# Deriv API Registration Steps

Recommended brand name: **IdenQuanta Auto**.

Quick web-search note: I found no obvious indexed trading-bot result for the exact name `IdenQuanta Auto` during a quick search. This is not a trademark guarantee. Before buying a domain or publishing ads, do a trademark and domain check.

## For The App Owner

1. Log in to your Deriv account.
2. Open the Deriv developers/API area.
3. Create a new app.
4. Name it `IdenQuanta Auto`.
5. Add this redirect URL:

```text
https://tradepilot-auto.rapostlesam.chatgpt.site/api/deriv/oauth/callback
```

6. Enable the trading/account scopes required by Deriv.
7. Copy the App ID or Client ID.
8. Add that App ID or Client ID to the hosted website backend.

## For A Customer

1. Create a Deriv account from the app button, or log in if already registered.
2. Choose Deriv OAuth connection inside the app.
3. Approve the requested permissions.
4. Set risk controls:
   - stake
   - stop loss
   - take profit
   - max daily loss
   - max open trades
5. Start with demo auto-trading before real-money mode.

## Manual API Token Option

Manual API token connection should be used mainly for testing.

1. Log in to Deriv.
2. Open Dashboard or account settings.
3. Go to API tokens.
4. Create a new token.
5. Select only the required permissions.
6. Avoid Admin permission unless absolutely necessary.
7. Copy the token immediately.
8. Paste it into the app.
