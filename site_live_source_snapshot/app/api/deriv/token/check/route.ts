export const runtime = "edge";

function env(name: string): string {
  return process.env[name]?.trim() ?? "";
}

function bearerToken(request: Request): string {
  const header = request.headers.get("authorization") ?? "";
  const match = header.match(/^Bearer\s+(.+)$/i);
  return match?.[1]?.trim() ?? "";
}

function appId() {
  return env("DERIV_APP_ID") || env("DERIV_CLIENT_ID");
}

function normalizeAccounts(payload: Record<string, unknown>) {
  const data = payload.data as Record<string, unknown> | undefined;
  const maybeAccounts =
    (Array.isArray(data?.accounts) && data?.accounts) ||
    (Array.isArray(data?.account_list) && data?.account_list) ||
    (Array.isArray(payload.accounts) && payload.accounts) ||
    (Array.isArray(payload.account_list) && payload.account_list) ||
    [];

  return maybeAccounts.map((item) => {
    const account = item as Record<string, unknown>;
    const accountId = String(
      account.account_id ?? account.loginid ?? account.id ?? "",
    );
    return {
      account_id: accountId,
      currency: account.currency ?? null,
      account_type: account.account_type ?? account.type ?? null,
      is_virtual:
        account.is_virtual === 1 ||
        account.is_virtual === true ||
        accountId.toUpperCase().startsWith("VRTC"),
    };
  });
}

export async function POST(request: Request) {
  const token = bearerToken(request);
  const derivAppId = appId();

  if (!token) {
    return Response.json(
      { ok: false, error: "Missing Deriv bearer token." },
      { status: 401 },
    );
  }
  if (!derivAppId) {
    return Response.json(
      { ok: false, error: "DERIV_APP_ID is not configured." },
      { status: 503 },
    );
  }

  const response = await fetch("https://api.derivws.com/trading/v1/options/accounts", {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      "Deriv-App-ID": derivAppId,
    },
  });
  const payload = (await response.json()) as Record<string, unknown>;

  if (!response.ok) {
    return Response.json(
      {
        ok: false,
        error: "Deriv token check failed.",
        status: response.status,
        detail: payload,
      },
      { status: response.status },
    );
  }

  const accounts = normalizeAccounts(payload);
  return Response.json({
    ok: true,
    can_trade: true,
    accounts,
    demo_accounts: accounts.filter((account) => account.is_virtual),
    note:
      "Token reached Deriv's authenticated accounts endpoint. This confirms trading-scope access for the token.",
  });
}
