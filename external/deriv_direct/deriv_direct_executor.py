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
HARD_MIN_WIN_RATE = 0.65
HARD_MIN_CLOSED_TRADES = 15
MULTIPLIER_CANDIDATES = (10, 20, 30, 40, 50, 100, 200)


@dataclass(frozen=True)
class TrackConfig:
    name: str
    decisions_csv: str
    closed_trades_csv: str


@dataclass(frozen=True)
class TrackQualification:
    name: str
    decisions_csv: str
    closed_trades_csv: str
    closed_trades: int
    wins: int
    win_rate: float
    qualified: bool
    reason: str


@dataclass(frozen=True)
class DerivDirectConfig:
    app_id: str
    enabled: bool
    allow_real_trading: bool
    arming_file: str
    journal_csv: str
    qualification_csv: str
    currency: str
    basis: str
    stake: float
    max_stake: float
    max_daily_stake: float
    max_open_contracts: int
    min_confidence: float
    max_signal_age_minutes: float
    allowed_symbols: list[str]
    tracks: list[TrackConfig]


@dataclass(frozen=True)
class CandidateSignal:
    track_name: str
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


@dataclass(frozen=True)
class PlannedOrder:
    signal: CandidateSignal
    contract_type: str
    stake: float
    stop_loss_amount: float
    take_profit_amount: float
    risk_reward_ratio: float
    multiplier_candidates: tuple[int, ...]


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


def safe_int(value: object, default: int = 0) -> int:
    try:
        if value in ("", None):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_repo_path(repo_root: Path, value: str) -> str:
    path = Path(value)
    if path.is_absolute():
        return str(path)
    return str(repo_root / path)


def default_tracks(repo_root: Path) -> list[TrackConfig]:
    return [
        TrackConfig(
            "Experimental pair candidates",
            str(repo_root / "outputs/pair_candidate_paper_decisions.csv"),
            str(repo_root / "outputs/pair_candidate_closed_trades.csv"),
        ),
        TrackConfig(
            "Advanced sniper candidates",
            str(repo_root / "outputs/advanced_sniper_paper_decisions.csv"),
            str(repo_root / "outputs/advanced_sniper_closed_trades.csv"),
        ),
        TrackConfig(
            "Boom/Crash expansion candidates",
            str(repo_root / "outputs/boom_crash_expansion_paper_decisions.csv"),
            str(repo_root / "outputs/boom_crash_expansion_closed_trades.csv"),
        ),
        TrackConfig(
            "Original stable rules",
            str(repo_root / "outputs/paper_stable_rules_decisions.csv"),
            str(repo_root / "outputs/paper_stable_closed_trades.csv"),
        ),
        TrackConfig(
            "Strict research candidates",
            str(repo_root / "outputs/strict_research_paper_decisions.csv"),
            str(repo_root / "outputs/strict_research_closed_trades.csv"),
        ),
    ]


