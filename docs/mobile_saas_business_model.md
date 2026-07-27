# Mobile Auto-Trading SaaS Business Model

## Product Direction

The product is an auto-trading app, not a signal-only app.

- Users pay a $50 monthly subscription.
- Users must create or connect a Deriv account.
- New users are routed through the embedded Deriv partner/signup link.
- Existing Deriv users connect by OAuth or by manually entering a Deriv API token.
- The bot runs 24/7 on a server.
- The app tracks 20% of net profits as a performance-fee target.
- User referrals can earn 5% of the registration fee.

## Deriv Connection Options

### New User

The app shows a simple button: `Create Deriv account`.

The partner link is stored in app configuration and opened behind the button. The user does not need to see or copy the raw affiliate URL.

### Existing User

The app offers:

- Deriv OAuth login/connect, preferred for web and mobile apps.
- Manual Deriv API token entry, useful for early testing.

Deriv documentation describes OAuth as a delegated flow where users grant the app access without sharing their password. It also describes Personal Access Token apps where the user generates a token and pastes it into the app.

For manual API tokens, the user should:

1. Log in to Deriv.
2. Open Dashboard or account settings.
3. Go to API tokens.
4. Create a new token.
5. Select only required scopes.
6. Copy the token immediately.
7. Paste it into the app.

Avoid requesting Admin permission unless absolutely necessary.

## Profit Share

Target: 20% of net profit.

Product rule:

- Charge only on net profitable cycles.
- Carry losses forward before charging another fee.
- Show a fee ledger to the user.
- Never charge a performance fee on losing periods.

This feature should be treated as compliance-sensitive. In many places, taking a percentage of trading profit can look like managed trading, copy trading, investment advice, or another regulated financial service.

## Live Trading Rule

The business app can be built now, but live execution should remain off until:

- Paper results pass the readiness checklist.
- Manual review approves the exact rule set.
- User accepts risk disclosure and auto-trading terms.
- Country availability rules are defined.
- Deriv account/API permissions are verified.
- Emergency stop, max loss, and max open-trade controls are active.

## Revenue Streams

1. $50 monthly subscription.
2. Deriv partner/affiliate commission from eligible referred users.
3. 20% performance fee after compliance review.
4. 5% user referral fee on registration payments.

## Build Order

1. Mobile auto-trading dashboard.
2. Deriv signup/connect flow.
3. Subscription gate.
4. Referral tracking.
5. Profit-fee ledger.
6. 24/7 server runner.
7. Demo auto-trading.
8. Tiny real-money pilot only after readiness passes.
