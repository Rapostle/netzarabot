import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "work"))
sys.path.insert(0, str(ROOT / "external" / "trading_bot"))
import confirm_rule as cr  # noqa: E402
import walk_forward_rule_search as wf  # noqa: E402


class SpacedTests(unittest.TestCase):
    def test_overlapping_signals_are_skipped(self):
        mask = np.zeros(100, dtype=bool)
        mask[[30, 31, 35, 42, 43, 60]] = True
        ret = np.arange(100, dtype=float)
        idx, out = cr.spaced_returns(mask, ret, horizon=12, start=0)
        self.assertEqual(list(idx), [30, 42, 60])   # 31 and 35 fall inside the first trade, 43 inside the second
        self.assertEqual(list(out), [30.0, 42.0, 60.0])

    def test_start_and_nan_respected(self):
        mask = np.ones(50, dtype=bool)
        ret = np.full(50, np.nan)
        ret[20:] = 0.01
        idx, _ = cr.spaced_returns(mask, ret, horizon=5, start=10)
        self.assertEqual(idx[0], 20)

    def test_evaluate_runs_and_is_reproducible(self):
        rng = np.random.default_rng(2)
        n = 1500
        c = 100 * np.cumprod(1 + rng.normal(0, 0.01, n))
        o = np.r_[c[0], c[:-1]]
        df = pd.DataFrame({"timestamp": pd.date_range("2020-01-01", periods=n, freq="D", tz="UTC"), "open": o,
                           "high": np.maximum(o, c) * 1.004, "low": np.minimum(o, c) * 0.996, "close": c, "volume": 0})
        cfg = wf.SearchConfig(cost=0.002)
        a = cr.evaluate(df, cfg, "bos", "bos_up", "buy", 7)
        b = cr.evaluate(df, cfg, "bos", "bos_up", "buy", 7)
        self.assertEqual(a["n"], b["n"])
        self.assertGreater(a["n"], 0)
        p = cr.luck_chance(df, cfg, "bos", "bos_up", "buy", 7, a["mean"], runs=5, seed=1)
        self.assertTrue(0 < p <= 1)


if __name__ == "__main__":
    unittest.main()
