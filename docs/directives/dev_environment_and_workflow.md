# Sentinel Development Environment and Workflow (Local + Droplet)

Purpose: describe **how we develop and deploy** (repo layout, local vs droplet, services, safe workflows). This is **not** an app description.

## Workspace + rules

- Local workspace root (Windows): `C:\Development\Sentinel`
- Shell: PowerShell
- Git branch prefix: `codex/`
- Primary process rules: `AGENTS.md`
  - Scope + approval required before edits.
  - Test-first methodology required for implementation.
  - Playwright required for runtime UI tests.
- Additional directive files live under `docs/` and are treated as equal to root directives.

## Temp test environment (`.tmp_apex_env`)

Purpose: single local venv for **Sentinel package deps, FastAPI stack, and Playwright** so regression and UI runtime tests do not depend on a random system Python.

- Path (venv, same machine): `C:\Development\Sentinel\.tmp_apex_env`
- Python venv structure: `Scripts\python`, `Lib\site-packages`
- **Create / refresh:** from repo root, run `python devtools/bootstrap_tmp_apex_env.py` (installs `pip install -e ".[dev]"` and `playwright install chromium`). Safe to re-run after `pyproject.toml` changes.
- **Regression tests:** `python devtools/run_regression_with_venv.py` (uses this venv and writes `devtools/last_regression_run.txt` if you need a log file).
- Details and optional `DATABASE_URL`: see `docs/directives/testing_strategy.md` → *Local execution*.
- Playwright browsers cache under the user profile, for example:
  - `C:\Users\<user>\AppData\Local\ms-playwright\chromium-*`
- **UNC / agent shells:** `cmd.exe` cannot keep a UNC path as the process current directory (`UNC paths are not supported`). `devtools/run_regression_with_venv.py` and `devtools/bootstrap_tmp_apex_env.py` run subprocess children with a local `cwd` (typically `%TEMP%`) when the repo lives on `\\server\...`, while passing **absolute** paths in argv. If automation cannot see your working tree, set **`SENTINEL_REPO_ROOT`** (folder that contains `pyproject.toml`) and/or **`SENTINEL_VENV_PYTHON`** (full path to `.tmp_apex_env\Scripts\python.exe`). See `devtools/repo_paths.py`.

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

Goal: deploy the **pushed GitHub commit** onto the droplet once, then restart. `/opt/sentinel/app` is a git checkout. Do **not** use `git archive` / `scp` / `deploy_from_head.ps1` unless Jamie explicitly asks for that old path.

### Why deploys fail

- **Pulling before push.** The droplet can only see commits that are on GitHub.
- **Skipping pre-restart checks.** If the on-disk `HEAD` is not the intended hash, do not restart.
- **502 immediately after restart** is normal for a few seconds. Retry health with `curl --max-time`.

### Preflight (local)

1. **Commit** the full release set (`src/`, `dev_tests/`, `pyproject.toml`, `docs/`, tracked `devtools/`, policy files). Do not commit `.tmp_apex_env/`, `generated/`, `uploads/`, or `*.egg-info/`.
2. `git status` — working tree clean.
3. `git rev-parse HEAD` — this is the hash you will deploy.
4. `git push` so `origin/<branch>` matches that hash.

### One-shot deploy (Mac local agent — `ssh sentinelServer`)

Cloud/Grokbot VMs cannot see Jamie’s Mac SSH keys. Local Mac agents can.

```
ssh -o BatchMode=yes sentinelServer 'sudo git -c safe.directory=/opt/sentinel/app -C /opt/sentinel/app fetch origin'
ssh -o BatchMode=yes sentinelServer 'sudo git -c safe.directory=/opt/sentinel/app -C /opt/sentinel/app reset --hard origin/<branch>'
ssh -o BatchMode=yes sentinelServer 'sudo git -c safe.directory=/opt/sentinel/app -C /opt/sentinel/app rev-parse HEAD'
```

Replace `<branch>` with the branch you just pushed. Confirm the printed hash equals local `HEAD`. Then prove a marker from this commit is on disk (example):

```
ssh -o BatchMode=yes sentinelServer 'grep -q retestReady /opt/sentinel/app/src/sentinel/server/api/testing.py && echo DEPLOY_OK'
```

If that fails, **do not restart**. Then:

```
ssh -o BatchMode=yes sentinelServer 'sudo -n systemctl restart sentinel'
sleep 6
ssh -o BatchMode=yes sentinelServer 'curl -sS --max-time 10 http://127.0.0.1/health'
ssh -o BatchMode=yes sentinelServer 'curl -sS --max-time 10 -I http://127.0.0.1/commissioning/ | head -n 5'
```

Keep `uploads/` on the droplet. Do not `git clean` it away.

### Mandatory deployment sequence (no parallelization)

1. Commit and push so GitHub `HEAD` matches intent.
2. `fetch` + `reset --hard` to `origin/<branch>` on `/opt/sentinel/app`.
3. Confirm remote `rev-parse HEAD` matches the hash you pushed.
4. **Verify on-disk content** (grep a marker from this commit) **before** `systemctl restart`.
5. Restart `sentinel.service`.
6. Health check after a short sleep; retry on 502.
7. Route-level check (`/commissioning/`).

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
- **`pip install -e .` / editable installs** can create `src/sentinel.egg-info/` (and similar). Do **not** commit them. They are listed in `.gitignore`.
- **SQL migrations:** `apply_migrations` runs each `*.sql` file using a **comment- and string-aware** splitter (skips `--` line comments, respects `'...'` literals including `''` escapes). Prefer keeping migrations simple; avoid PostgreSQL **dollar-quoted** bodies in migration files unless we extend the splitter.

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
     - `C:\Development\Sentinel\.tmp_apex_env\Scripts\python -m unittest discover -s dev_tests/regression -p "test_*.py"`
   - Do not run local tests with system/default `python`.
   - If a test skips for missing dependencies, re-run once with the temp env interpreter before reporting a skip.

2) UI runtime tests (Playwright)
   - Use the temp env:
     - `C:\Development\Sentinel\.tmp_apex_env\Scripts\python -m unittest dev_tests.ui.test_testing_result_posting`
     - `C:\Development\Sentinel\.tmp_apex_env\Scripts\python -m unittest dev_tests.ui.test_commissioning_console_runtime`

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
