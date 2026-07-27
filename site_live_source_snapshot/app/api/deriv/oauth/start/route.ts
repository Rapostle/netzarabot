export const runtime = "edge";

function env(name: string): string {
  return process.env[name]?.trim() ?? "";
}

function randomState(): string {
  return crypto.randomUUID().replaceAll("-", "");
}

export async function GET(request: Request) {
  const clientId = env("DERIV_CLIENT_ID");
  const redirectUri = env("DERIV_REDIRECT_URI");
  const scope = env("DERIV_OAUTH_SCOPE") || "trade account_manage";

  if (!clientId || !redirectUri) {
    return Response.json(
      {
        ok: false,
        error: "Deriv OAuth is not configured yet.",
        needed: ["DERIV_CLIENT_ID", "DERIV_REDIRECT_URI"],
      },
      { status: 503 },
    );
  }

  const url = new URL("https://auth.deriv.com/oauth2/auth");
  const state = randomState();
  url.searchParams.set("response_type", "code");
  url.searchParams.set("client_id", clientId);
  url.searchParams.set("redirect_uri", redirectUri);
  url.searchParams.set("scope", scope);
  url.searchParams.set("state", state);

  const appId = env("DERIV_LEGACY_APP_ID");
  if (appId) url.searchParams.set("app_id", appId);

  const returnTo = new URL(request.url).searchParams.get("return_to");
  const response = Response.redirect(url.toString(), 302);
  response.headers.append(
    "Set-Cookie",
    `deriv_oauth_state=${state}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=600`,
  );
  if (returnTo?.startsWith("/")) {
    response.headers.append(
      "Set-Cookie",
      `deriv_return_to=${encodeURIComponent(returnTo)}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=600`,
    );
  }
  return response;
}
