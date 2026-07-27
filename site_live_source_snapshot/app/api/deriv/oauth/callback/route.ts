export const runtime = "edge";

function env(name: string): string {
  return process.env[name]?.trim() ?? "";
}

function cookieValue(cookie: string | null, name: string): string {
  if (!cookie) return "";
  const part = cookie
    .split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith(`${name}=`));
  return part ? decodeURIComponent(part.slice(name.length + 1)) : "";
}

export async function GET(request: Request) {
  const clientId = env("DERIV_CLIENT_ID");
  const redirectUri = env("DERIV_REDIRECT_URI");
  const url = new URL(request.url);
  const code = url.searchParams.get("code") ?? "";
  const state = url.searchParams.get("state") ?? "";
  const expectedState = cookieValue(request.headers.get("cookie"), "deriv_oauth_state");

  if (!clientId || !redirectUri) {
    return Response.json(
      { ok: false, error: "Deriv OAuth is not configured yet." },
      { status: 503 },
    );
  }
  if (!code || !state || !expectedState || state !== expectedState) {
    return Response.json(
      { ok: false, error: "Invalid Deriv OAuth callback state." },
      { status: 400 },
    );
  }

  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: clientId,
    code,
    redirect_uri: redirectUri,
  });

  const tokenResponse = await fetch("https://auth.deriv.com/oauth2/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  const tokenPayload = (await tokenResponse.json()) as Record<string, unknown>;

  if (!tokenResponse.ok) {
    return Response.json(
      { ok: false, error: "Deriv token exchange failed.", detail: tokenPayload },
      { status: 502 },
    );
  }

  return Response.json({
    ok: true,
    message:
      "Deriv connected. In production this token should be encrypted and stored against the logged-in user.",
    token_type: tokenPayload.token_type,
    expires_in: tokenPayload.expires_in,
    access_token_preview:
      typeof tokenPayload.access_token === "string"
        ? `${tokenPayload.access_token.slice(0, 10)}...`
        : null,
  });
}
