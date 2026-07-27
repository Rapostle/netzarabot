from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


BOT_ROOT = Path("/Users/ocmix/Documents/Codex/2026-07-09/can-you-help-implement-in-the")
TASK_ROOT = Path("/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot")
DEFAULT_RULES = TASK_ROOT / "outputs/stable_rules_pair_execution_candidates.csv"
DEFAULT_DATA_DIR = TASK_ROOT / "outputs/pair_candidate_refreshed_data"
DEFAULT_DETAIL = TASK_ROOT / "outputs/advanced_accuracy_gate_detail.csv"
DEFAULT_SUMMARY = TASK_ROOT / "outputs/advanced_accuracy_gate_summary.csv"
DEFAULT_APPROVED = TASK_ROOT / "outputs/advanced_accuracy_approved_candidates.csv"
DEFAULT_EXECUTION = TASK_ROOT / "outputs/advanced_accuracy_execution_candidates.csv"
DEFAULT_REPORT = TASK_ROOT / "outputs/advanced_accuracy_report.md"

sys.path.insert(0, str(BOT_ROOT))
from trading_bot.indicators.technical import add_indicators  # noqa: E402
from trading_bot.research.signal_discovery import condition_frame  # noqa: E402


@dataclass(frozen=True)
class SymbolProfile:
    family: str
    min_score: int
    horizon: int
    allowed_regimes: tuple[str, ...]
    blocked_regimes: tuple[str, ...]
    max_risk_per_trade: float
    max_daily_loss_r: float
    max_losing_streak: int


PROFILES = {
    "boom": SymbolProfile(
        family="boom",
        min_score=75,
        horizon=12,
        allowed_regimes=("trending", "ranging"),
        blocked_regimes=("dead", "compressed", "spiking"),
        max_risk_per_trade=0.003,
        max_daily_loss_r=2.0,
        max_losing_streak=2,
    ),
    "crash": SymbolProfile(
        family="crash",
        min_score=78,
        horizon=12,
        allowed_regimes=("trending", "ranging"),
        blocked_regimes=("dead", "compressed", "spiking"),
        max_risk_per_trade=0.003,
        max_daily_loss_r=2.0,
        max_losing_streak=2,
    ),
    "default": SymbolProfile(
        family="default",
        min_score=72,
        horizon=12,
        allowed_regimes=("trending", "ranging"),
        blocked_regimes=("dead", "compressed", "spiking"),
        max_risk_per_trade=0.004,
        max_daily_loss_r=2.0,
        max_losing_streak=3,
    ),
}


def symbol_family(symbol: str) -> str:
    upper = symbol.upper()
    if "BOOM" in upper:
        return "boom"
    if "CRASH" in upper:
        return "crash"
    return "default"


def profile_for(symbol: str) -> SymbolProfile:
    return PROFILES.get(symbol_family(symbol), PROFILES["default"])


def safe_symbol_filename(symbol: str) -> str:
    return "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in symbol)


def data_path(data_dir: Path, symbol: str, timeframe: str) -> Path:
    return data_dir / f"deriv_{safe_symbol_filename(symbol)}_{timeframe}.csv"


def load_indicated(path: Path, max_rows: int | None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if df.empty or "timestamp" not in df.columns:
        return pd.DataFrame()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp")
    if max_rows:
        df = df.tail(max_rows + 300)
    enriched = add_indicators(df).dropna().reset_index(drop=True)
    if max_rows:
        enriched = enriched.tail(max_rows).reset_index(drop=True)
    return enriched


def pct(value: float) -> str:
    return f"{value:.2%}"


def profit_factor(returns: pd.Series) -> float:
    wins = returns[returns > 0]
    losses = returns[returns <= 0]
    gross_profit = float(wins.sum())
    gross_loss = abs(float(losses.sum()))
    if gross_loss > 0:
        return gross_profit / gross_loss
    if gross_profit > 0:
        return float("inf")
    return 0.0


def max_drawdown(equity_curve: pd.Series) -> float:
    if equity_curve.empty:
        return 0.0
    peak = equity_curve.cummax()
    drawdown = (equity_curve - peak) / peak.replace(0, pd.NA)
    return abs(float(drawdown.min())) if not drawdown.dropna().empty else 0.0


def markdown_table(rows: list[dict[str, object]], columns: list[str], empty: str) -> str:
    if not rows:
        return empty
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(str(row.get(column, "")) for column in columns) + " |" for row in rows]
    return "\n".join([header, divider, *body])


