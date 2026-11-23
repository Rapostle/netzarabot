"""Read-only health check of the pm2 jobs: is each stopped job meant to be stopped?

    .venv/bin/python scripts/job_health.py [--filter netzara]
A stopped job with a schedule (cron_restart) and recent log activity is normal: it runs, exits, and waits.
A stopped job with no schedule is stopped for good. Nothing is started, stopped or changed.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path


def classify(job: dict, now: float) -> tuple[str, str]:
    env = job.get("pm2_env", {})
    status = env.get("status", "?")
    cron = env.get("cron_restart") or ""
    logs = [Path(p) for p in (env.get("pm_out_log_path"), env.get("pm_err_log_path")) if p]
    mtimes = [p.stat().st_mtime for p in logs if p.exists()]
    age_h = (now - max(mtimes)) / 3600 if mtimes else None
    last = f"last log activity {age_h:.1f}h ago" if age_h is not None else "no log file found"
    if status == "online":
        return "running", last
    if status == "stopped" and cron:
        return "scheduled", f"schedule '{cron}'; {last}"
    if status == "stopped":
        return "STOPPED, NO SCHEDULE", f"restarts so far {env.get('restart_time', 0)}; {last}"
    return status.upper(), last


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--filter", default="")
    a = ap.parse_args()
    jobs = json.loads(subprocess.run(["pm2", "jlist"], capture_output=True, text=True, check=True).stdout)
    now = time.time()
    for j in sorted(jobs, key=lambda x: x.get("name", "")):
        if a.filter in j.get("name", ""):
            state, detail = classify(j, now)
            print(f"{j['name']:<28} {state:<22} {detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
