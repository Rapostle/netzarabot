import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import daily_scorecard as sc  # noqa: E402
import run_coin_paper as rc  # noqa: E402

NOW = datetime(2026, 11, 16, 1, 0, tzinfo=timezone.utc)


class RunnerTests(unittest.TestCase):
    def test_gate_caches_verdict_for_the_week(self):
        calls = []
        orig = rc.engine.run_check

        class R:
            verdict = "inconclusive"
        rc.engine.run_check = lambda *a, **k: (calls.append(k["tests_counted"]), R())[1]
        try:
            with tempfile.TemporaryDirectory() as d:
                gate = rc.make_gate(Path(d) / "g.json", 36, NOW)
                self.assertEqual(gate("BTC", "momentum_60", None), "inconclusive")
                self.assertEqual(rc.make_gate(Path(d) / "g.json", 36, NOW)("BTC", "momentum_60", None), "inconclusive")
                self.assertEqual(calls, [36])
        finally:
            rc.engine.run_check = orig

    def test_scorecard_shows_coin_books_and_no_real_money(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "outputs"
            out.mkdir()
            (out / "coin_paper_gated_state.json").write_text(json.dumps({"positions": {"a": {}}, "closed": 4, "wins": 1, "realized": -1.5}))
            text = sc.build_scorecard(Path(d), NOW)
            self.assertIn("Coin paper book 'gated' (pretend money): 1 open, 4 closed, win rate 25%", text)
            self.assertIn("DISARMED", text)


if __name__ == "__main__":
    unittest.main()


class StopMigrationTests(unittest.TestCase):
    def test_old_positions_get_one_atr_stop_once(self):
        import json
        import tempfile
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        import run_coin_paper as r
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.json"
            p.write_text(json.dumps({"positions": {
                "BTC|a": {"side": -1, "entry": 100.0, "stop": 130.0, "target": 40.0},       # short, old 3-ATR stop (ATR 10)
                "ETH|a": {"side": 1, "entry": 50.0, "stop": 35.0, "target": 80.0}}}))        # long, old 3-ATR stop (ATR 5)
            self.assertEqual(r.migrate_positions(p, 1.0), 2)
            pos = json.loads(p.read_text())["positions"]
            self.assertAlmostEqual(pos["BTC|a"]["stop"], 110.0)
            self.assertAlmostEqual(pos["ETH|a"]["stop"], 45.0)
            self.assertAlmostEqual(pos["BTC|a"]["atr"], 10.0)
            self.assertEqual(r.migrate_positions(p, 1.0), 0)   # second run changes nothing
