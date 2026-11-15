import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "work"))
import daily_trend_test as dt  # noqa: E402


def series(n=3000, phi=0.0, seed=1, drift=0.0):
    rng = np.random.default_rng(seed)
    shocks = rng.normal(drift, 0.01, n)
    ret = np.zeros(n)
    for i in range(1, n):
        ret[i] = phi * ret[i - 1] + shocks[i]
    idx = pd.date_range("2014-01-01", periods=n, freq="D", tz="UTC")
    return pd.Series(100 * np.cumprod(1 + ret), index=idx)


class StrategyTests(unittest.TestCase):
    def test_signal_is_applied_next_day_and_costs_charged(self):
        close = pd.Series(np.linspace(100, 200, 400), index=pd.date_range("2020-01-01", periods=400, freq="D", tz="UTC"))
        free = dt.strategy_returns(close, "momentum_20", 0.0, 0.0)
        costly = dt.strategy_returns(close, "momentum_20", 0.001, 0.0005)
        self.assertGreater(free.sum(), 0)
        self.assertLess(costly.sum(), free.sum())
        self.assertEqual(free.iloc[:20].abs().sum(), 0.0)  # no position before the lookback exists

    def test_short_position_profits_in_a_falling_market(self):
        close = pd.Series(np.linspace(200, 100, 400), index=pd.date_range("2020-01-01", periods=400, freq="D", tz="UTC"))
        self.assertGreater(dt.strategy_returns(close, "momentum_60", 0.0, 0.0).sum(), 0)

    def test_benjamini_hochberg(self):
        p = np.array([0.001, 0.009, 0.04, 0.2, 0.9])
        self.assertEqual(dt.benjamini_hochberg(p, 0.10).tolist(), [True, True, True, False, False])
        self.assertEqual(dt.benjamini_hochberg(np.array([0.5, 0.8]), 0.10).tolist(), [False, False])

    def test_shuffle_keeps_length_and_start(self):
        s = series()
        sh = dt.shuffled_close(s, np.random.default_rng(1))
        self.assertEqual(len(sh), len(s))
        self.assertAlmostEqual(sh.iloc[0], s.iloc[0])


class FindingTests(unittest.TestCase):
    def test_trending_market_is_detected_and_random_is_not(self):
        rng = np.random.default_rng(3)
        trending = dt.evaluate_market("T", series(phi=0.12), 0.0005, 0.0001, 60, rng)
        random_ = dt.evaluate_market("R", series(phi=0.0, seed=9), 0.0005, 0.0001, 60, rng)
        best_trend = min(r["p_luck"] for r in trending if r["rule"].startswith(("momentum", "ma_cross", "breakout")))
        self.assertLess(best_trend, 0.05)
        table = pd.DataFrame(random_)
        self.assertLessEqual(int((table["p_luck"] <= 0.05).sum()), 3)

    def test_cli_writes_report_and_skips_short_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "h"
            data.mkdir()
            for name, n in (("LONG", 1500), ("SHORT", 200)):
                s = series(n=n, seed=4)
                pd.DataFrame({"timestamp": (s.index.astype("int64") // 10**9), "open": s.values, "high": s.values, "low": s.values,
                              "close": s.values}).to_csv(data / f"deriv_{name}_1d.csv", index=False)
            argv = sys.argv
            sys.argv = ["x", "--data-dir", str(data), "--symbols", "LONG", "SHORT", "--null-runs", "20", "--out-dir", str(Path(tmp) / "o"),
                        "--cost-map", "LONG=0.0002"]
            try:
                self.assertEqual(dt.main(), 0)
            finally:
                sys.argv = argv
            report = (Path(tmp) / "o" / "daily_trend_report.md").read_text()
            self.assertIn("SHORT: skipped", report)
            self.assertIn("total tests: 9", report)
            self.assertTrue((Path(tmp) / "o" / "daily_trend_results.csv").exists())


if __name__ == "__main__":
    unittest.main()
