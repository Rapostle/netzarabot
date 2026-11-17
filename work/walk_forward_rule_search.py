"""Walk-forward rule search with a false-positive check.

Why this exists: the current paper rules were mined and judged on the same data
(a rule's confidence is its own in-sample win rate), with only 10 to 90 trades each.
This search keeps the data honest:

  train 50%  -> find rules          (hundreds of hypotheses, so many look good by luck)
  valid 25%  -> keep only rules that still work on data they never saw
  test  25%  -> judged once, at the end, on data nobody touched

and then repeats the whole procedure on shuffled copies of the same candles, where no
real pattern can exist. If shuffled data produces as many "winning" rules as the real
data, the real result is luck.

Trades are simulated exactly like the paper bot: enter at the close of the signal candle,
stop 1.4 x ATR, target 1.8 x ATR, exit after 12 candles; the stop is assumed to hit
first when a candle touches both levels. Costs and stop slippage are charged.

Read-only: it never trades and never touches the executor.
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

BOT_ROOT = Path(os.environ.get("TRADING_BOT_ROOT", str(Path(__file__).resolve().parent.parent / "external" / "trading_bot")))
sys.path.insert(0, str(BOT_ROOT))

from trading_bot.data.loader import load_ohlcv_csv  # noqa: E402
from trading_bot.indicators.technical import add_indicators  # noqa: E402
from trading_bot.research.signal_discovery import CONDITION_COLUMNS, condition_frame  # noqa: E402

WARMUP_BARS = 260  # the regime features use rolling 240-bar ranks


@dataclass(frozen=True)
class SearchConfig:
    horizon: int = 12
    sl_atr: float = 1.4
    tp_atr: float = 1.8
    cost: float = 0.001  # round-trip cost as a fraction of price (about $0.02 per $1 stake at x20)
    sl_slippage: float = 0.2  # extra loss on stop-outs, as a fraction of the stop distance (seen on the demo: -0.23 vs -0.19)
    train_frac: float = 0.50
    valid_frac: float = 0.25
    min_train: int = 30
    min_valid: int = 8
    min_test: int = 6
    min_train_win: float = 0.55
    min_valid_win: float = 0.50
    keep_top: int = 150
    time_features: bool = False  # add trading-session and weekday conditions (real markets)
    price_action: str = "off"  # off | add (alongside indicator conditions) | only (price-action families only)
    htf_factor: int = 12  # candles per higher-timeframe block (12 x 5m = 1 hour)


def simulate_trades(df: pd.DataFrame, cfg: SearchConfig) -> pd.DataFrame:
    """Net fractional return of a buy and of a sell opened at the close of every candle."""
    n = len(df)
    close = df["close"].to_numpy(float)
    high = df["high"].to_numpy(float)
    low = df["low"].to_numpy(float)
    atr = df["atr_14"].to_numpy(float)
    out = {}
    for side in ("buy", "sell"):
        sign = 1.0 if side == "buy" else -1.0
        entry = close
        risk = np.where(np.isfinite(atr) & (atr > 0), atr, np.nan)
        stop = entry - sign * cfg.sl_atr * risk
        target = entry + sign * cfg.tp_atr * risk
        result = np.full(n, np.nan)
        done = np.zeros(n, dtype=bool)
        for k in range(1, cfg.horizon + 1):
            idx = np.arange(n - k)  # candle i looks at candle i+k
            future_high = np.full(n, np.nan)
            future_low = np.full(n, np.nan)
            future_high[idx] = high[idx + k]
            future_low[idx] = low[idx + k]
            adverse = future_low if side == "buy" else future_high
            favourable = future_high if side == "buy" else future_low
            hit_stop = ~done & np.isfinite(adverse) & ((adverse <= stop) if side == "buy" else (adverse >= stop))
            result[hit_stop] = sign * (stop[hit_stop] - entry[hit_stop]) / entry[hit_stop] - cfg.sl_slippage * cfg.sl_atr * risk[hit_stop] / entry[hit_stop]
            done |= hit_stop
            hit_target = ~done & np.isfinite(favourable) & ((favourable >= target) if side == "buy" else (favourable <= target))
            result[hit_target] = sign * (target[hit_target] - entry[hit_target]) / entry[hit_target]
            done |= hit_target
        timeout = ~done
        last = np.full(n, np.nan)
        valid = np.arange(n) + cfg.horizon < n
        last[valid] = close[np.arange(n)[valid] + cfg.horizon]
        result[timeout] = sign * (last[timeout] - entry[timeout]) / entry[timeout]
        result = result - cfg.cost
        result[~np.isfinite(risk)] = np.nan
        result[~valid & ~done] = np.nan
        out[f"{side}_ret"] = result
    return pd.DataFrame(out, index=df.index)


def wilson_lower(wins: int, n: int, z: float = 1.64) -> float:
    if n == 0:
        return 0.0
    p = wins / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre - margin) / denom


def segment_stats(returns: np.ndarray) -> dict[str, float]:
    r = returns[np.isfinite(returns)]
    n = len(r)
    if n == 0:
        return {"n": 0, "win_rate": 0.0, "expectancy": 0.0, "profit_factor": 0.0, "wins": 0}
    wins = int((r > 0).sum())
    gross_win = float(r[r > 0].sum())
    gross_loss = abs(float(r[r <= 0].sum()))
    pf = gross_win / gross_loss if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)
    return {"n": n, "wins": wins, "win_rate": wins / n, "expectancy": float(r.mean()), "profit_factor": pf}


def hypotheses(conditions: pd.DataFrame):
    """Yield (feature, condition, boolean mask) for single conditions and pairs."""
    columns = list(conditions.columns)
    codes = {}
    for column in columns:
        cat = pd.Categorical(conditions[column].astype(str))
        codes[column] = (cat.codes, list(cat.categories))
    for column in columns:
        values, names = codes[column]
        for code, name in enumerate(names):
            if name in ("nan", "None"):
                continue
            yield column, name, values == code
    for i, left in enumerate(columns):
        lv, ln = codes[left]
        for right in columns[i + 1:]:
            rv, rn = codes[right]
            for lcode, lname in enumerate(ln):
                if lname in ("nan", "None"):
                    continue
                lmask = lv == lcode
                if lmask.sum() == 0:
                    continue
                for rcode, rname in enumerate(rn):
                    if rname in ("nan", "None"):
                        continue
                    yield f"{left}+{right}", f"{lname} & {rname}", lmask & (rv == rcode)


def run_protocol(df: pd.DataFrame, cfg: SearchConfig) -> tuple[pd.DataFrame, int]:
    """Return (all rules that survived train+valid with their test result, number of hypotheses tried)."""
    df = add_indicators(df).reset_index(drop=True)
    n = len(df)
    if n < WARMUP_BARS + 200:
        return pd.DataFrame(), 0
    trades = simulate_trades(df, cfg)
    conditions = condition_frame(df).astype(str)
    if cfg.price_action != "off":
        import price_action_features as pa
        pa_frame = pa.price_action_conditions(df, cfg.htf_factor).astype(str)
        conditions = pa_frame if cfg.price_action == "only" else pd.concat([conditions, pa_frame], axis=1)
    if cfg.time_features:
        stamps = pd.to_datetime(df["timestamp"], utc=True)
        hour = stamps.dt.hour
        conditions["session"] = np.select([hour < 7, hour < 12, hour < 16, hour < 21], ["asia_night", "europe_morning", "europe_us_overlap", "us_afternoon"], "late_us")
        conditions["weekday"] = stamps.dt.day_name().str.lower().to_numpy()
    usable = np.arange(n) >= WARMUP_BARS
    train_end = WARMUP_BARS + int((n - WARMUP_BARS) * cfg.train_frac)
    valid_end = train_end + int((n - WARMUP_BARS) * cfg.valid_frac)
    gap = cfg.horizon  # purge so no trade straddles two segments
    segments = {
        "train": (np.arange(n) >= WARMUP_BARS) & (np.arange(n) < train_end - gap),
        "valid": (np.arange(n) >= train_end) & (np.arange(n) < valid_end - gap),
        "test": (np.arange(n) >= valid_end) & (np.arange(n) < n),
    }
    # What buying (or selling) on EVERY candle earns in each segment. A rule must beat this, so a
    # market that simply drifts one way cannot make every rule look clever.
    baseline = {
        (side, name): float(np.nanmean(trades[f"{side}_ret"].to_numpy()[usable & seg]))
        for side in ("buy", "sell") for name, seg in segments.items()
    }
    tried = 0
    kept: list[dict] = []
    for feature, condition, mask in hypotheses(conditions):
        mask = mask & usable
        for side in ("buy", "sell"):
            tried += 1
            ret = trades[f"{side}_ret"].to_numpy()
            tr = segment_stats(ret[mask & segments["train"]])
            if tr["n"] < cfg.min_train or tr["expectancy"] <= 0 or tr["win_rate"] < cfg.min_train_win:
                continue
            if tr["expectancy"] <= baseline[(side, "train")]:
                continue
            kept.append({"feature": feature, "condition": condition, "side": side, "mask": mask, "train": tr,
                         "score": (tr["expectancy"] - baseline[(side, "train")]) * math.sqrt(tr["n"])})
    kept.sort(key=lambda row: row["score"], reverse=True)
    rows = []
    for row in kept[: cfg.keep_top]:
        ret = trades[f"{row['side']}_ret"].to_numpy()
        va = segment_stats(ret[row["mask"] & segments["valid"]])
        if va["n"] < cfg.min_valid or va["expectancy"] <= 0 or va["win_rate"] < cfg.min_valid_win:
            continue
        if va["expectancy"] <= baseline[(row["side"], "valid")]:
            continue
        te = segment_stats(ret[row["mask"] & segments["test"]])
        passed = te["n"] >= cfg.min_test and te["expectancy"] > 0 and te["expectancy"] > baseline[(row["side"], "test")]
        rows.append({
            "feature": row["feature"], "condition": row["condition"], "side": row["side"],
            "train_n": row["train"]["n"], "train_win": row["train"]["win_rate"], "train_exp": row["train"]["expectancy"],
            "valid_n": va["n"], "valid_win": va["win_rate"], "valid_exp": va["expectancy"],
            "test_n": te["n"], "test_wins": te["wins"], "test_win": te["win_rate"], "test_exp": te["expectancy"],
            "test_pf": te["profit_factor"], "test_baseline": baseline[(row["side"], "test")], "test_win_lower": wilson_lower(te["wins"], te["n"]), "final_pass": passed,
        })
    return pd.DataFrame(rows), tried


def shuffle_bars(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Same candles in random order: keeps every bar's shape, destroys any time pattern."""
    close = df["close"].to_numpy(float)
    prev = np.r_[close[0], close[:-1]]
    rel = np.column_stack([df["open"] / prev, df["high"] / prev, df["low"] / prev, df["close"] / prev])[1:]
    rel = rel[rng.permutation(len(rel))]
    levels = close[0] * np.cumprod(rel[:, 3])
    prev_levels = np.r_[close[0], levels[:-1]]
    out = df.iloc[1:].copy().reset_index(drop=True)
    out["open"] = rel[:, 0] * prev_levels
    out["high"] = rel[:, 1] * prev_levels
    out["low"] = rel[:, 2] * prev_levels
    out["close"] = levels
    return out