def classify_regime(row: pd.Series) -> str:
    close = float(row.get("close", 0) or 0)
    atr = float(row.get("atr_14", 0) or 0)
    if close <= 0 or atr <= 0:
        return "unknown"
    atr_pct = atr / close
    bb_width_atr = (float(row.get("bb_upper", 0) or 0) - float(row.get("bb_lower", 0) or 0)) / atr
    ema_spread_atr = abs(float(row.get("ema_50", 0) or 0) - float(row.get("ema_200", 0) or 0)) / atr
    if atr_pct < 0.00045:
        return "dead"
    if atr_pct > 0.009:
        return "spiking"
    if bb_width_atr < 1.0:
        return "compressed"
    if ema_spread_atr >= 0.55:
        return "trending"
    return "ranging"


def trend_direction(row: pd.Series) -> str:
    ema_50 = float(row.get("ema_50", 0) or 0)
    ema_200 = float(row.get("ema_200", 0) or 0)
    supertrend = float(row.get("supertrend_direction", 0) or 0)
    if ema_50 > ema_200 and supertrend > 0:
        return "bullish"
    if ema_50 < ema_200 and supertrend < 0:
        return "bearish"
    return "mixed"


def candle_stats(row: pd.Series) -> dict[str, float]:
    atr = float(row.get("atr_14", 0) or 0)
    if atr <= 0:
        return {"body_atr": 0.0, "upper_wick_atr": 0.0, "lower_wick_atr": 0.0, "range_atr": 0.0}
    open_price = float(row["open"])
    close = float(row["close"])
    high = float(row["high"])
    low = float(row["low"])
    return {
        "body_atr": (close - open_price) / atr,
        "upper_wick_atr": (high - max(open_price, close)) / atr,
        "lower_wick_atr": (min(open_price, close) - low) / atr,
        "range_atr": (high - low) / atr,
    }


def boom_crash_spike_risk(symbol: str, side: str, row: pd.Series, recent: pd.DataFrame) -> tuple[bool, str]:
    family = symbol_family(symbol)
    stats = candle_stats(row)
    recent_returns = recent["close"].pct_change().dropna().tail(8)
    recent_up_spike = bool((recent_returns > recent_returns.std() * 2.5).any()) if len(recent_returns) > 3 else False
    recent_down_spike = bool((recent_returns < -recent_returns.std() * 2.5).any()) if len(recent_returns) > 3 else False

    if family == "boom" and side == "sell":
        if stats["lower_wick_atr"] > 0.65 or recent_up_spike:
            return True, "boom upward spike risk against sell"
    if family == "crash" and side == "buy":
        if stats["upper_wick_atr"] > 0.65 or recent_down_spike:
            return True, "crash downward spike risk against buy"
    return False, "spike risk acceptable"


def no_trade_zone(row: pd.Series) -> tuple[bool, str]:
    stats = candle_stats(row)
    close = float(row.get("close", 0) or 0)
    atr = float(row.get("atr_14", 0) or 0)
    if atr <= 0 or close <= 0:
        return True, "missing volatility"
    bb_width_atr = (float(row["bb_upper"]) - float(row["bb_lower"])) / atr
    if bb_width_atr < 1.0:
        return True, "compressed chop"
    if stats["range_atr"] > 3.0:
        return True, "oversized candle"
    if abs(stats["body_atr"]) < 0.08 and stats["upper_wick_atr"] < 0.2 and stats["lower_wick_atr"] < 0.2:
        return True, "dead candle"
    return False, "clear enough"


def feature_match_mask(conditions: pd.DataFrame, feature: str, condition: str) -> pd.Series:
    features = [part.strip() for part in str(feature).split("+")]
    values = [part.strip() for part in str(condition).split("&")]
    if len(features) != len(values):
        return pd.Series(False, index=conditions.index)
    mask = pd.Series(True, index=conditions.index)
    for feature_name, value in zip(features, values):
        if feature_name not in conditions.columns:
            return pd.Series(False, index=conditions.index)
        mask &= conditions[feature_name].astype(str) == value
    return mask


def forward_trade_return(df: pd.DataFrame, idx: int, side: str, horizon: int) -> tuple[float, float, float, float]:
    if idx + horizon >= len(df):
        return 0.0, 0.0, 0.0, 0.0
    entry = float(df["close"].iloc[idx])
    future = df.iloc[idx + 1 : idx + horizon + 1]
    if future.empty or entry <= 0:
        return 0.0, 0.0, 0.0, 0.0
    exit_price = float(future["close"].iloc[-1])
    if side == "buy":
        raw_return = (exit_price - entry) / entry
        mfe = (float(future["high"].max()) - entry) / entry
        mae = (float(future["low"].min()) - entry) / entry
    else:
        raw_return = (entry - exit_price) / entry
        mfe = (entry - float(future["low"].min())) / entry
        mae = (entry - float(future["high"].max())) / entry
    atr = float(df["atr_14"].iloc[idx])
    risk_pct = atr / entry if entry > 0 else 0.0
    return raw_return, mfe, mae, risk_pct


