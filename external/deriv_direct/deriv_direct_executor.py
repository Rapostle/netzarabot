from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import websockets


DECISION_ORDER = {"paper_order", "live_order", "signal", "trade"}
HARD_MIN_WIN_RATE = 0.65
HARD_MIN_CLOSED_TRADES = 15
# Deriv's new options API offers these multipliers on Boom/Crash (checked 2026-11-03).
MULTIPLIER_CANDIDATES = (20, 40, 60, 80, 100)
# Deriv adds an automatic stop-out at 90% of stake, so a stop loss must sit below it.
MAX_STOP_LOSS_FRACTION_OF_STAKE = 0.8
# Paper trades are closed after this many candles if neither level was reached.
MAX_HOLD_BARS = 12
# Demo gate defaults (money-free): a rule with fewer closed trades than this is on probation and may trade.
DEFAULT_PROBATION_TRADES = 5
# A whole track is switched off in demo only if it has this many closed trades and a win rate below the floor.
DEFAULT_TRACK_FLOOR_WIN_RATE = 0.40
DEFAULT_TRACK_FLOOR_MIN_TRADES = 8
GATE_MODES = ("per_rule", "per_track")
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
            os.environ.setdefault(key.strip(), value.strip())


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
    account_mode: str = "demo"
    gate_mode: str = "per_rule"
    rule_qualification_csv: str = ""
    probation_trades: int = DEFAULT_PROBATION_TRADES
    track_floor_win_rate: float = DEFAULT_TRACK_FLOOR_WIN_RATE
    track_floor_min_trades: int = DEFAULT_TRACK_FLOOR_MIN_TRADES


