import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "work"))
import power_of_three_test as P  # noqa: E402


def walk(days=900, seed=4):
    rng = np.random.default_rng(seed)
    n = 24 * days
    c = 100 + np.cumsum(rng.normal(0, 0.3, n))
    o = np.r_[c[0], c[:-1]]
    df = pd.DataFrame({"open": o, "high": np.maximum(o, c) + 0.2, "low": np.minimum(o, c) - 0.2, "close": c})
    df["ts"] = pd.date_range("2022-01-01", periods=n, freq="h", tz="UTC")
    return df


class Tests(unittest.TestCase):
    def test_no_lookahead(self):
        df = walk()
        cut = 24 * 700
        for rule in P.RULES:
            _, full = P.signals(df, rule)
            _, part = P.signals(df.iloc[:cut].reset_index(drop=True), rule)
            full = [s for s in full if s[1] < cut - 24]
            part = [s for s in part if s[1] < cut - 24]
            self.assertEqual(full, part, rule)

    def test_stops_are_on_the_losing_side_and_exits_are_at_18(self):
        df = walk()
        for rule in P.RULES:
            _, sigs = P.signals(df, rule)
            self.assertTrue(sigs, rule)
            for ei, xi, side, entry, stop in sigs:
                self.assertGreater(side * (entry - stop), 0)
                self.assertEqual(xi % 24, P.EXIT_HOUR)
                self.assertLess(ei, xi)

    def test_day_shuffle_keeps_length_and_continuity(self):
        df = walk(days=200)
        sh = P.day_shuffle(df, np.random.default_rng(1))
        self.assertEqual(len(sh), len(df))
        o, c = sh["open"].to_numpy().reshape(-1, 24)[:, 0], sh["close"].to_numpy().reshape(-1, 24)[:, -1]
        self.assertTrue(np.allclose(o[1:], c[:-1]))
        self.assertTrue((sh["high"] >= sh[["open", "close"]].max(axis=1) - 1e-9).all())

    def test_gap_through_stop_fills_at_the_open(self):
        o = np.array([100, 100, 90.0, 90, 90]); h = np.array([100, 100, 91, 90, 90.0]); l = np.array([100, 99, 89, 90, 90.0])
        r, risk = P.run_trade(o, h, l, 1, 0, 100.0, 98.0, 4)    # long, stop 98, candle 2 opens at 90
        self.assertAlmostEqual(r, (90 - 100) / 2.0)


if __name__ == "__main__":
    unittest.main()
