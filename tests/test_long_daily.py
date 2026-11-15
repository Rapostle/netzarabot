import http.server
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "work"))
import download_long_daily as dl  # noqa: E402

DAY = 86400
T0 = 1_400_000_000 // DAY * DAY


def yahoo_payload(n=300, with_gap=True):
    ts = [T0 + i * DAY for i in range(n)]
    close = [100 + i * 0.1 for i in range(n)]
    quote = {"open": list(close), "high": [c + 1 for c in close], "low": [c - 1 for c in close], "close": list(close)}
    if with_gap:
        for k in quote:
            quote[k][5] = None
    return {"chart": {"result": [{"timestamp": ts, "indicators": {"quote": [quote]}}]}}


def stooq_csv(n=300):
    from datetime import datetime, timedelta, timezone
    day0 = datetime(2015, 1, 1, tzinfo=timezone.utc)
    lines = ["Date,Open,High,Low,Close,Volume"]
    for i in range(n):
        d = (day0 + timedelta(days=i)).strftime("%Y-%m-%d")
        lines.append(f"{d},1.1,1.2,1.0,1.15,0")
    return "\n".join(lines)


def klines(start_idx, count):
    return [[(T0 + (start_idx + i) * DAY) * 1000, "10", "11", "9", "10.5", "1", 0, "0", 0, "0", "0", "0"] for i in range(count)]


class Handler(http.server.BaseHTTPRequestHandler):
    mode = {"yahoo": "ok", "stooq": "ok"}

    def log_message(self, *a):
        pass

    def reply(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/v8/finance/chart/"):
            if Handler.mode["yahoo"] == "blocked":
                return self.reply(429, "{}")
            return self.reply(200, json.dumps(yahoo_payload()))
        if self.path.startswith("/q/d/l/"):
            if Handler.mode["stooq"] == "key":
                return self.reply(200, "Get your apikey", "text/plain")
            return self.reply(200, stooq_csv(), "text/csv")
        if self.path.startswith("/api/v3/klines"):
            start = int(self.path.split("startTime=")[1].split("&")[0]) // 1000
            first = max(0, (start - T0) // DAY) if start > T0 else 0
            total = 1500
            n = max(0, min(1000, total - first))
            return self.reply(200, json.dumps(klines(first, n)))
        self.reply(404, "{}")


class DownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["NO_PROXY"] = "127.0.0.1"
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        for key in ("YAHOO_BASE", "BINANCE_BASE", "STOOQ_BASE"):
            os.environ[key] = base

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        Handler.mode = {"yahoo": "ok", "stooq": "ok"}

    def test_parse_yahoo_skips_missing_values(self):
        rows = dl.parse_yahoo(yahoo_payload(10))
        self.assertEqual(len(rows), 9)

    def test_forex_uses_yahoo(self):
        rows, source, problems = dl.get_market("frxEURUSD", 12)
        self.assertEqual((source, problems), ("yahoo", []))
        self.assertEqual(len(rows), 299)

    def test_falls_back_to_stooq_when_yahoo_blocks(self):
        Handler.mode["yahoo"] = "blocked"
        rows, source, problems = dl.get_market("frxEURUSD", 12)
        self.assertEqual(source, "stooq")
        self.assertTrue(any(p.startswith("yahoo:") for p in problems))
        self.assertEqual(len(rows), 300)

    def test_all_sources_failing_reports_every_reason(self):
        Handler.mode = {"yahoo": "blocked", "stooq": "key"}
        rows, source, problems = dl.get_market("frxEURUSD", 12)
        self.assertEqual((rows, source), ([], ""))
        self.assertEqual(len(problems), 2)
        self.assertIn("key", problems[1])

    def test_binance_pages_until_a_short_batch(self):
        rows, source, _ = dl.get_market("cryBTCUSD", 40)
        self.assertEqual(source, "binance")
        self.assertEqual(len(rows), 1500)
        self.assertEqual([r[0] for r in rows], sorted({r[0] for r in rows}))

    def test_cli_writes_deriv_named_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            argv = sys.argv
            sys.argv = ["x", "--symbols", "frxEURUSD", "nonsense", "--out-dir", tmp]
            try:
                self.assertEqual(dl.main(), 1)  # the unknown name makes the exit code non-zero
            finally:
                sys.argv = argv
            lines = (Path(tmp) / "deriv_frxEURUSD_1d.csv").read_text().splitlines()
            self.assertEqual(lines[0], "timestamp,open,high,low,close,volume")
            self.assertEqual(len(lines), 300)


if __name__ == "__main__":
    unittest.main()
