# Path Fix Patch Notes v2 (applied on top of commit 2e084a4)

## Context

Commit `2e084a4 Rebuild missing trading_bot package` added a real, working
`external/trading_bot` package — verified end-to-end (see below) — but it was
built from a copy of the repo that predated the earlier path-portability
fixes, so it accidentally reverted all 74 of those fixes back to hardcoded
`/Users/ocmix/Documents/Codex/...` paths.

This patch reapplies the same portability fix as before, on top of the new
checkout, plus one additional real bug found by actually running the code
end-to-end this time (see "New fix" below).

## What's the same as before

- All `TASK_ROOT` / `ROOT` definitions in `work/*.py` and
  `live_candidate/work/live_order_blocker.py` resolve via
  `Path(__file__).resolve().parent.parent[.parent]` instead of a hardcoded path.
- All `.sh` scripts compute `PROJECT_ROOT` from their own location.
- `BOT_ROOT` / `TRADING_BOT_ROOT` resolves to `$PROJECT_ROOT/external/trading_bot`
  by default, overridable via the `TRADING_BOT_ROOT` env var.

## New fix: cross-venv import bug

`work/paper_stable_refresh.py` imports `trading_bot` **in-process**
(`from trading_bot.data.deriv_downloader import ...` inside `refresh_data()`),
not just via subprocess. That means the Python interpreter *running*
`paper_stable_refresh.py` itself needs `trading_bot`'s dependencies
(`websockets`, `pyyaml`) available, not just `pandas`.

Fix: the main project `.venv` now has `pandas`, `pyyaml`, and `websockets`
installed (i.e. `external/trading_bot/requirements.txt` installed into both
venvs). `external/trading_bot/.venv` remains separate and is what the
`-m trading_bot.cli.main` subprocess calls actually run under.

## Verified end-to-end (not just imported — actually run)

```
.venv/bin/python work/paper_stable_refresh.py --skip-download \
  --rules-csv live_candidate/config/primary_rules.csv
```
This produced a real decision row via the rebuilt `trading_bot.cli.main
--mode paper-stable-rules`, and updated the journal, dashboard, and
go-live-readiness report correctly.

`download_crypto_data.sh` and `run_crypto_research.sh` could **not** be
verified from this sandbox — they need a live connection to Deriv's
WebSocket API, which this sandbox can't reach. Test those on your Mac or VPS.

## To apply

Unzip over your local clone (overwrites the affected files), then:

```bash
python3 -m venv .venv
.venv/bin/pip install pandas pyyaml websockets

python3 -m venv external/trading_bot/.venv
external/trading_bot/.venv/bin/pip install -r external/trading_bot/requirements.txt
```

Then push this back to `main` (or hand it to Codex to reapply/commit) so the
GitHub copy has both the new package *and* working paths at the same time.
