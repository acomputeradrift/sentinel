# Sentinel Development Environment and Workflow (Local + Droplet)

Purpose: describe **how we develop and deploy** (repo layout, local vs droplet, services, safe workflows). This is **not** an app description.

## Workspace + rules

- Local workspace root (Windows): `\\mac\Home\Desktop\Development\Sentinel`
- Shell: PowerShell
- Git branch prefix: `codex/`
- Primary process rules: `AGENTS.md`
  - Scope + approval required before edits.
  - Test-first methodology required for implementation.
  - Playwright required for runtime UI tests.
- Additional directive files live under `docs/` and are treated as equal to root directives.

## Temp test environment (`.tmp_apex_env`)

Purpose: single local venv for **Sentinel package deps, FastAPI stack, and Playwright** so regression and UI runtime tests do not depend on a random system Python.

- Path (Windows): `Y:\Desktop\Development\Sentinel\.tmp_apex_env`
- Path (UNC): `\\mac\Home\Desktop\Development\Sentinel\.tmp_apex_env`
- Python venv structure: `Scripts\python`, `Lib\site-packages`
- **Create / refresh:** from repo root, run `python devtools/bootstrap_tmp_apex_env.py` (installs `pip install -e ".[dev]"` and `playwright install chromium`). Safe to re-run after `pyproject.toml` changes.
- **Regression tests:** `python devtools/run_regression_with_venv.py` (uses this venv and writes `devtools/last_regression_run.txt` if you need a log file).
- Details and optional `DATABASE_URL`: see `docs/directives/testing_strategy.md` → *Local execution*.
- Playwright browsers cache under the user profile, for example:
  - `C:\Users\<user>\AppData\Local\ms-playwright\chromium-*`

## Repo layout (high-level)

- Server (FastAPI):
  - `src/sentinel/server/`
- UI assets served by the server:
  - `src/sentinel/ui/`
  - Commissioning console UI: `src/sentinel/ui/commissioning/`
- Tests:
  - Regression: `dev_tests/regression/`
  - UI/runtime (Playwright): `dev_tests/ui/`

## Local development notes

- `rg` (ripgrep) may be blocked on this machine. Prefer PowerShell equivalents:
  - Find files: `Get-ChildItem -Recurse`
  - Search text: `Select-String`
- Prefer `python devtools/bootstrap_tmp_apex_env.py` and `python devtools/run_regression_with_venv.py` so FastAPI/Playwright tests do not skip for missing imports. If you run `python` without that venv, many server tests will skip or behave differently.
- **PowerShell command chaining:** on some Windows PowerShell versions, `cmd1 && cmd2` is not valid; use `cmd1 ; cmd2` to run deploy steps sequentially in one line.

## Droplet (remote server) topology

- SSH alias: `ssh sentinelServer`
- App directory: `/opt/sentinel/app`
- Python venv: `/opt/sentinel/venv`
- Services:
  - Sentinel app: `sentinel.service` (Uvicorn on `127.0.0.1:8000`)
  - Reverse proxy: `nginx` (port 80) → proxies to `127.0.0.1:8000`
- Nginx site config:
  - `/etc/nginx/sites-available/sentinel` (symlinked from `sites-enabled`)
  - Must proxy the normal HTTP app and any WebSocket endpoints with Upgrade headers.

## Safe deployment workflow (recommended)

Goal: deploy code **once**, without stale files, without a crash/restart loop, and without “it uploaded but the server is still old.”

### Why deploys feel slow or take multiple attempts

- **`git archive` only sees commits.** If you zip before `git commit`, the droplet gets the **previous** `HEAD` revision while `scp`/`extract` “succeed”—you only notice after verification (or never).
- **Skipping pre-restart checks.** If Postgres migrations or import errors occur at boot, `systemctl` restart-loops; you burn time in `journalctl` instead of one `grep` on extracted files before restart.
- **502 immediately after restart** is normal for a few seconds (Uvicorn behind nginx). Retry with `curl --max-time` instead of treating the first 502 as a failed deploy.

### Preflight (local — do this before `scp`)

