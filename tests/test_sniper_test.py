import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "work"))
sys.path.insert(0, str(ROOT / "external" / "trading_bot"))
import sniper_test as sn  # noqa: E402


def rw(n=8000, seed=4, drift=0.0):
    rng = np.random.default_rng(seed)
    c = 1000 * np.cumprod(1 + rng.normal(drift, 0.0008, n))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.0004, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.0004, n)))
    return pd.DataFrame({"timestamp": pd.date_range("2026-01-01", periods=n, freq="5min", tz="UTC"), "open": o, "high": h, "low": l, "close": c, "volume": 0})


class SniperTests(unittest.TestCase):
    def test_four_hour_context_has_no_lookahead(self):
        df = rw(3000)
        full = sn.four_hour_context(df)
        for t in (1000, 1777, 2500):
            part = sn.four_hour_context(df.iloc[: t + 1].reset_index(drop=True))
            for a, b in zip(full, part):
                self.assertTrue(np.array_equal(a[t:t + 1], b[t:t + 1], equal_nan=True), f"4h context changed at {t}")

    def test_signals_follow_the_description(self):
        df = rw(9000)
        sigs = sn.find_signals(df)
        self.assertGreater(len(sigs), 0)
        ind = sn.wf.add_indicators(df).reset_index(drop=True)
        trend, _lo, _hi = sn.four_hour_context(ind)
        atr = ind["atr_14"].to_numpy(float)
        for t, side, entry, stop in sigs:
            self.assertEqual(np.sign(trend[t]), side)                  # both timeframes agree
            self.assertGreater(side * (entry - stop), 0)              # stop is on the losing side
            self.assertLessEqual(abs(entry - stop), sn.MAX_STOP_ATR * atr[t] + 1e-9)

    def test_simulation_target_stop_and_no_overlap(self):
        n = 200
        df = pd.DataFrame({"open": 100.0, "high": 100.2, "low": 99.8, "close": 100.0}, index=range(n))
        df.loc[11, "high"] = 104.0                                   # target (entry 100, stop 99 -> 3R = 103) hit on candle 11
        sigs = [(10, 1, 100.0, 99.0), (11, 1, 100.0, 99.0), (30, 1, 100.0, 99.0)]
        t = sn.simulate(df, sigs)
        self.assertEqual(list(t["i"]), [10, 30])                     # the second signal falls inside the first trade
        self.assertAlmostEqual(t["r"].iloc[0], sn.REWARD_R - sn.COST * 100.0 / 1.0, places=6)

    def test_stop_wins_when_both_touched_and_short_side(self):
        n = 100
        df = pd.DataFrame({"open": 100.0, "high": 100.2, "low": 99.8, "close": 100.0}, index=range(n))
        df.loc[11, ["high", "low"]] = [102.0, 96.0]                  # short: stop 101, target 97 -> both touched, stop first
        t = sn.simulate(df, [(10, -1, 100.0, 101.0)])
        self.assertAlmostEqual(t["r"].iloc[0], -1.0 - sn.SLIP - sn.COST * 100.0 / 1.0, places=6)

    def test_full_run_is_reproducible(self):
        df = rw(9000)
        a, b = sn.evaluate(df), sn.evaluate(df)
        self.assertTrue(a.equals(b))
        if len(a):
            p = sn.luck_chance(df, float(a["r"].mean()), runs=3, seed=1)
            self.assertTrue(0 < p <= 1)


if __name__ == "__main__":
    unittest.main()