def exit_recommendation(mfe_r: float, mae_r: float) -> str:
    if mfe_r >= 2.0 and mae_r > -1.0:
        return "test fixed_2r_or_trail_after_1r"
    if mfe_r >= 1.5 and mae_r > -1.0:
        return "test fixed_1_5r_no_partial"
    if mfe_r >= 1.0:
        return "test fixed_1r_or_breakeven"
    return "skip_or_wait_for_better_entry"


def score_entry(
    symbol: str,
    side: str,
    row: pd.Series,
    recent: pd.DataFrame,
    rule_profit_factor: float,
    rule_win_rate: float,
) -> dict[str, object]:
    profile = profile_for(symbol)
    regime = classify_regime(row)
    trend = trend_direction(row)
    stats = candle_stats(row)
    spike_blocked, spike_reason = boom_crash_spike_risk(symbol, side, row, recent)
    no_trade, no_trade_reason = no_trade_zone(row)

    score = 0
    reasons = []

    if regime in profile.allowed_regimes:
        score += 18
    else:
        reasons.append(f"regime not ideal: {regime}")
    if regime in profile.blocked_regimes:
        reasons.append(f"blocked regime: {regime}")

    if (side == "buy" and trend == "bullish") or (side == "sell" and trend == "bearish"):
        score += 17
    elif trend == "mixed":
        score += 6
        reasons.append("mixed trend")
    else:
        reasons.append("trend disagrees")

    if not spike_blocked:
        score += 15
    else:
        reasons.append(spike_reason)

    if not no_trade:
        score += 12
    else:
        reasons.append(no_trade_reason)

    if side == "buy" and stats["lower_wick_atr"] >= 0.25:
        score += 8
    elif side == "sell" and stats["upper_wick_atr"] >= 0.25:
        score += 8
    else:
        score += 3

    if rule_profit_factor >= 2.0:
        score += 12
    elif rule_profit_factor >= 1.3:
        score += 8
    else:
        reasons.append("weak rule profit factor")

    if rule_win_rate >= 0.62:
        score += 10
    elif rule_win_rate >= 0.55:
        score += 6
    else:
        reasons.append("low rule win rate")

    if symbol_family(symbol) in {"boom", "crash"}:
        score += 8

    blocked = spike_blocked or no_trade or regime in profile.blocked_regimes or score < profile.min_score
    if score >= 85 and not blocked:
        grade = "A"
    elif score >= profile.min_score and not blocked:
        grade = "B"
    elif score >= 60:
        grade = "C"
    else:
        grade = "BLOCKED"

    return {
        "sniper_score": score,
        "quality_grade": grade,
        "regime": regime,
        "trend_direction": trend,
        "spike_blocked": spike_blocked,
        "no_trade_zone": no_trade,
        "blocked": blocked,
        "block_reason": "; ".join(reasons) if reasons else "passed",
        "risk_governor": (
            f"risk<={profile.max_risk_per_trade:.3f}, "
            f"daily_loss<={profile.max_daily_loss_r:.1f}R, "
            f"max_losing_streak={profile.max_losing_streak}"
        ),
    }


