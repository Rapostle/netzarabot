import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "work"))
import options_test as O  # noqa: E402


def walk(n=6000, seed=1, vol=0.001):
    rng = np.random.default_rng(seed)
    c = 100 * np.cumprod(1 + rng.normal(0, vol, n))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + abs(rng.normal(0, vol / 3, n)))
    l = np.minimum(o, c) * (1 - abs(rng.normal(0, vol / 3, n)))
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c})


class Tests(unittest.TestCase):
    def test_no_signal_costs_exactly_the_margin(self):
        df = walk()
        a = O.atr(df)
        ok, up, dn = O.outcomes(df, a, "rise_fall", 3)
        p0 = up[ok].mean()
        pnl = up * (1 - 0.05) / p0 - 1
        self.assertAlmostEqual(pnl[ok].mean(), -0.05, places=9)

    def test_rules_do_not_look_ahead(self):
        df = walk()
        a = O.atr(df)
        full = O.rule_sides(df, a)
        cut = df.iloc[:4000].reset_index(drop=True)
        part = O.rule_sides(cut, O.atr(cut))
        for k in full:
            np.testing.assert_array_equal(full[k][:4000], part[k], err_msg=k)

    def test_shuffle_keeps_size_shape_and_continuity(self):
        df = walk(500)
        sh = O.shuffle_candles(df, np.random.default_rng(2))
        self.assertEqual(len(sh), len(df) - 1)
        self.assertTrue((sh["high"] >= sh[["open", "close"]].max(axis=1) - 1e-9).all())
        self.assertTrue((sh["low"] <= sh[["open", "close"]].min(axis=1) + 1e-9).all())

    def test_random_walk_has_no_edge_after_the_margin(self):
        res = O.evaluate({"A": walk(5000, 1), "B": walk(5000, 2)}, 0.05, null_runs=12)
        for r in res["rows"]:
            if r["rule"]:
                self.assertLess(r["pnl"], 0.02, r)       # nothing close to profitable

    def test_a_planted_pattern_is_found(self):
        rng = np.random.default_rng(5)
        n = 8000
        r = np.zeros(n)
        for i in range(1, n):
            r[i] = 0.6 * r[i - 1] + rng.normal(0, 0.001)    # momentum: each move tends to continue
        c = 100 * np.cumprod(1 + r)
        o = np.r_[c[0], c[:-1]]
        df = pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.0002, "low": np.minimum(o, c) * 0.9998, "close": c})
        res = O.evaluate({"A": df}, 0.05, null_runs=10)
        rf = [x for x in res["rows"] if x["family"] == "rise_fall" and x["n"] == 1][0]
        self.assertIn(rf["rule"], ("follow_1", "follow_3", "follow_12", "breakout_follow"))   # a continuation rule wins
        self.assertGreater(rf["pnl"], 0.05)
        self.assertLessEqual(rf["luck"], 0.1)

    def test_digits_random_looks_random_and_planted_repeat_is_caught(self):
        rng = np.random.default_rng(3)
        ok = O.digits_report(rng.integers(0, 10, 5000))
        self.assertGreater(ok["p_uniform"], 0.01)
        self.assertGreater(ok["p_worst_cell"], 0.05)
        d = rng.integers(0, 10, 5000)
        for i in range(1, 5000):
            if rng.random() < 0.3:
                d[i] = d[i - 1]
        bad = O.digits_report(d)
        self.assertLess(bad["p_worst_cell"], 0.001)
        self.assertGreater(bad["repeat_z"], 10)

    def test_chi2_sf_matches_known_values(self):
        self.assertAlmostEqual(O.chi2_sf(16.919, 9), 0.05, places=3)
        self.assertAlmostEqual(O.chi2_sf(9.0, 9), 0.4372, places=3)


class PairTests(unittest.TestCase):
    def test_pair_report_counts_and_flags_a_planted_pair(self):
        rng = np.random.default_rng(8)
        d = rng.integers(0, 10, 20000)
        for i in range(1, len(d)):
            if d[i - 1] == 2 and rng.random() < 0.3:
                d[i] = 3
        r = O.pair_report(d, 2, 3)
        self.assertGreater(r["rate"], 0.2)
        self.assertLess(r["p_one_sided"], 0.001)
        fair = O.pair_report(rng.integers(0, 10, 20000), 2, 3)
        self.assertGreater(fair["p_one_sided"], 0.001)
        self.assertEqual(fair["n"], int((fair["n"])))
