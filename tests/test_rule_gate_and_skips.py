import csv
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "external" / "deriv_direct"))
import deriv_direct_executor as ex  # noqa: E402

DEC_COLS = ["symbol", "timeframe", "timestamp", "decision", "side", "confidence", "reason", "entry", "stop_loss", "take_profit", "quantity", "risk_amount", "paper_order_id"]
CLOSED_COLS = ["paper_order_id", "symbol", "timeframe", "opened_at", "side", "reason", "status", "paper_pnl"]


def write(path, cols, rows):
    with open(path, "w", newline="") as h:
        w = csv.DictWriter(h, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def reason(rule):
    return f"stable_promoted_rules: stable promoted rule {rule}: x is y"


def signal_row(rule, side="buy", conf=0.7375, age_min=20, symbol="CRASH300N"):
    ts = (datetime.now(timezone.utc) - timedelta(minutes=age_min)).isoformat()
    return dict(symbol=symbol, timeframe="15m", timestamp=ts, decision="paper_order", side=side, confidence=conf,
                reason=reason(rule), entry=2000, stop_loss=1980 if side == "buy" else 2020,
                take_profit=2025 if side == "buy" else 1975, quantity=1.4, risk_amount=30, paper_order_id="paper-1")


def closed(rule, wins, losses):
    rows = []
    for i in range(wins + losses):
        rows.append(dict(paper_order_id=f"p{i}", symbol="CRASH300N", timeframe="15m", opened_at="2026-11-01", side="buy",
                         reason=reason(rule), status="closed", paper_pnl=10 if i < wins else -8))
    return rows


class GateTests(unittest.TestCase):
    def setup(self, tmp, signals, closed_rows, mode="demo", **kw):
        d = Path(tmp)
        write(d / "dec.csv", DEC_COLS, signals)
        write(d / "closed.csv", CLOSED_COLS, closed_rows)
        track = ex.TrackConfig("Sniper", str(d / "dec.csv"), str(d / "closed.csv"))
        base = dict(app_id="A", enabled=True, allow_real_trading=False, arming_file=str(d / "arm"), journal_csv=str(d / "j.csv"),
                    qualification_csv=str(d / "q.csv"), currency="USD", basis="stake", stake=1.0, max_stake=1.0, max_daily_stake=5.0,
                    max_open_contracts=1, min_confidence=0.6, max_signal_age_minutes=30, allowed_symbols=["CRASH300N"],
                    tracks=[track], account_mode=mode, rule_qualification_csv=str(d / "rq.csv"))
        base.update(kw)
        return ex.DerivDirectConfig(**base)

    def test_rule_id(self):
        self.assertEqual(ex.rule_id_from_reason(reason("PAIR017")), "PAIR017")
        self.assertEqual(ex.rule_id_from_reason("custom rule BC12: z"), "BC12")
        self.assertEqual(ex.rule_id_from_reason("nothing here"), "unknown")

    def test_proven_rule_trades_even_when_track_is_below_65(self):
        # track overall 16/25 = 64% would freeze the old track gate; PAIR017 itself is 6/7
        rows = closed("PAIR017", 6, 1) + closed("PAIR001", 10, 8)
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.setup(tmp, [signal_row("PAIR017")], rows)
            sel, quals, skips, rules = ex.select_signal_detailed(cfg)
            self.assertIsNotNone(sel)
            self.assertEqual(rules[0].status, "proven")
            old = self.setup(tmp, [signal_row("PAIR017")], rows, gate_mode="per_track")
            sel2, _q, skips2, _r = ex.select_signal_detailed(old)
            self.assertIsNone(sel2)
            self.assertIn("track not qualified", skips2[0][1])

    def test_probation_rule_trades_in_demo_only(self):
        rows = closed("PAIR029", 1, 1)
        with tempfile.TemporaryDirectory() as tmp:
            sig = [signal_row("PAIR029", side="sell", conf=0.6333)]
            sel, *_ = ex.select_signal_detailed(self.setup(tmp, sig, rows))
            self.assertIsNotNone(sel)
            self.assertEqual(sel.side, "sell")
            real, _q, skips, _r = ex.select_signal_detailed(self.setup(tmp, sig, rows, mode="real"))
            self.assertIsNone(real)
            self.assertIn("closed_trades 2 < 15", skips[0][1])

    def test_confidence_below_minimum_is_skipped_with_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.setup(tmp, [signal_row("PAIR029", side="sell", conf=0.6333)], [], min_confidence=0.7)
            sel, _q, skips, _r = ex.select_signal_detailed(cfg)
            self.assertIsNone(sel)
            self.assertIn("confidence 0.6333 < min_confidence 0.70", skips[0][1])

    def test_proven_bad_rule_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.setup(tmp, [signal_row("PAIR019")], closed("PAIR019", 2, 4) + closed("PAIR017", 7, 0))
            sel, _q, skips, _r = ex.select_signal_detailed(cfg)
            self.assertIsNone(sel)
            self.assertIn("rule gate PAIR019", skips[0][1])

    def test_track_floor_blocks_a_disastrous_track(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.setup(tmp, [signal_row("PAIR099")], closed("PAIR001", 1, 9))
            sel, _q, skips, _r = ex.select_signal_detailed(cfg)
            self.assertIsNone(sel)
            self.assertIn("track win_rate", skips[0][1])

    def test_skips_are_logged_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.setup(tmp, [signal_row("PAIR029", side="sell", conf=0.5)], [])
            sel, _q, skips, _r = ex.select_signal_detailed(cfg)
            self.assertEqual(ex.log_skips(cfg, skips, sel), 1)
            self.assertEqual(ex.log_skips(cfg, skips, sel), 0)
            rows = ex.read_rows(Path(cfg.journal_csv))
            self.assertEqual([r["status"] for r in rows], ["skipped"])
            self.assertIn("skipped: confidence", rows[0]["message"])

    def test_skipped_rows_do_not_count_as_trades(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.setup(tmp, [signal_row("PAIR029", conf=0.5)], [])
            _sel, _q, skips, _r = ex.select_signal_detailed(cfg)
            ex.log_skips(cfg, skips, None)
            self.assertEqual(ex.traded_keys(cfg), set())
            self.assertEqual(ex.daily_journal_totals(Path(cfg.journal_csv)), (0, 0.0))

    def test_old_and_non_actionable_rows_are_not_skips(self):
        old = signal_row("PAIR017", age_min=300, conf=0.1)
        hold = dict(signal_row("PAIR017"), decision="no_trade", side="hold")
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.setup(tmp, [old, hold], [])
            sel, _q, skips, _r = ex.select_signal_detailed(cfg)
            self.assertIsNone(sel)
            self.assertEqual(skips, [])

    def test_invalid_gate_mode_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "c.json"
            p.write_text('{"gate_mode": "nonsense"}')
            with self.assertRaises(ValueError):
                ex.load_config(p, Path(tmp))


if __name__ == "__main__":
    unittest.main()
