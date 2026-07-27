export const runtime = "edge";

type TradeRequest = {
  account_id?: string;
  account_type?: "demo" | "real";
  proposal_id?: string;
  price?: number;
  contract?: Record<string, unknown>;
  client_reference?: string;
  consent?: boolean;
};

function env(name: string): string {
  return process.env[name]?.trim() ?? "";
}

function bearerToken(request: Request): string {
  const header = request.headers.get("authorization") ?? "";
  const match = header.match(/^Bearer\s+(.+)$/i);
  return match?.[1]?.trim() ?? "";
}

async function derivFetch(path: string, token: string, body?: unknown) {
  const response = await fetch(`https://api.derivws.com${path}`, {
    method: body ? "POST" : "GET",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      "Deriv-App-ID": env("DERIV_APP_ID") || env("DERIV_CLIENT_ID"),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const payload = (await response.json()) as Record<string, unknown>;
  if (!response.ok) {
    throw new Error(JSON.stringify(payload));
  }
  return payload;
}

function buildBuyPayload(payload: TradeRequest): Record<string, unknown> {
  if (payload.proposal_id) {
    return {
      buy: payload.proposal_id,
      price: payload.price ?? Number(env("DEFAULT_MAX_STAKE_USD") || "1"),
      passthrough: {
        client_reference: payload.client_reference ?? crypto.randomUUID(),
      },
    };
  }

  if (payload.contract) {
    return {
      buy: 1,
      price: payload.price ?? Number(env("DEFAULT_MAX_STAKE_USD") || "1"),
      parameters: payload.contract,
      passthrough: {
        client_reference: payload.client_reference ?? crypto.randomUUID(),
      },
    };
  }

  throw new Error("Provide proposal_id or contract parameters.");
}

export async function POST(request: Request) {
  if (env("LIVE_TRADING_ENABLED") !== "true") {
    return Response.json(
      {
        ok: false,
        error: "Live trading backend is installed but not enabled.",
        needed: ["LIVE_TRADING_ENABLED=true"],
      },
      { status: 403 },
    );
  }

  const token = bearerToken(request);
  if (!token) {
    return Response.json(
      { ok: false, error: "Missing Deriv bearer token." },
      { status: 401 },
    );
  }

  const payload = (await request.json()) as TradeRequest;
  if (payload.account_type === "real" && env("ALLOW_REAL_DERIV_TRADING") !== "true") {
    return Response.json(
      {
        ok: false,
        error: "Real Deriv trading requires ALLOW_REAL_DERIV_TRADING=true.",
      },
      { status: 403 },
    );
  }
  if (!payload.consent) {
    return Response.json(
      { ok: false, error: "User live-trading consent is required." },
      { status: 400 },
    );
  }
  if (!payload.account_id) {
    return Response.json(
      { ok: false, error: "account_id is required." },
      { status: 400 },
    );
  }

  try {
    const otp = await derivFetch(
      `/trading/v1/options/accounts/${encodeURIComponent(payload.account_id)}/otp`,
      token,
      {},
    );
    const wsUrl =
      typeof otp.websocket_url === "string"
        ? otp.websocket_url
        : typeof otp.url === "string"
          ? otp.url
          : "";
    if (!wsUrl) {
      return Response.json(
        { ok: false, error: "Deriv OTP response did not include a WebSocket URL.", otp },
        { status: 502 },
      );
    }

    const buyPayload = buildBuyPayload(payload);
    const result = await new Promise<Record<string, unknown>>((resolve, reject) => {
      const socket = new WebSocket(wsUrl);
      const timeout = setTimeout(() => {
        socket.close();
        reject(new Error("Deriv WebSocket trade timed out."));
      }, 15000);

      socket.addEventListener("open", () => socket.send(JSON.stringify(buyPayload)));
      socket.addEventListener("message", (event) => {
        clearTimeout(timeout);
        socket.close();
        try {
          resolve(JSON.parse(String(event.data)) as Record<string, unknown>);
        } catch {
          reject(new Error("Could not parse Deriv WebSocket response."));
        }
      });
      socket.addEventListener("error", () => {
        clearTimeout(timeout);
        reject(new Error("Deriv WebSocket error."));
      });
    });

    return Response.json({ ok: true, result });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unexpected trade error";
    return Response.json({ ok: false, error: message }, { status: 502 });
  }
}
