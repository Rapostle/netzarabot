import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import coin_status as cs  # noqa: E402

STATE = {"positions": {
    "BTC|a": {"side": -1, "entry": 100.0, "notional": 100.0},
    "BTC|b": {"side": -1, "entry": 100.0, "notional": 50.0},
    "BNB|a": {"side": 1, "entry": 10.0, "notional": 100.0}}}
ROWS = [["time", "book", "market", "rule", "action", "side", "price", "notional", "pnl", "gate_verdict"],
        ["t", "gated", "BTC", "a", "close", "-1", "1", "100", "0.6", "x"],
        ["t", "gated", "BNB", "a", "close", "-1", "1", "100", "-0.4", "x"],
        ["t", "gated", "BNB", "a", "open", "1", "1", "100", "", "x"]]


class CoinStatusTests(unittest.TestCase):
    def test_totals_and_per_coin(self):
        r = cs.compute(STATE, ROWS, {"BTC": 90.0, "BNB": 11.0})
        self.assertEqual(r["total"]["closed"], 2)
        self.assertEqual(r["total"]["wins"], 1)
        self.assertAlmostEqual(r["total"]["realised"], 0.2)
        self.assertAlmostEqual(r["coins"]["BTC"]["unrealised"], 15.0)   # short 150 notional, price -10%
        self.assertAlmostEqual(r["coins"]["BNB"]["unrealised"], 10.0)   # long 100, +10%
        self.assertEqual(r["coins"]["BTC"]["exposure"], -150.0)

    def test_costs_are_counted(self):
        rows = ROWS + [["t", "gated", "BTC", "a", "open", "-1", "1", "100", "", "x"]]
        r = cs.compute(STATE, rows, {"BTC": 100.0, "BNB": 10.0}, cost_round_trip=0.002)
        self.assertAlmostEqual(r["total"]["entry_costs"], 0.2)             # two opens of $100 at 0.1% each
        self.assertAlmostEqual(r["total"]["exit_costs"], 0.25)             # three open positions: 250 notional at 0.1%
        self.assertAlmostEqual(r["total"]["realised_net"], 0.2 - 0.2)
        self.assertIn("Net if everything closed now", cs.render(r, "now"))

    def test_missing_price_counts_zero(self):
        r = cs.compute(STATE, ROWS, {"BTC": 90.0})
        self.assertEqual(r["coins"]["BNB"]["unrealised"], 0.0)

    def test_render_mentions_net_direction(self):
        text = cs.render(cs.compute(STATE, ROWS, {"BTC": 90.0, "BNB": 11.0}), "now")
        self.assertIn("net short", text)
        self.assertIn("net long", text)
        self.assertIn("Net if everything closed now", text)


if __name__ == "__main__":
    unittest.main()
