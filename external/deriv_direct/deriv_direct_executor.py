from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import websockets


DECISION_ORDER = {"paper_order", "live_order", "signal", "trade"}


@dataclass(frozen=True)
class DerivDirectConfig:
    app_id: str
    enabled: bool
    allow_real_trading: bool
    arming_file: str
    decisions_csv: str
    journal_csv: str
    currency: str
    basis: str
    stake: float
    max_stake: float
    max_daily_stake: float
    max_daily_orders: int
    max_open_contracts: int
    min_confidence: float
    max_signal_age_minutes: float
    duration: int
    duration_unit: str
    allowed_symbols: list[str]
    symbol_contract_map: dict[str, dict[str, str]]


@dataclass(frozen=True)
class CandidateSignal:
    symbol: str
    timeframe: str
    timestamp: str
    decision: str
    side: str
    confidence: float
    reason: str
    entry: float
    stop_loss: float
    take_profit: float
    quantity: float
    risk_amount: float
    signal_id: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value in ("", None):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_config(path: Path, repo_root: Path) -> DerivDirectConfig:
    raw = load_json(path)
    return DerivDirectConfig(
        app_id=str(os.environ.get("DERIV_APP_ID") or raw.get("app_id") or "1089"),
        enabled=bool(raw.get("enabled", False)),
        allow_real_trading=bool(raw.get("allow_real_trading", False)),
        arming_file=str(repo_root / raw.get("arming_file", "live_candidate/config/ALLOW_REAL_LIVE_TRADING.txt")),
        decisions_csv=str(repo_root / raw.get("decisions_csv", "outputs/pair_candidate_paper_decisions.csv")),
        journal_csv=str(repo_root / raw.get("journal_csv", "outputs/deriv_direct_order_journal.csv")),
        currency=str(raw.get("currency") or "USD"),
        basis=str(raw.get("basis") or "stake"),
        stake=max(safe_float(raw.get("stake"), 1.0), 0.0),
        max_stake=max(safe_float(raw.get("max_stake"), 1.0), 0.0),
        max_daily_stake=max(safe_float(raw.get("max_daily_stake"), 5.0), 0.0),
        max_daily_orders=max(int(raw.get("max_daily_orders") or 1), 0),
        max_open_contracts=max(int(raw.get("max_open_contracts") or 1), 0),
        min_confidence=max(safe_float(raw.get("min_confidence"), 0.7), 0.0),
        max_signal_age_minutes=max(safe_float(raw.get("max_signal_age_minutes"), 30.0), 0.0),
        duration=max(int(raw.get("duration") or 5), 1),
        duration_unit=str(raw.get("duration_unit") or "m"),
        allowed_symbols=[str(item).strip() for item in raw.get("allowed_symbols", []) if str(item).strip()],
        symbol_contract_map=dict(raw.get("symbol_contract_map") or {}),
    )


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_journal_row(path: Path, row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "timestamp",
        "mode",
        "status",
        "symbol",
        "side",
        "contract_type",
        "stake",
        "currency",
        "signal_id",
        "proposal_id",
        "contract_id",
        "buy_price",
        "balance_after",
        "message",
    ]
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in fieldnames})


def latest_signal(path: Path, config: DerivDirectConfig) -> CandidateSignal | None:
    rows = read_rows(path)
    now = datetime.now(timezone.utc)
    candidates: list[tuple[datetime, dict[str, str]]] = []
    for row in rows:
        decision = (row.get("decision") or "").strip()
        side = (row.get("side") or "").strip().lower()
        symbol = (row.get("symbol") or "").strip()
        if decision not in DECISION_ORDER or side not in {"buy", "sell"}:
            continue
        if config.allowed_symbols and symbol not in config.allowed_symbols:
            continue
        confidence = safe_float(row.get("confidence"))
        if confidence < config.min_confidence:
            continue
        signal_time = parse_time(row.get("timestamp") or "")
        if signal_time is None:
            continue
        age_minutes = max((now - signal_time).total_seconds() / 60.0, 0.0)
        if config.max_signal_age_minutes > 0 and age_minutes > config.max_signal_age_minutes:
            continue
        candidates.append((signal_time, row))
    if not candidates:
        return None
    signal_time, row = sorted(candidates, key=lambda item: item[0], reverse=True)[0]
    symbol = (row.get("symbol") or "").strip()
    signal_id = "~".join(
        [
            symbol,
            row.get("timeframe", ""),
            row.get("side", ""),
            row.get("timestamp", ""),
            row.get("paper_order_id", ""),
        ]
    )
    return CandidateSignal(
        symbol=symbol,
        timeframe=row.get("timeframe", ""),
        timestamp=signal_time.isoformat(),
        decision=row.get("decision", ""),
        side=(row.get("side") or "").strip().lower(),
        confidence=safe_float(row.get("confidence")),
        reason=row.get("reason", ""),
        entry=safe_float(row.get("entry")),
        stop_loss=safe_float(row.get("stop_loss")),
        take_profit=safe_float(row.get("take_profit")),
        quantity=safe_float(row.get("quantity")),
        risk_amount=safe_float(row.get("risk_amount")),
        signal_id=signal_id,
    )


