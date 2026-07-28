from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


TASK_ROOT = Path("/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot")
BOT_ROOT = Path("/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/external/trading_bot")
OUTPUT_DIR = TASK_ROOT / "outputs"
BOT_REPORTS = BOT_ROOT / "reports"
BOT_DATA = BOT_ROOT / "data"

OUTPUT = OUTPUT_DIR / "crypto_research_report.md"


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def md_table(rows: list[dict[str, object]], columns: list[str], empty: str) -> str:
    if not rows:
        return empty
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(str(row.get(column, "")) for column in columns) + " |" for row in rows]
    return "\n".join([header, divider, *body])


def data_inventory() -> list[dict[str, object]]:
    rows = []
    for symbol in ["cryBTCUSD", "cryETHUSD"]:
        files = sorted(BOT_DATA.glob(f"deriv_{symbol}_*.csv"))
        timeframes = []
        candles = 0
        for path in files:
            label = path.stem.replace(f"deriv_{symbol}_", "")
            timeframes.append(label)
            try:
                candles += max(sum(1 for _ in path.open("r", encoding="utf-8")) - 1, 0)
            except OSError:
                pass
        rows.append(
            {
                "symbol": symbol,
                "timeframes": ", ".join(timeframes) if timeframes else "none",
                "files": len(files),
                "total_candles": candles,
            }
        )
    return rows


def summarize_report(path: Path, source: str) -> list[dict[str, object]]:
    df = load_csv(path)
    if df.empty:
        return []
    rows = []
    if "decision" in df.columns:
        candidates = df[df["decision"].astype(str).str.lower().isin(["watch", "promote", "candidate"])]
        if candidates.empty:
            best = df.sort_values(
                [column for column in ["avg_return", "avg_profit_factor", "total_trades"] if column in df.columns],
                ascending=False,
            ).head(5)
        else:
            best = candidates.head(5)
    else:
        best = df.head(5)
    for _, row in best.iterrows():
        rows.append(
            {
                "source": source,
                "strategy": row.get("strategy", ""),
                "recipe": row.get("combo_variant", row.get("timeframe", "")),
                "symbols": row.get("symbols", ""),
                "trades": row.get("total_trades", row.get("trades", "")),
                "avg_return": row.get("avg_return", row.get("total_return", "")),
                "profit_factor": row.get("avg_profit_factor", row.get("profit_factor", "")),
                "decision": row.get("decision", "research"),
            }
        )
    return rows


def existing_crypto_evidence() -> list[dict[str, object]]:
    rows = []
    rows.extend(summarize_report(BOT_REPORTS / "crypto_combined_optimizer_5m_promising_summary.csv", "existing combined optimizer"))
    rows.extend(summarize_report(OUTPUT_DIR / "crypto_timeframe_audit_summary.csv", "workspace timeframe audit"))
    rows.extend(summarize_report(OUTPUT_DIR / "crypto_combined_research_5m_summary.csv", "workspace combined research"))
    return rows


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    evidence = existing_crypto_evidence()
    has_candidate = any(str(row.get("decision", "")).lower() in {"watch", "promote", "candidate"} for row in evidence)
    status = "RESEARCH ONLY"
    reason = "No crypto recipe has passed the same evidence gates as Experimental pair or Advanced sniper."
    if has_candidate:
        status = "NEEDS PAPER TEST"
        reason = "At least one crypto research row needs a dedicated paper lane before it can be trusted."

    lines = [
        "# Crypto Research Report",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"Status: **{status}**",
        "",
        reason,
        "",
        "## Available Crypto Data",
        "",
        md_table(data_inventory(), ["symbol", "timeframes", "files", "total_candles"], "No crypto data files found."),
        "",
        "## Current Evidence",
        "",
        md_table(
            evidence,
            ["source", "strategy", "recipe", "symbols", "trades", "avg_return", "profit_factor", "decision"],
            "No crypto research evidence found yet.",
        ),
        "",
        "## Rule",
        "",
        "- Crypto stays separate from the current profitable Boom/Crash paper tracks.",
        "- Crypto must pass backtest, walk-forward, and paper testing before any live step.",
        "- Do not promote crypto just because BTC/ETH are popular; promote only if the numbers prove it.",
        "",
        "## Commands",
        "",
        "Refresh/download crypto data:",
        "",
        "`work/download_crypto_data.sh`",
        "",
        "Run crypto research locally:",
        "",
        "`work/run_crypto_research.sh`",
        "",
    ]
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved crypto research report to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
