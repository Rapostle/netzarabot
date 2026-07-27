export const runtime = "edge";

function flag(name: string) {
  return process.env[name]?.trim() === "true";
}

function has(name: string) {
  return Boolean(process.env[name]?.trim());
}

export async function GET() {
  return Response.json({
    payment_backend: has("STRIPE_PAYMENT_LINK") || has("PAYMENT_CHECKOUT_URL"),
    deriv_oauth: has("DERIV_CLIENT_ID") && has("DERIV_REDIRECT_URI"),
    deriv_app_id: has("DERIV_APP_ID") || has("DERIV_CLIENT_ID"),
    live_trading_enabled: flag("LIVE_TRADING_ENABLED"),
    real_trading_enabled: flag("ALLOW_REAL_DERIV_TRADING"),
    required_before_real_trades: [
      "Payment checkout URL or Stripe integration",
      "Deriv OAuth app ID and redirect URI",
      "User Deriv bearer token with trade scope",
      "LIVE_TRADING_ENABLED=true",
      "ALLOW_REAL_DERIV_TRADING=true for real accounts",
      "User consent on every live-trading account",
    ],
  });
}
