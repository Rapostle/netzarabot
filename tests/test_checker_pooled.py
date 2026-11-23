import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from checker import engine, pooled  # noqa: E402
from test_checker_engine import noise, trending  # noqa: E402


class PoolTests(unittest.TestCase):
    def test_too_few_markets_or_days_refused(self):
        r = pooled.run_pool_check({"A": noise(1, 400), "B": noise(2, 400)}, "momentum_20", null_runs=5)
        self.assertEqual(r.verdict, engine.VERDICT_REFUSED)
        r = pooled.run_pool_check({k: noise(i, 100) for i, k in enumerate("ABC")}, "momentum_20", null_runs=5)
        self.assertEqual(r.verdict, engine.VERDICT_REFUSED)

    def test_never_passes_and_reports_gross_and_break_even(self):
        closes = {k: trending(i, n=360, drift=0.003) for i, k in enumerate("ABCD")}
        r = pooled.run_pool_check(closes, "momentum_20", null_runs=60)
        self.assertNotEqual(r.verdict, engine.VERDICT_PASS)
        self.assertGreaterEqual(r.gross_return_pct, r.total_return_pct)
        self.assertTrue(any("best possible verdict" in n for n in r.notes))

    def test_pure_noise_is_not_inconclusive_much_of_the_time(self):
        hits = 0
        for s in range(6):
            closes = {k: noise(10 * s + i, 360) for i, k in enumerate("ABCD")}
            hits += pooled.run_pool_check(closes, "breakout_20", null_runs=60, tests_counted=10).verdict == engine.VERDICT_MAYBE
        self.assertLessEqual(hits, 3)

    def test_same_inputs_same_answer(self):
        closes = {k: noise(i, 360) for i, k in enumerate("ABC")}
        a = pooled.run_pool_check(closes, "momentum_60", null_runs=30).as_dict()
        b = pooled.run_pool_check(closes, "momentum_60", null_runs=30).as_dict()
        self.assertEqual(a, b)
