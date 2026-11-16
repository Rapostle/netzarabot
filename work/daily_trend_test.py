"""Do classic slow strategies work on years of daily candles? A fair, shuffled-data test.

A fixed list of well-known rules (nothing tuned to this data) is run on each market:
time-series momentum, moving-average crossovers, channel breakouts and one mean-reversion rule.
A position is held until the signal flips; costs are charged on every position change and a
small financing charge for every day a position is held.

Each (market, rule) result is compared with the same rule run on 200 shuffled copies of that
market's returns (same bars, random order, so any real trend or reversal pattern is destroyed).
With many markets and rules some always look good by luck, so p-values are corrected with
Benjamini-Hochberg before anything is called significant.

Read-only: it never trades.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BOT_ROOT = Path(os.environ.get("TRADING_BOT_ROOT", str(Path(__file__).resolve().parent.parent / "external" / "trading_bot")))
sys.path.insert(0, str(BOT_ROOT))

from trading_bot.data.loader import load_ohlcv_csv  # noqa: E402

MIN_DAYS = 800


def _sign(x: pd.Series) -> pd.Series:
    return np.sign(x).fillna(0.0)


def _donchian(close: pd.Series, n: int) -> pd.Series:
    high = close.shift(1).rolling(n).max()
    low = close.shift(1).rolling(n).min()
    raw = pd.Series(np.where(close > high, 1.0, np.where(close < low, -1.0, np.nan)), index=close.index)
    return raw.ffill().fillna(0.0)


def _mean_reversion(close: pd.Series) -> pd.Series:
    ret5 = close / close.shift(5) - 1.0
    z = (ret5 - ret5.rolling(60).mean()) / ret5.rolling(60).std()
    return pd.Series(np.where(z > 1.5, -1.0, np.where(z < -1.5, 1.0, 0.0)), index=close.index).where(z.notna(), 0.0)


RULES = {
    "momentum_20": lambda c: _sign(c / c.shift(20) - 1.0),
    "momentum_60": lambda c: _sign(c / c.shift(60) - 1.0),
    "momentum_120": lambda c: _sign(c / c.shift(120) - 1.0),
    "momentum_250": lambda c: _sign(c / c.shift(250) - 1.0),
    "ma_cross_20_100": lambda c: _sign(c.rolling(20).mean() - c.rolling(100).mean()),
    "ma_cross_50_200": lambda c: _sign(c.rolling(50).mean() - c.rolling(200).mean()),
    "breakout_20": lambda c: _donchian(c, 20),
    "breakout_55": lambda c: _donchian(c, 55),
    "mean_reversion_5": _mean_reversion,
}


def _consensus(close: pd.Series) -> pd.Series:
    """Trade only when most (5 or more) of the nine base rules agree; otherwise stay out."""
    votes = pd.concat([fn(close) for fn in BASE_RULES.values()], axis=1)
    longs, shorts = (votes > 0).sum(axis=1), (votes < 0).sum(axis=1)
    need = len(BASE_RULES) // 2 + 1
    return pd.Series(np.where(longs >= need, 1.0, np.where(shorts >= need, -1.0, 0.0)), index=close.index)


BASE_RULES = dict(RULES)
RULES["consensus"] = _consensus


def strategy_returns(close: pd.Series, rule: str, cost_one_way: float, hold_cost: float) -> pd.Series:
    """Daily net return: yesterday's signal decides today's position."""
    signal = RULES[rule](close)
    position = signal.shift(1).fillna(0.0)
    daily = close.pct_change().fillna(0.0)
    turnover = position.diff().abs().fillna(position.abs())
    return position * daily - turnover * cost_one_way - position.abs() * hold_cost


def sharpe(returns: pd.Series, periods_per_year: float) -> float:
    r = returns.dropna()
    if len(r) < 30 or r.std() == 0:
        return 0.0
    return float(r.mean() / r.std() * np.sqrt(periods_per_year))


def shuffled_close(close: pd.Series, rng: np.random.Generator) -> pd.Series:
    ret = close.pct_change().dropna().to_numpy()
    ret = ret[rng.permutation(len(ret))]
    return pd.Series(close.iloc[0] * np.cumprod(np.r_[1.0, 1.0 + ret]), index=close.index)


def benjamini_hochberg(p: np.ndarray, q: float = 0.10) -> np.ndarray:
    n = len(p)
    order = np.argsort(p)
    passed = np.zeros(n, dtype=bool)
    threshold = 0
    for rank, idx in enumerate(order, start=1):
        if p[idx] <= q * rank / n:
            threshold = rank
    passed[order[:threshold]] = True
    return passed


def load_daily(data_dir: Path, symbol: str) -> pd.Series | None:
    path = data_dir / f"deriv_{symbol}_1d.csv"
    if not path.exists():
        return None
    df = load_ohlcv_csv(path)
    close = df.set_index("timestamp")["close"].astype(float)
    close = close[~close.index.duplicated(keep="last")].sort_index()
    return close[close > 0]


def evaluate_market(symbol: str, close: pd.Series, cost_round_trip: float, hold_cost: float, null_runs: int, rng: np.random.Generator) -> list[dict]:
    years = (close.index[-1] - close.index[0]).days / 365.25
    ppy = len(close) / years if years > 0 else 252.0
    half = len(close) // 2
    rows = []
    nulls = {rule: [] for rule in RULES}
    for _ in range(null_runs):
        fake = shuffled_close(close, rng)
        for rule in RULES:
            nulls[rule].append(sharpe(strategy_returns(fake, rule, cost_round_trip / 2, hold_cost), ppy))
    buy_hold = sharpe(close.pct_change().fillna(0.0), ppy)
    for rule in RULES:
        net = strategy_returns(close, rule, cost_round_trip / 2, hold_cost)
        real = sharpe(net, ppy)
        p = (sum(1 for value in nulls[rule] if value >= real) + 1) / (null_runs + 1)
        rows.append({"symbol": symbol, "rule": rule, "years": round(years, 1), "net_sharpe": round(real, 2),
                     "first_half": round(sharpe(net.iloc[:half], ppy), 2), "second_half": round(sharpe(net.iloc[half:], ppy), 2),
                     "total_return_pct": round(float((1 + net).prod() - 1) * 100, 1), "buy_hold_sharpe": round(buy_hold, 2),
                     "p_luck": round(p, 3)})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data-dir", default="outputs/history")
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--cost", type=float, default=0.0005, help="round-trip cost as a fraction of price")
    parser.add_argument("--cost-map", default="", help="per-symbol round-trip costs, e.g. frxEURUSD=0.0003,cryBTCUSD=0.0015")
    parser.add_argument("--hold-cost", type=float, default=0.0001, help="financing charge per day a position is held (fraction of price)")
    parser.add_argument("--null-runs", type=int, default=200)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--out-dir", default="outputs")
    args = parser.parse_args()
    cost_map = {}
    for part in filter(None, (item.strip() for item in args.cost_map.split(","))):
        name, _, value = part.partition("=")
        cost_map[name.strip()] = float(value)
    rng = np.random.default_rng(args.seed)
    rows: list[dict] = []
    notes: list[str] = []
    for symbol in args.symbols:
        close = load_daily(Path(args.data_dir), symbol)
        if close is None or len(close) < MIN_DAYS:
            notes.append(f"- {symbol}: skipped ({0 if close is None else len(close)} daily candles, needs {MIN_DAYS})")
            continue
        rows.extend(evaluate_market(symbol, close, cost_map.get(symbol, args.cost), args.hold_cost, args.null_runs, rng))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not rows:
        print("No market had enough daily history.\n" + "\n".join(notes))
        return 1
    table = pd.DataFrame(rows)
    table["significant"] = benjamini_hochberg(table["p_luck"].to_numpy())
    table["persistent"] = (table["first_half"] > 0) & (table["second_half"] > 0) & (table["net_sharpe"] > 0)
    table.to_csv(out_dir / "daily_trend_results.csv", index=False)
    tested = len(table)
    lucky_expected = 0.05 * tested
    below_05 = int((table["p_luck"] <= 0.05).sum())
    good = table[table["significant"] & table["persistent"]]
    per_rule = table.groupby("rule").agg(markets_positive=("net_sharpe", lambda s: int((s > 0).sum())), markets=("net_sharpe", "size"),
                                         average_sharpe=("net_sharpe", "mean")).round(2)
    lines = [
        "# Daily-candle test of classic strategies", "",
        f"- markets tested: {table['symbol'].nunique()}, rules per market: {len(RULES)}, total tests: {tested}",
        f"- results with a luck chance of 5% or less: {below_05} (about {lucky_expected:.1f} expected from luck alone)",
        f"- **still significant after the multiple-testing correction AND positive in both halves of history: {len(good)}**",
        f"- shuffled copies per test: {args.null_runs}; financing {args.hold_cost:.4%} per held day", "",
        "## Best results (net Sharpe ratio after costs; above about 0.5 is decent, buy_hold_sharpe is simply holding the market)",
        table.sort_values("net_sharpe", ascending=False).head(12).to_string(index=False), "",
        "## Each rule across markets", per_rule.to_string(), "",
    ]
    if len(good):
        lines += ["## Survivors", good.to_string(index=False), ""]
    lines += notes
    report = "\n".join(lines)
    (out_dir / "daily_trend_report.md").write_text(report + "\n")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
