"""Fake-server tests for the ported Deriv executor. No real network, no real tokens."""
import asyncio, json, os, sys, tempfile, threading, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import websockets

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "external" / "deriv_direct"))
import deriv_direct_executor as ex  # noqa: E402

SEEN = {"rest": [], "ws": [], "otp_kind": "demo", "reject_mult": set(), "open": 0}


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
        SEEN.update(rest=[], ws=[], otp_kind="demo", reject_mult=set(), open=0)
        self.tmp = tempfile.mkdtemp()

    def run_exec(self, config, dry):
        plan = ex.plan_order(SIG, config)
        return asyncio.run(ex.DerivDirectTrader(config, "pat_test", "APP1").execute(plan, dry))

    def test_plan_stoploss_below_stopout_and_field_name(self):
        c = cfg(self.tmp); plan = ex.plan_order(SIG, c)
        self.assertEqual(plan.stop_loss_amount, 1.6)
        p = ex.proposal_payload(plan, c, 20)
        self.assertIn("underlying_symbol", p); self.assertNotIn("symbol", p)

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


if __name__ == "__main__":
    unittest.main()
