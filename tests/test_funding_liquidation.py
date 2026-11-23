import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "work"))
import funding_liquidation as F  # noqa: E402


def frame(close, high=None):
    close = np.asarray(close, float)
    high = close if high is None else np.asarray(high, float)
    return pd.DataFrame({"close": close, "high": high}, index=pd.date_range("2024-01-01", periods=len(close), freq="D", tz="UTC"))


class Tests(unittest.TestCase):
    def test_flat_market_never_liquidates(self):
        t = F.liquidation_table(frame([100.0] * 500))
        for lev in F.LEVERAGES:
            self.assertEqual(t[lev][30], 0.0)

    def test_spike_liquidates_high_leverage_only(self):
        close = [100.0] * 100
        high = list(close)
        high[50] = 130.0  # a 30% spike
        t = F.liquidation_table(frame(close, high), windows=(30,))
        self.assertGreater(t[5][30], 0)       # 5x trigger = 19.5%
        self.assertEqual(t[3][30], 0.0)       # 3x trigger = 32.8%, above the 30% spike
        self.assertEqual(t[1][30], 0.0)

    def test_trigger_formula(self):
        t = F.liquidation_table(frame([100.0] * 60), windows=(30,))
        self.assertAlmostEqual(t[2]["trigger"], 0.5 - F.MMR)