def load_history(data_dir: Path, symbol: str, timeframe: str) -> pd.DataFrame | None:
    for name in (f"deriv_{symbol}_{timeframe}.csv", f"{symbol}_{timeframe}.csv"):
        path = data_dir / name
        if path.exists():
            return load_ohlcv_csv(path)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data-dir", default="outputs/history")
    parser.add_argument("--symbols", nargs="+", default=["CRASH300N", "BOOM300N"])
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--null-runs", type=int, default=20)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out-dir", default="outputs")
    parser.add_argument("--min-bars", type=int, default=2500, help="skip symbols with less history than this")
    parser.add_argument("--cost", type=float, default=SearchConfig.cost, help="round-trip cost as a fraction of price (0.001 = 0.1%%)")
    parser.add_argument("--sl-slippage", type=float, default=SearchConfig.sl_slippage)
    parser.add_argument("--cost-map", default="", help="per-symbol costs, e.g. frxEURUSD=0.0003,cryBTCUSD=0.0015 (others use --cost)")
    parser.add_argument("--time-features", action="store_true", help="also search trading-session and weekday conditions (real markets)")
    parser.add_argument("--price-action", choices=["off", "add", "only"], default="off", help="search trendline, structure, candle, fair-value-gap, order-block and higher-timeframe conditions")
    parser.add_argument("--htf-factor", type=int, default=12, help="candles per higher-timeframe block")
    parser.add_argument("--tag", default="", help="suffix for the output file names, e.g. markets")
    args = parser.parse_args()
    cfg = SearchConfig(cost=args.cost, sl_slippage=args.sl_slippage, time_features=args.time_features, price_action=args.price_action, htf_factor=args.htf_factor)
    tag = f"_{args.tag}" if args.tag else ""
    cost_map = {}
    for part in filter(None, (item.strip() for item in args.cost_map.split(","))):
        name, _, value = part.partition("=")
        cost_map[name.strip()] = float(value)
    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    real_rows = []
    report = ["# Walk-forward rule search", ""]
    for symbol in args.symbols:
        df = load_history(data_dir, symbol, args.timeframe)
        if df is None or len(df) < args.min_bars:
            have = 0 if df is None else len(df)
            report.append(f"- **{symbol}**: skipped, only {have} candles (needs {args.min_bars}). Run work/download_history.py first.")
            continue
        symbol_cfg = replace(cfg, cost=cost_map.get(symbol, cfg.cost))
        found, tried = run_protocol(df, symbol_cfg)
        passes = int(found["final_pass"].sum()) if not found.empty else 0
        null_counts = []
        for _ in range(args.null_runs):
            null_found, _t = run_protocol(shuffle_bars(df, rng), symbol_cfg)
            null_counts.append(int(null_found["final_pass"].sum()) if not null_found.empty else 0)
        null_mean = float(np.mean(null_counts)) if null_counts else float("nan")
        p_value = (sum(1 for c in null_counts if c >= passes) + 1) / (len(null_counts) + 1) if null_counts else float("nan")
        days = (df["timestamp"].iloc[-1] - df["timestamp"].iloc[0]).days
        report += [
            f"## {symbol} {args.timeframe}: {len(df)} candles, {days} days",
            f"- cost charged: {symbol_cfg.cost:.3%} per trade (plus {symbol_cfg.sl_slippage:.0%} extra on stop-outs)",
            f"- hypotheses tried (rule x side): {tried}",
            f"- survived train and validation, then judged on test: {0 if found.empty else len(found)}",
            f"- **passed the final test: {passes}**",
            f"- shuffled-data runs ({args.null_runs}): average {null_mean:.2f} passes per run, "
            f"worst {max(null_counts) if null_counts else 'n/a'}; chance of doing this well by luck: **{p_value:.2f}**",
            "",
        ]
        if not found.empty:
            found.insert(0, "symbol", symbol)
            found.insert(1, "timeframe", args.timeframe)
            real_rows.append(found)
    results = pd.concat(real_rows, ignore_index=True) if real_rows else pd.DataFrame()
    if not results.empty:
        results.to_csv(out_dir / f"walkforward_all_survivors{tag}.csv", index=False)
        winners = results[results["final_pass"]].copy().reset_index(drop=True)
    else:
        winners = pd.DataFrame()
    rules = pd.DataFrame(columns=["rule_id", "symbol", "timeframe", "suggested_side", "feature", "condition", "trades", "total_return",
                                  "win_rate", "profit_factor", "expectancy", "symbol_rule_rank", "promotion_status"])
    if not winners.empty:
        oos_n = winners["valid_n"] + winners["test_n"]
        oos_wins = (winners["valid_win"] * winners["valid_n"] + winners["test_win"] * winners["test_n"]) / oos_n
        rules = pd.DataFrame({
            "rule_id": [f"WF{i + 1:03d}" for i in range(len(winners))],
            "symbol": winners["symbol"], "timeframe": winners["timeframe"], "suggested_side": winners["side"],
            "feature": winners["feature"], "condition": winners["condition"], "trades": oos_n,
            "total_return": winners["test_exp"] * winners["test_n"], "win_rate": oos_wins.round(4),
            "profit_factor": winners["test_pf"], "expectancy": winners["test_exp"],
            "symbol_rule_rank": winners.groupby("symbol").cumcount() + 1, "promotion_status": "walkforward_candidate",
        })
    rules.to_csv(out_dir / f"walkforward_candidate_rules{tag}.csv", index=False)
    report += [
        "## How to read this",
        "- A rule only counts if it worked on the train period (first half), then the validation quarter, then the final test quarter, in that order.",
        "- 'Chance of doing this well by luck' near 0.05 or lower would be real evidence; 0.20 or higher means the search found nothing better than noise.",
        "- Passing rules are candidates for PAPER trading only. They must still earn their record on live candles.",
        f"- Price-action families searched: {cfg.price_action}.",
        "- Session and weekday conditions were included in the search." if cfg.time_features else "- Session and weekday conditions were not searched.",
    ]
    (out_dir / f"walkforward_report{tag}.md").write_text("\n".join(report) + "\n")
    print("\n".join(report))
    print(f"\nCandidate rules written: {len(rules)} -> {out_dir / f'walkforward_candidate_rules{tag}.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
