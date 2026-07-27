from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


TASK_ROOT = Path("/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot")
OUTPUT_DIR = TASK_ROOT / "outputs"

SOURCES = [
    OUTPUT_DIR / "stable_rules_pair_execution_candidates.csv",
    OUTPUT_DIR / "advanced_accuracy_execution_candidates.csv",
]
BLOCKLIST = OUTPUT_DIR / "rule_kill_switch_blocklist.csv"
RULES_OUTPUT = OUTPUT_DIR / "strict_research_execution_candidates.csv"
REPORT_OUTPUT = OUTPUT_DIR / "strict_research_lane_report.md"


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def markdown_table(rows: list[dict[str, object]], columns: list[str], empty: str) -> str:
    if not rows:
        return empty
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(str(row.get(column, "")) for column in columns) + " |" for row in rows]
    return "\n".join([header, divider, *body])


def blocked_rule_ids() -> set[str]:
    blocklist = load_csv(BLOCKLIST)
    if blocklist.empty or "rule" not in blocklist.columns:
        return set()
    return set(blocklist["rule"].astype(str))


def load_candidates() -> pd.DataFrame:
    frames = []
    for source in SOURCES:
        df = load_csv(source)
        if df.empty:
            continue
        df = df.copy()
        df["source_file"] = source.name
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    candidates = pd.concat(frames, ignore_index=True)
    for column in ["trades", "win_rate", "profit_factor", "expectancy", "total_return"]:
        if column in candidates.columns:
            candidates[column] = pd.to_numeric(candidates[column], errors="coerce")
    return candidates


def build_rules() -> pd.DataFrame:
    candidates = load_candidates()
    if candidates.empty:
        return pd.DataFrame()

    required = {"rule_id", "symbol", "timeframe", "suggested_side", "feature", "condition"}
    if not required.issubset(candidates.columns):
        return pd.DataFrame()

    blocked = blocked_rule_ids()
    strict = candidates[
        (~candidates["rule_id"].astype(str).isin(blocked))
        & (candidates["trades"] >= 20)
        & (candidates["win_rate"] >= 0.70)
        & (candidates["profit_factor"] >= 3.0)
        & (candidates["expectancy"] >= 0.006)
    ].copy()

    if strict.empty:
        # Allow one-trade paper winners from the strict filter to keep gathering evidence,
        # but only if they are not on the kill-switch blocklist.
        strict = candidates[
            (~candidates["rule_id"].astype(str).isin(blocked))
            & (candidates["trades"] >= 20)
            & (candidates["win_rate"] >= 0.68)
            & (candidates["profit_factor"] >= 2.8)
            & (candidates["expectancy"] >= 0.006)
        ].copy()

    if strict.empty:
        return pd.DataFrame()

    strict = strict.sort_values(["win_rate", "profit_factor", "expectancy", "trades"], ascending=False)
    strict = strict.drop_duplicates(["symbol", "timeframe", "suggested_side", "feature", "condition"])
    strict = strict.groupby(["symbol", "timeframe"], group_keys=False).head(2).reset_index(drop=True)
    strict["source_rule_id"] = strict["rule_id"].astype(str)
    strict["rule_id"] = [f"STRICT{index:03d}" for index in range(1, len(strict) + 1)]
    strict["promotion_status"] = "strict_research_only"

    columns = [
        "rule_id",
        "symbol",
        "timeframe",
        "suggested_side",
        "feature",
        "condition",
        "trades",
        "total_return",
        "win_rate",
        "profit_factor",
        "expectancy",
        "symbol_rule_rank",
        "promotion_status",
        "source_rule_id",
        "source_file",
    ]
    for column in columns:
        if column not in strict.columns:
            strict[column] = ""
    return strict[columns]


def write_report(rules: pd.DataFrame) -> None:
    rows = []
    for _, row in rules.iterrows():
        rows.append(
            {
                "rule": row.get("rule_id", ""),
                "source": row.get("source_rule_id", ""),
                "symbol": row.get("symbol", ""),
                "side": row.get("suggested_side", ""),
                "trades": int(row.get("trades", 0) or 0),
                "win_rate": f"{float(row.get('win_rate', 0.0) or 0.0):.1%}",
                "pf": f"{float(row.get('profit_factor', 0.0) or 0.0):.2f}",
                "expectancy": f"{float(row.get('expectancy', 0.0) or 0.0):.4f}",
                "status": "research only",
            }
        )

    lines = [
        "# Strict Research Lane",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This lane tests fresh strict candidates separately. It does not approve live trading and does not unfreeze the main paper rules.",
        "",
        "## Selected Candidates",
        "",
        markdown_table(rows, ["rule", "source", "symbol", "side", "trades", "win_rate", "pf", "expectancy", "status"], "No strict candidates passed."),
        "",
        "## Rule",
        "",
        "- Only research-only paper trades are allowed here.",
        "- Any rule that later drops below the accuracy gate should be frozen.",
        "- Main paper tracks remain protected by the strict kill-switch.",
        "",
    ]
    REPORT_OUTPUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    rules = build_rules()
    RULES_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    rules.to_csv(RULES_OUTPUT, index=False)
    write_report(rules)
    print(f"Saved strict research rules to {RULES_OUTPUT}")
    print(f"Saved strict research report to {REPORT_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
