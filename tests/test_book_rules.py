import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "work"))
sys.path.insert(0, str(ROOT / "external" / "trading_bot"))
sys.path.insert(0, str(ROOT / "tests"))
import book_rules_test as br  # noqa: E402
from test_sniper_test import rw  # noqa: E402


def triangle_then_breakout(up=True, noise=0.0, seed=1):
    """Hourly closes that oscillate inside converging lines, then break out; each hour expanded to 12 five-minute candles."""
    rng = np.random.default_rng(seed)
    n_h = 130
    j = np.arange(n_h)
    amp = 6.0 * np.clip(1 - j / 130.0, 0.25, 1)
    closes = 100 + amp * np.sin(2 * np.pi * j / 12)
    tail = 102.7 + 1.0 * np.arange(n_h - 100) if up else 97.3 - 1.0 * np.arange(n_h - 100)
    tail[1] = tail[0] - 0.4 if up else tail[0] + 0.4     # a pullback right after the break, as the strategy waits for
    closes[100:] = tail
    path = [closes[0]]
    for k in range(1, n_h):
        path.extend(np.linspace(closes[k - 1], closes[k], 13)[1:])
    c = np.array(path)
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + 0.05 + abs(rng.normal(0, noise, len(c)))
    l = np.minimum(o, c) - 0.05 - abs(rng.normal(0, noise, len(c)))
    return pd.DataFrame({"timestamp": pd.date_range("2026-01-01", periods=len(c), freq="5min", tz="UTC"), "open": o, "high": h, "low": l, "close": c, "volume": 0})


class BookRuleTests(unittest.TestCase):
    def test_stochastic_stays_between_0_and_100(self):
        df = rw(3000)
        k = br.slow_stochastic(df["high"], df["low"], df["close"])
        ok = k[np.isfinite(k)]
        self.assertGreater(len(ok), 100)
        self.assertTrue(((ok >= 0) & (ok <= 100)).all())

    def test_signals_never_use_the_future(self):
        df = rw(12000, seed=5)
        for rule in br.RULES:
            full = br.find_signals(df, rule)
            self.assertGreater(len(full), 0, rule)
            cut = 8000
            part = br.find_signals(df.iloc[:cut].reset_index(drop=True), rule)
            early_full = [s for s in full if s[0] < cut - 120]
            early_part = [s for s in part if s[0] < cut - 120]
            self.assertEqual([tuple(np.round(s, 8)) for s in early_full], [tuple(np.round(s, 8)) for s in early_part], rule)

    def test_dtf_stop_is_on_the_right_side_and_target_is_2r(self):
        for t, side, entry, stop, target in br.find_signals(rw(12000, seed=6), "dtf"):
            self.assertGreater(side * (entry - stop), 0)
            self.assertAlmostEqual(side * (target - entry), br.DTF_REWARD * side * (entry - stop), places=6)

    def test_triangle_breakout_up_gives_a_buy_with_stop_inside_the_pattern(self):
        df = triangle_then_breakout(up=True)
        sigs = br.find_signals(df, "tri_height")
        self.assertTrue(sigs and all(s[1] == 1 for s in sigs))
        for t, side, entry, stop, target in sigs:
            self.assertLess(stop, entry)
            self.assertGreater(target, entry)

    def test_triangle_breakout_down_gives_a_sell(self):
        sigs = br.find_signals(triangle_then_breakout(up=False), "tri_3r")
        self.assertTrue(sigs and all(s[1] == -1 for s in sigs))
        for t, side, entry, stop, target in sigs:
            self.assertAlmostEqual(entry - target, br.FIXED_REWARD * (stop - entry), places=6)

    def test_simulate_stop_wins_a_tie_and_target_pays_r(self):
        base = pd.DataFrame({"open": [100.0] * 6, "high": [100.5] * 6, "low": [99.5] * 6, "close": [100.0] * 6})
        win = base.copy()
        win.loc[3, "high"] = 103.0
        t = br.simulate(win, [(1, 1, 100.0, 99.0, 102.0)])
        self.assertAlmostEqual(float(t["r"].iloc[0]), 2.0 - br.COST * 100.0 / 1.0, places=6)
        tie = base.copy()
        tie.loc[3, "high"], tie.loc[3, "low"] = 103.0, 98.0
        t = br.simulate(tie, [(1, 1, 100.0, 99.0, 102.0)])
        self.assertLess(float(t["r"].iloc[0]), -1.0)
        self.assertEqual(len(br.simulate(win, [(1, 1, 100.0, 99.0, 102.0), (2, 1, 100.0, 99.0, 102.0)])), 1)   # no overlapping trades


if __name__ == "__main__":
    unittest.main()
