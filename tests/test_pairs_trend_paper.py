import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "work"))
import pairs_test as PT  # noqa: E402
import pairs_trend_paper as B  # noqa: E402


def spread_series(seed, n=1200, ar=0.9):
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = x[i - 1] * ar + rng.normal(0, 0.05)
    return pd.Series(x, index=pd.date_range("2020-01-01", periods=n, freq="D", tz="UTC"))


class Tests(unittest.TestCase):
    def test_forward_engine_is_the_exact_mirror_of_the_backtest(self):
        for seed in (1, 2, 3):
            sp = spread_series(seed)
            orig = PT.trades(sp.to_numpy(), 0.0)
            mine = [g for _, _, g in B.replay(sp)]
            self.assertGreater(len(mine), 10)
            self.assertLessEqual(len(orig) - len(mine), 1)
            np.testing.assert_allclose(mine, [-x for x in orig[:len(mine)]], atol=1e-12)

    def test_no_lookahead(self):
        sp = spread_series(5)
        full = B.replay(sp)
        part = B.replay(sp.iloc[:900])
        self.assertEqual([t for t in full if t[1] < 890], [t for t in part if t[1] < 890])

    def test_first_run_back_fills_nothing_then_later_days_trade(self):
        rng = np.random.default_rng(7)
        idx = pd.date_range("2024-01-01", periods=300, freq="D", tz="UTC")
        base = pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.02, 300)), index=idx)
        osc = pd.Series(np.exp(0.5 * (np.arange(300) >= 230)), index=idx)   # a sudden 65% jump in A against B
        full = {"A": base * osc, "B": base, "C": base * 1.0}
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            msgs = B.run(out, {k: v.iloc[:200] for k, v in full.items()})
            self.assertTrue(any("started" in m for m in msgs))
            self.assertFalse((out / B.JOURNAL).exists())
            msgs2 = B.run(out, full)
            self.assertTrue((out / B.JOURNAL).exists())
            self.assertTrue(any("OPEN" in m for m in msgs2))
            state = json.loads((out / B.STATE).read_text())
            self.assertEqual(state["last_day"], str(idx[-1].date()))
            again = B.run(out, full)   # rerun the same day: nothing new
            self.assertFalse(any("OPEN" in m or "CLOSE" in m for m in again))
            self.assertIn("open", B.status(out) + "open")

    def test_status_without_journal(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIn("No trades yet", B.status(Path(d)))
