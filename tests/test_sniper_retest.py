import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "work"))
sys.path.insert(0, str(ROOT / "external" / "trading_bot"))
sys.path.insert(0, str(ROOT / "tests"))
import sniper_retest as rt  # noqa: E402
import sniper_test as st  # noqa: E402
from test_sniper_test import rw  # noqa: E402


class RetestTests(unittest.TestCase):
    def test_only_the_three_numbers_change(self):
        before = (st.BLOCK, st.TOUCH_ATR, st.CONFIRM_WINDOW, st.LIMIT, st.COST, st.SLIP)
        orig = (st.STOP_PAD_ATR, st.MAX_STOP_ATR, st.REWARD_R)
        try:
            rt.apply_settings()
            self.assertEqual((st.STOP_PAD_ATR, st.MAX_STOP_ATR, st.REWARD_R), (0.5, 6.0, 1.5))
            self.assertEqual(before, (st.BLOCK, st.TOUCH_ATR, st.CONFIRM_WINDOW, st.LIMIT, st.COST, st.SLIP))
            df = rw(9000)
            for t, side, entry, stop in st.find_signals(df):
                atr = st.wf.add_indicators(df).reset_index(drop=True)["atr_14"].to_numpy(float)[t]
                self.assertLessEqual(abs(entry - stop), 6.0 * atr + 1e-9)
            tr = st.evaluate(df)
            self.assertTrue(((tr["r"] <= 1.5) | (tr["exit"] >= 0)).all())
            self.assertLessEqual(tr["r"].max(), 1.5)
        finally:
            st.STOP_PAD_ATR, st.MAX_STOP_ATR, st.REWARD_R = orig


if __name__ == "__main__":
    unittest.main()
