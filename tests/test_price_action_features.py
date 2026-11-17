import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "work"))
sys.path.insert(0, str(ROOT / "external" / "trading_bot"))
import walk_forward_rule_search as wf  # noqa: E402
import price_action_features as pa  # noqa: E402


def market(n=1800, seed=3):
    rng = np.random.default_rng(seed)
    c = 1000 + np.cumsum(rng.normal(0, 1.0, n))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + np.abs(rng.normal(0, 0.6, n))
    l = np.minimum(o, c) - np.abs(rng.normal(0, 0.6, n))
    df = pd.DataFrame({"timestamp": pd.date_range("2026-01-01", periods=n, freq="5min", tz="UTC"), "open": o, "high": h, "low": l, "close": c, "volume": 0})
    return wf.add_indicators(df).reset_index(drop=True)


class PriceActionTests(unittest.TestCase):
    def test_columns_and_length(self):
        df = market()
        out = pa.price_action_conditions(df)
        self.assertEqual(list(out.columns), pa.COLUMNS)
        self.assertEqual(len(out), len(df))

    def test_every_family_fires_sometimes_and_none_is_skipped_label(self):
        out = pa.price_action_conditions(market(5000))
        for col in pa.COLUMNS:
            labels = set(out[col].unique()) - {"None"}
            self.assertTrue(labels, f"{col} never fired")
        found = {(f, c) for f, c, _m in wf.hypotheses(out.astype(str)) if "+" not in f}
        self.assertFalse(any(c == "None" for _f, c in found))

    def test_no_lookahead_any_column(self):
        df = market(1500)
        full = pa.price_action_conditions(df)
        for t in (400, 777, 1100, 1499):
            part = pa.price_action_conditions(df.iloc[: t + 1].reset_index(drop=True))
            self.assertEqual(list(full.iloc[t]), list(part.iloc[t]), f"row {t} changed when the future was removed")

    def test_swing_needs_confirmation_candles(self):
        n = 40
        h = np.full(n, 10.0); l = np.full(n, 9.0)
        h[20] = 15.0                      # a clear swing high at candle 20
        sw = pa._swings(h, l)
        self.assertTrue(np.isnan(sw[20 + pa.PIVOT_K - 1, 0]))      # not known yet
        self.assertEqual(sw[20 + pa.PIVOT_K, 0], 15.0)             # known once confirmed

    def test_engulfing_and_pin_detected(self):
        df = market(400)
        i = 300
        df.loc[i - 1, ["open", "close", "high", "low"]] = [1010.0, 1008.0, 1010.5, 1007.5]   # small bearish
        df.loc[i, ["open", "close", "high", "low"]] = [1007.0, 1011.5, 1012.0, 1006.5]       # bullish engulfing
        self.assertEqual(pa.price_action_conditions(df)["candle_pattern"].iloc[i], "bull_engulfing")
        df.loc[i, ["open", "close", "high", "low"]] = [1010.0, 1010.3, 1010.4, 1004.0]       # long lower wick
        self.assertEqual(pa.price_action_conditions(df)["candle_pattern"].iloc[i], "bull_pin_bar")

    def test_fair_value_gap_formed(self):
        df = market(400)
        i = 300
        atr = float(df["atr_14"].iloc[i])
        base = float(df["high"].iloc[i - 2])
        df.loc[i, ["open", "low", "close", "high"]] = [base + atr, base + 0.6 * atr, base + 2 * atr, base + 2.1 * atr]
        self.assertEqual(pa.price_action_conditions(df)["fvg"].iloc[i], "bull_fvg_formed")

    def test_higher_timeframe_trend_in_steady_uptrend(self):
        n = 1200
        c = 100 + np.arange(n) * 0.1 + np.random.default_rng(1).normal(0, 0.02, n)
        df = pd.DataFrame({"timestamp": pd.date_range("2026-01-01", periods=n, freq="5min", tz="UTC"), "open": c, "high": c + 0.05, "low": c - 0.05, "close": c, "volume": 0})
        out = pa.price_action_conditions(wf.add_indicators(df).reset_index(drop=True), 12)
        self.assertEqual(out["htf_trend"].iloc[-1], "htf_up")

    def test_search_runs_with_price_action_modes(self):
        df = market(2200)[["timestamp", "open", "high", "low", "close", "volume"]]
        for mode in ("only", "add"):
            found, tried = wf.run_protocol(df, wf.SearchConfig(price_action=mode))
            self.assertGreater(tried, 0)
        _f, tried_only = wf.run_protocol(df, wf.SearchConfig(price_action="only"))
        _f, tried_off = wf.run_protocol(df, wf.SearchConfig(price_action="off"))
        self.assertNotEqual(tried_only, tried_off)


if __name__ == "__main__":
    unittest.main()
