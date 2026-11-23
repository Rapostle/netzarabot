import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "work"))
import funding_carry_test as C  # noqa: E402


class Tests(unittest.TestCase):
    def test_always_on_is_the_sum_minus_one_round_trip(self):
        r = np.full(1000, 0.0001)
        self.assertAlmostEqual(C.always_on(r).sum(), 0.1 - C.ROUND_TRIP, places=9)

    def test_switch_enters_after_the_window_and_pays_half_each_way(self):
        r = np.full(1000, 0.0001)
        out = C.switch(r)
        self.assertAlmostEqual(out.sum(), 0.0001 * (1000 - C.SWITCH_WINDOW) - C.ROUND_TRIP, places=9)

    def test_switch_stays_out_when_funding_is_negative(self):
        r = np.full(500, -0.0001)
        self.assertEqual(C.switch(r).sum(), 0.0)

    def test_switch_uses_only_past_payments(self):
        r = np.r_[np.full(50, 0.0001), np.full(50, -0.0001)]
        a = C.switch(r)
        r2 = r.copy(); r2[60] = 5.0                  # a huge payment at k=60 must not change decisions up to k=60 (it is paid, not predicted)
        b = C.switch(r2)
        self.assertTrue(np.allclose(a[:60], b[:60]))

    def test_stats_drawdown(self):
        x = np.array([0.01, 0.01, -0.03, 0.01])
        self.assertAlmostEqual(C.stats(x)["max_dd"], 0.03, places=9)


if __name__ == "__main__":
    unittest.main()