def contract_type_for(signal: CandidateSignal, config: DerivDirectConfig) -> str:
    mapping = config.symbol_contract_map.get(signal.symbol, {})
    if signal.side == "buy":
        return str(mapping.get("buy") or "CALL")
    return str(mapping.get("sell") or "PUT")


def proposal_payload(signal: CandidateSignal, config: DerivDirectConfig, stake: float) -> dict[str, Any]:
    return {
        "proposal": 1,
        "amount": stake,
        "basis": config.basis,
        "contract_type": contract_type_for(signal, config),
        "currency": config.currency,
        "duration": config.duration,
        "duration_unit": config.duration_unit,
        "symbol": signal.symbol,
    }


def daily_journal_totals(path: Path) -> tuple[int, float]:
    today = datetime.now(timezone.utc).date().isoformat()
    orders = 0
    stake = 0.0
    for row in read_rows(path):
        if not (row.get("timestamp") or "").startswith(today):
            continue
        if row.get("status") != "bought":
            continue
        orders += 1
        stake += safe_float(row.get("stake"))
    return orders, stake


class DerivDirectTrader:
    def __init__(self, config: DerivDirectConfig, token: str) -> None:
        self.config = config
        self.token = token
        self.req_id = 0

    def next_req_id(self) -> int:
        self.req_id += 1
        return self.req_id

    async def call(self, ws: Any, payload: dict[str, Any]) -> dict[str, Any]:
        payload.setdefault("req_id", self.next_req_id())
        await ws.send(json.dumps(payload))
        response = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
        if "error" in response:
            error = response["error"]
            raise RuntimeError(str(error.get("message") or error))
        return response

    async def authorize(self, ws: Any) -> dict[str, Any]:
        return await self.call(ws, {"authorize": self.token})

    async def balance(self, ws: Any) -> dict[str, Any]:
        return await self.call(ws, {"balance": 1})

    async def portfolio(self, ws: Any) -> dict[str, Any]:
        return await self.call(ws, {"portfolio": 1})

    async def proposal(self, ws: Any, signal: CandidateSignal, stake: float) -> dict[str, Any]:
        return await self.call(ws, proposal_payload(signal, self.config, stake))

    async def buy(self, ws: Any, proposal_id: str, stake: float, signal: CandidateSignal) -> dict[str, Any]:
        return await self.call(
            ws,
            {
                "buy": proposal_id,
                "price": stake,
                "passthrough": {
                    "bot": "netzarabot",
                    "signal_id": signal.signal_id,
                    "symbol": signal.symbol,
                    "side": signal.side,
                },
            },
        )

    async def execute(self, signal: CandidateSignal, dry_run: bool) -> dict[str, Any]:
        stake = min(self.config.stake, self.config.max_stake)
        if stake <= 0:
            raise RuntimeError("Stake is zero after applying limits.")

        daily_orders, daily_stake = daily_journal_totals(Path(self.config.journal_csv))
        if self.config.max_daily_orders and daily_orders >= self.config.max_daily_orders:
            raise RuntimeError("Daily order limit reached.")
        if self.config.max_daily_stake and daily_stake + stake > self.config.max_daily_stake:
            raise RuntimeError("Daily stake limit would be exceeded.")

        url = f"wss://ws.derivws.com/websockets/v3?app_id={self.config.app_id}"
        async with websockets.connect(url, ping_interval=20, close_timeout=10) as ws:
            auth = await self.authorize(ws)
            portfolio = await self.portfolio(ws)
            open_contracts = portfolio.get("portfolio", {}).get("contracts") or []
            if self.config.max_open_contracts and len(open_contracts) >= self.config.max_open_contracts:
                raise RuntimeError("Max open contracts reached.")
            proposal = await self.proposal(ws, signal, stake)
            proposal_id = proposal.get("proposal", {}).get("id")
            if not proposal_id:
                raise RuntimeError("Deriv did not return a proposal id.")
            if dry_run:
                balance = await self.balance(ws)
                return {
                    "status": "dry_run_proposal_ok",
                    "authorize": auth.get("authorize", {}),
                    "proposal": proposal.get("proposal", {}),
                    "balance": balance.get("balance", {}),
                    "stake": stake,
                }
            bought = await self.buy(ws, proposal_id, stake, signal)
            balance = await self.balance(ws)
            return {
                "status": "bought",
                "authorize": auth.get("authorize", {}),
                "proposal": proposal.get("proposal", {}),
                "buy": bought.get("buy", {}),
                "balance": balance.get("balance", {}),
                "stake": stake,
            }