1. **Commit** — `git add` / `git commit` everything you intend to deploy. **`git archive` only packs committed files**; uncommitted edits never reach the zip. (Avoid blind `git add src`; see Known gotchas for `egg-info`.)
2. `git status` — working tree clean (or you explicitly accept no further changes before archiving).
3. `git rev-parse HEAD` — copy the hash into chat / ticket (**this is what you are deploying**).
4. `git archive --format=zip -o sentinel_patch.zip HEAD src`
5. **Prove the zip contains new bits** (pick a path you changed in this commit):
   - PowerShell: `python -m zipfile -l sentinel_patch.zip | Select-String "sentinel/server/persistence/queries.py"`
   - If the member is missing or looks wrong, **stop** — fix commit/archive, do not `scp` yet.

### One-shot deploy (PowerShell — strict order, no `&&`)

Run **one line at a time** (or a single script block where each step must succeed). Use `ssh -o BatchMode=yes` so a missing key does not hang waiting for a password.

```powershell
# 0) From repo root — commit first (see Preflight step 1). Optional: $env:SENTINEL_DEPLOY_TIP = (git rev-parse --short HEAD)

# 1) Archive (only committed files under src/)
git archive --format=zip -o sentinel_patch.zip HEAD src

# 2) Upload
scp sentinel_patch.zip sentinelServer:/tmp/sentinel_patch.zip

# 3) Extract (overwrite)
ssh -o BatchMode=yes sentinelServer 'sudo python3 -m zipfile -e /tmp/sentinel_patch.zip /opt/sentinel/app'

# 4) PRE-RESTART proof — replace the grep string when this deploy’s marker changes
ssh -o BatchMode=yes sentinelServer 'test -f /opt/sentinel/app/src/sentinel/server/persistence/db.py && grep -q _split_sql_migration_statements /opt/sentinel/app/src/sentinel/server/persistence/db.py && echo DEPLOY_OK'

# 5) Restart (needs passwordless sudo for systemctl, or run from an interactive root shell)
ssh -o BatchMode=yes sentinelServer 'sudo -n systemctl restart sentinel'

# 6) Warm-up + health (retry 502 a few times)
Start-Sleep -Seconds 6
ssh -o BatchMode=yes sentinelServer 'curl -sS --max-time 10 http://127.0.0.1/health'

# 7) Route check (nginx → app)
ssh -o BatchMode=yes sentinelServer 'curl -sS --max-time 10 -I http://127.0.0.1/commissioning/ | head -n 5'
```

If step **4** fails, **do not restart** — re-archive, re-copy, re-extract until it passes (or fix the marker/grep).

### Mandatory deployment sequence (no parallelization)

Same as the script above, in words:

1. Commit so `HEAD` matches intent; record `git rev-parse HEAD`; build archive; **confirm zip lists expected paths**.
2. Copy archive to `/tmp/sentinel_patch.zip` on the droplet.
3. Extract with overwrite into `/opt/sentinel/app`.
4. **Verify on-disk content** (grep marker, or `verify_deploy_hash.py` on the droplet — see below) **before** `systemctl restart`.
5. Restart `sentinel.service`.
6. Health check after a short sleep; retry on 502.
7. Route-level check (`/commissioning/` or equivalent).

Do not run copy, extract, and restart in parallel, and **do not restart before step 4 passes**.

**Route-level verification (proven on 2026-04-12):** after health is OK, from the droplet check the commissioning UI path (served via nginx → app), for example:

- `curl -sS -I http://127.0.0.1/commissioning/` → expect `HTTP/1.1 200` and HTML content type.
- Responses may include an `x-request-id` header (trace middleware); presence confirms the new stack is in front of static routes.

If `SENTINEL_COMMISSIONING_API_KEY` is set in the service environment **without** configuring the browser (see `docs/directives/commissioning_security_model.md`), commissioning REST calls will return **401** until the matching header or WS `commissioningKey` query is supplied—either unset the key on trusted LAN-only deploys or configure operators accordingly.

### Mandatory post-extract verification

Before restarting, verify the server file matches the archive for changed files.

Example (required check pattern):
- Compare hash of `/tmp/sentinel_patch.zip` entry vs `/opt/sentinel/app/...` target file.
- Or verify exact expected marker lines in deployed source with `grep`/`sed`.

If verification fails, stop and re-extract with overwrite before restart.

Important hash-check note:
- On Windows working trees, local file hashes can differ from deployed hashes because of line-ending conversion.
- Verify against archive bytes (`sentinel_patch.zip` entry hash) vs server file hash, not working-tree file hash.

