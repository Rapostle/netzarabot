import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import coin_compare as C  # noqa: E402

FIELDS = ["time", "book", "market", "rule", "action", "side", "price", "notional", "pnl", "gate_verdict"]


class Tests(unittest.TestCase):
    def test_summary_groups_by_action_and_day(self):
        rows = [
            {"time": "2026-11-22 01:10", "action": "lock_stop", "market": "BTC", "pnl": "10"},
            {"time": "2026-11-22 01:10", "action": "lock_stop", "market": "ETH", "pnl": "20"},
            {"time": "2026-11-23 01:10", "action": "stop", "market": "BNB", "pnl": "-5"},
            {"time": "2026-11-23 01:10", "action": "open", "market": "BNB", "pnl": ""},
        ]
        s = C.summarise([r for r in rows if r["action"] in C.CLOSE_ACTIONS and r["pnl"] != ""])
        self.assertEqual(s["n"], 3)
        self.assertEqual(s["wins"], 2)
        self.assertAlmostEqual(s["total"], 25.0)
        self.assertEqual(s["best_day"][0], "2026-11-22")
        self.assertAlmostEqual(s["by_action"]["lock_stop"][1], 30.0)

    def test_read_skips_opens_and_missing_files(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "j.csv"
            with p.open("w", newline="") as h:
                w = csv.DictWriter(h, fieldnames=FIELDS); w.writeheader()
                w.writerow({"time": "2026-11-22", "action": "open", "pnl": ""})
                w.writerow({"time": "2026-11-22", "action": "target", "pnl": "7", "market": "SOL"})
            self.assertEqual(len(C.read(p)), 1)
            self.assertEqual(C.read(Path(d) / "missing.csv"), [])


if __name__ == "__main__":
    unittest.main()
