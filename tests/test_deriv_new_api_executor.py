"""Fake-server tests for the ported Deriv executor. No real network, no real tokens."""
import asyncio, json, os, sys, tempfile, threading, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import websockets

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "external" / "deriv_direct"))
import deriv_direct_executor as ex  # noqa: E402

SEEN = {"rest": [], "ws": [], "otp_kind": "demo", "reject_mult": set(), "open": 0, "contract": {}, "sell_fails": False}


class Rest(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body):
        raw = json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(raw)

    def _auth_ok(self):
        return self.headers.get("Authorization") == "Bearer pat_test" and self.headers.get("Deriv-App-ID") == "APP1"

    def do_GET(self):
        SEEN["rest"].append(("GET", self.path))
        if not self._auth_ok():
            return self._send(401, {"error": "bad auth"})
        self._send(200, {"data": [{"account_id": "REAL1", "account_type": "real"}, {"account_id": "DEMO1", "account_type": "demo"}]})

    def do_POST(self):
        SEEN["rest"].append(("POST", self.path))
        if not self._auth_ok():
            return self._send(401, {"error": "bad auth"})
        kind = SEEN["otp_kind"]
        self._send(200, {"data": {"url": f"ws://127.0.0.1:{self.server.ws_port}/ws/{kind}?otp=SECRET"}})


async def ws_handler(ws):
    async for raw in ws:
        msg = json.loads(raw); SEEN["ws"].append(msg); rid = msg.get("req_id")
        if "portfolio" in msg:
            out = {"portfolio": {"contracts": [{}] * SEEN["open"]}}
        elif "balance" in msg:
            out = {"balance": {"balance": 1000, "currency": "USD"}}
        elif "proposal" in msg:
            if msg["multiplier"] in SEEN["reject_mult"]:
                out = {"error": {"message": "multiplier not offered"}}
            else:
                out = {"proposal": {"id": "P1", "ask_price": msg["amount"]}}
        elif "proposal_open_contract" in msg:
            out = {"proposal_open_contract": dict(SEEN["contract"], contract_id=msg["contract_id"])}
        elif "sell" in msg:
            out = {"error": {"message": "sell refused"}} if SEEN["sell_fails"] else {"sell": {"contract_id": msg["sell"], "sold_for": 0.98}}
        elif "buy" in msg:
            out = {"buy": {"contract_id": 99, "buy_price": msg["price"]}}
        else:
            out = {"error": {"message": "unknown"}}
        await ws.send(json.dumps(dict(out, req_id=rid)))


def cfg(tmp, mode="demo", **kw):
    base = dict(app_id="APP1", enabled=True, allow_real_trading=False, arming_file=str(Path(tmp) / "arm.txt"),
                journal_csv=str(Path(tmp) / "j.csv"), qualification_csv=str(Path(tmp) / "q.csv"), currency="USD",
                basis="stake", stake=2.0, max_stake=2.0, max_daily_stake=10.0, max_open_contracts=1,
                min_confidence=0.7, max_signal_age_minutes=60, allowed_symbols=["BOOM300N"], tracks=[], account_mode=mode)
    base.update(kw)
    return ex.DerivDirectConfig(**base)