@dataclass(frozen=True)
class RuleQualification:
    track_name: str
    rule: str
    closed_trades: int
    wins: int
    win_rate: float
    allowed: bool
    status: str
    reason: str


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

    gate_mode = str(raw.get("gate_mode") or "per_rule").strip().lower()
    if gate_mode not in GATE_MODES:
        raise ValueError(f"gate_mode must be one of {GATE_MODES}, got {gate_mode!r}")

    return DerivDirectConfig(
        app_id=str(os.environ.get("DERIV_APP_ID") or raw.get("app_id") or ""),
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
        account_mode=str(raw.get("account_mode") or "demo").strip().lower(),
        gate_mode=gate_mode,
        rule_qualification_csv=resolve_repo_path(repo_root, str(raw.get("rule_qualification_csv", "outputs/deriv_direct_rule_qualification.csv"))),
        probation_trades=max(safe_int(raw.get("probation_trades"), DEFAULT_PROBATION_TRADES), 0),
        track_floor_win_rate=min(max(safe_float(raw.get("track_floor_win_rate"), DEFAULT_TRACK_FLOOR_WIN_RATE), 0.0), 1.0),
        track_floor_min_trades=max(safe_int(raw.get("track_floor_min_trades"), DEFAULT_TRACK_FLOOR_MIN_TRADES), 1),
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


def scan_track_signals(
    track: TrackConfig, config: DerivDirectConfig, now: datetime
) -> tuple[list[tuple[datetime, CandidateSignal]], list[tuple[CandidateSignal, str]]]:
    """Return (eligible, skipped) for the fresh actionable rows of one track.

    Skipped signals carry the reason, so a signal the executor passes on is never silent.
    Rows that are not actionable (no trade, hold) or already too old are history, not skips.
    """
    eligible: list[tuple[datetime, CandidateSignal]] = []
    skipped: list[tuple[CandidateSignal, str]] = []
    for row in read_rows(Path(track.decisions_csv)):
        decision = (row.get("decision") or "").strip()
        side = (row.get("side") or "").strip().lower()
        symbol = (row.get("symbol") or "").strip()
        if decision not in DECISION_ORDER or side not in {"buy", "sell"}:
            continue
        signal_time = parse_time(row.get("timestamp") or "")
        if signal_time is None:
            continue
        age_minutes = max((now - signal_time).total_seconds() / 60.0, 0.0)
        if config.max_signal_age_minutes > 0 and age_minutes > config.max_signal_age_minutes:
            continue
        signal = signal_from_row(row, track.name, signal_time)
        if config.allowed_symbols and symbol not in config.allowed_symbols:
            skipped.append((signal, f"symbol {symbol} not in allowed_symbols"))
            continue
        if signal.confidence < config.min_confidence:
            skipped.append((signal, f"confidence {signal.confidence:.4f} < min_confidence {config.min_confidence:.2f}"))
            continue
        if signal.entry <= 0 or signal.stop_loss <= 0 or signal.take_profit <= 0 or abs(signal.entry - signal.stop_loss) <= 0 or abs(signal.take_profit - signal.entry) <= 0:
            skipped.append((signal, "invalid entry/stop-loss/take-profit levels"))
            continue
        eligible.append((signal_time, signal))
    return eligible, skipped


def latest_track_signal(track: TrackConfig, config: DerivDirectConfig) -> tuple[datetime, CandidateSignal] | None:
    eligible, _skipped = scan_track_signals(track, config, datetime.now(timezone.utc))
    if not eligible:
        return None
    return sorted(eligible, key=lambda item: item[0], reverse=True)[0]


def rule_id_from_reason(reason: str) -> str:
    """Pull the rule id (for example PAIR017) out of a paper reason text."""
    text = reason or ""
    for pattern in (r"\brule\s+([A-Za-z0-9_\-]+)", r"(PAIR\d+)"):
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return "unknown"


def rule_stats(track: TrackConfig) -> dict[str, tuple[int, int]]:
    """Closed paper trades and wins for each rule of one track."""
    stats: dict[str, list[int]] = {}
    for row in read_rows(Path(track.closed_trades_csv)):
        if (row.get("status") or "").strip().lower() != "closed":
            continue
        entry = stats.setdefault(rule_id_from_reason(row.get("reason", "")), [0, 0])
        entry[0] += 1
        if safe_float(row.get("paper_pnl")) > 0:
            entry[1] += 1
    return {rule: (counts[0], counts[1]) for rule, counts in stats.items()}


def rule_gate(config: DerivDirectConfig, track_q: TrackQualification, closed: int, wins: int) -> tuple[bool, str, str]:
    """Decide whether one rule may trade. Returns (allowed, status, reason).

    Real mode keeps the hard evidence bar. Demo mode uses probation so unproven rules can
    gather evidence with $1 stakes, but a rule or track that has proven bad stays blocked.
    """
    win_rate = wins / closed if closed else 0.0
    if config.account_mode == "real":
        if closed < HARD_MIN_CLOSED_TRADES:
            return False, "blocked", f"rule closed_trades {closed} < {HARD_MIN_CLOSED_TRADES}"
        if win_rate < HARD_MIN_WIN_RATE:
            return False, "blocked", f"rule win_rate {win_rate:.2%} < {HARD_MIN_WIN_RATE:.2%}"
        return True, "proven", f"{wins}/{closed} = {win_rate:.0%}"
    if track_q.closed_trades >= config.track_floor_min_trades and track_q.win_rate < config.track_floor_win_rate:
        return False, "blocked", (
            f"track win_rate {track_q.win_rate:.2%} < floor {config.track_floor_win_rate:.0%} over {track_q.closed_trades} trades"
        )
    if closed < config.probation_trades:
        return True, "probation", f"probation: {closed} < {config.probation_trades} closed trades, collecting demo evidence"
    if win_rate >= HARD_MIN_WIN_RATE:
        return True, "proven", f"{wins}/{closed} = {win_rate:.0%}"
    return False, "blocked", f"rule win_rate {win_rate:.2%} < {HARD_MIN_WIN_RATE:.2%} over {closed} trades"


def signal_key(signal: CandidateSignal) -> str:
    """Same market entry seen by several tracks shares one key."""
    return f"{signal.symbol}|{signal.side}|{signal.timestamp}"


def traded_keys(config: DerivDirectConfig) -> set[str]:
    keys: set[str] = set()
    for row in read_rows(Path(config.journal_csv)):
        if row.get("status") != "bought":
            continue
        if row.get("signal_id"):
            keys.add(row["signal_id"])
        message = row.get("message", "")
        if "|" in message:
            keys.add(message.split(" ", 1)[1] if " " in message else message)
    return keys


def select_signal_detailed(
    config: DerivDirectConfig,
) -> tuple[CandidateSignal | None, list[TrackQualification], list[tuple[CandidateSignal, str]], list[RuleQualification]]:
    qualifications = [qualify_track(track) for track in config.tracks]
    now = datetime.now(timezone.utc)
    done = traded_keys(config)
    candidates: list[tuple[datetime, CandidateSignal]] = []
    skips: list[tuple[CandidateSignal, str]] = []
    rule_rows: list[RuleQualification] = []
    for track, qualification in zip(config.tracks, qualifications):
        eligible, track_skips = scan_track_signals(track, config, now)
        skips.extend(track_skips)
        passing: list[tuple[datetime, CandidateSignal]] = []
        if config.gate_mode == "per_track":
            if qualification.qualified:
                passing = eligible
            else:
                skips.extend((signal, f"track not qualified: {qualification.reason}") for _time, signal in eligible)
        else:
            stats = rule_stats(track)
            for signal_time, signal in eligible:
                rule = rule_id_from_reason(signal.reason)
                closed, wins = stats.get(rule, (0, 0))
                allowed, status, reason = rule_gate(config, qualification, closed, wins)
                rule_rows.append(
                    RuleQualification(track.name, rule, closed, wins, wins / closed if closed else 0.0, allowed, status, reason)
                )
                if allowed:
                    passing.append((signal_time, signal))
                else:
                    skips.append((signal, f"rule gate {rule}: {reason}"))
        if not passing:
            continue
        newest = sorted(passing, key=lambda item: item[0], reverse=True)[0]
        if {newest[1].signal_id, signal_key(newest[1])} & done:
            continue
        candidates.append(newest)
    selected = sorted(candidates, key=lambda item: item[0], reverse=True)[0][1] if candidates else None
    return selected, qualifications, skips, rule_rows


def select_signal(config: DerivDirectConfig) -> tuple[CandidateSignal | None, list[TrackQualification]]:
    selected, qualifications, _skips, _rules = select_signal_detailed(config)
    return selected, qualifications


def log_skips(config: DerivDirectConfig, skips: list[tuple[CandidateSignal, str]], selected: CandidateSignal | None) -> int:
    """Write each skipped signal to the journal once (same signal and reason is never repeated)."""
    seen = {
        (row.get("signal_id", ""), row.get("message", ""))
        for row in read_rows(Path(config.journal_csv))
        if row.get("status") == "skipped"
    }
    written = 0
    for signal, reason in skips:
        message = f"skipped: {reason}"
        if (signal.signal_id, message) in seen:
            continue
        seen.add((signal.signal_id, message))
        write_journal_row(
            Path(config.journal_csv),
            {
                "timestamp": utc_now(),
                "mode": config.account_mode,
                "status": "skipped",
                "track_name": signal.track_name,
                "symbol": signal.symbol,
                "side": signal.side,
                "currency": config.currency,
                "signal_id": signal.signal_id,
                "message": message,
            },
        )
        written += 1
    return written


def write_rule_rows(config: DerivDirectConfig, rows: list[RuleQualification]) -> None:
    if not rows:
        return
    path = Path(config.rule_qualification_csv or Path(config.qualification_csv).with_name("deriv_direct_rule_qualification.csv"))
    run_timestamp = utc_now()
    seen: set[tuple[str, str]] = set()
    for row in rows:
        if (row.track_name, row.rule) in seen:
            continue
        seen.add((row.track_name, row.rule))
        append_csv_row(
            path,
            ["timestamp", "track_name", "rule", "closed_trades", "wins", "win_rate", "allowed", "status", "reason"],
            {
                "timestamp": run_timestamp,
                "track_name": row.track_name,
                "rule": row.rule,
                "closed_trades": row.closed_trades,
                "wins": row.wins,
                "win_rate": round(row.win_rate, 6),
                "allowed": row.allowed,
                "status": row.status,
                "reason": row.reason,
            },
        )


def contract_type_for(signal: CandidateSignal) -> str:
    return "MULTUP" if signal.side == "buy" else "MULTDOWN"


def risk_reward_ratio(signal: CandidateSignal) -> float:
    risk_distance = abs(signal.entry - signal.stop_loss)
    reward_distance = abs(signal.take_profit - signal.entry)
    if risk_distance <= 0 or reward_distance <= 0:
        raise RuntimeError("Signal stop_loss/take_profit cannot produce a risk/reward ratio.")
    return reward_distance / risk_distance


def limit_amounts(signal: CandidateSignal, stake: float, multiplier: int) -> tuple[float, float]:
    """Dollar stop-loss / take-profit that reproduce the signal's price levels.

    A multiplier contract gains or loses stake * multiplier * (price change / entry price).
    The stop must stay under the stop-out Deriv adds at 90% of stake.
    """
    if signal.entry <= 0:
        raise RuntimeError("Signal has no valid entry price.")
    stop = round(stake * multiplier * abs(signal.entry - signal.stop_loss) / signal.entry, 2)
    take = round(stake * multiplier * abs(signal.take_profit - signal.entry) / signal.entry, 2)
    ceiling = round(stake * MAX_STOP_LOSS_FRACTION_OF_STAKE, 2)
    if stop > ceiling:
        raise RuntimeError(f"stop too wide for x{multiplier}: would risk ${stop} on a ${stake} stake (limit ${ceiling})")
    if stop <= 0 or take <= 0:
        raise RuntimeError(f"stop or target too close to entry for x{multiplier}")
    return stop, take


def plan_order(signal: CandidateSignal, config: DerivDirectConfig) -> PlannedOrder:
    ratio = risk_reward_ratio(signal)
    stake = min(config.stake, config.max_stake) if config.max_stake > 0 else config.stake
    # Indicative dollar limits at the lowest multiplier; the real ones are set per multiplier.
    try:
        stop_loss_amount, take_profit_amount = limit_amounts(signal, stake, MULTIPLIER_CANDIDATES[0])
    except RuntimeError:
        stop_loss_amount, take_profit_amount = 0.0, 0.0
    return PlannedOrder(
        signal=signal,
        contract_type=contract_type_for(signal),
        stake=stake,
        stop_loss_amount=stop_loss_amount,
        take_profit_amount=take_profit_amount,
        risk_reward_ratio=ratio,
        multiplier_candidates=MULTIPLIER_CANDIDATES,
    )


def proposal_payload(plan: PlannedOrder, config: DerivDirectConfig, multiplier: int) -> dict[str, Any]:
    stop_loss, take_profit = limit_amounts(plan.signal, plan.stake, multiplier)
    return {
        "proposal": 1,
        "amount": plan.stake,
        "basis": config.basis,
        "contract_type": plan.contract_type,
        "currency": config.currency,
        "underlying_symbol": plan.signal.symbol,
        "multiplier": multiplier,
        "limit_order": {
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        },
    }


def notify(text: str) -> bool:
    """Telegram message to the owner. Never raises; returns whether it was sent."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return False
    try:
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text[:3900]}).encode()
        urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data), timeout=20).read()
        return True
    except Exception:  # noqa: BLE001 - an alert problem must never stop trading logic
        return False


def open_positions_path(config: DerivDirectConfig) -> Path:
    return Path(config.journal_csv).with_name("deriv_direct_open_positions.json")


def load_open_positions(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def save_open_positions(path: Path, positions: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(positions, indent=2), encoding="utf-8")
    temp.replace(path)


def record_open_position(config: DerivDirectConfig, plan: PlannedOrder, result: dict[str, Any]) -> None:
    buy = result.get("buy", {})
    if not buy.get("contract_id"):
        return
    signal = plan.signal
    limits = result.get("proposal_payload", {}).get("limit_order", {})
    positions = load_open_positions(open_positions_path(config))
    positions.append(
        {
            "contract_id": buy["contract_id"],
            "opened_at": utc_now(),
            "mode": config.account_mode,
            "track_name": signal.track_name,
            "signal_id": signal.signal_id,
            "symbol": signal.symbol,
            "timeframe": signal.timeframe,
            "side": signal.side,
            "entry": signal.entry,
            "stop_loss": signal.stop_loss,
            "take_profit": signal.take_profit,
            "stake": plan.stake,
            "multiplier": result.get("multiplier"),
            "stop_loss_amount": limits.get("stop_loss"),
            "take_profit_amount": limits.get("take_profit"),
            "buy_price": buy.get("buy_price"),
            "max_bars": MAX_HOLD_BARS,
        }
    )
    save_open_positions(open_positions_path(config), positions)


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


def validate_live_arming(config: DerivDirectConfig, pat: str, dry_run: bool) -> None:
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute one Deriv-direct Multiplier order from the freshest qualified NetzaraBot signal.")
    parser.add_argument("--config", default="live_candidate/config/deriv_direct_live_config.json")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--dry-run", action="store_true", help="Request a real Deriv price quote, but do not buy.")
    parser.add_argument("--plan-only", action="store_true", help="Print track qualification, selected signal, and proposal payload without network.")
    return parser.parse_args()


def example_payload(plan: PlannedOrder, config: DerivDirectConfig) -> dict[str, Any]:
    try:
        return proposal_payload(plan, config, plan.multiplier_candidates[0])
    except RuntimeError as exc:
        return {"not_tradeable_at_lowest_multiplier": str(exc)}


def response_payload(status: str, config: DerivDirectConfig, qualifications: list[TrackQualification], selected: CandidateSignal | None, plan: PlannedOrder | None, result: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": True,
        "status": status,
        "hard_limits": {
            "min_win_rate": HARD_MIN_WIN_RATE,
            "min_closed_trades": HARD_MIN_CLOSED_TRADES,
        },
        "gate": {
            "mode": config.gate_mode,
            "probation_trades": config.probation_trades,
            "min_confidence": config.min_confidence,
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
            "example_proposal_payload": example_payload(plan, config),
        }
    if result is not None:
        payload["result"] = result
    return payload


def main() -> int:
    args = parse_args()
    load_env_file()
    repo_root = Path(args.repo_root).resolve()
    config = load_config(repo_root / args.config, repo_root)
    token = (os.environ.get("DERIV_PAT") or os.environ.get("DERIV_API_TOKEN") or "").strip()
    try:
        if not args.plan_only:
            validate_live_arming(config, token, args.dry_run)
        selected, qualifications, skips, rule_rows = select_signal_detailed(config)
        write_qualification_rows(Path(config.qualification_csv), qualifications, selected)
        write_rule_rows(config, rule_rows)
        if not args.plan_only:
            log_skips(config, skips, selected)
        if selected is None:
            print(json.dumps(response_payload("no_fresh_qualified_signal", config, qualifications, None, None), indent=2))
            return 0
        plan = plan_order(selected, config)
        if args.plan_only:
            print(json.dumps(response_payload("plan_only", config, qualifications, selected, plan), indent=2))
            return 0
        trader = DerivDirectTrader(config, token, os.environ.get("DERIV_APP_ID", ""))
        result = asyncio.run(trader.execute(plan, dry_run=args.dry_run))
        proposal = result.get("proposal", {})
        buy = result.get("buy", {})
        balance = result.get("balance", {})
        status = "dry_run_proposal_ok" if args.dry_run else "bought"
        limits = result.get("proposal_payload", {}).get("limit_order", {})
        if status == "bought":
            record_open_position(config, plan, result)
            notify(
                f"[{config.account_mode.upper()}] Trade opened: {selected.symbol} {selected.side} x{result.get('multiplier')}, "
                f"stake ${plan.stake:g}, stop-loss ${limits.get('stop_loss')}, take-profit ${limits.get('take_profit')}\n"
                f"Track: {selected.track_name}"
            )
        write_journal_row(
            Path(config.journal_csv),
            {
                "timestamp": utc_now(),
                "mode": "dry_run" if args.dry_run else config.account_mode,
                "status": status,
                "track_name": selected.track_name,
                "symbol": selected.symbol,
                "side": selected.side,
                "contract_type": plan.contract_type,
                "stake": plan.stake,
                "multiplier": result.get("multiplier", ""),
                "stop_loss_amount": limits.get("stop_loss", ""),
                "take_profit_amount": limits.get("take_profit", ""),
                "risk_reward_ratio": round(plan.risk_reward_ratio, 6),
                "currency": config.currency,
                "signal_id": selected.signal_id,
                "proposal_id": proposal.get("id", ""),
                "contract_id": buy.get("contract_id", ""),
                "buy_price": buy.get("buy_price", ""),
                "balance_after": balance.get("balance", ""),
                "message": f"{status} {signal_key(selected)}" if status == "bought" else status,
            },
        )
        print(json.dumps(response_payload(status, config, qualifications, selected, plan, result), indent=2))
        return 0
    except Exception as exc:
        write_journal_row(
            Path(config.journal_csv),
            {
                "timestamp": utc_now(),
                "mode": "dry_run" if args.dry_run else config.account_mode,
                "status": "error",
                "message": str(exc),
            },
        )
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
