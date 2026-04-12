# Sentinel Development Environment (Local + Droplet)

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

1) **Commit** what you intend to ship, then build an archive from git (preferred):
   - `git archive … HEAD` packs **only the `HEAD` commit**; uncommitted edits are not in the zip. Run `git status`, commit, optionally note `git rev-parse HEAD`, then archive.
   - Example: `git archive --format=zip -o sentinel_patch.zip HEAD src`
2) Copy the archive to the droplet:
   - Example: `scp sentinel_patch.zip sentinelServer:/tmp/sentinel_patch.zip`
3) Extract on the droplet:
   - If `unzip` is not available, use Python:
     - `sudo python3 -m zipfile -e /tmp/sentinel_patch.zip /opt/sentinel/app`
4) Restart the app:
   - `sudo systemctl restart sentinel`
5) Validate:
   - `curl http://127.0.0.1/health`
   - `sudo journalctl -u sentinel -n 50 --no-pager`

Known gotchas:
- Avoid `rsync --delete` against `/opt/sentinel/app` (it can remove required modules and break imports).

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