Validation note:
- A brief `502 Bad Gateway` can occur immediately after restart while Uvicorn is still coming up behind Nginx.
- Treat this as expected during the first seconds; retry health check after a short delay before treating it as a failure.

Known gotchas:
- Avoid `rsync --delete` against `/opt/sentinel/app` (it can remove required modules and break imports).
- I initially did a bad deploy step by running copy/extract in parallel; that could extract an old zip.
- I corrected it with a strict sequential redeploy and re-verified server file contents.
- Repeated failure: extraction completed but did not overwrite an existing server file, leaving old runtime behavior active.
- Prevention: force overwrite extraction + pre-restart source/hash verification is mandatory.
- Some droplets do not have `unzip` installed; do not assume `unzip -o` is available.
- Preferred fallback when `unzip` is missing: `sudo python3 -m zipfile -e /tmp/sentinel_patch.zip /opt/sentinel/app`.
- Windows PowerShell quoting for complex `ssh "...python -c ..."` commands is fragile; prefer simple remote commands (or script files) over nested one-liners.
- Proven Windows-safe remote execution pattern (verified on 2026-04-12):
  1) Write a local temporary script file.
  2) `scp .tmp_remote_probe.py sentinelServer:/tmp/codex_remote_probe.py`
  3) `ssh sentinelServer "python3 /tmp/codex_remote_probe.py"`
  4) Cleanup both sides: `ssh sentinelServer "rm -f /tmp/codex_remote_probe.py"` and `Remove-Item -Force .tmp_remote_probe.py`
- Do not use inline PowerShell heredoc/one-liner remote Python payloads over `ssh` for deploy verification steps.
- **`pip install -e .` / editable installs** can create `src/sentinel.egg-info/` (and similar). Do **not** commit those into `git archive HEAD src` deploys—they are build metadata, not application source. They are listed in `.gitignore`; if they were ever committed, remove them from the index with `git rm -r --cached src/sentinel.egg-info` and commit once.
- **SQL migrations:** `apply_migrations` runs each `*.sql` file using a **comment- and string-aware** splitter (skips `--` line comments, respects `'...'` literals including `''` escapes). Prefer keeping migrations simple; avoid PostgreSQL **dollar-quoted** bodies in migration files unless we extend the splitter.

### Optional: `verify_deploy_hash.py` (strongest pre-restart proof)

Path: `deployment/verify_deploy_hash.py` — compares SHA-256 of a zip member to the extracted file on disk. **Copy it to the droplet** (or `scp` to `/tmp/`), run **after extract, before restart**:

```powershell
scp deployment/verify_deploy_hash.py sentinelServer:/tmp/verify_deploy_hash.py
ssh -o BatchMode=yes sentinelServer 'python3 /tmp/verify_deploy_hash.py --member src/sentinel/server/persistence/db.py --deployed /opt/sentinel/app/src/sentinel/server/persistence/db.py'
```

Adjust `--member` / `--deployed` to a file you changed. Exit code `0` means zip and disk match. Defaults: `--help` on the droplet.

### If zip creation is blocked locally

In some environments, the command runner/policy layer may block zip creation via:
- `Compress-Archive`
- `python -m zipfile`

Proven workaround:
- Prefer `git archive` to create deployment zips (it has been reliable in this project).

Fallback (only if zipping is not possible):
- Use targeted copy of specific folders (example: deploy only `src/`), and avoid any “delete” behavior.
- Do not use `rsync --delete` for deployment.

## WebSocket support on the droplet

If the server logs show:
- `No supported WebSocket library detected...`

Install WebSocket runtime support into the venv:
- `/opt/sentinel/venv/bin/python -m pip install websockets`

Then restart:
- `sudo systemctl restart sentinel`

## State + live updates (dev wiring)

Principles:
- **Server is source of truth**.
- UI panels subscribe to project-scoped updates.
- Actions are sent to the server, validated, persisted, and then broadcast back to all subscribers.

Project subscription concept:
- “Room/channel per project” maps to a project-scoped endpoint.
- Panels connect once per open browser session and stay connected while the page is open.

Operational requirement:
- If live updates are expected but not observed, verify:
  - The browser is actually connecting (WS accepted in logs).
  - Nginx has Upgrade headers for the endpoint.
  - The venv has `websockets` or equivalent installed.
  - The UI assets being served are the ones you think (avoid stale deploys/caches).

