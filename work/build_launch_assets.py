from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path


TASK_ROOT = Path("/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot")
OUTPUT_DIR = TASK_ROOT / "outputs"
DOCS_DIR = TASK_ROOT / "docs"
RELEASE_DIR = TASK_ROOT / "releases/v0.1-paper-alpha"
ZIP_PATH = TASK_ROOT / "releases/v0.1-paper-alpha.zip"

ONBOARDING = OUTPUT_DIR / "onboarding_wizard.html"
COMMERCIAL_DOCS = DOCS_DIR / "COMMERCIAL_LAUNCH_DOCS.md"
LAUNCH_SUMMARY = OUTPUT_DIR / "launch_assets_summary.md"
NOTIFICATIONS = OUTPUT_DIR / "local_notifications.md"
RELEASE_MANIFEST = OUTPUT_DIR / "release_manifest.md"
FINAL_GAP_REPORT = OUTPUT_DIR / "final_gap_report.md"


def read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def write_onboarding() -> None:
    html = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trading Bot Onboarding</title>
<style>
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f6f8fb;color:#142033;margin:0}
main{width:min(900px,calc(100% - 28px));margin:0 auto;padding:28px 0}
.step{background:white;border:1px solid #d7deea;border-radius:8px;padding:16px;margin:12px 0}
.danger{background:#fee2e2;border-color:#991b1b;color:#991b1b;font-weight:800}
code{display:block;background:#eef2f7;border-radius:6px;padding:8px;margin-top:8px}
</style></head><body><main>
<h1>Trading Bot Onboarding</h1>
<div class="step danger">This bot is paper-only right now. Do not trade live yet.</div>
<div class="step"><h2>1. Start Paper Test</h2><code>work/start_trading_bot_suite.sh</code></div>
<div class="step"><h2>2. Check Results</h2><code>work/check_bot_status.sh</code></div>
<div class="step"><h2>3. Open Operator Console</h2><code>outputs/operator_console.html</code></div>
<div class="step"><h2>4. Read Readiness</h2><code>outputs/live_readiness_checklist.md</code></div>
</main></body></html>"""
    ONBOARDING.write_text(html, encoding="utf-8")


def write_commercial_docs() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Commercial Launch Docs",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Pricing Ideas",
        "",
        "- Free demo: delayed paper dashboard only.",
        "- Starter: limited paper monitors and reports.",
        "- Pro: all monitors, alerts, rule scorecards, optimization reports.",
        "- Managed pilot: only after legal/compliance review and strict risk limits.",
        "",
        "## User Disclaimer Draft",
        "",
        "This software is a research and automation tool. It does not guarantee profit. Trading involves risk, including loss of capital. Use paper mode first and trade live only after independent review.",
        "",
        "## Refund Policy Draft",
        "",
        "Offer a simple 7-day refund for self-serve subscriptions if the user has not requested custom setup or managed support.",
        "",
        "## Onboarding Message",
        "",
        "Welcome. Start in paper mode, let the monitor collect closed trades, and do not enable live trading until the readiness report approves it.",
        "",
        "## Support Checklist",
        "",
        "- Confirm user is in paper mode.",
        "- Ask for `work/check_bot_status.sh` output.",
        "- Check `outputs/action_alerts.md`.",
        "- Check `outputs/live_readiness_checklist.md`.",
        "- Never advise increasing risk to recover losses.",
        "",
    ]
    COMMERCIAL_DOCS.write_text("\n".join(lines), encoding="utf-8")


def write_notifications() -> None:
    alerts = read(OUTPUT_DIR / "action_alerts.md")
    readiness = read(OUTPUT_DIR / "live_readiness_checklist.md")
    rows = []
    if "near stop" in alerts:
        rows.append(("warning", "Paper trade near stop", "Wait for emergency stop enforcer; do not promote rule."))
    if "stuck" in alerts:
        rows.append(("warning", "Paper trade stuck", "Review stale cleanup report."))
    if "NOT READY" in readiness:
        rows.append(("info", "Live trading blocked", "Readiness checklist still says NOT READY."))
    if not rows:
        rows.append(("info", "No urgent notification", "Keep paper monitors running."))
    table = ["| level | message | action |", "| --- | --- | --- |"]
    table.extend(f"| {level} | {message} | {action} |" for level, message, action in rows)
    NOTIFICATIONS.write_text(
        "\n".join(["# Local Notifications", "", f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}", "", *table, ""]),
        encoding="utf-8",
    )


def build_zip() -> None:
    ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    if RELEASE_DIR.exists():
        shutil.make_archive(str(ZIP_PATH.with_suffix("")), "zip", RELEASE_DIR)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_release_manifest() -> None:
    rows = []
    if RELEASE_DIR.exists():
        for path in sorted(RELEASE_DIR.rglob("*")):
            if path.is_file():
                rows.append(
                    {
                        "file": str(path.relative_to(RELEASE_DIR)),
                        "size": path.stat().st_size,
                        "sha256": file_sha256(path)[:16],
                    }
                )
    if ZIP_PATH.exists():
        rows.append({"file": ZIP_PATH.name, "size": ZIP_PATH.stat().st_size, "sha256": file_sha256(ZIP_PATH)[:16]})
    table = ["| file | size | sha256 short |", "| --- | --- | --- |"]
    table.extend(f"| {row['file']} | {row['size']} | {row['sha256']} |" for row in rows)
    RELEASE_MANIFEST.write_text(
        "\n".join(["# Release Manifest", "", f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}", "", *table, ""]),
        encoding="utf-8",
    )


def write_final_gap_report() -> None:
    readiness = read(OUTPUT_DIR / "live_readiness_checklist.md")
    stale = read(OUTPUT_DIR / "stale_trade_cleanup_report.md")
    gaps = [
        {"area": "Live trading", "status": "blocked", "next": "Wait until readiness checklist no longer says NOT READY."},
        {"area": "Expansion paper trades", "status": "needs cleanup" if "manual cleanup" in stale else "monitoring", "next": "Use cleanup apply only if stale trade is confirmed."},
        {"area": "Paper evidence", "status": "not enough", "next": "Collect at least 10 closed paper trades per candidate track."},
        {"area": "Commercial release", "status": "demo-ready only", "next": "Use demo mode; do not promise profits."},
    ]
    table = ["| area | status | next |", "| --- | --- | --- |"]
    table.extend(f"| {row['area']} | {row['status']} | {row['next']} |" for row in gaps)
    FINAL_GAP_REPORT.write_text(
        "\n".join(["# Final Gap Report", "", f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}", "", *table, ""]),
        encoding="utf-8",
    )


def write_summary() -> None:
    lines = [
        "# Launch Assets Summary",
        "",
        f"Last updated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "- Clickable local app server: `work/local_app_server.py`",
        "- Start local app: `work/start_local_app.sh`",
        "- Onboarding wizard: `outputs/onboarding_wizard.html`",
        "- Local notifications: `outputs/local_notifications.md`",
        "- Commercial launch docs: `docs/COMMERCIAL_LAUNCH_DOCS.md`",
        "- Stale cleanup report: `outputs/stale_trade_cleanup_report.md`",
        "- Release zip: `releases/v0.1-paper-alpha.zip`",
        "- Release manifest: `outputs/release_manifest.md`",
        "- Final gap report: `outputs/final_gap_report.md`",
        "",
    ]
    LAUNCH_SUMMARY.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_onboarding()
    write_commercial_docs()
    write_notifications()
    build_zip()
    write_release_manifest()
    write_final_gap_report()
    write_summary()
    print(f"Saved onboarding wizard to {ONBOARDING}")
    print(f"Saved commercial docs to {COMMERCIAL_DOCS}")
    print(f"Saved notifications to {NOTIFICATIONS}")
    print(f"Saved release zip to {ZIP_PATH}")
    print(f"Saved release manifest to {RELEASE_MANIFEST}")
    print(f"Saved final gap report to {FINAL_GAP_REPORT}")
    print(f"Saved launch summary to {LAUNCH_SUMMARY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
