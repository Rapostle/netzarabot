import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "work"))
import pairs_wide_test as W  # noqa: E402


def coin(seed, n=1500, link=None):
    rng = np.random.default_rng(seed)
    r = rng.normal(0, 0.02, n)
    idx = pd.date_range("2018-01-01", periods=n, freq="D", tz="UTC")
    return pd.Series(100 * np.cumprod(1 + r), index=idx)


class Tests(unittest.TestCase):
    def test_all_pairs_are_built(self):
        sp = W.build_spreads({k: coin(i) for i, k in enumerate("ABCD")})
        self.assertEqual(len(sp), 6)

    def test_random_coins_do_not_beat_their_shuffles(self):
        sp = W.build_spreads({k: coin(i) for i, k in enumerate("ABCDE")})
        r = W.evaluate(sp, null_runs=40)
        self.assertEqual(r["pairs"], 10)
        self.assertGreater(r["pool_luck"], 0.05)
        self.assertGreater(r["best_luck"], 0.05)

    def test_a_planted_mean_reverting_pair_is_found(self):
        rng = np.random.default_rng(3)
        n = 1500
        ou = np.zeros(n)
        for i in range(1, n):
            ou[i] = ou[i - 1] * 0.8 + rng.normal(0, 0.05)
        idx = pd.date_range("2018-01-01", periods=n, freq="D", tz="UTC")
        base = pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.02, n)), index=idx)
        r = W.evaluate(W.build_spreads({"A": base * np.exp(ou), "B": base}), null_runs=40)
        self.assertGreater(r["gross"], 0)
        self.assertLessEqual(r["best_luck"], 0.05)

    def test_render_has_both_luck_lines(self):
        sp = W.build_spreads({k: coin(i) for i, k in enumerate("ABC")})
        text = W.render(W.evaluate(sp, null_runs=10))
        self.assertIn("pooled vs shuffles", text)
        self.assertIn("best pair", text)
