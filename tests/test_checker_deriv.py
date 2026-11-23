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
    pd.DataFrame({"timestamp": ts.astype("int64") // 10**9, "open": c, "high": c * 1.01, "low": c * 0.99, "close": c, "volume": 0}).to_csv(path, index=False)


class Tests(unittest.TestCase):
    def test_only_boom_and_crash_files_are_found(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("BOOM500", "CRASH300N", "R_75"):
                write_daily(Path(d) / f"deriv_{name}_1d.csv")
            self.assertEqual(D.find_symbols(Path(d)), ["BOOM500", "CRASH300N"])

    def test_empty_directory_message(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, str(ROOT / "scripts/checker_deriv.py"), "--data-dir", d], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("No Boom or Crash", r.stdout)
