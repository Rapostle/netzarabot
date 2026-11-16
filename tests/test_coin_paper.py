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
from checker import engine  # noqa: E402
from coinbot.paper import Book, Combo, closed_only, gate_allows, run_cycle  # noqa: E402

NOW = datetime(2026, 11, 16, 0, 5, tzinfo=timezone.utc)


def rising(n=700, step=0.01):
    idx = pd.date_range(end="2026-11-16", periods=n, freq="D", tz="UTC")  # last bar is today (unfinished)
    return pd.Series(100 * np.cumprod(np.full(n, 1 + step)), index=idx)


def falling(n=700, step=0.01):
    idx = pd.date_range(end="2026-11-16", periods=n, freq="D", tz="UTC")
    return pd.Series(100 * np.cumprod(np.full(n, 1 - step * 0.5)), index=idx)


class PaperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.combo = Combo("BTC", "momentum_60")

    def tearDown(self):
        self.tmp.cleanup()

    def book(self, mode="off", name="t"):
        return Book(name, mode, self.tmp.name)

    def test_unfinished_day_is_dropped(self):
        c = closed_only(rising(), NOW)
        self.assertEqual(str(c.index[-1].date()), "2026-11-15")

    def test_opens_long_in_uptrend_once(self):
        b = self.book()
        self.assertIn("changed 0->1", b.step(self.combo, rising(), engine.VERDICT_PASS, NOW))
        self.assertIn("already handled", b.step(self.combo, rising(), engine.VERDICT_PASS, NOW))
        self.assertEqual(len(b.state["positions"]), 1)

    def test_flip_closes_with_correct_pnl_and_costs(self):
        b = self.book()
        b.step(self.combo, rising(), engine.VERDICT_PASS, NOW)
        p1 = b.state["positions"]["BTC|momentum_60"]["entry"]
        self.assertAlmostEqual(b.state["realized"], -0.1, places=9)  # half the round-trip cost on open
        later = datetime(2026, 11, 17, 0, 5, tzinfo=timezone.utc)
        idx = pd.date_range(end="2026-11-17", periods=700, freq="D", tz="UTC")
        steps = np.r_[np.full(600, 1.01), np.full(100, 0.99)]
        falling_later = pd.Series(100 * np.cumprod(steps), index=idx)
        self.assertIn("changed 1->-1", b.step(self.combo, falling_later, engine.VERDICT_PASS, later))
        p2 = float(closed_only(falling_later, later).iloc[-1])
        pnl_close = (p2 / p1 - 1.0) * 100 - 0.1
        self.assertAlmostEqual(b.state["realized"], -0.1 + pnl_close - 0.1, places=6)
        self.assertEqual(b.state["closed"], 1)
        self.assertEqual(b.state["positions"]["BTC|momentum_60"]["side"], -1)

    def test_strict_gate_blocks_without_pass(self):
        b = self.book("strict")
        self.assertIn("gate blocked", b.step(self.combo, rising(), engine.VERDICT_NONE, NOW))
        self.assertEqual(b.state["positions"], {})

    def test_watch_gate_allows_inconclusive(self):
        self.assertTrue(gate_allows("watch", engine.VERDICT_MAYBE))
        self.assertFalse(gate_allows("watch", engine.VERDICT_NONE))
        self.assertFalse(gate_allows("strict", engine.VERDICT_MAYBE))

    def test_short_history_does_nothing(self):
        b = self.book()
        self.assertIn("not enough history", b.step(self.combo, rising(100), engine.VERDICT_PASS, NOW))

    def test_state_survives_restart(self):
        b = self.book()
        b.step(self.combo, rising(), engine.VERDICT_PASS, NOW)
        again = self.book()
        self.assertEqual(again.state["positions"], b.state["positions"])

    def test_run_cycle_feeds_both_books_one_gate_call(self):
        calls = []
        gate = lambda m, r, c: (calls.append(1), engine.VERDICT_NONE)[1]
        ungated, gated = self.book("off", "ungated"), self.book("strict", "gated")
        out = run_cycle([ungated, gated], [self.combo], {"BTC": rising()}, gate, NOW)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(ungated.state["positions"]), 1)
        self.assertEqual(len(gated.state["positions"]), 0)
        self.assertIn("gate blocked", out["gated"][0])

    def test_bad_mode_rejected(self):
        with self.assertRaises(ValueError):
            Book("x", "yolo", self.tmp.name)

    def test_summary_counts_unrealized(self):
        b = self.book()
        b.step(self.combo, rising(), engine.VERDICT_PASS, NOW)
        s = b.summary({"BTC": float(rising().iloc[-2]) * 1.1})
        self.assertGreater(s["unrealized_usd"], 9.0)


if __name__ == "__main__":
    unittest.main()
