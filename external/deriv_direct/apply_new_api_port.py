# One-off: converts the old executor to the new Deriv API. Exact-match edits; stops if the file is not the expected original.
import re, sys
from pathlib import Path
p = Path("external/deriv_direct/deriv_direct_executor.py")
s = p.read_text()

def sub(old, new, count=1):
    global s
    assert s.count(old) == count, f"expected {count} match(es), found {s.count(old)} for: {old[:70]!r}"
    s = s.replace(old, new)

# 1. imports
sub("import os\nfrom dataclasses", "import os\nimport urllib.error\nimport urllib.request\nfrom dataclasses")

# 2. constants
sub("MULTIPLIER_CANDIDATES = (10, 20, 30, 40, 50, 100, 200)",
    '''# Deriv's new options API offers these multipliers on Boom/Crash (checked 2026-11-03).
MULTIPLIER_CANDIDATES = (20, 40, 60, 80, 100)
# Deriv adds an automatic stop-out at 90% of stake, so a stop loss must sit below it.
MAX_STOP_LOSS_FRACTION_OF_STAKE = 0.8
ENV_FILE = "/root/.deriv_env"
VALID_ACCOUNT_MODES = ("demo", "real")


def rest_base() -> str:
    return os.environ.get("DERIV_REST_BASE") or "https://api.derivws.com/trading/v1/options"


def load_env_file(path: str = ENV_FILE) -> None:
    """Load KEY=VALUE lines (never overriding variables already set)."""
    file = Path(path)
    if not file.exists():
        return
    for line in file.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())''')

# 3. config dataclass + loader
sub("    allowed_symbols: list[str]\n    tracks: list[TrackConfig]\n",
    "    allowed_symbols: list[str]\n    tracks: list[TrackConfig]\n    account_mode: str = \"demo\"\n")
sub('app_id=str(os.environ.get("DERIV_APP_ID") or raw.get("app_id") or "1089"),',
    'app_id=str(os.environ.get("DERIV_APP_ID") or raw.get("app_id") or ""),')
sub("        tracks=tracks,\n    )\n",
    '        tracks=tracks,\n        account_mode=str(raw.get("account_mode") or "demo").strip().lower(),\n    )\n')

# 4. sizing: stop loss must stay below Deriv's stop-out
sub("    stop_loss_amount = config.max_stake if config.max_stake > 0 else stake\n",
    "    stop_loss_amount = config.max_stake if config.max_stake > 0 else stake\n"
    "    stop_loss_amount = round(min(stop_loss_amount, stake * MAX_STOP_LOSS_FRACTION_OF_STAKE), 2)\n")

# 5. proposal field rename
sub('        "symbol": plan.signal.symbol,\n        "multiplier": multiplier,', '        "underlying_symbol": plan.signal.symbol,\n        "multiplier": multiplier,')

# 6. replace trader class
start = s.index("class DerivDirectTrader:")
end = s.index("def validate_live_arming")
new_class = '''class DerivDirectTrader:
    """Talks to Deriv's new options API: token -> one-time link -> WebSocket."""

    def __init__(self, config: DerivDirectConfig, pat: str = "", app_id: str = "") -> None:
        self.config = config
        self.pat = pat
        self.app_id = app_id or config.app_id
        self.req_id = 0

    def next_req_id(self) -> int:
        self.req_id += 1
        return self.req_id

    def _rest(self, method: str, path: str) -> dict[str, Any]:
        request = urllib.request.Request(rest_base() + path, method=method)
        request.add_header("Authorization", f"Bearer {self.pat}")
        request.add_header("Deriv-App-ID", self.app_id)
        request.add_header("Content-Type", "application/json")
        request.add_header("User-Agent", "netzarabot/1.0")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Deriv REST {path.split('/otp')[0]} failed (HTTP {exc.code}): {text[:200]}") from None

    def account_id(self) -> str:
        if self.config.account_mode == "real":
            ident = os.environ.get("DERIV_REAL_ACCOUNT_ID", "").strip()
            if not ident:
                raise RuntimeError("Real mode needs DERIV_REAL_ACCOUNT_ID to be set explicitly.")
            return ident
        ident = os.environ.get("DERIV_DEMO_ACCOUNT_ID", "").strip()
        if ident:
            return ident
        listing = self._rest("GET", "/accounts")
        data = listing.get("data", listing)
        items = data if isinstance(data, list) else (data.get("accounts") if isinstance(data, dict) else None) or []
        for item in items:
            kind = str(item.get("account_type") or item.get("type") or "").lower()
            ident = item.get("account_id") or item.get("id") or item.get("loginid")
            if ident and (kind == "demo" or item.get("is_virtual") in (True, 1)):
                return str(ident)
        raise RuntimeError("Could not identify a demo account; set DERIV_DEMO_ACCOUNT_ID.")

    def ws_url(self) -> str:
        otp = self._rest("POST", f"/accounts/{self.account_id()}/otp")
        url = str((otp.get("data") or {}).get("url", ""))
        expected = "/ws/real" if self.config.account_mode == "real" else "/ws/demo"
        if expected not in url:
            # Never include the link in the message: it contains the one-time password.
            raise RuntimeError(f"Refusing to connect: the one-time link is not the {self.config.account_mode} endpoint.")
        return url

    async def call(self, ws: Any, payload: dict[str, Any]) -> dict[str, Any]:
        payload.setdefault("req_id", self.next_req_id())
        await ws.send(json.dumps(payload))
        while True:
            response = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
            if response.get("req_id") == payload["req_id"]:
                break
        if "error" in response:
            error = response["error"]
            raise RuntimeError(str(error.get("message") or error))
        return response

    async def balance(self, ws: Any) -> dict[str, Any]:
        return await self.call(ws, {"balance": 1})

    async def portfolio(self, ws: Any) -> dict[str, Any]:
        return await self.call(ws, {"portfolio": 1})

    async def proposal_with_smallest_multiplier(self, ws: Any, plan: PlannedOrder) -> tuple[int, dict[str, Any]]:
        errors: list[str] = []
        for multiplier in plan.multiplier_candidates:
            try:
                return multiplier, await self.call(ws, proposal_payload(plan, self.config, multiplier))
            except RuntimeError as exc:
                errors.append(f"{multiplier}: {exc}")
        raise RuntimeError("No configured multiplier candidate was accepted by Deriv. " + " | ".join(errors))

    async def buy(self, ws: Any, proposal_id: str, stake: float, signal: CandidateSignal) -> dict[str, Any]:
        # The signal is recorded in our own journal; the new API no longer takes passthrough.
        return await self.call(ws, {"buy": proposal_id, "price": stake})

    async def execute(self, plan: PlannedOrder, dry_run: bool) -> dict[str, Any]:
        if plan.stake <= 0:
            raise RuntimeError("Stake is zero after applying limits.")
        if not self.pat or not self.app_id:
            raise RuntimeError("DERIV_PAT and DERIV_APP_ID are required.")

        _daily_orders, daily_stake = daily_journal_totals(Path(self.config.journal_csv))
        if self.config.max_daily_stake > 0 and daily_stake + plan.stake > self.config.max_daily_stake:
            raise RuntimeError("Configured daily stake limit would be exceeded.")

        url = await asyncio.to_thread(self.ws_url)
        async with websockets.connect(url, ping_interval=20, close_timeout=10) as ws:
            portfolio = await self.portfolio(ws)
            open_contracts = portfolio.get("portfolio", {}).get("contracts") or []
            if self.config.max_open_contracts and len(open_contracts) >= self.config.max_open_contracts:
                raise RuntimeError("Max open contracts reached.")
            multiplier, proposal = await self.proposal_with_smallest_multiplier(ws, plan)
            proposal_id = proposal.get("proposal", {}).get("id")
            if not proposal_id:
                raise RuntimeError("Deriv did not return a proposal id.")
            result = {
                "account_mode": self.config.account_mode,
                "portfolio": portfolio.get("portfolio", {}),
                "proposal": proposal.get("proposal", {}),
                "stake": plan.stake,
                "multiplier": multiplier,
                "proposal_payload": proposal_payload(plan, self.config, multiplier),
            }
            if dry_run:
                balance = await self.balance(ws)
                return dict(result, status="dry_run_proposal_ok", balance=balance.get("balance", {}))
            bought = await self.buy(ws, proposal_id, plan.stake, plan.signal)
            balance = await self.balance(ws)
            return dict(result, status="bought", buy=bought.get("buy", {}), balance=balance.get("balance", {}))


'''
s = s[:start] + new_class + s[end:]