SIG = ex.CandidateSignal("t", "BOOM300N", "15m", "2026-11-03T00:00:00Z", "buy", "buy", 0.8, "r", 100.0, 99.0, 102.0, 1, 1, "s1")


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loop = asyncio.new_event_loop()
        started = threading.Event()

        def run():
            asyncio.set_event_loop(cls.loop)
            async def start():
                return await websockets.serve(ws_handler, "127.0.0.1", 0)
            cls.ws_server = cls.loop.run_until_complete(start())
            cls.ws_port = cls.ws_server.sockets[0].getsockname()[1]
            started.set(); cls.loop.run_forever()
        threading.Thread(target=run, daemon=True).start(); started.wait()
        cls.http = HTTPServer(("127.0.0.1", 0), Rest); cls.http.ws_port = cls.ws_port
        threading.Thread(target=cls.http.serve_forever, daemon=True).start()
        os.environ["DERIV_REST_BASE"] = f"http://127.0.0.1:{cls.http.server_port}"
        for k in ("DERIV_DEMO_ACCOUNT_ID", "DERIV_REAL_ACCOUNT_ID"):
            os.environ.pop(k, None)

    def setUp(self):
        SEEN.update(rest=[], ws=[], otp_kind="demo", reject_mult=set(), open=0, contract={}, sell_fails=False)
        self.tmp = tempfile.mkdtemp()

    def run_exec(self, config, dry):
        plan = ex.plan_order(SIG, config)
        return asyncio.run(ex.DerivDirectTrader(config, "pat_test", "APP1").execute(plan, dry))

    def test_plan_stoploss_below_stopout_and_field_name(self):
        c = cfg(self.tmp); plan = ex.plan_order(SIG, c)
        p = ex.proposal_payload(plan, c, 20)
        self.assertIn("underlying_symbol", p); self.assertNotIn("symbol", p)
        self.assertEqual(p["limit_order"], {"stop_loss": 0.4, "take_profit": 0.8})   # 2 * 20 * 1% and 2 * 20 * 2%
        self.assertEqual(ex.proposal_payload(plan, c, 40)["limit_order"]["stop_loss"], 0.8)

    def test_stop_too_wide_is_refused_not_clamped(self):
        wide = ex.CandidateSignal("t", "BOOM300N", "15m", "x", "buy", "buy", 0.8, "r", 100.0, 95.0, 110.0, 1, 1, "w")  # 5% stop x20 = 100% of stake
        c = cfg(self.tmp); plan = ex.plan_order(wide, c)
        with self.assertRaises(RuntimeError) as cm:
            ex.proposal_payload(plan, c, 20)
        self.assertIn("too wide", str(cm.exception))
        with self.assertRaises(RuntimeError):
            asyncio.run(ex.DerivDirectTrader(c, "pat_test", "APP1").execute(plan, True))
        self.assertFalse(any("buy" in m for m in SEEN["ws"]))

    def test_demo_dry_run_never_buys_and_picks_demo_account(self):
        r = self.run_exec(cfg(self.tmp), True)
        self.assertEqual(r["status"], "dry_run_proposal_ok")
        self.assertIn(("POST", "/accounts/DEMO1/otp"), SEEN["rest"])
        self.assertFalse(any("buy" in m for m in SEEN["ws"]))
        self.assertFalse(any("authorize" in m for m in SEEN["ws"]))

    def test_demo_buy_has_no_passthrough(self):
        r = self.run_exec(cfg(self.tmp), False)
        self.assertEqual(r["status"], "bought")
        buys = [m for m in SEEN["ws"] if "buy" in m]
        self.assertEqual(len(buys), 1); self.assertNotIn("passthrough", buys[0]); self.assertEqual(buys[0]["buy"], "P1")

    def test_multiplier_fallback_uses_next_candidate(self):
        SEEN["reject_mult"] = {20}
        r = self.run_exec(cfg(self.tmp), True)
        self.assertEqual(r["multiplier"], 40)

    def test_refuses_real_link_in_demo_mode_without_connecting(self):
        SEEN["otp_kind"] = "real"
        with self.assertRaises(RuntimeError) as cm:
            self.run_exec(cfg(self.tmp), False)
        self.assertNotIn("SECRET", str(cm.exception)); self.assertEqual(SEEN["ws"], [])

    def test_real_mode_needs_explicit_account_id(self):
        with self.assertRaises(RuntimeError):
            self.run_exec(cfg(self.tmp, "real"), True)

    def test_open_contract_and_daily_limits(self):
        SEEN["open"] = 1
        with self.assertRaises(RuntimeError):
            self.run_exec(cfg(self.tmp), False)
        with self.assertRaises(RuntimeError):
            self.run_exec(cfg(self.tmp, max_daily_stake=1.0), False)

    def test_bad_token_error_is_clean(self):
        c = cfg(self.tmp); plan = ex.plan_order(SIG, c)
        with self.assertRaises(RuntimeError) as cm:
            asyncio.run(ex.DerivDirectTrader(c, "wrong", "APP1").execute(plan, True))
        self.assertIn("401", str(cm.exception)); self.assertNotIn("wrong", str(cm.exception))

    def test_arming_gates(self):
        for var in ("ALLOW_REAL_DERIV_DIRECT", "DERIV_DIRECT_CONSENT", "DERIV_REAL_ACCOUNT_ID"):
            os.environ.pop(var, None)
        ex.validate_live_arming(cfg(self.tmp), "pat_test", False)            # demo: fine
        ex.validate_live_arming(cfg(self.tmp, "real"), "", True)              # real dry run: fine
        with self.assertRaises(RuntimeError):
            ex.validate_live_arming(cfg(self.tmp, "real"), "pat_test", False)  # no arming file
        Path(self.tmp, "arm.txt").write_text("x")
        with self.assertRaises(RuntimeError):
            ex.validate_live_arming(cfg(self.tmp, "real", allow_real_trading=True), "pat_test", False)  # no account id/env
        with self.assertRaises(RuntimeError):
            ex.validate_live_arming(cfg(self.tmp, "bogus"), "pat_test", False)


class ManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Tests.setUpClass.__func__(Tests)
        import deriv_position_manager as mgr
        cls.mgr = mgr

    def setUp(self):
        SEEN.update(rest=[], ws=[], otp_kind="demo", reject_mult=set(), open=0, contract={}, sell_fails=False)
        self.tmp = tempfile.mkdtemp()
        self.c = cfg(self.tmp)
        self.trader = ex.DerivDirectTrader(self.c, "pat_test", "APP1")

    def seed(self, opened_minutes_ago=1, **kw):
        from datetime import datetime, timedelta, timezone
        pos = {"contract_id": 7, "opened_at": (datetime.now(timezone.utc) - timedelta(minutes=opened_minutes_ago)).isoformat(),
               "mode": "demo", "track_name": "t", "signal_id": "s", "symbol": "BOOM300N", "timeframe": "15m", "side": "buy",
               "entry": 100.0, "stop_loss": 99.0, "take_profit": 102.0, "stake": 1.0, "multiplier": 20,
               "stop_loss_amount": 0.2, "take_profit_amount": 0.4, "buy_price": 1.0, "max_bars": 12}
        pos.update(kw)
        ex.save_open_positions(ex.open_positions_path(self.c), [pos])

    def run_mgr(self):
        return asyncio.run(self.mgr.manage_once(self.c, self.trader))

    def closed_rows(self):
        return ex.read_rows(self.mgr.closed_path(self.c))

    def left(self):
        return ex.load_open_positions(ex.open_positions_path(self.c))

    def test_nothing_open(self):
        self.assertEqual(self.run_mgr(), ["no open positions"])

    def test_keeps_young_position_with_no_trigger(self):
        self.seed(); SEEN["contract"] = {"is_sold": 0, "current_spot": 100.2}
        self.run_mgr()
        self.assertEqual(len(self.left()), 1); self.assertEqual(self.closed_rows(), [])
        self.assertFalse(any("sell" in m for m in SEEN["ws"]))

    def test_time_exit_after_12_candles(self):
        self.seed(opened_minutes_ago=181); SEEN["contract"] = {"is_sold": 0, "current_spot": 100.2}   # 12 x 15m = 180m
        self.run_mgr()
        rows = self.closed_rows()
        self.assertEqual(len(rows), 1); self.assertEqual(rows[0]["exit_reason"], "time exit"); self.assertEqual(self.left(), [])
        self.assertAlmostEqual(float(rows[0]["pnl"]), -0.02, places=6)

    def test_profit_lock_at_2r(self):
        self.seed(); SEEN["contract"] = {"is_sold": 0, "current_spot": 102.0}   # 2R = entry + 2 * 1.0
        self.run_mgr()
        self.assertEqual(self.closed_rows()[0]["exit_reason"], "profit lock 2R")

    def test_profit_lock_ignored_when_price_scale_does_not_match(self):
        self.seed(); SEEN["contract"] = {"is_sold": 0, "current_spot": 315.0}   # entry 100: stale signal or other price scale
        self.run_mgr()
        self.assertEqual(len(self.left()), 1); self.assertEqual(self.closed_rows(), [])

    def test_sell_side_profit_lock_uses_downward_move(self):
        self.seed(side="sell", stop_loss=101.0, take_profit=98.0); SEEN["contract"] = {"is_sold": 0, "current_spot": 98.0}
        self.run_mgr()
        self.assertEqual(self.closed_rows()[0]["exit_reason"], "profit lock 2R")

    def test_deriv_closed_it_on_stop_loss(self):
        self.seed(); SEEN["contract"] = {"is_sold": 1, "profit": -0.2, "sell_price": 0.8}
        self.run_mgr()
        rows = self.closed_rows()
        self.assertEqual(rows[0]["exit_reason"], "deriv stop loss"); self.assertEqual(self.left(), [])
        self.assertFalse(any("sell" in m for m in SEEN["ws"]))

    def test_failed_sell_keeps_position_for_retry(self):
        self.seed(opened_minutes_ago=200); SEEN["contract"] = {"is_sold": 0, "current_spot": 100.0}; SEEN["sell_fails"] = True
        log = self.run_mgr()
        self.assertEqual(len(self.left()), 1); self.assertEqual(self.closed_rows(), [])
        self.assertTrue(any("will retry" in line for line in log))

    def test_manager_needs_no_arming_in_real_mode_but_demo_link_rule_still_holds(self):
        SEEN["otp_kind"] = "real"; self.seed()
        with self.assertRaises(RuntimeError):
            self.run_mgr()
        self.assertEqual(len(self.left()), 1)

    def test_executor_records_the_position_it_opens(self):
        plan = ex.plan_order(SIG, self.c)
        result = asyncio.run(self.trader.execute(plan, False))
        ex.record_open_position(self.c, plan, result)
        saved = self.left()
        self.assertEqual(saved[0]["contract_id"], 99); self.assertEqual(saved[0]["max_bars"], 12)
        self.assertEqual(saved[0]["stop_loss_amount"], 0.4)   # test config stake is $2: 2 * 20 * 1%


class DedupeTests(unittest.TestCase):
    def test_signal_already_bought_is_skipped_even_from_another_track(self):
        tmp = tempfile.mkdtemp(); c = cfg(tmp)
        ex.write_journal_row(Path(c.journal_csv), {"status": "bought", "signal_id": "trackA~x", "message": f"bought {ex.signal_key(SIG)}"})
        ex.write_journal_row(Path(c.journal_csv), {"status": "error", "signal_id": "trackB~y", "message": "boom"})
        keys = ex.traded_keys(c)
        self.assertIn("trackA~x", keys); self.assertIn(ex.signal_key(SIG), keys)
        self.assertNotIn("trackB~y", keys)           # errors do not count as traded
        other_track_same_entry = ex.CandidateSignal("trackB", "BOOM300N", "15m", SIG.timestamp, "buy", "buy", 0.8, "r", 100.0, 99.0, 102.0, 1, 1, "trackB~z")
        self.assertIn(ex.signal_key(other_track_same_entry), keys)


if __name__ == "__main__":
    unittest.main()
