import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
import checker_deriv as D  # noqa: E402


def write_daily(path: Path, n=900, seed=1):
    rng = np.random.default_rng(seed)
    c = 1000 * np.cumprod(1 + rng.normal(0, 0.01, n))
    ts = pd.date_range("2022-01-01", periods=n, freq="D", tz="UTC")
    pd.DataFrame({"timestamp": (ts - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta("1s"), "open": c, "high": c * 1.01, "low": c * 0.99, "close": c, "volume": 0}).to_csv(path, index=False)


class Tests(unittest.TestCase):
    def test_only_boom_and_crash_files_are_found(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("BOOM500", "CRASH300N", "R_75"):
                write_daily(Path(d) / f"deriv_{name}_1d.csv")
            self.assertEqual(D.find_symbols(Path(d)), ["BOOM500", "CRASH300N"])

    def test_daily_candles_are_built_from_five_minute_files(self):
        with tempfile.TemporaryDirectory() as d:
            n = 288 * 40
            rng = np.random.default_rng(3)
            c = 1000 * np.cumprod(1 + rng.normal(0, 0.001, n))
            ts = pd.date_range("2024-01-01", periods=n, freq="5min", tz="UTC")
            pd.DataFrame({"timestamp": (ts - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta("1s"), "open": c, "high": c, "low": c, "close": c}).to_csv(Path(d) / "deriv_BOOM500_5m.csv", index=False)
            self.assertEqual(D.find_symbols(Path(d)), ["BOOM500"])
            day = D.daily_close(Path(d), "BOOM500")
            self.assertEqual(len(day), 40)
            self.assertAlmostEqual(float(day.iloc[0]), float(c[287]))

    def test_short_history_prints_one_line(self):
        with tempfile.TemporaryDirectory() as d:
            write_daily(Path(d) / "deriv_BOOM500_1d.csv", n=100)
            r = subprocess.run([sys.executable, str(ROOT / "scripts/checker_deriv.py"), "--data-dir", d, "--null-runs", "5"], capture_output=True, text=True)
            self.assertIn("BOOM500: only 100 daily candles", r.stdout)
            self.assertNotIn("momentum_20", r.stdout)

    def test_short_indices_fall_back_to_family_bundles(self):
        with tempfile.TemporaryDirectory() as d:
            for i, n in enumerate(("BOOM300N", "BOOM500", "BOOM900", "CRASH300N", "CRASH500", "CRASH900")):
                write_daily(Path(d) / f"deriv_{n}_1d.csv", n=360, seed=i)
            r = subprocess.run([sys.executable, str(ROOT / "scripts/checker_deriv.py"), "--data-dir", d, "--null-runs", "20"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("BOOM bundle (3 indices", r.stdout)
            self.assertIn("CRASH bundle (3 indices", r.stdout)
            self.assertIn("momentum_20", r.stdout)

    def test_empty_directory_message(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, str(ROOT / "scripts/checker_deriv.py"), "--data-dir", d], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("No Boom or Crash", r.stdout)
