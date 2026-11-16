import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "work"))
import daily_trend_test as dtt  # noqa: E402
from checker import engine, layers as lay, report  # noqa: E402
from coinbot.paper import Book, Combo  # noqa: E402

NOW = datetime(2026, 11, 16, 0, 5, tzinfo=timezone.utc)


def px(returns):
    idx = pd.date_range(end="2026-11-16", periods=len(returns) + 1, freq="D", tz="UTC")
    return pd.Series(100 * np.cumprod(np.r_[1.0, 1.0 + np.asarray(returns)]), index=idx)


def regimes(seed, n=2500, drift=0.004, noise=0.02):
    rng = np.random.default_rng(seed)
    r, sign, left = np.zeros(n), 1.0, 0
    for i in range(n):
        if left == 0:
            sign, left = rng.choice([-1.0, 1.0]), int(rng.integers(50, 110))
        left -= 1
        r[i] = sign * drift + rng.normal(0, noise)
    return px(r)


class ConsensusTests(unittest.TestCase):
    def test_rule_is_registered_and_base_rules_are_nine(self):
        self.assertIn("consensus", engine.RULE_NAMES)
        self.assertEqual(len(dtt.BASE_RULES), 9)
        self.assertIn("consensus", report.RULE_TEXT)

    def test_all_agree_up_gives_long(self):
        self.assertEqual(float(dtt.RULES["consensus"](px(np.full(700, 0.01))).iloc[-1]), 1.0)

    def test_all_agree_down_gives_short(self):
        self.assertEqual(float(dtt.RULES["consensus"](px(np.full(700, -0.004))).iloc[-1]), -1.0)

    def test_split_vote_stays_out(self):
        close = px(np.random.default_rng(3).normal(0, 0.02, 800))
        signals = dtt.RULES["consensus"](close)
        votes = pd.concat([f(close) for f in dtt.BASE_RULES.values()], axis=1)
        agree = ((votes > 0).sum(axis=1) >= 5) | ((votes < 0).sum(axis=1) >= 5)
        self.assertTrue((signals[~agree] == 0).all())
        self.assertTrue((signals[agree] != 0).all())


class LayerTests(unittest.TestCase):
    def test_efficiency_ratio_straight_line_vs_zigzag(self):
        self.assertGreater(lay.efficiency_ratio(px(np.full(100, 0.01)), 30).iloc[-1], 0.99)
        zig = px(np.tile([0.02, -0.0196], 60))
        self.assertLess(lay.efficiency_ratio(zig, 30).iloc[-1], 0.1)

    def test_filter_flattens_choppy_market(self):
        zig = px(np.tile([0.02, -0.0196], 300))
        sig = pd.Series(1.0, index=zig.index)
        self.assertTrue((lay.filtered_signal(zig, sig, lay.Layers()).iloc[60:] == 0).all())

    def test_filter_keeps_trending_market(self):
        up = px(np.full(300, 0.01))
        sig = pd.Series(1.0, index=up.index)
        self.assertTrue((lay.filtered_signal(up, sig, lay.Layers()).iloc[60:] == 1).all())

    def test_size_smaller_when_wild_full_when_calm(self):
        rng = np.random.default_rng(1)
        calm, wild = px(rng.normal(0, 0.005, 300)), px(rng.normal(0, 0.08, 300))
        self.assertEqual(lay.raw_size(calm, lay.Layers()).iloc[-1], 1.0)
        self.assertLess(lay.raw_size(wild, lay.Layers()).iloc[-1], 0.5)
        self.assertGreaterEqual(lay.raw_size(wild, lay.Layers()).iloc[-1], 0.25)

    def test_size_is_held_between_signal_changes(self):
        close = px(np.random.default_rng(2).normal(0, 0.03, 400))
        sig = pd.Series(np.r_[np.ones(200), -np.ones(201)], index=close.index)
        held = lay.held_size(close, sig, lay.Layers())
        self.assertEqual(held.iloc[10:199].nunique(), 1)
        self.assertEqual(held.iloc[201:].nunique(), 1)

    def test_turning_layers_off_matches_the_plain_strategy(self):
        close = px(np.random.default_rng(5).normal(0.0005, 0.02, 900))
        off = lay.Layers(er_min=0.0, target_vol=0.0)
        plain = dtt.strategy_returns(close, "momentum_60", 0.001, 0.0)
        layered = lay.layered_returns(close, dtt.RULES["momentum_60"](close), 0.001, 0.0, off)
        np.testing.assert_allclose(plain.to_numpy(), layered.to_numpy(), atol=1e-12)

    def test_engine_runs_with_layers_and_says_so(self):
        res = engine.run_check(regimes(4), "momentum_20", null_runs=300, layers=lay.Layers(), cost_round_trip=0.001)
        self.assertIn("choppy", res.layers)
        self.assertIn("Risk layers on", report.format_report(res))
        self.assertLess(res.p_luck, 0.10)

    def test_engine_plain_default_unchanged(self):
        res = engine.run_check(regimes(4), "momentum_20", null_runs=100)
        self.assertEqual(res.layers, "plain")
        self.assertNotIn("Risk layers", report.format_report(res))

    def test_layers_do_not_pass_pure_noise(self):
        passes = sum(engine.run_check(px(np.random.default_rng(s).normal(0, 0.02, 2500)), "consensus", null_runs=300,
                                      layers=lay.Layers()).verdict == engine.VERDICT_PASS for s in range(40, 50))
        self.assertLessEqual(passes, 1)


class PaperLayerTests(unittest.TestCase):
    def test_position_is_sized_down_in_a_wild_market(self):
        rng = np.random.default_rng(8)
        close = px(0.01 + rng.normal(0, 0.05, 700))
        high, low = close * 1.02, close * 0.98
        with tempfile.TemporaryDirectory() as d:
            b = Book("t", "off", d, layers=lay.Layers())
            combo = Combo("BTC", "momentum_60")
            b.step(combo, close, engine.VERDICT_PASS, NOW, high, low)
            pos = b.state["positions"].get("BTC|momentum_60")
            if pos is None:
                self.skipTest("no entry with this seed")
            self.assertGreaterEqual(pos["notional"], 25.0)
            self.assertLess(pos["notional"], 100.0)
            self.assertAlmostEqual(b.state["realized"], -pos["notional"] * 0.002 / 2, places=9)

    def test_no_entry_in_choppy_market(self):
        zig = px(np.tile([0.02, -0.0196], 400))
        with tempfile.TemporaryDirectory() as d:
            b = Book("t", "off", d, layers=lay.Layers())
            b.step(Combo("BTC", "momentum_20"), zig, engine.VERDICT_PASS, NOW, zig * 1.01, zig * 0.99)
            self.assertEqual(b.state["positions"], {})


if __name__ == "__main__":
    unittest.main()
