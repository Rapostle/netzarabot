from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


TASK_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = TASK_ROOT / "outputs"
REPORT = OUTPUT_DIR / "stale_trade_cleanup_report.md"
QUARANTINE_DIR = OUTPUT_DIR / "quarantined_paper_trades"

OPEN_FILES = [
    ("Original stable rules", OUTPUT_DIR / "paper_stable_open_positions.csv"),
    ("Experimental pair candidates", OUTPUT_DIR / "pair_candidate_open_positions.csv"),
    ("Advanced sniper candidates", OUTPUT_DIR / "advanced_sniper_open_positions.csv"),
    ("Boom/Crash expansion candidates", OUTPUT_DIR / "boom_crash_expansion_open_positions.csv"),
]


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def table(rows: list[dict[str, object]]) -> str:
    if not rows:
        return "No stale open paper trades found."
    cols = ["track", "symbol", "timeframe", "side", "opened_at", "age_hours", "suggested_action"]
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body = ["| " + " | ".join(str(row.get(col, "")) for col in cols) + " |" for row in rows]
    return "\n".join([header, sep, *body])


def close_price(row: pd.Series) -> float:
    for key in ["entry", "exit_price"]:
        try:
            value = float(row.get(key, 0.0))
            if value:
                return value
        except (TypeError, ValueError):
            continue
    return 0.0


def paper_pnl(row: pd.Series, exit_price: float) -> float:
    try:
        entry = float(row.get("entry", 0.0))
        qty = float(row.get("quantity", 0.0))
    except (TypeError, ValueError):
        return 0.0
    pnl = (exit_price - entry) * qty
    if str(row.get("side", "")).lower() == "sell":
        pnl *= -1
    return pnl


def scan_stale(apply: bool, min_age_hours: float) -> list[dict[str, object]]:
    now = pd.Timestamp.now(tz="UTC")
    rows = []
    for track, path in OPEN_FILES:
        df = load_csv(path)
        if df.empty or "opened_at" not in df:
            continue
        keep_rows = []
        quarantine_rows = []
        for _, row in df.iterrows():
            opened_at = pd.to_datetime(row.get("opened_at", ""), utc=True, errors="coerce")
            if pd.isna(opened_at):
                keep_rows.append(row.to_dict())
                continue
            age_hours = max((now - opened_at).total_seconds() / 3600.0, 0.0)
            should_quarantine = age_hours >= min_age_hours
            if age_hours >= min_age_hours:
                action = "manual cleanup review; likely stale local-data trade"
            elif age_hours >= 8:
                action = "watch; old paper trade"
            else:
                keep_rows.append(row.to_dict())
                continue
            if apply and should_quarantine:
                exit_price = close_price(row)
                closed = row.to_dict()
                closed.update(
                    {
                        "status": "quarantined",
                        "closed_at": now.isoformat(),
                        "exit_price": exit_price,
                        "paper_pnl": paper_pnl(row, exit_price),
                        "exit_reason": "paper stale cleanup quarantine",
                    }
                )
                quarantine_rows.append(closed)
            else:
                keep_rows.append(row.to_dict())
            rows.append(
                {
                    "track": track,
                    "symbol": row.get("symbol", ""),
                    "timeframe": row.get("timeframe", ""),
                    "side": row.get("side", ""),
                    "opened_at": row.get("opened_at", ""),
                    "age_hours": f"{age_hours:.1f}",
                    "suggested_action": action,
                }
            )
        if apply and quarantine_rows:
            backup = QUARANTINE_DIR / f"{path.stem}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.csv"
            QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_csv(backup, index=False)
            pd.DataFrame(keep_rows, columns=df.columns).to_csv(path, index=False)
            quarantine_path = QUARANTINE_DIR / f"{path.stem}_quarantined.csv"
            pd.DataFrame(quarantine_rows).to_csv(
                quarantine_path,
                mode="a",
                index=False,
                header=not quarantine_path.exists(),
            )
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review or quarantine stale paper trades.")
    parser.add_argument("--apply", action="store_true", help="Move stale paper trades to quarantine files.")
    parser.add_argument("--min-age-hours", type=float, default=24.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = scan_stale(apply=args.apply, min_age_hours=args.min_age_hours)
    lines = [
        "# Stale Trade Cleanup",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Mode: " + ("APPLY - stale trades were quarantined." if args.apply else "REVIEW - no ledgers were changed."),
        "",
        table(rows),
        "",
        "Apply command: `work/run_stale_trade_cleanup_apply.sh`",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved stale trade cleanup report to {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
