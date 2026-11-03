"""The paper rules must be judged on finished candles only."""
import argparse, os, sys, tempfile, unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "external" / "trading_bot"))
from trading_bot.cli import main as cli  # noqa: E402
from trading_bot.indicators.technical import add_indicators  # noqa: E402
from trading_bot.research.signal_discovery import condition_frame  # noqa: E402


def candles(end, n=600, seconds=900, seed=3):
    rng = np.random.default_rng(seed)
    close = 300.0 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    ts = pd.date_range(end=end, periods=n, freq=f"{seconds}s", tz="UTC")
    return pd.DataFrame({"timestamp": ts, "open": close * (1 + rng.normal(0, .0005, n)), "high": close * 1.002,
                         "low": close * 0.998, "close": close, "volume": 0.0})


class Tests(unittest.TestCase):
    def test_forming_candle_is_dropped_and_closed_ones_kept(self):
        now = pd.Timestamp("2026-11-03 19:26:00", tz="UTC")
        df = candles(end="2026-11-03 19:15:00")            # newest candle opened 19:15, still forming at 19:26
        out = cli.completed_candles(df, 900, now)
        self.assertEqual(len(out), len(df) - 1)
        self.assertEqual(out["timestamp"].iloc[-1], pd.Timestamp("2026-11-03 19:00:00", tz="UTC"))

    def test_candle_counts_as_closed_exactly_at_its_close_time(self):
        df = candles(end="2026-11-03 19:15:00")
        self.assertEqual(len(cli.completed_candles(df, 900, pd.Timestamp("2026-11-03 19:30:00", tz="UTC"))), len(df))
        self.assertEqual(len(cli.completed_candles(df, 900, pd.Timestamp("2026-11-03 19:29:59", tz="UTC"))), len(df) - 1)

    def test_escape_hatch_restores_old_behaviour(self):
        df = candles(end="2026-11-03 19:15:00")
        os.environ["PAPER_USE_PARTIAL_CANDLE"] = "1"
        try:
            self.assertEqual(len(cli.completed_candles(df, 900, pd.Timestamp("2026-11-03 19:26:00", tz="UTC"))), len(df))
        finally:
            os.environ.pop("PAPER_USE_PARTIAL_CANDLE")

    def test_decision_uses_last_finished_candle_end_to_end(self):
        tmp = Path(tempfile.mkdtemp())
        now = pd.Timestamp.now(tz="UTC")
        newest_open = now.floor("15min")                  # the candle in progress right now
        df = candles(end=newest_open)
        df.to_csv(tmp / "deriv_BOOM300N_15m.csv", index=False)
        full = add_indicators(df)
        cond = condition_frame(full).astype(str)
        # a rule that matches exactly the last FINISHED candle, built from its own conditions
        finished = cond.iloc[-2]
        feats = list(finished.index[:2])
        rule = {"rule_id": "T1", "symbol": "BOOM300N", "timeframe": "15m", "suggested_side": "buy",
                "feature": "+".join(feats), "condition": " & ".join(finished[f] for f in feats),
                "win_rate": 0.7, "profit_factor": 2.0, "symbol_rule_rank": 1}
        pd.DataFrame([rule]).to_csv(tmp / "rules.csv", index=False)
        out = tmp / "decisions.csv"
        args = argparse.Namespace(rules_csv=str(tmp / "rules.csv"), data_dir=str(tmp), max_rows=1500, audit_output=str(out))
        self.assertEqual(cli.run_paper_stable_rules(args, {}), 0)
        row = pd.read_csv(out).iloc[0]
        self.assertEqual(pd.Timestamp(row["timestamp"]), df["timestamp"].iloc[-2])   # not the forming candle
        self.assertAlmostEqual(float(row["entry"]), float(df["close"].iloc[-2]), places=6)


if __name__ == "__main__":
    unittest.main()
