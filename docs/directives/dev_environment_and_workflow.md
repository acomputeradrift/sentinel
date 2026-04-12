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

## Temp test environment (Playwright)

Purpose: run UI runtime tests with Playwright.

- Path (Windows): `Y:\Desktop\Development\Sentinel\.tmp_apex_env`
- Path (UNC): `\\mac\Home\Desktop\Development\Sentinel\.tmp_apex_env`
- Python venv structure: `Scripts\python`, `Lib\site-packages`
- Installed deps (verified):
  - `playwright==1.58.0`
  - Playwright browsers present under:
    - `C:\Users\jamiefeeny\AppData\Local\ms-playwright\chromium-1208`
    - `C:\Users\jamiefeeny\AppData\Local\ms-playwright\chromium_headless_shell-1208`
    - `C:\Users\jamiefeeny\AppData\Local\ms-playwright\ffmpeg-1011`
    - `C:\Users\jamiefeeny\AppData\Local\ms-playwright\winldd-1007`

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
- When unsure whether local environment has dependencies (FastAPI, Playwright, etc.), tests may skip locally. Prefer verifying on the droplet when needed.
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

Goal: deploy code without accidentally deleting server files.

1) **Commit** anything you intend to ship, then build an archive from git (preferred):
   - `git archive` only includes **committed** blobs for the ref you pass (usually `HEAD`). **Uncommitted working-tree changes are not in the zip**—a deploy built before commit will look successful but will still run the previous revision on the server.
   - Before archiving, run `git status` (clean or intentional commits only), then record what you are shipping, e.g. `git rev-parse HEAD` (full hash) or `git rev-parse --short HEAD` for runbooks / chat.
   - Example: `git archive --format=zip -o sentinel_patch.zip HEAD src`
2) Copy the archive to the droplet:
   - Example: `scp sentinel_patch.zip sentinelServer:/tmp/sentinel_patch.zip`
3) Extract on the droplet (overwrite required):
   - Do not rely on extraction behavior that might skip existing files.
   - Required: force-write archive contents into `/opt/sentinel/app` (overwrite existing files).
   - If using Python extraction, use a script that explicitly writes each file with `wb` mode.
4) Restart the app:
   - `sudo systemctl restart sentinel`
5) Validate:
   - Wait ~3-5 seconds after restart (service warm-up window).
   - `curl http://127.0.0.1/health`
   - `sudo journalctl -u sentinel -n 50 --no-pager`

### Mandatory deployment sequence (no parallelization)

Run these steps strictly one at a time:
1. Commit (if needed) so `HEAD` matches what you intend to deploy, then build archive.
2. Copy archive.
3. Extract with overwrite.
4. Verify deployed file content/hash on server.
5. Restart service.
6. Health check.
7. Route-level verification for the user-visible path.

Do not run copy/extract/restart in parallel under any circumstances.

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
- **SQL migrations under `src/sentinel/server/persistence/migrations/`:** `apply_migrations` splits each file on every `;` (semicolon). Do **not** put a semicolon inside a line—even inside a `--` SQL comment—or a fragment can be executed as its own statement and Postgres will error (example failure: `syntax error at or near "historical"` when a comment contained `...result; historical...`).

### Optional: `verify_deploy_hash.py` (pre-restart hash match)

Repo root: `verify_deploy_hash.py` — compares SHA-256 of a member inside `/tmp/sentinel_patch.zip` on the droplet to the deployed file under `/opt/sentinel/app/...`. Intended to be **copied to the server** (or `scp` to `/tmp/`) and run with `python3` **on the droplet** after extract and **before** `systemctl restart` (mandatory sequence: verify, then restart). Defaults match the standard paths; run with `--help` for overrides.

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
   - **Commit before `git archive`:** the archive is built from **git objects only** (the `HEAD` commit). Neither staged nor unstaged working-tree edits are included until you `git commit`. Record what shipped: `git rev-parse HEAD`.
   - Prefer **`git add` with paths you intend to ship** (e.g. specific packages under `src/sentinel/`), not blind `git add src`, so editable-install metadata such as `src/sentinel.egg-info/` is never committed (see Known gotchas).
   - `git commit -m "Describe change"`
   - Build archive: `git archive --format=zip -o sentinel_patch.zip HEAD src`
   - Copy: `scp sentinel_patch.zip sentinelServer:/tmp/sentinel_patch.zip`
   - Extract: `sudo python3 -m zipfile -e /tmp/sentinel_patch.zip /opt/sentinel/app`
   - Restart: `sudo systemctl restart sentinel`
   - Validate: `curl http://127.0.0.1/health`

## Post-test cleanup workflow (required)

Goal: do not leave disposable test/deploy artifacts behind after local runs.

Run this cleanup step after test or perf runs:

1) Remove known disposable temp run folders:
   - `Remove-Item -Recurse -Force .tmp_perf_*`
   - `Remove-Item -Recurse -Force .tmp_run_*`

2) Remove disposable deployment/test zip artifacts from repo root:
   - `Remove-Item -Force deploy_*.zip`
   - `Remove-Item -Force sentinel_patch.zip`

3) Keep persistent tooling env:
   - Do not delete `.tmp_apex_env` (shared Playwright/runtime environment).

4) Verify workspace is clean of disposable artifacts:
   - `git status --short`
   - `Get-ChildItem -Force -Name .tmp_*`
   - `Get-ChildItem -Force -Name *.zip`

Operator rule:
- If a disposable artifact appears repeatedly from a command, either run cleanup immediately after that command or add the command to a wrapper that runs cleanup in a `finally` step.
