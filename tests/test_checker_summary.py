import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from checker import engine, intraday, summary  # noqa: E402
from test_checker_engine import trending  # noqa: E402
from test_checker_intraday import walk  # noqa: E402


class SummaryTests(unittest.TestCase):
    def test_summary_lists_every_rule_with_columns_and_disclaimer(self):
        close = trending(5, drift=0.0012)
        daily = [engine.run_check(close, r, "T", null_runs=20, tests_counted=len(engine.RULE_NAMES)) for r in engine.RULE_NAMES]
        intra = [intraday.run_intraday_check(walk(400), r, "T", null_runs=5) for r in intraday.INTRADAY_RULES]
        text = summary.format_summary("T", daily, intra)
        for r in engine.RULE_NAMES + intraday.INTRADAY_RULES:
            self.assertIn(r, text)
        self.assertIn("break-even", text)
        self.assertIn("Simply holding", text)
        self.assertIn("not financial advice", text.lower())
        self.assertNotIn("guaranteed", text.lower())

    def test_short_history_row_is_readable(self):
        daily = [engine.run_check(trending(1, n=100), "momentum_20", "T", null_runs=5)]
        self.assertIn("not enough history", summary.format_summary("T", daily, []))
