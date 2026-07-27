# Real Deriv Trading Backend

The hosted app now includes backend routes for:

- Payment checkout: `/api/payments/checkout`
- Deriv OAuth start: `/api/deriv/oauth/start`
- Deriv OAuth callback: `/api/deriv/oauth/callback`
- Deriv trade execution: `/api/deriv/trade/execute`
- Deriv token check: `/api/deriv/token/check`
- Readiness check: `/api/system/readiness`

## Required Hosted Environment Variables

Payment:

- `STRIPE_PAYMENT_LINK` or `PAYMENT_CHECKOUT_URL`
- `FOUNDER_FREE_EMAILS`, comma-separated emails that bypass subscription checks while the app is being built

Deriv:

- `DERIV_CLIENT_ID`
- `DERIV_APP_ID` if different from client ID
- `DERIV_REDIRECT_URI`
- `DERIV_OAUTH_SCOPE`, usually `trade account_manage`

Trading switches:

- `LIVE_TRADING_ENABLED=true`
- `ALLOW_REAL_DERIV_TRADING=true`
- `DEFAULT_MAX_STAKE_USD=1`

## Trade Execution Request

The execution route requires:

- Authorization header: `Bearer USER_DERIV_ACCESS_TOKEN`
- `account_id`
- `account_type`: `demo` or `real`
- `consent: true`
- `proposal_id` or explicit `contract` parameters

Example:

```json
{
  "account_id": "CR1234567",
  "account_type": "real",
  "proposal_id": "proposal-id-from-deriv",
  "price": 1,
  "consent": true,
  "client_reference": "tradepilot-001"
}
```

## Important

The endpoint can place real Deriv trades only after the hosted environment variables are set and the user provides a valid Deriv token with trade permission.

Do not store raw user tokens unencrypted. The current route accepts a bearer token per request so no token is stored in the prototype.

## Private Token Test

Use this to confirm a demo token without placing a trade:

```bash
read -s DERIV_TOKEN
curl -X POST https://www.netzarabot.com/api/deriv/token/check \
  -H "Authorization: Bearer $DERIV_TOKEN"
```

Expected result:

- `ok: true`
- account ID shown
- scopes include `read` and `trade`
- demo accounts usually show as virtual

## Founder Free Access

Add your own email to `FOUNDER_FREE_EMAILS` so your account can use the app without paying the subscription during setup and testing.

Current founder/free-access email:

- `idengelirose@gmail.com`