def evaluate_rule(rule: pd.Series, data_dir: Path, max_rows: int) -> tuple[pd.DataFrame, dict[str, object]]:
    symbol = str(rule["symbol"])
    timeframe = str(rule["timeframe"])
    side = str(rule["suggested_side"])
    path = data_path(data_dir, symbol, timeframe)
    df = load_indicated(path, max_rows=max_rows)
    if df.empty:
        return pd.DataFrame(), {
            "rule_id": rule.get("rule_id", ""),
            "symbol": symbol,
            "timeframe": timeframe,
            "side": side,
            "status": "missing data",
        }

    profile = profile_for(symbol)
    conditions = condition_frame(df)
    mask = feature_match_mask(conditions, str(rule["feature"]), str(rule["condition"]))
    indexes = [idx for idx in df[mask].index.tolist() if idx + profile.horizon < len(df)]
    rule_pf = float(rule.get("profit_factor", 0) or 0)
    rule_wr = float(rule.get("win_rate", 0) or 0)

    rows = []
    for idx in indexes:
        row = df.iloc[idx]
        recent = df.iloc[max(0, idx - 12) : idx + 1]
        scored = score_entry(symbol, side, row, recent, rule_pf, rule_wr)
        raw_return, mfe, mae, risk_pct = forward_trade_return(df, idx, side, profile.horizon)
        risk_pct = risk_pct if risk_pct > 0 else 0.0001
        mfe_r = mfe / risk_pct
        mae_r = mae / risk_pct
        rows.append(
            {
                "rule_id": rule.get("rule_id", ""),
                "symbol": symbol,
                "timeframe": timeframe,
                "side": side,
                "feature": rule["feature"],
                "condition": rule["condition"],
                "timestamp": row.get("timestamp", ""),
                "sniper_score": scored["sniper_score"],
                "quality_grade": scored["quality_grade"],
                "regime": scored["regime"],
                "trend_direction": scored["trend_direction"],
                "spike_blocked": scored["spike_blocked"],
                "no_trade_zone": scored["no_trade_zone"],
                "blocked": scored["blocked"],
                "block_reason": scored["block_reason"],
                "risk_governor": scored["risk_governor"],
                "raw_forward_return": raw_return,
                "mfe_r": mfe_r,
                "mae_r": mae_r,
                "exit_recommendation": exit_recommendation(mfe_r, mae_r),
            }
        )

    detail = pd.DataFrame(rows)
    summary = summarize_rule(rule, detail)
    return detail, summary


def summarize_rule(rule: pd.Series, detail: pd.DataFrame) -> dict[str, object]:
    base = {
        "rule_id": rule.get("rule_id", ""),
        "symbol": rule.get("symbol", ""),
        "timeframe": rule.get("timeframe", ""),
        "side": rule.get("suggested_side", ""),
        "feature": rule.get("feature", ""),
        "condition": rule.get("condition", ""),
    }
    if detail.empty:
        return {**base, "status": "no matches", "matches": 0, "approved_matches": 0}

    approved = detail[~detail["blocked"]]
    returns = pd.to_numeric(approved["raw_forward_return"], errors="coerce").fillna(0.0)
    all_returns = pd.to_numeric(detail["raw_forward_return"], errors="coerce").fillna(0.0)
    split = max(math.floor(len(approved) * 0.6), 1)
    train_returns = returns.iloc[:split]
    test_returns = returns.iloc[split:]
    test_pf = profit_factor(test_returns) if not test_returns.empty else 0.0
    test_expectancy = float(test_returns.mean()) if not test_returns.empty else 0.0
    equity = (1 + returns).cumprod() if not returns.empty else pd.Series(dtype="float64")
    approved_count = len(approved)
    pass_walk_forward = approved_count >= 10 and test_expectancy > 0 and test_pf >= 1.2
    avg_score = float(approved["sniper_score"].mean()) if approved_count else 0.0
    verdict = "APPROVED_RESEARCH" if pass_walk_forward and avg_score >= profile_for(str(rule.get("symbol", ""))).min_score else "RESEARCH_ONLY"
    if approved_count < 10:
        verdict = "NEEDS_MORE_TRADES"

    return {
        **base,
        "status": "evaluated",
        "matches": len(detail),
        "approved_matches": approved_count,
        "blocked_matches": int(detail["blocked"].sum()),
        "avg_sniper_score": round(avg_score, 2),
        "a_grade_matches": int((approved["quality_grade"] == "A").sum()) if approved_count else 0,
        "approved_win_rate": round(float((returns > 0).mean()), 4) if approved_count else 0.0,
        "approved_return": round(float(returns.sum()), 6) if approved_count else 0.0,
        "approved_profit_factor": round(profit_factor(returns), 4) if approved_count else 0.0,
        "approved_expectancy": round(float(returns.mean()), 6) if approved_count else 0.0,
        "approved_max_drawdown": round(max_drawdown(equity), 6),
        "walk_forward_train_return": round(float(train_returns.sum()), 6) if not train_returns.empty else 0.0,
        "walk_forward_test_return": round(float(test_returns.sum()), 6) if not test_returns.empty else 0.0,
        "walk_forward_test_pf": round(test_pf, 4),
        "walk_forward_pass": pass_walk_forward,
        "best_exit_mode": approved["exit_recommendation"].mode().iloc[0] if approved_count else "none",
        "verdict": verdict,
        "raw_unfiltered_return": round(float(all_returns.sum()), 6),
    }


