import asyncio
import csv
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
sys.path.insert(0, str(ROOT / "scripts"))
import walk_forward_rule_search as wf  # noqa: E402
import download_history as dh  # noqa: E402
import daily_scorecard as sc  # noqa: E402

CFG = wf.SearchConfig(cost=0.001, sl_slippage=0.2, horizon=12)


def flat(n=30, price=100.0):
    return pd.DataFrame({"high": [price] * n, "low": [price] * n, "close": [price] * n, "atr_14": [1.0] * n})


class SimulateTests(unittest.TestCase):
    def test_target_hit_buy(self):
        df = flat()
        df.loc[1, "high"] = 102.0
        got = wf.simulate_trades(df, CFG)["buy_ret"].iloc[0]
        self.assertAlmostEqual(got, 1.8 / 100 - 0.001, places=9)

    def test_stop_hit_buy_includes_slippage(self):
        df = flat()
        df.loc[2, "low"] = 98.0
        got = wf.simulate_trades(df, CFG)["buy_ret"].iloc[0]
        self.assertAlmostEqual(got, -1.4 / 100 - 0.2 * 1.4 / 100 - 0.001, places=9)

    def test_both_levels_in_one_candle_counts_as_stop(self):
        df = flat()
        df.loc[1, "high"] = 103.0
        df.loc[1, "low"] = 97.0
        got = wf.simulate_trades(df, CFG)["buy_ret"].iloc[0]
        self.assertLess(got, 0)

    def test_timeout_exit_and_sell_side(self):
        df = flat()
        df.loc[12, "close"] = 100.5
        out = wf.simulate_trades(df, CFG)
        self.assertAlmostEqual(out["buy_ret"].iloc[0], 0.005 - 0.001, places=9)
        self.assertAlmostEqual(out["sell_ret"].iloc[0], -0.005 - 0.001, places=9)

    def test_last_candles_have_no_result(self):
        out = wf.simulate_trades(flat(), CFG)
        self.assertTrue(np.isnan(out["buy_ret"].iloc[-1]))


def noise(n=6000, seed=1, planted=False):
    rng = np.random.default_rng(seed)
    sigma = 0.004
    r = rng.normal(0, sigma, n)
    if planted:
        for i in range(1, n - 4):
            if r[i - 1] < -1.6 * sigma:
                r[i:i + 3] += 0.9 * sigma
    close = 2000 * np.exp(np.cumsum(r))
    prev = np.r_[2000, close[:-1]]
    hi = np.maximum(prev, close) * (1 + np.abs(rng.normal(0, sigma / 2, n)))
    lo = np.minimum(prev, close) * (1 - np.abs(rng.normal(0, sigma / 2, n)))
    ts = pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC")
    return pd.DataFrame({"timestamp": ts, "open": prev, "high": hi, "low": lo, "close": close, "volume": 0.0})


class ProtocolTests(unittest.TestCase):
    def test_shuffle_keeps_bar_shapes_and_validity(self):
        df = noise(500)
        sh = wf.shuffle_bars(df, np.random.default_rng(1))
        self.assertEqual(len(sh), len(df) - 1)
        self.assertTrue((sh["high"] >= sh[["open", "close"]].max(axis=1) - 1e-9).all())
        self.assertTrue((sh["low"] <= sh[["open", "close"]].min(axis=1) + 1e-9).all())

    def test_pure_noise_finds_little(self):
        found, tried = wf.run_protocol(noise(), CFG)
        self.assertGreater(tried, 1000)
        passes = int(found["final_pass"].sum()) if len(found) else 0
        self.assertLessEqual(passes, 12)

    def test_short_history_is_refused_not_crashed(self):
        found, tried = wf.run_protocol(noise(300), CFG)
        self.assertEqual((len(found), tried), (0, 0))

    def test_planted_pattern_beats_shuffled_copies(self):
        df = noise(planted=True)
        found, _ = wf.run_protocol(df, CFG)
        real = int(found["final_pass"].sum())
        rng = np.random.default_rng(5)
        nulls = []
        for _ in range(6):
            nf, _t = wf.run_protocol(wf.shuffle_bars(df, rng), CFG)
            nulls.append(int(nf["final_pass"].sum()) if len(nf) else 0)
        self.assertGreater(real, float(np.median(nulls)))
        self.assertIn("large_bear_body", " ".join(found[found["final_pass"]]["condition"]))