def validate_live_arming(config: DerivDirectConfig, token: str, dry_run: bool) -> None:
    if not config.enabled:
        raise RuntimeError("Deriv-direct config enabled=false.")
    if not token:
        raise RuntimeError("DERIV_API_TOKEN is not set.")
    if not Path(config.arming_file).exists():
        raise RuntimeError(f"Arming file is missing: {config.arming_file}")
    if dry_run:
        return
    if not config.allow_real_trading:
        raise RuntimeError("Config allow_real_trading=false.")
    if os.environ.get("ALLOW_REAL_DERIV_DIRECT") != "true":
        raise RuntimeError("Set ALLOW_REAL_DERIV_DIRECT=true to permit real Deriv-direct buys.")
    if os.environ.get("DERIV_DIRECT_CONSENT") != "I_UNDERSTAND_REAL_MONEY_TRADING":
        raise RuntimeError("Set DERIV_DIRECT_CONSENT=I_UNDERSTAND_REAL_MONEY_TRADING.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute one Deriv-direct order from the latest NetzaraBot signal.")
    parser.add_argument("--config", default="live_candidate/config/deriv_direct_live_config.json")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--dry-run", action="store_true", help="Authorize and request a proposal, but do not buy.")
    parser.add_argument("--plan-only", action="store_true", help="Print the selected signal and proposal payload without token or network.")
    parser.add_argument("--force-signal-csv", default="", help="Override decision CSV path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    config = load_config(repo_root / args.config, repo_root)
    if args.force_signal_csv:
        config = DerivDirectConfig(**{**asdict(config), "decisions_csv": str(repo_root / args.force_signal_csv)})
    token = os.environ.get("DERIV_API_TOKEN", "").strip()
    try:
        if not args.plan_only:
            validate_live_arming(config, token, args.dry_run)
        signal = latest_signal(Path(config.decisions_csv), config)
        if signal is None:
            print("No fresh Deriv-direct signal passed filters.")
            return 0
        stake = min(config.stake, config.max_stake)
        if args.plan_only:
            print(
                json.dumps(
                    {
                        "ok": True,
                        "status": "plan_only",
                        "signal": asdict(signal),
                        "proposal_payload": proposal_payload(signal, config, stake),
                        "journal_csv": config.journal_csv,
                    },
                    indent=2,
                )
            )
            return 0
        trader = DerivDirectTrader(config, token)
        result = asyncio.run(trader.execute(signal, dry_run=args.dry_run))
        proposal = result.get("proposal", {})
        buy = result.get("buy", {})
        balance = result.get("balance", {})
        status = "dry_run_proposal_ok" if args.dry_run else "bought"
        write_journal_row(
            Path(config.journal_csv),
            {
                "timestamp": utc_now(),
                "mode": "dry_run" if args.dry_run else "live",
                "status": status,
                "symbol": signal.symbol,
                "side": signal.side,
                "contract_type": contract_type_for(signal, config),
                "stake": result.get("stake", ""),
                "currency": config.currency,
                "signal_id": signal.signal_id,
                "proposal_id": proposal.get("id", ""),
                "contract_id": buy.get("contract_id", ""),
                "buy_price": buy.get("buy_price", ""),
                "balance_after": balance.get("balance", ""),
                "message": status,
            },
        )
        print(json.dumps({"ok": True, "status": status, "signal": asdict(signal), "result": result}, indent=2))
        return 0
    except Exception as exc:
        write_journal_row(
            Path(config.journal_csv),
            {
                "timestamp": utc_now(),
                "mode": "dry_run" if args.dry_run else "live",
                "status": "error",
                "message": str(exc),
            },
        )
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