def write_report(report_path: Path, summary: pd.DataFrame, approved: pd.DataFrame) -> None:
    if summary.empty:
        top_rows: list[dict[str, object]] = []
    else:
        top = summary.sort_values(
            ["verdict", "walk_forward_pass", "approved_profit_factor", "approved_expectancy", "approved_matches"],
            ascending=[True, False, False, False, False],
        ).head(12)
        top_rows = top.to_dict("records")

    lines = [
        "# Advanced Accuracy Lab",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This is an offline research gate. It does not touch the running paper trade and does not place real trades.",
        "",
        "## What Was Built",
        "",
        "- Sniper entry score.",
        "- Market regime filter.",
        "- Boom/Crash spike filter.",
        "- Multi-timeframe-style trend confirmation using EMA and supertrend.",
        "- Exit recommendation testing from MFE/MAE behavior.",
        "- No-trade zone detector.",
        "- Symbol-specific profiles.",
        "- Trade quality grading.",
        "- Walk-forward train/test split.",
        "- Risk governor recommendations.",
        "",
        "## Top Research Results",
        "",
        markdown_table(
            top_rows,
            [
                "rule_id",
                "symbol",
                "timeframe",
                "side",
                "verdict",
                "approved_matches",
                "avg_sniper_score",
                "approved_win_rate",
                "approved_return",
                "approved_profit_factor",
                "walk_forward_test_return",
                "walk_forward_test_pf",
                "best_exit_mode",
            ],
            "No rules were evaluated.",
        ),
        "",
        "## Promotion Result",
        "",
        f"- Research-approved candidates: {0 if approved.empty else len(approved)}",
        "- These are not live rules yet. They must be paper-tested separately before promotion.",
        "",
        "## Next Safe Step",
        "",
        "Use the approved research candidates only in a new experimental paper track after the current open paper trade closes or in a separate runner with different output files.",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def execution_candidates(approved: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "rule_id",
        "symbol",
        "timeframe",
        "suggested_side",
        "feature",
        "condition",
        "trades",
        "total_return",
        "win_rate",
        "profit_factor",
        "expectancy",
        "symbol_rule_rank",
        "promotion_status",
    ]
    if approved.empty:
        return pd.DataFrame(columns=columns)

    rows = approved.copy()
    rows["suggested_side"] = rows["side"]
    rows["trades"] = rows["approved_matches"]
    rows["total_return"] = rows["approved_return"]
    rows["win_rate"] = rows["approved_win_rate"]
    rows["profit_factor"] = rows["approved_profit_factor"]
    rows["expectancy"] = rows["approved_expectancy"]
    rows = rows.sort_values(
        ["symbol", "timeframe", "suggested_side", "approved_profit_factor", "approved_expectancy"],
        ascending=[True, True, True, False, False],
    )
    rows["symbol_rule_rank"] = rows.groupby(["symbol", "timeframe", "suggested_side"]).cumcount() + 1
    rows["promotion_status"] = "advanced_sniper_research_candidate"
    return rows[columns]


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline sniper-entry and profitability gate for paper candidates.")
    parser.add_argument("--rules-csv", default=str(DEFAULT_RULES))
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--detail-output", default=str(DEFAULT_DETAIL))
    parser.add_argument("--summary-output", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--approved-output", default=str(DEFAULT_APPROVED))
    parser.add_argument("--execution-output", default=str(DEFAULT_EXECUTION))
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT))
    parser.add_argument("--max-rows", type=int, default=5000)
    args = parser.parse_args()

    rules = pd.read_csv(args.rules_csv)
    detail_parts = []
    summaries = []
    for _, rule in rules.iterrows():
        detail, summary = evaluate_rule(rule, Path(args.data_dir), max_rows=args.max_rows)
        if not detail.empty:
            detail_parts.append(detail)
        summaries.append(summary)

    detail_df = pd.concat(detail_parts, ignore_index=True) if detail_parts else pd.DataFrame()
    summary_df = pd.DataFrame(summaries)
    approved = summary_df[summary_df.get("verdict", "") == "APPROVED_RESEARCH"].copy() if not summary_df.empty else pd.DataFrame()
    execution = execution_candidates(approved)

    for path, df in [
        (Path(args.detail_output), detail_df),
        (Path(args.summary_output), summary_df),
        (Path(args.approved_output), approved),
        (Path(args.execution_output), execution),
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)

    write_report(Path(args.report_output), summary_df, approved)
    print(f"Saved advanced gate detail to {args.detail_output}")
    print(f"Saved advanced gate summary to {args.summary_output}")
    print(f"Saved advanced approved research candidates to {args.approved_output}")
    print(f"Saved advanced execution candidates to {args.execution_output}")
    print(f"Saved advanced accuracy report to {args.report_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
