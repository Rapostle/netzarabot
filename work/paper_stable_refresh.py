from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


BOT_ROOT = Path("/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/external/trading_bot")
TASK_ROOT = Path("/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot")
DEFAULT_RULES = TASK_ROOT / "outputs/crash_boom_execution_approved_stable_rules_15m_30m.csv"
DEFAULT_OUTPUT = TASK_ROOT / "outputs/paper_stable_rules_decisions.csv"
DEFAULT_JOURNAL = TASK_ROOT / "outputs/paper_stable_rules_journal.csv"
DEFAULT_JOURNAL_SUMMARY = TASK_ROOT / "outputs/paper_stable_rules_journal_summary.csv"
DEFAULT_OPEN_POSITIONS = TASK_ROOT / "outputs/paper_stable_open_positions.csv"
DEFAULT_CLOSED_TRADES = TASK_ROOT / "outputs/paper_stable_closed_trades.csv"
DEFAULT_POSITION_SUMMARY = TASK_ROOT / "outputs/paper_stable_position_summary.csv"
DEFAULT_STATUS = TASK_ROOT / "outputs/paper_stable_status.csv"
DEFAULT_DASHBOARD = TASK_ROOT / "outputs/paper_stable_dashboard.md"
DEFAULT_READINESS = TASK_ROOT / "outputs/paper_stable_go_live_readiness.md"
DEFAULT_BLOCKED_RULES = TASK_ROOT / "outputs/rule_kill_switch_blocklist.csv"
DEFAULT_DATA_DIR = TASK_ROOT / "outputs/paper_refreshed_data"
OPEN_POSITION_COLUMNS = [
    "paper_order_id",
    "symbol",
    "timeframe",
    "opened_at",
    "recorded_at_utc",
    "side",
    "entry",
    "stop_loss",
    "take_profit",
    "quantity",
    "risk_amount",
    "reason",
    "status",
]


def parse_timeframe_label(value: str) -> int:
    normalized = value.strip().lower()
    if normalized.isdigit():
        return int(normalized)
    if normalized.endswith("m") and normalized[:-1].isdigit():
        return int(normalized[:-1]) * 60
    if normalized.endswith("h") and normalized[:-1].isdigit():
        return int(normalized[:-1]) * 3600
    raise ValueError(f"Unsupported timeframe: {value}")


def granularity_label(seconds: int) -> str:
    if seconds % 3600 == 0:
        return f"{seconds // 3600}h"
    if seconds % 60 == 0:
        return f"{seconds // 60}m"
    return f"{seconds}s"


def safe_symbol_filename(symbol: str) -> str:
    return "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in symbol)


def data_path(data_dir: Path, symbol: str, timeframe: str) -> Path:
    return data_dir / f"deriv_{safe_symbol_filename(symbol)}_{timeframe}.csv"


def refresh_data(rules: pd.DataFrame, data_dir: Path, count: int, app_id: int, skip_download: bool) -> pd.DataFrame:
    sys.path.insert(0, str(BOT_ROOT))
    from trading_bot.data.deriv_downloader import DerivDataDownloader, DerivDownloadRequest

    data_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    downloader = DerivDataDownloader(app_id)
    pairs = rules[["symbol", "timeframe"]].drop_duplicates().sort_values(["symbol", "timeframe"])

    for _, pair in pairs.iterrows():
        symbol = str(pair["symbol"])
        timeframe = str(pair["timeframe"])
        output = data_path(data_dir, symbol, timeframe)
        task_fallback = data_path(DEFAULT_DATA_DIR, symbol, timeframe)
        bot_fallback = data_path(BOT_ROOT / "data", symbol, timeframe)
        fallback_paths = [path for path in (task_fallback, bot_fallback) if path != output]
        status = "skipped"
        candles = 0
        error = ""

        if not skip_download:
            try:
                df = downloader.download(
                    DerivDownloadRequest(
                        symbol=symbol,
                        granularity=parse_timeframe_label(timeframe),
                        output=output,
                        count=count,
                        app_id=app_id,
                    )
                )
                status = "refreshed"
                candles = len(df)
            except Exception as exc:  # noqa: BLE001 - fall back to local data for paper decisions.
                status = "refresh_failed"
                error = str(exc)

        if status != "refreshed":
            copied = False
            for source_fallback in fallback_paths:
                if source_fallback.exists():
                    shutil.copy2(source_fallback, output)
                    candles = max(sum(1 for _ in output.open("r", encoding="utf-8")) - 1, 0)
                    status = "fallback_local" if status == "refresh_failed" else "local_copy"
                    copied = True
                    break
            if not copied and output.exists():
                candles = max(sum(1 for _ in output.open("r", encoding="utf-8")) - 1, 0)
                status = "existing_local"

        rows.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "output": str(output),
                "status": status,
                "candles": candles,
                "error": error,
            }
        )

    return pd.DataFrame(rows)


def run_paper_mode(data_dir: Path, rules_csv: Path, output: Path) -> int:
    data_dir = data_dir.resolve()
    rules_csv = rules_csv.resolve()
    output = output.resolve()
    cmd = [
        str(BOT_ROOT / ".venv/bin/python"),
        "-m",
        "trading_bot.cli.main",
        "--config",
        str(BOT_ROOT / "config.deriv_stable_execution.yaml"),
        "--mode",
        "paper-stable-rules",
        "--rules-csv",
        str(rules_csv),
        "--data-dir",
        str(data_dir),
        "--max-rows",
        "1500",
        "--audit-output",
        str(output),
    ]
    return subprocess.call(cmd, cwd=BOT_ROOT)


