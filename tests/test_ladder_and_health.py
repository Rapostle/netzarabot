import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ladder_days as L  # noqa: E402
import job_health as J  # noqa: E402


def row(day, coin, pnl, action="lock_stop"):
    return {"time": f"{day} 01:10", "market": coin, "pnl": str(pnl), "action": action}


class LadderTests(unittest.TestCase):
    def test_market_wide_day_is_flagged_and_quiet_days_summed(self):
        rows = [row("2026-11-22", c, 50) for c in "ABCD"] + [row("2026-11-23", "A", -4, "stop"), row("2026-11-24", "B", 3)]
        days = L.by_day(rows)
        self.assertTrue(days[0]["market_wide"])
        self.assertFalse(days[1]["market_wide"])
        text = L.render("x", days)
        self.assertIn("market-wide win day", text)
        self.assertIn("2 days, $-1.00", text)
        self.assertIn("Still one event", text)

    def test_repeatable_message_needs_three_quiet_positive_days(self):
        rows = [row("2026-11-22", c, 50) for c in "ABCD"] + [row(f"2026-11-{23+i}", "A", 5) for i in range(3)]
        self.assertIn("also made money on ordinary days", L.render("x", L.by_day(rows)))

    def test_no_trades(self):
        self.assertIn("no closed trades", L.render("x", []))


class HealthTests(unittest.TestCase):
    def test_classification(self):
        now = time.time()
        self.assertEqual(J.classify({"pm2_env": {"status": "online"}}, now)[0], "running")
        self.assertEqual(J.classify({"pm2_env": {"status": "stopped", "cron_restart": "10 0 * * *"}}, now)[0], "scheduled")
        self.assertEqual(J.classify({"pm2_env": {"status": "stopped"}}, now)[0], "STOPPED, NO SCHEDULE")
