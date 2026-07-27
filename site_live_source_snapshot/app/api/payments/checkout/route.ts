export const runtime = "edge";

function env(name: string): string {
  return process.env[name]?.trim() ?? "";
}

export async function GET() {
  const paymentLink = env("STRIPE_PAYMENT_LINK") || env("PAYMENT_CHECKOUT_URL");
  if (!paymentLink) {
    return Response.json(
      {
        ok: false,
        error: "Payment backend is not configured yet.",
        needed: ["STRIPE_PAYMENT_LINK or PAYMENT_CHECKOUT_URL"],
      },
      { status: 503 },
    );
  }

  return Response.redirect(paymentLink, 302);
}
