import csv
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from coinbot.report import build_weekly, book_stats  # noqa: E402
from coinbot.paper import JOURNAL_FIELDS  # noqa: E402

NOW = datetime(2026, 11, 22, 8, 0, tzinfo=timezone.utc)


def write_book(out: Path, name: str, pnls: list[float], positions=None, realized=0.0):
    (out / f"coin_paper_{name}_state.json").write_text(json.dumps(
        {"positions": positions or {}, "closed": len(pnls), "wins": sum(p > 0 for p in pnls), "realized": realized}))
    with (out / f"coin_paper_{name}_journal.csv").open("w", newline="") as h:
        w = csv.DictWriter(h, fieldnames=JOURNAL_FIELDS)
        w.writeheader()
        for i, p in enumerate(pnls):
            w.writerow({"time": "t", "book": name, "market": "BTC", "rule": "momentum_60" if i % 2 else "breakout_20",
                        "action": "close", "side": 1, "price": 1, "notional": 100, "pnl": p, "gate_verdict": "x"})


class WeeklyTests(unittest.TestCase):
    def test_too_early_message_and_disarmed_line(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            write_book(out, "gated", [1.0, -2.0])
            text = build_weekly(out, out, NOW)
            self.assertIn("too early", text)
            self.assertIn("DISARMED", text)
            self.assertIn("PRETEND", text)

    def test_per_trade_net_charges_opening_cost(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            write_book(out, "gated", [1.0, 1.0])
            s = book_stats(out, "gated", {})
            self.assertAlmostEqual(s["avg"], 0.9, places=6)

    def test_verdict_warns_about_overlap_once_enough_trades(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            write_book(out, "gated", [0.5] * 30)
            text = build_weekly(out, out, NOW)
            self.assertIn("ahead so far", text)
            self.assertIn("ONE experiment", text)

    def test_losing_book_is_called_losing(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            write_book(out, "gated", [-0.5] * 30)
            self.assertIn("not working so far", build_weekly(out, out, NOW))

    def test_missing_files_do_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIn("0 closed", build_weekly(Path(d), Path(d), NOW))


if __name__ == "__main__":
    unittest.main()
