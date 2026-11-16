import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from checker import payments  # noqa: E402
from checker.bot import Bot  # noqa: E402
from checker.store import Store  # noqa: E402

OWNER, MEMBER = 1, 7


def prices(*_):
    r = np.random.default_rng(2).normal(0, 0.02, 1500)
    return pd.Series(100 * np.cumprod(np.r_[1.0, 1 + r]), index=pd.date_range("2020-01-01", periods=1501, freq="D", tz="UTC"))


class BotTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        cfg = payments.PaymentConfig("0xWALLET", "BEP20", [payments.Pack("single", 1, 3.0), payments.Pack("ten", 10, 20.0)], 1500, (OWNER,))
        self.calls = 0

        def counting(coin):
            self.calls += 1
            return prices()
        self.bot = Bot(Store(str(Path(self.dir.name) / "b.db"), (OWNER,)), cfg, counting, null_runs=50, today=lambda: "2026-11-16")

    def tearDown(self):
        self.dir.cleanup()

    def text(self, uid, msg):
        return "\n".join(t for _, t in self.bot.handle(uid, msg))

    def test_member_without_credit_is_refused(self):
        self.assertIn("no checks left", self.text(MEMBER, "/check BTC momentum_20"))
        self.assertEqual(self.calls, 0)

    def test_owner_checks_free(self):
        self.assertIn("Check:", self.text(OWNER, "/check BTC momentum_20"))
        self.assertIn("free for you", self.text(OWNER, "/balance"))

    def test_full_payment_flow(self):
        self.assertIn("0xWALLET", self.text(MEMBER, "/buy single"))
        out = self.bot.handle(MEMBER, "/paid single TX9")
        self.assertIn(OWNER, [c for c, _ in out])
        self.assertIn("no checks left", self.text(MEMBER, "/check BTC momentum_20"))
        self.assertIn("added", self.text(OWNER, "/approve TX9"))
        self.assertIn("Check:", self.text(MEMBER, "/check BTC momentum_20"))
        self.assertIn("Checks left: 0", self.text(MEMBER, "/balance"))

    def test_member_cannot_approve_own_payment(self):
        self.bot.handle(MEMBER, "/paid single TX1")
        self.assertIn("did not understand", self.text(MEMBER, "/approve TX1"))
        self.assertIn("Checks left: 0", self.text(MEMBER, "/balance"))

    def test_data_failure_refunds_credit(self):
        self.bot.handle(MEMBER, "/paid single TX2")
        self.bot.handle(OWNER, "/approve TX2")
        self.bot.get_close = lambda c: (_ for _ in ()).throw(RuntimeError("down"))
        self.assertIn("was not used", self.text(MEMBER, "/check ETH momentum_60"))
        self.assertIn("Checks left: 1", self.text(MEMBER, "/balance"))

    def test_same_check_same_day_is_cached(self):
        self.text(OWNER, "/check BTC momentum_20")
        self.text(OWNER, "/check BTC momentum_20")
        self.assertEqual(self.calls, 1)

    def test_bad_input_is_helpful_not_charged(self):
        self.assertIn("Unknown coin", self.text(OWNER, "/check FAKE momentum_20"))
        self.assertIn("Unknown rule", self.text(OWNER, "/check BTC magic"))

    def test_no_advice_words(self):
        out = self.text(OWNER, "/check BTC momentum_20").lower()
        for word in ("you should buy", "guaranteed", "sure profit"):
            self.assertNotIn(word, out)


if __name__ == "__main__":
    unittest.main()
