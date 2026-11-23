import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from checker import intraday, report  # noqa: E402


def walk(days=1500, seed=4):
    rng = np.random.default_rng(seed)
    n = 24 * days
    c = 100 + np.cumsum(rng.normal(0, 0.3, n))
    o = np.r_[c[0], c[:-1]]
    df = pd.DataFrame({"open": o, "high": np.maximum(o, c) + 0.2, "low": np.minimum(o, c) - 0.2, "close": c})
    df["ts"] = pd.date_range("2018-01-01", periods=n, freq="h", tz="UTC")
    return df


class IntradayTests(unittest.TestCase):
    def test_unknown_rule_rejected(self):
        with self.assertRaises(ValueError):
            intraday.run_intraday_check(walk(200), "nope")

    def test_too_few_trades_refused(self):
        res = intraday.run_intraday_check(walk(30), "judas", null_runs=5)
        self.assertEqual(res.verdict, intraday.V_REFUSED)
        self.assertIn("NOT ENOUGH", report.format_intraday_report(res))

    def test_random_walk_is_not_a_pass_and_costs_hurt(self):
        res = intraday.run_intraday_check(walk(), "wr", "TEST", null_runs=30)
        self.assertGreaterEqual(res.trades, intraday.MIN_TRADES)
        self.assertGreater(res.gross_r, res.net_r)
        self.assertNotEqual(res.verdict, intraday.V_PASS)
        text = report.format_intraday_report(res)
        self.assertIn(report.DISCLAIMER, text)
        self.assertNotIn("guaranteed", text.lower())

    def test_same_inputs_same_answer(self):
        a = intraday.run_intraday_check(walk(), "wr", null_runs=20).as_dict()
        b = intraday.run_intraday_check(walk(), "wr", null_runs=20).as_dict()
        self.assertEqual(a, b)
