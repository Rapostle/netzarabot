import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "work"))
import pairs_test as T  # noqa: E402


class Tests(unittest.TestCase):
    def test_mean_reverting_spread_makes_money_and_a_random_walk_does_not(self):
        rng = np.random.default_rng(3)
        n = 3000
        ou = np.zeros(n)
        for i in range(1, n):
            ou[i] = ou[i - 1] * 0.8 + rng.normal(0, 0.05)
        g = np.array(T.trades(ou))
        self.assertGreater(len(g), 20)
        self.assertGreater(g.mean(), 0)
        rw = np.cumsum(rng.normal(0, 0.05, n))
        self.assertLess(np.mean(T.trades(rw)), g.mean())

    def test_no_lookahead(self):
        rng = np.random.default_rng(4)
        sp = np.cumsum(rng.normal(0, 0.05, 2000))
        full = T.trades(sp)
        part = T.trades(sp[:1500])
        self.assertEqual(full[:len(part) - 3], part[:len(part) - 3])

    def test_cost_is_subtracted_per_trade(self):
        rng = np.random.default_rng(5)
        sp = np.cumsum(rng.normal(0, 0.05, 1500))
        a, b = T.trades(sp, 0.0), T.trades(sp, 0.004)
        self.assertEqual(len(a), len(b))
        self.assertTrue(np.allclose(np.array(a) - 0.004, b))


if __name__ == "__main__":
    unittest.main()
