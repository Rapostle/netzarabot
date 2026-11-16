import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from checker import engine, payments, report  # noqa: E402
from checker.store import Store  # noqa: E402


def result(verdict):
    return engine.CheckResult("momentum_20", "BTC", 3000, 8.2, 40, 0.3, 0.2, 0.4, 50.0, 120.0, 0.5, 0.2, 0.2, 1, 1000, 0.002, verdict, ["short"])


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = Store(str(Path(self.dir.name) / "t.db"), owner_ids=(1,))

    def tearDown(self):
        self.dir.cleanup()

    def test_no_credit_no_check(self):
        self.assertFalse(self.store.spend_credit(5))

    def test_owner_is_exempt_and_never_charged(self):
        self.assertTrue(self.store.spend_credit(1))
        self.assertEqual(self.store.balance(1), 0)

    def test_payment_credits_once(self):
        self.assertTrue(self.store.submit_payment("0xAB", 5, 10, 10))
        self.assertEqual(self.store.approve_payment("0xab"), (5, 10))
        self.assertIsNone(self.store.approve_payment("0xab"))
        self.assertEqual(self.store.balance(5), 10)
        self.assertTrue(self.store.spend_credit(5))
        self.assertEqual(self.store.balance(5), 9)

    def test_same_txid_cannot_be_reused(self):
        self.assertTrue(self.store.submit_payment("tx1", 5, 3, 1))
        self.assertFalse(self.store.submit_payment("TX1", 6, 3, 1))

    def test_unapproved_payment_gives_nothing(self):
        self.store.submit_payment("tx2", 5, 3, 1)
        self.assertEqual(self.store.balance(5), 0)
        self.assertEqual(len(self.store.pending()), 1)

    def test_refund_after_failed_run(self):
        self.store.submit_payment("tx3", 5, 3, 1)
        self.store.approve_payment("tx3")
        self.assertTrue(self.store.spend_credit(5))
        self.store.refund_credit(5)
        self.assertEqual(self.store.balance(5), 1)

    def test_cache_and_daily_count(self):
        self.assertIsNone(self.store.cached_report("d", "BTC", "momentum_20"))
        self.store.save_report("d", "BTC", "momentum_20", {"a": 1})
        self.store.save_report("d", "ETH", "momentum_20", {"a": 2})
        self.assertEqual(self.store.cached_report("d", "BTC", "momentum_20"), {"a": 1})
        self.assertEqual(self.store.combinations_today("d"), 2)


class ReportAndPaymentTests(unittest.TestCase):
    def test_each_verdict_has_wording_and_disclaimer(self):
        for v in (engine.VERDICT_NONE, engine.VERDICT_MAYBE, engine.VERDICT_PASS):
            text = report.format_report(result(v))
            self.assertIn(report.DISCLAIMER, text)
            self.assertNotIn("guaranteed", text.lower())
            self.assertNotIn("buy now", text.lower())

    def test_correction_sentence_only_when_many_tried(self):
        res = result(engine.VERDICT_NONE)
        self.assertNotIn("tries are counted", report.format_report(res))
        res.tests_counted = 40
        self.assertIn("at least 40 tries", report.format_report(res))

    def test_price_shows_usd_first_with_naira_in_brackets(self):
        self.assertEqual(payments.price_text(5, 1500), "$5.00 (about ₦7,500)")
        self.assertEqual(payments.price_text(5, 0), "$5.00")

    def test_example_config_refused_until_wallet_set(self):
        with self.assertRaises(ValueError):
            payments.load_config(str(Path(__file__).resolve().parent.parent / "checker" / "config.example.json"))


if __name__ == "__main__":
    unittest.main()
