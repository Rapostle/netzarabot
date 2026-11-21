import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "work"))
import book_levels_test as L  # noqa: E402


def walk(n=30000, seed=5):
    rng = np.random.default_rng(seed)
    c = 100 + np.cumsum(rng.normal(0, 0.1, n))
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"time": pd.date_range("2026-01-01", periods=n, freq="5min"), "open": o,
                         "high": np.maximum(o, c) + 0.05, "low": np.minimum(o, c) - 0.05, "close": c, "volume": 1})


class NoLookahead(unittest.TestCase):
    def test_signals_do_not_depend_on_the_future(self):
        df = walk()
        cut = 24000
        for rule, fn in L.FINDERS.items():
            full = [s for s in fn(df) if s[0] < cut - 2]
            part = [s for s in fn(df.iloc[:cut].reset_index(drop=True)) if s[0] < cut - 2]
            self.assertEqual(full, part, rule)


class Ocl(unittest.TestCase):
    def test_two_bearish_candles_give_a_sell_at_the_second_open(self):
        # 40 flat hours, then two bearish 1-hour candles (second opens at the first's close), then price returns to the level
        rows, p = [], 100.0
        def hour(o_, c_, pts=12):
            path = np.linspace(o_, c_, pts + 1)
            for i in range(pts):
                rows.append((path[i], max(path[i], path[i + 1]) + 0.02, min(path[i], path[i + 1]) - 0.02, path[i + 1]))
        for k in range(40):
            hour(100 + (0.3 if k % 2 else -0.3), 100 + (-0.3 if k % 2 else 0.3))
        hour(100, 98); hour(98, 96)                 # two bearish bodies, level = 98
        hour(96, 98.5)                              # price returns up through 98
        for _ in range(10):
            hour(98.5, 98.4)
        df = pd.DataFrame(rows, columns=["open", "high", "low", "close"])
        df["time"] = pd.date_range("2026-01-01", periods=len(df), freq="5min"); df["volume"] = 1
        sig = L.ocl(df)
        sells = [s for s in sig if s[1] == -1 and abs(s[2] - 98.0) < 1e-6]
        self.assertTrue(sells, sig)
        self.assertGreater(sells[0][3], sells[0][2])   # stop above entry for a sell
        self.assertLess(sells[0][4], sells[0][2])      # target below


if __name__ == "__main__":
    unittest.main()
