import csv
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import run_wf_track as t  # noqa: E402

T0 = 1_700_000_000 - (1_700_000_000 % 300)
RULE = {"rule_id": "WF001", "symbol": "CRASH300N", "timeframe": "5m", "side": "buy", "feature": "rsi_zone+upper_wick",
        "condition": "rsi_high & large_upper_wick", "confidence": 0.6786}


def candles(n=400, last_drop=None, last_pump=None):
    rng = np.random.default_rng(1)
    close = 1000 + np.cumsum(rng.normal(0, 1.0, n))
    rows = []
    for i in range(n):
        c = close[i]
        rows.append({"epoch": T0 + i * 300, "open": c, "high": c + 1.0, "low": c - 1.0, "close": c, "volume": 0})
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["epoch"], unit="s", utc=True)
    return df


def now_after(df, extra=10):
    return datetime.fromtimestamp(int(df["epoch"].iloc[-1]) + 300 + extra, tz=timezone.utc)


def always(cond, f, c):
    return np.ones(len(cond), dtype=bool)


def never(cond, f, c):
    return np.zeros(len(cond), dtype=bool)


def read(path):
    with open(path, newline="") as h:
        return list(csv.DictReader(h))


class WfTrackTests(unittest.TestCase):
    def run_once(self, root, df, mask_fn, now=None):
        return t.process(root, fetch=lambda s, tf: df, now=now or now_after(df), rules=[RULE], mask_fn=mask_fn)

    def test_signal_row_levels_and_header(self):
        df = candles()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            notes = self.run_once(root, df, always)
            rows = read(root / "outputs" / "wf_5m_paper_decisions.csv")
            self.assertEqual(len(rows), 1, notes)
            r = rows[0]
            self.assertEqual(list(r.keys()), t.DECISION_FIELDS)
            self.assertEqual(r["decision"], "paper_order")
            self.assertEqual(r["side"], "buy")
            self.assertIn("rule WF001", r["reason"])
            entry, stop, tp = float(r["entry"]), float(r["stop_loss"]), float(r["take_profit"])
            self.assertLess(stop, entry)
            self.assertGreater(tp, entry)
            self.assertAlmostEqual((entry - stop) / (tp - entry), t.SL_ATR / t.TP_ATR, places=6)
            self.assertAlmostEqual(float(r["quantity"]) * (entry - stop), t.RISK_USD, places=4)

    def test_unfinished_candle_is_ignored(self):
        df = candles()
        early = datetime.fromtimestamp(int(df["epoch"].iloc[-1]) + 100, tz=timezone.utc)  # last candle still forming
        with tempfile.TemporaryDirectory() as d:
            self.run_once(Path(d), df, always, now=early)
            row = read(Path(d) / "outputs" / "wf_5m_paper_decisions.csv")[0]
            self.assertEqual(row["timestamp"], t.fmt_time(int(df["epoch"].iloc[-2])))

    def test_no_duplicate_for_same_candle(self):
        df = candles()
        with tempfile.TemporaryDirectory() as d:
            self.run_once(Path(d), df, always)
            notes = self.run_once(Path(d), df, always)
            self.assertEqual(len(read(Path(d) / "outputs" / "wf_5m_paper_decisions.csv")), 1)
            self.assertTrue(any("already" in n for n in notes))

    def test_one_open_position_at_a_time(self):
        df = candles()
        with tempfile.TemporaryDirectory() as d:
            self.run_once(Path(d), df, always)
            df2 = candles(401)  # one more candle, price stays inside stop and target
            df2.loc[400, ["open", "high", "low", "close"]] = df["close"].iloc[-1]
            notes = self.run_once(Path(d), df2, always)
            self.assertEqual(len(read(Path(d) / "outputs" / "wf_5m_paper_decisions.csv")), 1, notes)
            self.assertTrue(any("still open" in n for n in notes))

    def test_no_signal_writes_nothing(self):
        df = candles()
        with tempfile.TemporaryDirectory() as d:
            self.run_once(Path(d), df, never)
            self.assertFalse((Path(d) / "outputs" / "wf_5m_paper_decisions.csv").exists())

    def _open_then(self, mutate):
        df = candles()
        d = tempfile.TemporaryDirectory()
        root = Path(d.name)
        self.run_once(root, df, always)
        row = read(root / "outputs" / "wf_5m_paper_decisions.csv")[0]
        df2 = candles(401 + 12)
        mutate(df2, float(row["entry"]), float(row["stop_loss"]), float(row["take_profit"]))
        t.process(root, fetch=lambda s, tf: df2, now=now_after(df2), rules=[RULE], mask_fn=never)
        return d, read(root / "outputs" / "wf_5m_closed_trades.csv")

    def test_take_profit_closes_with_profit(self):
        def m(df2, e, s, tp):
            df2.loc[400:, ["open", "high", "low", "close"]] = e
            df2.loc[401, "high"] = tp + 1
        d, rows = self._open_then(m)
        self.assertEqual(len(rows), 1)
        self.assertEqual(list(rows[0].keys()), t.CLOSED_FIELDS)
        self.assertEqual(rows[0]["exit_reason"], "paper take profit")
        self.assertEqual(rows[0]["status"], "closed")
        self.assertGreater(float(rows[0]["paper_pnl"]), 0)
        d.cleanup()

    def test_stop_wins_when_both_touched(self):
        def m(df2, e, s, tp):
            df2.loc[400:, ["open", "high", "low", "close"]] = e
            df2.loc[401, "high"] = tp + 1
            df2.loc[401, "low"] = s - 1
        d, rows = self._open_then(m)
        self.assertEqual(rows[0]["exit_reason"], "paper stop loss")
        self.assertLess(float(rows[0]["paper_pnl"]), 0)
        d.cleanup()

    def test_time_exit_after_twelve_candles(self):
        def m(df2, e, s, tp):
            df2.loc[400:, ["open", "high", "low", "close"]] = e
        d, rows = self._open_then(m)
        self.assertEqual(rows[0]["exit_reason"], "paper time exit")
        d.cleanup()

    def test_rule_id_parses_like_the_executor(self):
        import re
        m = re.search(r"\brule\s+([A-Za-z0-9_\-]+)", t.reason_text(RULE))
        self.assertEqual(m.group(1), "WF001")

    def test_real_condition_frame_runs(self):
        from evaluate_existing_rules import rule_mask
        import walk_forward_rule_search as wf
        df = candles()
        cond = wf.condition_frame(wf.add_indicators(df).reset_index(drop=True)).astype(str)
        mask = rule_mask(cond, RULE["feature"], RULE["condition"])
        self.assertEqual(len(mask), len(df))

    def test_fetch_failure_is_reported_not_raised(self):
        def boom(s, tf):
            raise RuntimeError("offline")
        with tempfile.TemporaryDirectory() as d:
            notes = t.process(Path(d), fetch=boom, rules=[RULE])
            self.assertTrue(any("no candles" in n for n in notes))


if __name__ == "__main__":
    unittest.main()
