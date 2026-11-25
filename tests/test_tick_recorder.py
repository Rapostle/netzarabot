import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "work"))
import tick_recorder as T  # noqa: E402


def make_ticks(n, start=1_000_000, plant=0.0, seed=1):
    rng = np.random.default_rng(seed)
    d = rng.integers(0, 10, n)
    for i in range(1, n):
        if d[i - 1] == 2 and rng.random() < plant:
            d[i] = 3
    return [(start + i, int(x)) for i, x in enumerate(d)]


class Tests(unittest.TestCase):
    def test_parse_tick_keeps_trailing_zero(self):
        msg = {"msg_type": "tick", "tick": {"symbol": "CRASH500", "epoch": 5, "quote": 1234.5, "pip_size": 2}}
        self.assertEqual(T.parse_tick(msg), ("CRASH500", 5, "1234.50", 0))
        self.assertIsNone(T.parse_tick({"msg_type": "ping"}))
        self.assertIsNone(T.parse_tick({"msg_type": "tick", "tick": {"symbol": "X"}}))

    def test_random_digits_do_not_hold_and_planted_pair_does(self):
        fair = T.analyze_pair(make_ticks(30000), 2, 3)
        self.assertGreater(fair["events"], T.JUDGE_EVENTS)
        self.assertIn("DOES NOT HOLD", T.verdict(fair))
        planted = T.analyze_pair(make_ticks(30000, plant=0.4), 2, 3)
        self.assertIn("HOLDS", T.verdict(planted))

    def test_not_judged_before_enough_cases(self):
        self.assertIn("not judged yet", T.verdict(T.analyze_pair(make_ticks(3000), 2, 3)))

    def test_gaps_do_not_create_pairs(self):
        ticks, t = [], 1000
        for _ in range(300):
            for _ in range(20):               # ordinary one-second ticks, never a 2
                ticks.append((t, 5))
                t += 1
            ticks.append((t, 2))
            t += 100                          # a dropped connection between a 2 and the next tick
            ticks.append((t, 3))
            t += 1
        self.assertEqual(T.analyze_pair(ticks, 2, 3).get("events", 0), 0)

    def test_only_ticks_after_registration_count_and_start_cannot_move(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            rows = [(e, "1.00", dg) for e, dg in make_ticks(5000, plant=0.9)]
            T.append_rows(out / "CRASH500.csv", rows)
            T.register(out, "CRASH500", 2, 3, now=1_000_000 + 4000)     # registered after the planted data
            r = T.analyze_pair(T.read_ticks(out / "CRASH500.csv", 1_000_000 + 4000), 2, 3)
            self.assertLessEqual(r["events"], 1000 // 5)   # only the last ~1000 ticks count
            with self.assertRaises(SystemExit):
                T.register(out, "CRASH500", 2, 3)
            self.assertIn("CRASH500", T.analyze(out))

    def test_analyze_without_registration(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIn("No pair registered", T.analyze(Path(d)))