def load_config(path: Path, repo_root: Path) -> DerivDirectConfig:
    raw = load_json(path)
    max_stake = max(safe_float(raw.get("max_stake"), safe_float(raw.get("stake"), 1.0)), 0.0)
    stake = max(safe_float(raw.get("stake"), max_stake or 1.0), 0.0)
    max_daily_stake = max(safe_float(raw.get("max_daily_stake"), 0.0), 0.0)
    if max_stake > 0 and stake > max_stake:
        stake = max_stake

    raw_tracks = raw.get("tracks") or []
    tracks = [
        TrackConfig(
            name=str(item.get("name") or "Unnamed track"),
            decisions_csv=resolve_repo_path(repo_root, str(item.get("decisions_csv") or "")),
            closed_trades_csv=resolve_repo_path(repo_root, str(item.get("closed_trades_csv") or "")),
        )
        for item in raw_tracks
        if item.get("decisions_csv") and item.get("closed_trades_csv")
    ] or default_tracks(repo_root)

    return DerivDirectConfig(
        app_id=str(os.environ.get("DERIV_APP_ID") or raw.get("app_id") or "1089"),
        enabled=bool(raw.get("enabled", False)),
        allow_real_trading=bool(raw.get("allow_real_trading", False)),
        arming_file=resolve_repo_path(repo_root, str(raw.get("arming_file", "live_candidate/config/ALLOW_REAL_LIVE_TRADING.txt"))),
        journal_csv=resolve_repo_path(repo_root, str(raw.get("journal_csv", "outputs/deriv_direct_order_journal.csv"))),
        qualification_csv=resolve_repo_path(repo_root, str(raw.get("qualification_csv", "outputs/deriv_direct_track_qualification.csv"))),
        currency=str(raw.get("currency") or "USD"),
        basis="stake",
        stake=stake,
        max_stake=max_stake,
        max_daily_stake=max_daily_stake,
        max_open_contracts=max(safe_int(raw.get("max_open_contracts"), 1), 0),
        min_confidence=max(safe_float(raw.get("min_confidence"), 0.7), 0.0),
        max_signal_age_minutes=max(safe_float(raw.get("max_signal_age_minutes"), 30.0), 0.0),
        allowed_symbols=[str(item).strip() for item in raw.get("allowed_symbols", []) if str(item).strip()],
        tracks=tracks,
    )


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def append_csv_row(path: Path, fieldnames: list[str], row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_journal_row(path: Path, row: dict[str, object]) -> None:
    append_csv_row(
        path,
        [
            "timestamp",
            "mode",
            "status",
            "track_name",
            "symbol",
            "side",
            "contract_type",
            "stake",
            "multiplier",
            "stop_loss_amount",
            "take_profit_amount",
            "risk_reward_ratio",
            "currency",
            "signal_id",
            "proposal_id",
            "contract_id",
            "buy_price",
            "balance_after",
            "message",
        ],
        row,
    )


def write_qualification_rows(path: Path, rows: list[TrackQualification], selected: CandidateSignal | None) -> None:
    run_timestamp = utc_now()
    selected_id = selected.signal_id if selected else ""
    selected_track = selected.track_name if selected else ""
    for row in rows:
        append_csv_row(
            path,
            [
                "timestamp",
                "track_name",
                "decisions_csv",
                "closed_trades_csv",
                "closed_trades",
                "wins",
                "win_rate",
                "qualified",
                "reason",
                "selected_track",
                "selected_signal_id",
            ],
            {
                "timestamp": run_timestamp,
                "track_name": row.name,
                "decisions_csv": row.decisions_csv,
                "closed_trades_csv": row.closed_trades_csv,
                "closed_trades": row.closed_trades,
                "wins": row.wins,
                "win_rate": round(row.win_rate, 6),
                "qualified": row.qualified,
                "reason": row.reason,
                "selected_track": selected_track,
                "selected_signal_id": selected_id,
            },
        )


def qualify_track(track: TrackConfig) -> TrackQualification:
    path = Path(track.closed_trades_csv)
    rows = [row for row in read_rows(path) if (row.get("status") or "").strip().lower() == "closed"]
    closed = len(rows)
    wins = sum(1 for row in rows if safe_float(row.get("paper_pnl")) > 0)
    win_rate = wins / closed if closed else 0.0
    reasons = []
    if closed < HARD_MIN_CLOSED_TRADES:
        reasons.append(f"closed_trades {closed} < {HARD_MIN_CLOSED_TRADES}")
    if win_rate < HARD_MIN_WIN_RATE:
        reasons.append(f"win_rate {win_rate:.2%} < {HARD_MIN_WIN_RATE:.2%}")
    qualified = not reasons
    return TrackQualification(
        name=track.name,
        decisions_csv=track.decisions_csv,
        closed_trades_csv=track.closed_trades_csv,
        closed_trades=closed,
        wins=wins,
        win_rate=win_rate,
        qualified=qualified,
        reason="qualified" if qualified else "; ".join(reasons),
    )


def signal_from_row(row: dict[str, str], track_name: str, signal_time: datetime) -> CandidateSignal:
    symbol = (row.get("symbol") or "").strip()
    signal_id = "~".join(
        [
            track_name,
            symbol,
            row.get("timeframe", ""),
            row.get("side", ""),
            row.get("timestamp", ""),
            row.get("paper_order_id", ""),
        ]
    )
    return CandidateSignal(
        track_name=track_name,
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


def latest_track_signal(track: TrackConfig, config: DerivDirectConfig) -> tuple[datetime, CandidateSignal] | None:
    rows = read_rows(Path(track.decisions_csv))
    now = datetime.now(timezone.utc)
    candidates: list[tuple[datetime, CandidateSignal]] = []
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
        signal = signal_from_row(row, track.name, signal_time)
        if signal.entry <= 0 or signal.stop_loss <= 0 or signal.take_profit <= 0:
            continue
        if abs(signal.entry - signal.stop_loss) <= 0 or abs(signal.take_profit - signal.entry) <= 0:
            continue
        candidates.append((signal_time, signal))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item[0], reverse=True)[0]


def select_signal(config: DerivDirectConfig) -> tuple[CandidateSignal | None, list[TrackQualification]]:
    qualifications = [qualify_track(track) for track in config.tracks]
    track_by_name = {track.name: track for track in config.tracks}
    candidates: list[tuple[datetime, CandidateSignal]] = []
    for qualification in qualifications:
        if not qualification.qualified:
            continue
        candidate = latest_track_signal(track_by_name[qualification.name], config)
        if candidate is not None:
            candidates.append(candidate)
    selected = sorted(candidates, key=lambda item: item[0], reverse=True)[0][1] if candidates else None
    return selected, qualifications


def contract_type_for(signal: CandidateSignal) -> str:
    return "MULTUP" if signal.side == "buy" else "MULTDOWN"


def risk_reward_ratio(signal: CandidateSignal) -> float:
    risk_distance = abs(signal.entry - signal.stop_loss)
    reward_distance = abs(signal.take_profit - signal.entry)
    if risk_distance <= 0 or reward_distance <= 0:
        raise RuntimeError("Signal stop_loss/take_profit cannot produce a risk/reward ratio.")
    return reward_distance / risk_distance


def plan_order(signal: CandidateSignal, config: DerivDirectConfig) -> PlannedOrder:
    ratio = risk_reward_ratio(signal)
    stake = min(config.stake, config.max_stake) if config.max_stake > 0 else config.stake
    stop_loss_amount = config.max_stake if config.max_stake > 0 else stake
    return PlannedOrder(
        signal=signal,
        contract_type=contract_type_for(signal),
        stake=stake,
        stop_loss_amount=stop_loss_amount,
        take_profit_amount=round(stop_loss_amount * ratio, 2),
        risk_reward_ratio=ratio,
        multiplier_candidates=MULTIPLIER_CANDIDATES,
    )


def proposal_payload(plan: PlannedOrder, config: DerivDirectConfig, multiplier: int) -> dict[str, Any]:
    return {
        "proposal": 1,
        "amount": plan.stake,
        "basis": config.basis,
        "contract_type": plan.contract_type,
        "currency": config.currency,
        "symbol": plan.signal.symbol,
        "multiplier": multiplier,
        "limit_order": {
            "stop_loss": plan.stop_loss_amount,
            "take_profit": plan.take_profit_amount,
        },
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
    def __init__(self, config: DerivDirectConfig, token: str = "") -> None:
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

    async def proposal_with_smallest_multiplier(self, ws: Any, plan: PlannedOrder) -> tuple[int, dict[str, Any]]:
        errors: list[str] = []
        for multiplier in plan.multiplier_candidates:
            try:
                return multiplier, await self.call(ws, proposal_payload(plan, self.config, multiplier))
            except RuntimeError as exc:
                errors.append(f"{multiplier}: {exc}")
        raise RuntimeError("No configured multiplier candidate was accepted by Deriv. " + " | ".join(errors))

    async def buy(self, ws: Any, proposal_id: str, stake: float, signal: CandidateSignal) -> dict[str, Any]:
        return await self.call(
            ws,
            {
                "buy": proposal_id,
                "price": stake,
                "passthrough": {
                    "bot": "netzarabot",
                    "track": signal.track_name,
                    "signal_id": signal.signal_id,
                    "symbol": signal.symbol,
                    "side": signal.side,
                },
            },
        )

    async def execute(self, plan: PlannedOrder, dry_run: bool) -> dict[str, Any]:
        if plan.stake <= 0:
            raise RuntimeError("Stake is zero after applying limits.")

        _daily_orders, daily_stake = daily_journal_totals(Path(self.config.journal_csv))
        if self.config.max_daily_stake > 0 and daily_stake + plan.stake > self.config.max_daily_stake:
            raise RuntimeError("Configured daily stake limit would be exceeded.")

        url = f"wss://ws.derivws.com/websockets/v3?app_id={self.config.app_id}"
        async with websockets.connect(url, ping_interval=20, close_timeout=10) as ws:
            auth: dict[str, Any] = {}
            portfolio: dict[str, Any] = {}
            if self.token:
                auth = await self.authorize(ws)
                portfolio = await self.portfolio(ws)
                open_contracts = portfolio.get("portfolio", {}).get("contracts") or []
                if self.config.max_open_contracts and len(open_contracts) >= self.config.max_open_contracts:
                    raise RuntimeError("Max open contracts reached.")
            multiplier, proposal = await self.proposal_with_smallest_multiplier(ws, plan)
            proposal_id = proposal.get("proposal", {}).get("id")
            if not proposal_id:
                raise RuntimeError("Deriv did not return a proposal id.")
            if dry_run:
                balance = await self.balance(ws) if self.token else {}
                return {
                    "status": "dry_run_proposal_ok",
                    "authorize": auth.get("authorize", {}),
                    "portfolio": portfolio.get("portfolio", {}),
                    "proposal": proposal.get("proposal", {}),
                    "balance": balance.get("balance", {}),
                    "stake": plan.stake,
                    "multiplier": multiplier,
                    "proposal_payload": proposal_payload(plan, self.config, multiplier),
                }
            if not self.token:
                raise RuntimeError("DERIV_API_TOKEN is required for a real buy.")
            bought = await self.buy(ws, proposal_id, plan.stake, plan.signal)
            balance = await self.balance(ws)
            return {
                "status": "bought",
                "authorize": auth.get("authorize", {}),
                "portfolio": portfolio.get("portfolio", {}),
                "proposal": proposal.get("proposal", {}),
                "buy": bought.get("buy", {}),
                "balance": balance.get("balance", {}),
                "stake": plan.stake,
                "multiplier": multiplier,
                "proposal_payload": proposal_payload(plan, self.config, multiplier),
            }


def validate_live_arming(config: DerivDirectConfig, token: str, dry_run: bool) -> None:
    if not config.enabled:
        raise RuntimeError("Deriv-direct config enabled=false.")
    if not Path(config.arming_file).exists():
        raise RuntimeError(f"Arming file is missing: {config.arming_file}")
    if dry_run:
        return
    if not token:
        raise RuntimeError("DERIV_API_TOKEN is not set.")
    if not config.allow_real_trading:
        raise RuntimeError("Config allow_real_trading=false.")
    if os.environ.get("ALLOW_REAL_DERIV_DIRECT") != "true":
        raise RuntimeError("Set ALLOW_REAL_DERIV_DIRECT=true to permit real Deriv-direct buys.")
    if os.environ.get("DERIV_DIRECT_CONSENT") != "I_UNDERSTAND_REAL_MONEY_TRADING":
        raise RuntimeError("Set DERIV_DIRECT_CONSENT=I_UNDERSTAND_REAL_MONEY_TRADING.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute one Deriv-direct Multiplier order from the freshest qualified NetzaraBot signal.")
    parser.add_argument("--config", default="live_candidate/config/deriv_direct_live_config.json")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--dry-run", action="store_true", help="Request a real Deriv proposal, but do not buy.")
    parser.add_argument("--plan-only", action="store_true", help="Print track qualification, selected signal, and proposal payload without network.")
    return parser.parse_args()


def response_payload(status: str, config: DerivDirectConfig, qualifications: list[TrackQualification], selected: CandidateSignal | None, plan: PlannedOrder | None, result: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": True,
        "status": status,
        "hard_limits": {
            "min_win_rate": HARD_MIN_WIN_RATE,
            "min_closed_trades": HARD_MIN_CLOSED_TRADES,
        },
        "stake_limits": {
            "stake": config.stake,
            "max_stake": config.max_stake,
            "max_daily_stake": config.max_daily_stake,
            "max_daily_orders": "unlimited",
        },
        "tracks": [asdict(row) for row in qualifications],
        "selected_signal": asdict(selected) if selected else None,
        "qualification_csv": config.qualification_csv,
        "journal_csv": config.journal_csv,
    }
    if plan is not None:
        payload["planned_order"] = {
            "contract_type": plan.contract_type,
            "stake": plan.stake,
            "stop_loss_amount": plan.stop_loss_amount,
            "take_profit_amount": plan.take_profit_amount,
            "risk_reward_ratio": plan.risk_reward_ratio,
            "multiplier_candidates": list(plan.multiplier_candidates),
            "example_proposal_payload": proposal_payload(plan, config, plan.multiplier_candidates[0]),
        }
    if result is not None:
        payload["result"] = result
    return payload


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    config = load_config(repo_root / args.config, repo_root)
    token = os.environ.get("DERIV_API_TOKEN", "").strip()
    try:
        if not args.plan_only:
            validate_live_arming(config, token, args.dry_run)
        selected, qualifications = select_signal(config)
        write_qualification_rows(Path(config.qualification_csv), qualifications, selected)
        if selected is None:
            print(json.dumps(response_payload("no_fresh_qualified_signal", config, qualifications, None, None), indent=2))
            return 0
        plan = plan_order(selected, config)
        if args.plan_only:
            print(json.dumps(response_payload("plan_only", config, qualifications, selected, plan), indent=2))
            return 0
        trader = DerivDirectTrader(config, token)
        result = asyncio.run(trader.execute(plan, dry_run=args.dry_run))
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
                "track_name": selected.track_name,
                "symbol": selected.symbol,
                "side": selected.side,
                "contract_type": plan.contract_type,
                "stake": plan.stake,
                "multiplier": result.get("multiplier", ""),
                "stop_loss_amount": plan.stop_loss_amount,
                "take_profit_amount": plan.take_profit_amount,
                "risk_reward_ratio": round(plan.risk_reward_ratio, 6),
                "currency": config.currency,
                "signal_id": selected.signal_id,
                "proposal_id": proposal.get("id", ""),
                "contract_id": buy.get("contract_id", ""),
                "buy_price": buy.get("buy_price", ""),
                "balance_after": balance.get("balance", ""),
                "message": status,
            },
        )
        print(json.dumps(response_payload(status, config, qualifications, selected, plan, result), indent=2))
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
