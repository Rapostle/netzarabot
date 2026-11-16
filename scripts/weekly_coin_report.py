"""Weekly coin paper-bot report.  python3 scripts/weekly_coin_report.py --repo-root /root/netzarabot [--send]"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from coinbot.report import build_weekly  # noqa: E402
import daily_scorecard as sc  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--send", action="store_true")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    sc.load_env()
    text = build_weekly(root / "outputs", root / "checker_cache", datetime.now(timezone.utc))
    print(text)
    if args.send:
        print("sent" if sc.send_telegram(text) else "not sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