def load_csv_or_empty(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def load_open_positions(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=OPEN_POSITION_COLUMNS)
    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=OPEN_POSITION_COLUMNS)
    if set(OPEN_POSITION_COLUMNS).issubset(df.columns):
        return df
    raw = pd.read_csv(path, header=None)
    raw = raw.dropna(how="all")
    if raw.empty:
        return pd.DataFrame(columns=OPEN_POSITION_COLUMNS)
    raw = raw.iloc[:, : len(OPEN_POSITION_COLUMNS)]
    raw.columns = OPEN_POSITION_COLUMNS[: len(raw.columns)]
    for column in OPEN_POSITION_COLUMNS:
        if column not in raw.columns:
            raw[column] = ""
    return raw[OPEN_POSITION_COLUMNS]


def write_open_positions(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=OPEN_POSITION_COLUMNS).to_csv(path, index=False)


def load_candles(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if df.empty or "timestamp" not in df.columns:
        return pd.DataFrame()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df.sort_values("timestamp")


def close_position(position: pd.Series, exit_price: float, exit_reason: str, closed_at, slippage_bps: float = 0.0) -> dict:
    side = str(position["side"])
    entry = float(position["entry"])
    quantity = float(position["quantity"])
    slippage = max(slippage_bps, 0.0) / 10000.0
    adjusted_exit = exit_price
    if slippage:
        adjusted_exit = exit_price * (1.0 - slippage) if side == "buy" else exit_price * (1.0 + slippage)
    gross = (adjusted_exit - entry) * quantity
    if side == "sell":
        gross *= -1
    closed = position.to_dict()
    closed.update(
        {
            "closed_at": closed_at,
            "exit_price": adjusted_exit,
            "paper_pnl": gross,
            "exit_reason": exit_reason,
            "status": "closed",
        }
    )
    return closed


def update_open_positions(
    open_path: Path,
    closed_path: Path,
    data_dir: Path,
    max_bars: int = 12,
    slippage_bps: float = 0.0,
    emergency_stop: bool = True,
    profit_lock_r: float = 2.0,
) -> tuple[int, int]:
    open_positions = load_open_positions(open_path)
    if open_positions.empty:
        write_open_positions(open_path, [])
        return 0, 0

    still_open = []
    closed_rows = []
    for _, position in open_positions.iterrows():
        symbol = str(position["symbol"])
        timeframe = str(position["timeframe"])
        candles = load_candles(data_path(data_dir, symbol, timeframe))
        if candles.empty:
            still_open.append(position.to_dict())
            continue

        opened_at = pd.to_datetime(position["opened_at"], utc=True)
        future = candles[candles["timestamp"] > opened_at].head(max_bars)
        if future.empty:
            still_open.append(position.to_dict())
            continue

        side = str(position["side"])
        entry = float(position["entry"])
        stop_loss = float(position["stop_loss"])
        take_profit = float(position["take_profit"])
        quantity = float(position["quantity"])
        risk_per_unit = abs(entry - stop_loss)
        exit_price = None
        exit_reason = ""
        closed_at = None

        for _, candle in future.iterrows():
            if side == "buy":
                if float(candle["low"]) <= stop_loss:
                    exit_price = stop_loss
                    exit_reason = "paper stop loss"
                elif float(candle["high"]) >= take_profit:
                    exit_price = take_profit
                    exit_reason = "paper take profit"
            elif side == "sell":
                if float(candle["high"]) >= stop_loss:
                    exit_price = stop_loss
                    exit_reason = "paper stop loss"
                elif float(candle["low"]) <= take_profit:
                    exit_price = take_profit
                    exit_reason = "paper take profit"
            if (
                exit_price is None
                and profit_lock_r > 0
                and risk_per_unit > 0
            ):
                close_price = float(candle["close"])
                if side == "buy" and (close_price - entry) / risk_per_unit >= profit_lock_r:
                    exit_price = close_price
                    exit_reason = f"paper profit lock {profit_lock_r:g}R"
                elif side == "sell" and (entry - close_price) / risk_per_unit >= profit_lock_r:
                    exit_price = close_price
                    exit_reason = f"paper profit lock {profit_lock_r:g}R"
            if exit_price is not None:
                closed_at = candle["timestamp"]
                break

        if exit_price is None and len(future) >= max_bars:
            last = future.iloc[-1]
            exit_price = float(last["close"])
            exit_reason = "paper time exit"
            closed_at = last["timestamp"]

        if exit_price is None:
            still_open.append(position.to_dict())
            continue

        closed_rows.append(close_position(position, exit_price, exit_reason, closed_at, slippage_bps=slippage_bps))

    if emergency_stop and still_open:
        rechecked = []
        for position_dict in still_open:
            position = pd.Series(position_dict)
            symbol = str(position["symbol"])
            timeframe = str(position["timeframe"])
            candles = load_candles(data_path(data_dir, symbol, timeframe))
            if candles.empty:
                rechecked.append(position_dict)
                continue
            opened_at = pd.to_datetime(position["opened_at"], utc=True, errors="coerce")
            latest = candles.tail(1).iloc[0]
            if pd.notna(opened_at) and pd.to_datetime(latest["timestamp"], utc=True) < opened_at:
                rechecked.append(position_dict)
                continue
            side = str(position["side"])
            entry = float(position["entry"])
            stop_loss = float(position["stop_loss"])
            take_profit = float(position["take_profit"])
            risk_per_unit = abs(entry - stop_loss)
            exit_price = None
            exit_reason = ""
            if side == "buy":
                if float(latest["low"]) <= stop_loss or float(latest["close"]) <= stop_loss:
                    exit_price = stop_loss
                    exit_reason = "paper emergency stop"
                elif float(latest["high"]) >= take_profit or float(latest["close"]) >= take_profit:
                    exit_price = take_profit
                    exit_reason = "paper emergency take profit"
                elif (
                    profit_lock_r > 0
                    and risk_per_unit > 0
                    and (float(latest["close"]) - entry) / risk_per_unit >= profit_lock_r
                ):
                    exit_price = float(latest["close"])
                    exit_reason = f"paper emergency profit lock {profit_lock_r:g}R"
            elif side == "sell":
                if float(latest["high"]) >= stop_loss or float(latest["close"]) >= stop_loss:
                    exit_price = stop_loss
                    exit_reason = "paper emergency stop"
                elif float(latest["low"]) <= take_profit or float(latest["close"]) <= take_profit:
                    exit_price = take_profit
                    exit_reason = "paper emergency take profit"
                elif (
                    profit_lock_r > 0
                    and risk_per_unit > 0
                    and (entry - float(latest["close"])) / risk_per_unit >= profit_lock_r
                ):
                    exit_price = float(latest["close"])
                    exit_reason = f"paper emergency profit lock {profit_lock_r:g}R"
            if exit_price is None:
                rechecked.append(position_dict)
            else:
                closed_rows.append(
                    close_position(position, exit_price, exit_reason, latest["timestamp"], slippage_bps=slippage_bps)
                )
        still_open = rechecked

    write_open_positions(open_path, still_open)
    if closed_rows:
        closed_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(closed_rows).to_csv(closed_path, mode="a", index=False, header=not closed_path.exists())
    return len(closed_rows), len(still_open)


def extract_rule_id(reason: object) -> str:
    match = re.search(r"\b(SR\d+|PAIR\d+|BCX\d+)\b", str(reason))
    return match.group(1) if match else "unknown_rule"


def symbol_family(symbol: object) -> str:
    text = str(symbol).upper()
    if text.startswith("BOOM"):
        return "BOOM"
    if text.startswith("CRASH"):
        return "CRASH"
    if text.startswith("R_") or text.startswith("1HZ"):
        return "VOLATILITY"
    if any(token in text for token in ["BTC", "ETH", "LTC", "XRP"]):
        return "CRYPTO"
    return "OTHER"


def block_decision(decisions: pd.DataFrame, mask: pd.Series, label: str) -> int:
    if not mask.any():
        return 0
    count = int(mask.sum())
    decisions.loc[mask, "decision"] = "blocked_guard"
    if "reason" not in decisions.columns:
        decisions["reason"] = ""
    decisions.loc[mask, "reason"] = decisions.loc[mask, "reason"].astype(str) + f" | blocked by guard: {label}"
    return count


def latest_candle_age_minutes(data_dir: Path, symbol: str, timeframe: str) -> float | None:
    candles = load_candles(data_path(data_dir, symbol, timeframe))
    if candles.empty:
        return None
    latest = candles.iloc[-1]["timestamp"]
    return max((datetime.now(timezone.utc) - latest.to_pydatetime()).total_seconds() / 60.0, 0.0)


def apply_entry_guards(
    decisions_path: Path,
    open_path: Path,
    closed_path: Path,
    data_dir: Path,
    max_open_positions: int,
    max_family_side_open: int,
    cooldown_losses: int,
    stale_candle_minutes: float,
    stale_signal_minutes: float,
) -> int:
    decisions = load_csv_or_empty(decisions_path)
    if decisions.empty or "decision" not in decisions.columns:
        return 0
    open_positions = load_open_positions(open_path)
    closed = load_csv_or_empty(closed_path)
    decisions = decisions.copy()
    blocked = 0

    order_mask = decisions["decision"] == "paper_order"
    if not order_mask.any():
        return 0

    if not open_positions.empty:
        existing_symbol_tf = set(zip(open_positions["symbol"].astype(str), open_positions["timeframe"].astype(str)))
        duplicate_mask = decisions.apply(
            lambda row: row.get("decision") == "paper_order"
            and (str(row.get("symbol", "")), str(row.get("timeframe", ""))) in existing_symbol_tf,
            axis=1,
        )
        blocked += block_decision(decisions, duplicate_mask, "duplicate symbol/timeframe already open")

    open_count = 0 if open_positions.empty else len(open_positions)
    available_slots = max(max_open_positions - open_count, 0)
    active_orders = decisions[decisions["decision"] == "paper_order"].index.tolist()
    if len(active_orders) > available_slots:
        blocked += block_decision(decisions, decisions.index.isin(active_orders[available_slots:]), "max open paper trades reached")

    if not open_positions.empty and max_family_side_open > 0:
        exposure_counts: dict[tuple[str, str], int] = {}
        for _, position in open_positions.iterrows():
            key = (symbol_family(position.get("symbol", "")), str(position.get("side", "")))
            exposure_counts[key] = exposure_counts.get(key, 0) + 1
        for index, row in decisions[decisions["decision"] == "paper_order"].iterrows():
            key = (symbol_family(row.get("symbol", "")), str(row.get("side", "")))
            if exposure_counts.get(key, 0) >= max_family_side_open:
                blocked += block_decision(decisions, decisions.index == index, "instrument family exposure limit")
            else:
                exposure_counts[key] = exposure_counts.get(key, 0) + 1

    if cooldown_losses > 0 and not closed.empty and "paper_pnl" in closed.columns:
        closed = closed.copy()
        closed["rule_id"] = closed["reason"].map(extract_rule_id) if "reason" in closed else "unknown_rule"
        closed["pnl_num"] = pd.to_numeric(closed["paper_pnl"], errors="coerce").fillna(0.0)
        cooled_rules = set()
        for rule_id, group in closed.groupby("rule_id"):
            tail = group.tail(cooldown_losses)
            if not tail.empty and (tail["pnl_num"] < 0).any():
                cooled_rules.add(rule_id)
        if cooled_rules:
            cooldown_mask = decisions.apply(
                lambda row: row.get("decision") == "paper_order" and extract_rule_id(row.get("reason", "")) in cooled_rules,
                axis=1,
            )
            blocked += block_decision(decisions, cooldown_mask, "rule cooldown after recent loss")

    if stale_candle_minutes > 0:
        for index, row in decisions[decisions["decision"] == "paper_order"].iterrows():
            age = latest_candle_age_minutes(data_dir, str(row.get("symbol", "")), str(row.get("timeframe", "")))
            if age is None or age > stale_candle_minutes:
                label = "missing fresh candle" if age is None else f"stale candle {age:.1f}m old"
                blocked += block_decision(decisions, decisions.index == index, label)

    if stale_signal_minutes > 0 and "timestamp" in decisions.columns:
        now = datetime.now(timezone.utc)
        for index, row in decisions[decisions["decision"] == "paper_order"].iterrows():
            signal_time = pd.to_datetime(row.get("timestamp", ""), utc=True, errors="coerce")
            if pd.isna(signal_time):
                blocked += block_decision(decisions, decisions.index == index, "missing signal timestamp")
                continue
            age = max((now - signal_time.to_pydatetime()).total_seconds() / 60.0, 0.0)
            if age > stale_signal_minutes:
                blocked += block_decision(decisions, decisions.index == index, f"stale signal {age:.1f}m old")

    if blocked:
        decisions.to_csv(decisions_path, index=False)
    return blocked


def append_new_paper_positions(decisions_path: Path, open_path: Path) -> int:
    decisions = load_csv_or_empty(decisions_path)
    if decisions.empty or "decision" not in decisions.columns:
        return 0
    orders = decisions[decisions["decision"] == "paper_order"].copy()
    if orders.empty:
        return 0

    open_positions = load_open_positions(open_path)
    existing_keys = set()
    if not open_positions.empty:
        existing_keys = set(zip(open_positions["symbol"], open_positions["timeframe"], open_positions["status"]))

    rows = []
    now = datetime.now(timezone.utc).isoformat()
    next_id = len(open_positions) + 1
    for _, order in orders.iterrows():
        key = (order["symbol"], order["timeframe"], "open")
        if key in existing_keys:
            continue
        rows.append(
            {
                "paper_order_id": f"paper-{next_id}",
                "symbol": order["symbol"],
                "timeframe": order["timeframe"],
                "opened_at": order["timestamp"],
                "recorded_at_utc": now,
                "side": order["side"],
                "entry": order["entry"],
                "stop_loss": order["stop_loss"],
                "take_profit": order["take_profit"],
                "quantity": order["quantity"],
                "risk_amount": order["risk_amount"],
                "reason": order["reason"],
                "status": "open",
            }
        )
        next_id += 1
    if not rows:
        return 0
    combined = pd.concat([open_positions, pd.DataFrame(rows, columns=OPEN_POSITION_COLUMNS)], ignore_index=True)
    write_open_positions(open_path, combined.to_dict("records"))
    return len(rows)


def apply_rule_blocklist(decisions_path: Path, blocklist_path: Path, track_name: str) -> int:
    decisions = load_csv_or_empty(decisions_path)
    blocklist = load_csv_or_empty(blocklist_path)
    if decisions.empty or blocklist.empty or "decision" not in decisions.columns:
        return 0
    required = {"track", "rule", "action"}
    if not required.issubset(blocklist.columns):
        return 0

    blocked = blocklist[
        (blocklist["track"].astype(str) == str(track_name))
        & (blocklist["action"].astype(str).isin(["KILL NOW", "FREEZE"]))
    ].copy()
    if blocked.empty:
        return 0

    blocked_count = 0
    decisions = decisions.copy()
    if "reason" not in decisions.columns:
        decisions["reason"] = ""
    for _, rule_row in blocked.iterrows():
        rule_id = str(rule_row["rule"])
        action = str(rule_row["action"])
        if not rule_id or rule_id == "unknown_rule":
            continue
        mask = (decisions["decision"] == "paper_order") & decisions["reason"].astype(str).str.contains(
            rf"\b{re.escape(rule_id)}\b",
            regex=True,
            na=False,
        )
        if not mask.any():
            continue
        blocked_count += int(mask.sum())
        decisions.loc[mask, "decision"] = "blocked_rule"
        decisions.loc[mask, "reason"] = (
            decisions.loc[mask, "reason"].astype(str)
            + f" | blocked by kill-switch: {rule_id} is {action}"
        )

    if blocked_count:
        decisions.to_csv(decisions_path, index=False)
    return blocked_count


def write_position_summary(open_path: Path, closed_path: Path, summary_path: Path) -> int:
    open_positions = load_open_positions(open_path)
    closed = load_csv_or_empty(closed_path)
    rows = [
        {"metric": "open_positions", "value": 0 if open_positions.empty else len(open_positions)},
        {"metric": "closed_trades", "value": 0 if closed.empty else len(closed)},
        {"metric": "closed_pnl", "value": 0.0 if closed.empty or "paper_pnl" not in closed.columns else float(closed["paper_pnl"].sum())},
    ]
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(summary_path, index=False)
    return len(rows)


def closed_paper_pnl(closed_path: Path) -> float:
    closed = load_csv_or_empty(closed_path)
    if closed.empty or "paper_pnl" not in closed.columns:
        return 0.0
    return float(pd.to_numeric(closed["paper_pnl"], errors="coerce").fillna(0.0).sum())


def write_status(
    decisions_path: Path,
    journal_path: Path,
    open_path: Path,
    closed_path: Path,
    status_path: Path,
    latest_opened_count: int | None = None,
    blocked_signal_count: int = 0,
) -> int:
    decisions = load_csv_or_empty(decisions_path)
    journal = load_csv_or_empty(journal_path)
    open_positions = load_open_positions(open_path)
    closed = load_csv_or_empty(closed_path)
    latest_decision = "none"
    paper_orders = 0
    if not decisions.empty and "decision" in decisions.columns:
        latest_decision = ", ".join(f"{row.symbol}:{row.decision}" for row in decisions.itertuples())
        paper_orders = int((decisions["decision"] == "paper_order").sum())
    latest_opened = paper_orders if latest_opened_count is None else latest_opened_count
    rows = [
        {"metric": "last_run_utc", "value": datetime.now(timezone.utc).isoformat()},
        {"metric": "latest_decisions", "value": latest_decision},
        {"metric": "latest_paper_signals", "value": paper_orders},
        {"metric": "latest_paper_orders", "value": latest_opened},
        {"metric": "latest_blocked_signals", "value": blocked_signal_count},
        {"metric": "journal_rows", "value": 0 if journal.empty else len(journal)},
        {"metric": "open_positions", "value": 0 if open_positions.empty else len(open_positions)},
        {"metric": "closed_trades", "value": 0 if closed.empty else len(closed)},
        {"metric": "closed_pnl", "value": 0.0 if closed.empty or "paper_pnl" not in closed.columns else float(closed["paper_pnl"].sum())},
    ]
    status_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(status_path, index=False)
    return len(rows)


def metric_value(df: pd.DataFrame, metric: str, default: str = "0") -> str:
    if df.empty or "metric" not in df.columns or "value" not in df.columns:
        return default
    matches = df[df["metric"] == metric]
    if matches.empty:
        return default
    value = matches.iloc[-1]["value"]
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def metric_float(df: pd.DataFrame, metric: str, default: float = 0.0) -> float:
    try:
        return float(metric_value(df, metric, str(default)))
    except ValueError:
        return default


def markdown_table(df: pd.DataFrame, columns: list[str], empty_message: str) -> str:
    if df.empty:
        return empty_message
    available = [column for column in columns if column in df.columns]
    if not available:
        return empty_message
    view = df[available].fillna("").astype(str)
    header = "| " + " | ".join(available) + " |"
    divider = "| " + " | ".join("---" for _ in available) + " |"
    rows = ["| " + " | ".join(row) + " |" for row in view.to_numpy()]
    return "\n".join([header, divider, *rows])


def write_readiness_report(
    readiness_path: Path,
    status_path: Path,
    journal_path: Path,
    open_path: Path,
    closed_path: Path,
    position_summary_path: Path,
    min_runs: int,
    min_closed_trades: int,
    min_closed_pnl: float,
) -> str:
    status = load_csv_or_empty(status_path)
    journal = load_csv_or_empty(journal_path)
    open_positions = load_open_positions(open_path)
    closed = load_csv_or_empty(closed_path)
    position_summary = load_csv_or_empty(position_summary_path)

    journal_runs = 0
    paper_order_rows = 0
    latest_paper_orders = int(metric_float(status, "latest_paper_orders", 0.0))
    if not journal.empty:
        if "run_id" in journal.columns:
            journal_runs = int(journal["run_id"].nunique())
        else:
            journal_runs = len(journal)
        if "decision" in journal.columns:
            paper_order_rows = int((journal["decision"] == "paper_order").sum())

    open_count = int(metric_float(position_summary, "open_positions", metric_float(status, "open_positions", 0.0)))
    closed_count = int(metric_float(position_summary, "closed_trades", metric_float(status, "closed_trades", 0.0)))
    closed_pnl = metric_float(position_summary, "closed_pnl", metric_float(status, "closed_pnl", 0.0))
    wins = 0
    losses = 0
    win_rate = 0.0
    if not closed.empty and "paper_pnl" in closed.columns:
        pnl = pd.to_numeric(closed["paper_pnl"], errors="coerce").fillna(0.0)
        wins = int((pnl > 0).sum())
        losses = int((pnl < 0).sum())
        if len(pnl) > 0:
            win_rate = wins / len(pnl)

    checks = [
        ("Enough paper-monitor runs", journal_runs >= min_runs, f"{journal_runs}/{min_runs} runs"),
        ("Rules produced paper orders", paper_order_rows > 0 or latest_paper_orders > 0, f"{paper_order_rows} historical order rows"),
        ("Enough closed paper trades", closed_count >= min_closed_trades, f"{closed_count}/{min_closed_trades} closed trades"),
        ("Closed paper PnL is positive", closed_pnl >= min_closed_pnl, f"{closed_pnl:.2f} minimum {min_closed_pnl:.2f}"),
        ("No unresolved open paper positions", open_count == 0, f"{open_count} open positions"),
    ]
    ready = all(passed for _, passed, _ in checks)
    verdict = "READY FOR TINY LIVE PILOT" if ready else "NOT READY FOR LIVE TRADING"

    check_rows = pd.DataFrame(
        [{"check": name, "status": "pass" if passed else "fail", "detail": detail} for name, passed, detail in checks]
    )
    lines = [
        "# Go-Live Readiness",
        "",
        f"Last updated UTC: {metric_value(status, 'last_run_utc', datetime.now(timezone.utc).isoformat())}",
        "",
        f"Verdict: {verdict}",
        "",
        "This gate is intentionally strict. It is meant to protect the account, not make the bot look busy.",
        "",
        "## Checks",
        "",
        markdown_table(check_rows, ["check", "status", "detail"], "No readiness checks available."),
        "",
        "## Paper Results",
        "",
        f"- Paper monitor runs: {journal_runs}",
        f"- Paper order rows: {paper_order_rows}",
        f"- Open paper positions: {open_count}",
        f"- Closed paper trades: {closed_count}",
        f"- Closed paper PnL: {closed_pnl:.2f}",
        f"- Closed paper wins/losses: {wins}/{losses}",
        f"- Closed paper win rate: {win_rate:.2%}",
        "",
        "## Required Before Real Money",
        "",
        "- Keep this in paper mode until the verdict changes.",
        "- Do not add a real Deriv token yet.",
        "- When it becomes ready, start only with a tiny live pilot and daily loss limits.",
        "",
    ]
    readiness_path.parent.mkdir(parents=True, exist_ok=True)
    readiness_path.write_text("\n".join(lines), encoding="utf-8")
    return verdict


def write_dashboard(
    dashboard_path: Path,
    status_path: Path,
    manifest_path: Path,
    decisions_path: Path,
    journal_summary_path: Path,
    open_path: Path,
    closed_path: Path,
    position_summary_path: Path,
    readiness_path: Path,
) -> int:
    status = load_csv_or_empty(status_path)
    manifest = load_csv_or_empty(manifest_path)
    decisions = load_csv_or_empty(decisions_path)
    journal_summary = load_csv_or_empty(journal_summary_path)
    open_positions = load_csv_or_empty(open_path)
    closed = load_csv_or_empty(closed_path)
    position_summary = load_csv_or_empty(position_summary_path)

    closed_pnl = metric_value(position_summary, "closed_pnl", metric_value(status, "closed_pnl", "0.0"))
    open_count = metric_value(position_summary, "open_positions", metric_value(status, "open_positions", "0"))
    closed_count = metric_value(position_summary, "closed_trades", metric_value(status, "closed_trades", "0"))
    paper_orders = metric_value(status, "latest_paper_orders", "0")

    lines = [
        "# Paper Stable Rules Dashboard",
        "",
        f"Last updated UTC: {metric_value(status, 'last_run_utc', datetime.now(timezone.utc).isoformat())}",
        "",
        "This is a paper-trading monitor only. It does not place real trades.",
        "",
        "## Current Verdict",
        "",
        f"- Latest decisions: {metric_value(status, 'latest_decisions', 'none')}",
        f"- New paper orders on latest run: {paper_orders}",
        f"- Open paper positions: {open_count}",
        f"- Closed paper trades: {closed_count}",
        f"- Closed paper PnL: {closed_pnl}",
        "",
        "## Data Refresh",
        "",
        markdown_table(manifest, ["symbol", "timeframe", "status", "candles", "error"], "No refresh data recorded yet."),
        "",
        "## Latest Decisions",
        "",
        markdown_table(
            decisions,
            ["symbol", "timeframe", "decision", "side", "entry", "stop_loss", "take_profit", "reason"],
            "No decisions recorded yet.",
        ),
        "",
        "## Open Positions",
        "",
        markdown_table(
            open_positions,
            ["paper_order_id", "symbol", "timeframe", "opened_at", "side", "entry", "stop_loss", "take_profit", "status"],
            "No open paper positions.",
        ),
        "",
        "## Closed Trades",
        "",
        markdown_table(
            closed.tail(10) if not closed.empty else closed,
            ["paper_order_id", "symbol", "timeframe", "closed_at", "exit_price", "paper_pnl", "exit_reason"],
            "No closed paper trades yet.",
        ),
        "",
        "## Journal Summary",
        "",
        markdown_table(journal_summary, ["symbol", "timeframe", "decision", "runs", "rows", "last_seen"], "No journal summary yet."),
        "",
        "## What To Run Next",
        "",
        f"- Read go-live readiness: `{readiness_path}`",
        f"- Read signal-frequency report: `{TASK_ROOT / 'outputs/stable_rules_signal_frequency_report.md'}`",
        "- Rebuild signal-frequency report: `work/run_near_miss_report.sh`",
        "- Continuous paper monitor: `work/run_paper_monitor.sh`",
        "- Fast local paper check: `work/run_paper_local.sh`",
        "- Fresh Deriv data paper check: `work/run_paper_refresh.sh`",
        "",
    ]

    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_path.write_text("\n".join(lines), encoding="utf-8")
    return len(lines)


def append_journal(decisions_path: Path, journal_path: Path, manifest: pd.DataFrame) -> int:
    if not decisions_path.exists():
        return 0
    decisions = pd.read_csv(decisions_path)
    if decisions.empty:
        return 0

    run_id = datetime.now(timezone.utc).strftime("paper-%Y%m%dT%H%M%SZ")
    decisions.insert(0, "run_id", run_id)
    decisions.insert(1, "run_recorded_at_utc", datetime.now(timezone.utc).isoformat())

    refresh = manifest[["symbol", "timeframe", "status", "candles", "error"]].rename(
        columns={
            "status": "refresh_status",
            "candles": "refresh_candles",
            "error": "refresh_error",
        }
    )
    decisions = decisions.merge(refresh, on=["symbol", "timeframe"], how="left", suffixes=("", "_manifest"))

    journal_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not journal_path.exists()
    decisions.to_csv(journal_path, mode="a", index=False, header=write_header)
    return len(decisions)


def write_journal_summary(journal_path: Path, summary_path: Path) -> int:
    if not journal_path.exists():
        return 0
    journal = pd.read_csv(journal_path)
    if journal.empty:
        return 0
    summary = (
        journal.groupby(["symbol", "timeframe", "decision"], as_index=False)
        .agg(
            runs=("run_id", "nunique"),
            rows=("decision", "size"),
            last_seen=("run_recorded_at_utc", "max"),
        )
        .sort_values(["symbol", "timeframe", "decision"])
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_path, index=False)
    return len(summary)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh approved Deriv paper data, then run stable-rule paper decisions.")
    parser.add_argument("--rules-csv", default=str(DEFAULT_RULES))
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--journal-output", default=str(DEFAULT_JOURNAL))
    parser.add_argument("--journal-summary-output", default=str(DEFAULT_JOURNAL_SUMMARY))
    parser.add_argument("--open-positions-output", default=str(DEFAULT_OPEN_POSITIONS))
    parser.add_argument("--closed-trades-output", default=str(DEFAULT_CLOSED_TRADES))
    parser.add_argument("--position-summary-output", default=str(DEFAULT_POSITION_SUMMARY))
    parser.add_argument("--status-output", default=str(DEFAULT_STATUS))
    parser.add_argument("--dashboard-output", default=str(DEFAULT_DASHBOARD))
    parser.add_argument("--readiness-output", default=str(DEFAULT_READINESS))
    parser.add_argument("--track-name", default="Original stable rules")
    parser.add_argument("--blocked-rules-csv", default=str(DEFAULT_BLOCKED_RULES))
    parser.add_argument("--paper-max-bars", type=int, default=12)
    parser.add_argument("--paper-slippage-bps", type=float, default=2.0, help="Paper exit slippage/spread cost in basis points.")
    parser.add_argument("--disable-emergency-stop", action="store_true", help="Disable immediate paper stop/take-profit enforcement.")
    parser.add_argument(
        "--paper-profit-lock-r",
        type=float,
        default=2.0,
        help="Close an open paper trade once candle close reaches this R multiple. Use 0 to disable.",
    )
    parser.add_argument("--max-open-positions", type=int, default=4, help="Maximum open paper positions per track.")
    parser.add_argument("--max-family-side-open", type=int, default=2, help="Maximum open positions per instrument family and side.")
    parser.add_argument("--cooldown-losses", type=int, default=2, help="Pause a rule if it lost in this many recent closed trades.")
    parser.add_argument(
        "--stale-candle-minutes",
        type=float,
        default=180.0,
        help="Block new paper entries when latest candle is older than this many minutes. Use 0 to disable.",
    )
    parser.add_argument(
        "--stale-signal-minutes",
        type=float,
        default=180.0,
        help="Block new paper entries when the signal timestamp is older than this many minutes. Use 0 to disable.",
    )
    parser.add_argument("--no-positions", action="store_true", help="Do not update paper open/closed position ledgers.")
    parser.add_argument("--no-new-positions", action="store_true", help="Track existing paper positions but do not add new paper orders.")
    parser.add_argument(
        "--quarantine-loss-limit",
        type=float,
        default=60.0,
        help="Block new paper positions once closed paper PnL is below this loss amount. Use 0 to disable.",
    )
    parser.add_argument("--manifest-output", default=str(TASK_ROOT / "outputs/paper_stable_rules_refresh_manifest.csv"))
    parser.add_argument("--count", type=int, default=5000)
    parser.add_argument("--app-id", type=int, default=1089)
    parser.add_argument("--skip-download", action="store_true", help="Use copied local data only; no Deriv API call.")
    parser.add_argument("--no-journal", action="store_true", help="Do not append this run to the paper journal.")
    parser.add_argument("--repeat", action="store_true", help="Keep running paper checks on a timer.")
    parser.add_argument("--interval-minutes", type=float, default=15.0, help="Minutes between repeated paper checks.")
    parser.add_argument("--max-runs", type=int, help="Stop after this many runs. Leave blank to keep monitoring.")
    parser.add_argument("--readiness-min-runs", type=int, default=30, help="Minimum paper runs before live readiness can pass.")
    parser.add_argument("--readiness-min-closed-trades", type=int, default=10, help="Minimum closed paper trades before readiness can pass.")
    parser.add_argument("--readiness-min-closed-pnl", type=float, default=0.0, help="Minimum closed paper PnL before readiness can pass.")
    return parser.parse_args()


def run_once(args: argparse.Namespace) -> int:
    rules_csv = Path(args.rules_csv)
    data_dir = Path(args.data_dir)
    output = Path(args.output)
    journal_output = Path(args.journal_output)
    journal_summary_output = Path(args.journal_summary_output)
    open_positions_output = Path(args.open_positions_output)
    closed_trades_output = Path(args.closed_trades_output)
    position_summary_output = Path(args.position_summary_output)
    status_output = Path(args.status_output)
    dashboard_output = Path(args.dashboard_output)
    readiness_output = Path(args.readiness_output)
    manifest_output = Path(args.manifest_output)
    blocked_rules_csv = Path(args.blocked_rules_csv)

    rules = pd.read_csv(rules_csv)
    manifest = refresh_data(rules, data_dir, count=args.count, app_id=args.app_id, skip_download=args.skip_download)
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(manifest_output, index=False)
    print(f"Saved refresh manifest to {manifest_output}")
    print(manifest.to_string(index=False))

    result = run_paper_mode(data_dir, rules_csv, output)
    if result == 0:
        print(f"Saved paper decisions to {output}")
        opened_count = 0
        blocked_signal_count = 0
        kill_blocked_count = apply_rule_blocklist(output, blocked_rules_csv, args.track_name)
        if kill_blocked_count:
            blocked_signal_count += kill_blocked_count
            print(f"Kill-switch blocked {kill_blocked_count} paper signal(s) for {args.track_name}.")
        if not args.no_positions:
            closed_count, still_open = update_open_positions(
                open_positions_output,
                closed_trades_output,
                data_dir,
                max_bars=args.paper_max_bars,
                slippage_bps=args.paper_slippage_bps,
                emergency_stop=not args.disable_emergency_stop,
                profit_lock_r=args.paper_profit_lock_r,
            )
            closed_pnl = closed_paper_pnl(closed_trades_output)
            quarantined = args.quarantine_loss_limit > 0 and closed_pnl <= -abs(args.quarantine_loss_limit)
            if quarantined:
                print(
                    f"Original stable paper track is quarantined after closed PnL {closed_pnl:.2f}. "
                    "No new paper positions will be added.",
                    flush=True,
                )
            if args.no_new_positions or quarantined:
                decisions = load_csv_or_empty(output)
                if not decisions.empty and "decision" in decisions.columns:
                    blocked_signal_count += int((decisions["decision"] == "paper_order").sum())
            else:
                guard_blocked_count = apply_entry_guards(
                    output,
                    open_positions_output,
                    closed_trades_output,
                    data_dir,
                    max_open_positions=args.max_open_positions,
                    max_family_side_open=args.max_family_side_open,
                    cooldown_losses=args.cooldown_losses,
                    stale_candle_minutes=args.stale_candle_minutes,
                    stale_signal_minutes=args.stale_signal_minutes,
                )
                if guard_blocked_count:
                    blocked_signal_count += guard_blocked_count
                    print(f"Entry guards blocked {guard_blocked_count} paper signal(s) for {args.track_name}.")
                opened_count = append_new_paper_positions(output, open_positions_output)
            write_position_summary(open_positions_output, closed_trades_output, position_summary_output)
            print(
                f"Paper positions: opened {opened_count}, closed {closed_count}, "
                f"still open {still_open}. Summary: {position_summary_output}"
            )
        if not args.no_journal:
            appended = append_journal(output, journal_output, manifest)
            print(f"Appended {appended} decision rows to journal {journal_output}")
            summary_rows = write_journal_summary(journal_output, journal_summary_output)
            print(f"Updated journal summary with {summary_rows} rows at {journal_summary_output}")
        status_rows = write_status(
            output,
            journal_output,
            open_positions_output,
            closed_trades_output,
            status_output,
            latest_opened_count=opened_count,
            blocked_signal_count=blocked_signal_count,
        )
        print(f"Updated paper status with {status_rows} rows at {status_output}")
        verdict = write_readiness_report(
            readiness_output,
            status_output,
            journal_output,
            open_positions_output,
            closed_trades_output,
            position_summary_output,
            min_runs=args.readiness_min_runs,
            min_closed_trades=args.readiness_min_closed_trades,
            min_closed_pnl=args.readiness_min_closed_pnl,
        )
        print(f"Updated go-live readiness at {readiness_output}: {verdict}")
        dashboard_rows = write_dashboard(
            dashboard_output,
            status_output,
            manifest_output,
            output,
            journal_summary_output,
            open_positions_output,
            closed_trades_output,
            position_summary_output,
            readiness_output,
        )
        print(f"Updated paper dashboard with {dashboard_rows} lines at {dashboard_output}")
    return result


def main() -> int:
    args = parse_args()
    if not args.repeat:
        return run_once(args)

    run_number = 0
    while True:
        run_number += 1
        print(f"\nPaper monitor run {run_number} started at {datetime.now(timezone.utc).isoformat()}", flush=True)
        result = run_once(args)
        if result != 0:
            return result
        if args.max_runs is not None and run_number >= args.max_runs:
            print(f"Paper monitor finished after {run_number} run(s).", flush=True)
            return 0
        print(f"Next paper monitor run in {args.interval_minutes:g} minute(s). Press Ctrl+C to stop.", flush=True)
        try:
            time.sleep(max(args.interval_minutes * 60.0, 1.0))
        except KeyboardInterrupt:
            print("\nPaper monitor stopped by user.")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
