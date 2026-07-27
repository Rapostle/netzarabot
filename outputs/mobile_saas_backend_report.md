# Mobile SaaS Backend Report

Last updated UTC: 2026-07-27T17:21:32.874897+00:00

This backend skeleton supports the auto-trading business app. It is still a local prototype.

## Live Trading Gate

- Allowed: **False**
- Reason: Live-readiness checklist still says NOT READY.

## Users

| id | email | full_name | referral_code | referred_by_code |
| --- | --- | --- | --- | --- |
| 1 | founder@example.com | Founder Admin | TA-FOUNDER | None |
| 2 | demo.user@example.com | Demo Subscriber | TA-4821 | TA-FOUNDER |

## Subscriptions

| id | user_id | plan_name | monthly_price_usd | status |
| --- | --- | --- | --- | --- |
| 1 | 2 | Auto Trader | 50.0 | demo_active |
| 2 | 2 | Auto Trader | 50.0 | demo_active |
| 3 | 2 | Auto Trader | 50.0 | demo_active |
| 4 | 2 | Auto Trader | 50.0 | demo_active |
| 5 | 2 | Auto Trader | 50.0 | demo_active |

## Deriv Connections

| id | user_id | connection_type | deriv_account_id | account_mode | status |
| --- | --- | --- | --- | --- | --- |
| 1 | 2 | manual_api_token | CR-DEMO-PENDING | demo | demo_connected_live_locked |
| 2 | 2 | manual_api_token | CR-DEMO-PENDING | demo | demo_connected_live_locked |
| 3 | 2 | manual_api_token | CR-DEMO-PENDING | demo | demo_connected_live_locked |
| 4 | 2 | manual_api_token | CR-DEMO-PENDING | demo | demo_connected_live_locked |
| 5 | 2 | manual_api_token | CR-DEMO-PENDING | demo | demo_connected_live_locked |

## Auto-Trade Settings

| user_id | enabled_requested | live_execution_allowed | strategy_group | max_daily_loss_pct | max_open_trades | max_risk_per_trade_pct |
| --- | --- | --- | --- | --- | --- | --- |
| 2 | 1 | 0 | strict_approved_candidates_only | 2.0 | 1 | 0.5 |

## Referral Ledger

| id | referrer_user_id | referred_user_id | registration_fee_usd | referral_percent | referral_fee_usd | status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 2 | 50.0 | 5.0 | 2.5 | pending_real_payment |
| 2 | 1 | 2 | 50.0 | 5.0 | 2.5 | pending_real_payment |
| 3 | 1 | 2 | 50.0 | 5.0 | 2.5 | pending_real_payment |
| 4 | 1 | 2 | 50.0 | 5.0 | 2.5 | pending_real_payment |
| 5 | 1 | 2 | 50.0 | 5.0 | 2.5 | pending_real_payment |

## Profit-Share Ledger

| id | user_id | gross_profit_usd | carried_loss_usd | net_profit_after_carry_usd | performance_fee_percent | fee_due_usd | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2 | 0.0 | 0.0 | 0.0 | 20.0 | 0.0 | tracking_only_not_billable |
| 2 | 2 | 0.0 | 0.0 | 0.0 | 20.0 | 0.0 | tracking_only_not_billable |
| 3 | 2 | 0.0 | 0.0 | 0.0 | 20.0 | 0.0 | tracking_only_not_billable |
| 4 | 2 | 0.0 | 0.0 | 0.0 | 20.0 | 0.0 | tracking_only_not_billable |
| 5 | 2 | 0.0 | 0.0 | 0.0 | 20.0 | 0.0 | tracking_only_not_billable |

## Rule

Real Deriv trading remains blocked until the live-readiness checklist and manual review both approve it.
