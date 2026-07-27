from __future__ import annotations

import json
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


TASK_ROOT = Path("/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot")
OUTPUT_DIR = TASK_ROOT / "outputs"
LOG_DIR = OUTPUT_DIR / "service_logs"
HOST = "127.0.0.1"
PORT = 8765


def run_command(command: list[str]) -> dict[str, object]:
    result = subprocess.run(command, cwd=TASK_ROOT, capture_output=True, text=True, check=False)
    return {
        "ok": result.returncode == 0,
        "exit_code": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
    }


def service_status(name: str) -> dict[str, object]:
    pid_file = LOG_DIR / f"{name}.pid"
    log_file = LOG_DIR / f"{name}.log"
    running = False
    pid = ""
    if pid_file.exists():
        pid = pid_file.read_text(encoding="utf-8").strip()
        if pid:
            running = subprocess.run(["kill", "-0", pid], check=False, capture_output=True).returncode == 0
    log_tail = ""
    if log_file.exists():
        log_tail = "\n".join(log_file.read_text(encoding="utf-8", errors="ignore").splitlines()[-20:])
    return {"name": name, "running": running, "pid": pid, "log_tail": log_tail}


def read_status() -> dict[str, object]:
    return {
        "services": [service_status("main_monitor"), service_status("expansion_monitor")],
        "alerts": read_text(OUTPUT_DIR / "action_alerts.md"),
        "readiness": read_text(OUTPUT_DIR / "live_readiness_checklist.md"),
        "watchdog": read_text(OUTPUT_DIR / "open_trade_watchdog.md"),
    }


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def page_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Trading Bot Local App</title>
  <style>
    :root { --bg:#f6f8fb; --panel:#fff; --ink:#142033; --muted:#667085; --line:#d7deea; --ok:#075985; --bad:#991b1b; }
    * { box-sizing:border-box; }
    body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:var(--bg); color:var(--ink); }
    main { width:min(1100px,calc(100% - 28px)); margin:0 auto; padding:28px 0; }
    h1 { margin:0 0 6px; }
    .banner { background:#fee2e2; color:var(--bad); border:1px solid var(--bad); border-radius:8px; padding:12px; font-weight:800; margin:14px 0; }
    .buttons { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:10px; margin:16px 0; }
    button { border:1px solid var(--line); background:var(--panel); border-radius:8px; padding:12px; font-weight:800; cursor:pointer; }
    button.primary { border-color:var(--ok); color:var(--ok); }
    button.danger { border-color:var(--bad); color:var(--bad); }
    .grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }
    .panel { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:14px; min-height:120px; }
    pre { white-space:pre-wrap; overflow:auto; background:#eef2f7; padding:10px; border-radius:8px; }
    .service { border:1px solid var(--line); border-radius:8px; padding:10px; margin:8px 0; }
    .running { border-color:var(--ok); }
    @media(max-width:900px){ .buttons,.grid { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <main>
    <h1>Trading Bot Local App</h1>
    <p>Clickable local controls for paper monitoring.</p>
    <div class="banner">Paper mode only. Live trading is locked out.</div>
    <div class="buttons">
      <button class="primary" onclick="callApi('/api/start')">Start Monitors</button>
      <button class="danger" onclick="callApi('/api/stop')">Stop Monitors</button>
      <button onclick="callApi('/api/refresh')">Refresh Reports</button>
      <button onclick="callApi('/api/cleanup')">Cleanup Check</button>
      <button class="danger" onclick="callApi('/api/cleanup-apply')">Apply Stale Cleanup</button>
      <button onclick="loadStatus()">Check Status</button>
      <button onclick="location.href='/mobile'">Mobile Auto App</button>
      <button onclick="location.href='/mobile-admin'">SaaS Admin</button>
    </div>
    <div class="grid">
      <section class="panel"><h2>Services</h2><div id="services"></div></section>
      <section class="panel"><h2>Last Action</h2><pre id="action">Ready.</pre></section>
      <section class="panel"><h2>Alerts</h2><pre id="alerts"></pre></section>
      <section class="panel"><h2>Readiness</h2><pre id="readiness"></pre></section>
      <section class="panel"><h2>Watchdog</h2><pre id="watchdog"></pre></section>
    </div>
  </main>
<script>
async function callApi(path) {
  const res = await fetch(path, {method: 'POST'});
  const data = await res.json();
  document.getElementById('action').textContent = JSON.stringify(data, null, 2);
  await loadStatus();
}
async function loadStatus() {
  const res = await fetch('/api/status');
  const data = await res.json();
  document.getElementById('services').innerHTML = data.services.map(s => `<div class="service ${s.running ? 'running' : ''}"><strong>${s.name}</strong><br>${s.running ? 'Running' : 'Stopped'} ${s.pid || ''}<pre>${s.log_tail || ''}</pre></div>`).join('');
  document.getElementById('alerts').textContent = data.alerts || 'No alerts file yet.';
  document.getElementById('readiness').textContent = data.readiness || 'No readiness file yet.';
  document.getElementById('watchdog').textContent = data.watchdog || 'No watchdog file yet.';
}
loadStatus();
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def send_json(self, data: dict[str, object]) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/status":
            self.send_json(read_status())
            return
        if path == "/mobile":
            body = read_text(OUTPUT_DIR / "mobile_saas_app.html").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/mobile-admin":
            body = read_text(OUTPUT_DIR / "mobile_saas_admin.html").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        body = page_html().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/start":
            self.send_json(run_command(["bash", "work/start_trading_bot_suite.sh"]))
        elif path == "/api/stop":
            self.send_json(run_command(["bash", "work/stop_trading_bot_suite.sh"]))
        elif path == "/api/refresh":
            self.send_json(run_command(["bash", "work/run_monitor_overview.sh"]))
        elif path == "/api/cleanup":
            self.send_json(run_command(["bash", "work/run_stale_trade_cleanup.sh"]))
        elif path == "/api/cleanup-apply":
            self.send_json(run_command(["bash", "work/run_stale_trade_cleanup_apply.sh"]))
        else:
            self.send_json({"ok": False, "error": "Unknown endpoint"})


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Local trading bot app: http://{HOST}:{PORT}", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