## Subagents + branch hygiene

- Subagents should have **non-overlapping file scopes**.
- Prefer read-only subagent work unless explicitly instructed to implement.
- Coordinator merges only after user approves the scoped file list for each change.

## Full workflow (tests → deploy)

Goal: ensure tested code only is deployed.

If test have been run on the new work, already, skip the retest below, but tell me.

1) Unit/regression tests (local)
   - Use temp env interpreter (required):
     - `Y:\Desktop\Development\Sentinel\.tmp_apex_env\Scripts\python -m unittest discover -s dev_tests/regression -p "test_*.py"`
   - Do not run local tests with system/default `python`.
   - If a test skips for missing dependencies, re-run once with the temp env interpreter before reporting a skip.

2) UI runtime tests (Playwright)
   - Use the temp env:
     - `\\mac\Home\Desktop\Development\Sentinel\.tmp_apex_env\Scripts\python -m unittest dev_tests.ui.test_testing_result_posting`
     - `\\mac\Home\Desktop\Development\Sentinel\.tmp_apex_env\Scripts\python -m unittest dev_tests.ui.test_commissioning_console_runtime`

Intent Check Gate (required before deploy)
- Question: `Did this solution fix the exact user-visible problem Jamie reported?`
- Record evidence in this exact format:
  - `Original problem: ...`
  - `Test run that directly reproduces it: ...`
  - `Observed before: ...`
  - `Observed after: ...`
  - `Pass/Fail: ...`
- Deploy is blocked unless `Pass/Fail` is explicitly `Pass`.

3) Deploy to droplet
   - Follow **Safe deployment workflow** above (preflight → one-shot script → pre-restart verify → restart → health → route).
   - Prefer **`git add` with paths you intend to ship** (e.g. specific packages under `src/sentinel/`), not blind `git add src`, so editable-install metadata such as `src/sentinel.egg-info/` is never committed (see Known gotchas).
   - After deploy validation passes, run cleanup helper:
     - Local only: `powershell -ExecutionPolicy Bypass -File deployment/cleanup_post_run.ps1`
     - Local + remote `/tmp`: `powershell -ExecutionPolicy Bypass -File deployment/cleanup_post_run.ps1 -CleanRemote`

## Post-test cleanup workflow (required)

Goal: do not leave disposable test/deploy artifacts behind after local runs.

Run this cleanup step after test runs, perf runs, and deploy runs.

Preferred (single command):

- Local only: `powershell -ExecutionPolicy Bypass -File deployment/cleanup_post_run.ps1`
- Local + remote `/tmp`: `powershell -ExecutionPolicy Bypass -File deployment/cleanup_post_run.ps1 -CleanRemote`

Manual equivalent (if helper script is unavailable):

1) Remove known local disposable temp run folders:
   - `Remove-Item -Recurse -Force .tmp_perf_*`
   - `Remove-Item -Recurse -Force .tmp_run_*`

2) Remove local disposable deployment/test artifacts from repo root:
   - `Remove-Item -Force deploy_*.zip`
   - `Remove-Item -Force sentinel_patch.zip`
   - `Remove-Item -Force .deploy_verify.txt`
   - `Remove-Item -Force npx_mermaid_log.txt`
   - `Remove-Item -Force .tmp_remote_probe.py`

3) Keep persistent tooling env:
   - Do not delete `.tmp_apex_env` (shared Playwright/runtime environment).

4) Remote cleanup after deploy (droplet):
   - `ssh -o BatchMode=yes sentinelServer "rm -f /tmp/sentinel_patch.zip /tmp/verify_deploy_hash.py /tmp/codex_remote_probe.py"`
   - If deploy used ad-hoc temp probes/scripts, remove them from `/tmp` in the same step.

5) Verify workspace is clean of disposable artifacts:
   - `git status --short`
   - `Get-ChildItem -Force -Name .tmp_*`
   - `Get-ChildItem -Force -Name *.zip`
   - `Get-ChildItem -Force -Name *.txt`
   - If `*.txt` is noisy for your repo, at least verify `.deploy_verify.txt` and `npx_mermaid_log.txt` are absent.

Operator rule:
- If a disposable artifact appears repeatedly from a command, either run cleanup immediately after that command or add the command to a wrapper that runs cleanup in a `finally` step.
