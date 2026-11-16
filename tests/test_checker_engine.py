import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from checker import engine  # noqa: E402


def series(returns: np.ndarray) -> pd.Series:
    idx = pd.date_range("2016-01-01", periods=len(returns) + 1, freq="D", tz="UTC")
    return pd.Series(100 * np.cumprod(np.r_[1.0, 1.0 + returns]), index=idx)


def noise(seed: int, n: int = 3000) -> pd.Series:
    return series(np.random.default_rng(seed).normal(0.0, 0.02, n))


def trending(seed: int, n: int = 3000, drift: float = 0.004) -> pd.Series:
    """Slow regimes: the market drifts up or down for about 80 days at a time, which is the
    kind of pattern trend rules are built to catch."""
    rng = np.random.default_rng(seed)
    r = np.zeros(n)
    sign, left = 1.0, 0
    for i in range(n):
        if left == 0:
            sign, left = rng.choice([-1.0, 1.0]), int(rng.integers(50, 110))
        left -= 1
        r[i] = sign * drift + rng.normal(0.0, 0.02)
    return series(r)


class EngineTests(unittest.TestCase):
    def test_unknown_rule_rejected(self):
        with self.assertRaises(ValueError):
            engine.run_check(noise(1), "magic_rule")

    def test_short_history_refused(self):
        res = engine.run_check(noise(1, 200), "momentum_20", null_runs=50)
        self.assertEqual(res.verdict, engine.VERDICT_REFUSED)

    def test_planted_edge_passes(self):
        res = engine.run_check(trending(3), "momentum_20", null_runs=600, cost_round_trip=0.001)
        self.assertEqual(res.verdict, engine.VERDICT_PASS, res.as_dict())
        self.assertLess(res.p_luck, 0.05)

    def test_pure_noise_rarely_passes(self):
        passes = sum(
            engine.run_check(noise(seed), "momentum_20", null_runs=300).verdict == engine.VERDICT_PASS
            for seed in range(10, 22)
        )
        self.assertLessEqual(passes, 1)

    def test_few_shuffles_cannot_pass(self):
        res = engine.run_check(trending(3), "momentum_20", null_runs=100)
        self.assertNotEqual(res.verdict, engine.VERDICT_PASS)
        self.assertTrue(any("too few" in n for n in res.notes))

    def test_trying_many_combinations_weakens_a_pass(self):
        res = engine.run_check(trending(3, drift=0.0012), "momentum_20", null_runs=600, tests_counted=1)
        many = engine.run_check(trending(3, drift=0.0012), "momentum_20", null_runs=600, tests_counted=200)
        self.assertGreater(many.p_adjusted, res.p_adjusted)
        self.assertNotEqual(many.verdict, engine.VERDICT_PASS)

    def test_costs_can_erase_a_thin_edge(self):
        cheap = engine.run_check(trending(5, drift=0.0012), "momentum_20", null_runs=200, cost_round_trip=0.0)
        dear = engine.run_check(trending(5, drift=0.0012), "momentum_20", null_runs=200, cost_round_trip=0.02)
        self.assertGreater(cheap.net_sharpe, dear.net_sharpe)

    def test_same_inputs_give_same_answer(self):
        a = engine.run_check(noise(7), "breakout_20", null_runs=200).as_dict()
        b = engine.run_check(noise(7), "breakout_20", null_runs=200).as_dict()
        self.assertEqual(a, b)

    def test_result_never_claims_profit_wording(self):
        res = engine.run_check(trending(3), "momentum_20", null_runs=600)
        self.assertNotIn("profitable", res.verdict)


if __name__ == "__main__":
    unittest.main()
