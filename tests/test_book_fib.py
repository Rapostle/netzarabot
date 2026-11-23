import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "work"))
import book_fib_test as F  # noqa: E402


def walk(n=40000, seed=5):
    rng = np.random.default_rng(seed)
    c = 100 + np.cumsum(rng.normal(0, 0.1, n))
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"time": pd.date_range("2026-01-01", periods=n, freq="5min"), "open": o,
                         "high": np.maximum(o, c) + 0.05, "low": np.minimum(o, c) - 0.05, "close": c, "volume": 1})


class Tests(unittest.TestCase):
    def test_no_lookahead(self):
        df = walk()
        cut = 32000
        for name, ratio in F.RATIOS.items():
            full = [s for s in F.fib_signals(df, ratio) if s[0] < cut - 2]
            part = [s for s in F.fib_signals(df.iloc[:cut].reset_index(drop=True), ratio) if s[0] < cut - 2]
            self.assertEqual(full, part, name)

    def test_geometry(self):
        df = walk()
        sigs = F.fib_signals(df, 0.618)
        self.assertTrue(sigs)
        for t, side, entry, stop, target in sigs:
            self.assertGreater(side * (entry - stop), 0)      # stop on the losing side
            self.assertGreater(side * (target - entry), 0)    # target on the winning side


if __name__ == "__main__":
    unittest.main()