class DownloadTests(unittest.TestCase):
    def test_paging_and_dedupe(self):
        import websockets

        now = int(datetime.now(timezone.utc).timestamp()) // 900 * 900
        all_epochs = [now - 900 * i for i in range(3000)][::-1]  # 31 days of 15m candles, oldest first

        async def handler(ws):
            async for raw in ws:
                msg = json.loads(raw)
                end = now if msg["end"] == "latest" else int(msg["end"])
                chosen = [e for e in all_epochs if e <= end][-msg["count"]:]
                await ws.send(json.dumps({"candles": [{"epoch": e, "open": 1, "high": 2, "low": 0.5, "close": 1.5} for e in chosen]}))

        async def run():
            async with websockets.serve(handler, "127.0.0.1", 0) as server:
                port = server.sockets[0].getsockname()[1]
                return await dh.download_history(f"ws://127.0.0.1:{port}", "X", 900, days=20, count=1000)

        candles, note = asyncio.run(run())
        epochs = [c["epoch"] for c in candles]
        self.assertEqual(epochs, sorted(set(epochs)))
        self.assertGreaterEqual(len(candles), 20 * 96 - 2)
        self.assertLessEqual(epochs[0], now - 20 * 86400 + 900)

    def test_server_error_keeps_what_we_have(self):
        import websockets

        calls = {"n": 0}

        async def handler(ws):
            async for raw in ws:
                calls["n"] += 1
                if calls["n"] == 1:
                    base = 1_700_000_000
                    await ws.send(json.dumps({"candles": [{"epoch": base + i * 900, "open": 1, "high": 1, "low": 1, "close": 1} for i in range(10)]}))
                else:
                    await ws.send(json.dumps({"error": {"message": "limit"}}))

        async def run():
            async with websockets.serve(handler, "127.0.0.1", 0) as server:
                port = server.sockets[0].getsockname()[1]
                return await dh.download_history(f"ws://127.0.0.1:{port}", "X", 900, days=100000, count=10)

        candles, note = asyncio.run(run())
        self.assertEqual(len(candles), 10)
        self.assertIn("limit", note)


def write_csv(path, cols, rows):
    with open(path, "w", newline="") as h:
        w = csv.DictWriter(h, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


class ScorecardTests(unittest.TestCase):
    def test_scorecard_content(self):
        now = datetime(2026, 11, 16, 7, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "outputs"
            out.mkdir()
            write_csv(out / "deriv_direct_closed_trades.csv", ["track_name", "pnl"],
                      [{"track_name": "demo-cycle-test", "pnl": -0.02}, {"track_name": "Sniper", "pnl": 0.25},
                       {"track_name": "Sniper", "pnl": 0.24}, {"track_name": "Sniper", "pnl": -0.23}])
            ts = (now - timedelta(hours=3)).isoformat()
            write_csv(out / "deriv_direct_order_journal.csv", ["timestamp", "status", "symbol", "side", "message"],
                      [{"timestamp": ts, "status": "skipped", "symbol": "CRASH300N", "side": "sell", "message": "skipped: confidence 0.5 < min_confidence 0.60"},
                       {"timestamp": (now - timedelta(days=3)).isoformat(), "status": "bought"}])
            (out / "deriv_direct_open_positions.json").write_text("[]")
            write_csv(out / "x_paper_journal.csv", ["run_recorded_at_utc", "decision", "symbol", "side", "reason"],
                      [{"run_recorded_at_utc": ts, "decision": "paper_order", "symbol": "CRASH300N", "side": "buy",
                        "reason": "stable promoted rule PAIR017: a is b"},
                       {"run_recorded_at_utc": ts, "decision": "blocked_rule", "symbol": "BOOM300N", "side": "buy",
                        "reason": "stable promoted rule PAIR006: x | blocked by kill-switch: PAIR006 is FREEZE"}])
            text = sc.build_scorecard(Path(tmp), now)
        self.assertIn("3 (2 wins, 1 losses), net +0.26 USD", text)
        self.assertNotIn("demo-cycle-test", text)
        self.assertIn("too early to judge (3 of 30 trades)", text)
        self.assertIn("0 opened, 1 skipped", text)
        self.assertIn("skipped CRASH300N sell: confidence 0.5", text)
        self.assertIn("PAIR017 CRASH300N buy x1", text)
        self.assertIn("PAIR006 freeze", text)
        self.assertIn("DISARMED", text)

    def test_verdict_rules(self):
        base = {"n": 40, "wins": 28, "losses": 12, "net": 3.0, "breakeven": 0.45, "lower": 0.58, "win_rate": 0.7}
        self.assertIn("evidence of an edge", sc.verdict(base))
        self.assertIn("no edge", sc.verdict(dict(base, win_rate=0.4, net=-1.0)))
        self.assertIn("inconclusive", sc.verdict(dict(base, lower=0.40)))

    def test_empty_folder_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = sc.build_scorecard(Path(tmp), datetime(2026, 11, 16, tzinfo=timezone.utc))
        self.assertIn("Closed demo trades: 0 so far", text)


if __name__ == "__main__":
    unittest.main()