# 7. arming validation
start = s.index("def validate_live_arming")
end = s.index("def parse_args")
new_validate = '''def validate_live_arming(config: DerivDirectConfig, pat: str, dry_run: bool) -> None:
    if not config.enabled:
        raise RuntimeError("Deriv-direct config enabled=false.")
    if config.account_mode not in VALID_ACCOUNT_MODES:
        raise RuntimeError(f"Config account_mode must be one of {VALID_ACCOUNT_MODES}.")
    if dry_run:
        return
    if not pat:
        raise RuntimeError("DERIV_PAT is not set.")
    if config.account_mode == "demo":
        return  # demo money only; the real-money gates below do not apply
    if not Path(config.arming_file).exists():
        raise RuntimeError(f"Arming file is missing: {config.arming_file}")
    if not config.allow_real_trading:
        raise RuntimeError("Config allow_real_trading=false.")
    if not os.environ.get("DERIV_REAL_ACCOUNT_ID", "").strip():
        raise RuntimeError("Set DERIV_REAL_ACCOUNT_ID to name the real account explicitly.")
    if os.environ.get("ALLOW_REAL_DERIV_DIRECT") != "true":
        raise RuntimeError("Set ALLOW_REAL_DERIV_DIRECT=true to permit real Deriv-direct buys.")
    if os.environ.get("DERIV_DIRECT_CONSENT") != "I_UNDERSTAND_REAL_MONEY_TRADING":
        raise RuntimeError("Set DERIV_DIRECT_CONSENT=I_UNDERSTAND_REAL_MONEY_TRADING.")


'''
s = s[:start] + new_validate + s[end:]

# 8. main()
sub('    repo_root = Path(args.repo_root).resolve()\n    config = load_config(repo_root / args.config, repo_root)\n    token = os.environ.get("DERIV_API_TOKEN", "").strip()\n',
    '    load_env_file()\n    repo_root = Path(args.repo_root).resolve()\n    config = load_config(repo_root / args.config, repo_root)\n    token = (os.environ.get("DERIV_PAT") or os.environ.get("DERIV_API_TOKEN") or "").strip()\n')
sub("trader = DerivDirectTrader(config, token)", 'trader = DerivDirectTrader(config, token, os.environ.get("DERIV_APP_ID", ""))')
sub('"mode": "dry_run" if args.dry_run else "live",\n                "status": status,\n                "track_name"',
    '"mode": "dry_run" if args.dry_run else config.account_mode,\n                "status": status,\n                "track_name"')
sub('"mode": "dry_run" if args.dry_run else "live",\n                "status": "error",',
    '"mode": "dry_run" if args.dry_run else config.account_mode,\n                "status": "error",')
sub('help="Request a real Deriv proposal, but do not buy."', 'help="Request a real Deriv price quote, but do not buy."')
p.write_text(s)
print("patched OK")
