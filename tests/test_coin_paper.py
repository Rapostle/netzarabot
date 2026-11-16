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

    # ---- stop-loss and take-profit ----
    def ohlc(self, n=700, step=0.01, extra=None):
        close = rising(n, step)
        high, low = close * 1.005, close * 0.995
        if extra:
            idx = close.index[-1] + pd.Timedelta(days=1)
            close = pd.concat([close, pd.Series([extra["close"]], index=[idx])])
            high = pd.concat([high, pd.Series([extra["high"]], index=[idx])])
            low = pd.concat([low, pd.Series([extra["low"]], index=[idx])])
        return close, high, low

    def open_long(self, b):
        c, h, l = self.ohlc()
        b.step(self.combo, c, engine.VERDICT_PASS, NOW, h, l)
        return b.state["positions"]["BTC|momentum_60"]

    def test_position_gets_stop_and_target_levels(self):
        pos = self.open_long(self.book())
        self.assertLess(pos["stop"], pos["entry"])
        self.assertGreater(pos["target"], pos["entry"])
        self.assertGreater(pos["target"] - pos["entry"], pos["entry"] - pos["stop"])

    def test_stop_loss_closes_at_the_stop_level_with_a_loss(self):
        b = self.book()
        pos = self.open_long(b)
        last = float(rising().iloc[-2])
        c, h, l = self.ohlc(extra={"close": last * 0.95, "high": last * 1.0, "low": pos["stop"] * 0.98})
        out = b.step(self.combo, c, engine.VERDICT_PASS, datetime(2026, 11, 18, 0, 5, tzinfo=timezone.utc), h, l)
        self.assertIn("stop hit", out)
        self.assertEqual(b.state["closed"], 1)
        self.assertLess(b.state["realized"], 0)
        self.assertNotIn("BTC|momentum_60", b.state["positions"])
        self.assertIn("BTC|momentum_60", b.state["cooldown"])

    def test_take_profit_closes_with_a_gain(self):
        b = self.book()
        pos = self.open_long(b)
        c, h, l = self.ohlc(extra={"close": pos["target"], "high": pos["target"] * 1.01, "low": pos["entry"]})
        out = b.step(self.combo, c, engine.VERDICT_PASS, datetime(2026, 11, 18, 0, 5, tzinfo=timezone.utc), h, l)
        self.assertIn("target hit", out)
        self.assertGreater(b.state["realized"], 0)

    def test_stop_wins_when_both_touched_in_one_candle(self):
        b = self.book()
        pos = self.open_long(b)
        c, h, l = self.ohlc(extra={"close": pos["entry"], "high": pos["target"] * 1.1, "low": pos["stop"] * 0.9})
        out = b.step(self.combo, c, engine.VERDICT_PASS, datetime(2026, 11, 18, 0, 5, tzinfo=timezone.utc), h, l)
        self.assertIn("stop hit", out)

    def test_no_reentry_on_same_signal_after_a_stop(self):
        b = self.book()
        pos = self.open_long(b)
        c, h, l = self.ohlc(extra={"close": pos["entry"], "high": pos["entry"], "low": pos["stop"] * 0.9})
        b.step(self.combo, c, engine.VERDICT_PASS, datetime(2026, 11, 18, 0, 5, tzinfo=timezone.utc), h, l)
        again = b.step(self.combo, c, engine.VERDICT_PASS, datetime(2026, 11, 19, 0, 5, tzinfo=timezone.utc), h, l)
        self.assertEqual(len(b.state["positions"]), 0)
        self.assertTrue("skipped" in again or "cooling" in again)

    def test_stops_can_be_turned_off(self):
        b = Book("n", "off", self.tmp.name, stop_atr=0, take_atr=0)
        c, h, l = self.ohlc()
        b.step(self.combo, c, engine.VERDICT_PASS, NOW, h, l)
        pos = b.state["positions"]["BTC|momentum_60"]
        self.assertIsNone(pos["stop"])
        self.assertIsNone(pos["target"])

    def test_old_position_without_levels_gets_them(self):
        b = self.book()
        b.state["positions"]["BTC|momentum_60"] = {"side": 1, "entry": 1000.0, "opened": "2026-11-15"}
        c, h, l = self.ohlc()
        b.step(self.combo, c, engine.VERDICT_PASS, NOW, h, l)
        pos = b.state["positions"].get("BTC|momentum_60")
        self.assertTrue(pos is None or "stop" in pos)

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
