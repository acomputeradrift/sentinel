# Continuity

Start file for **local** and **cloud/Grokbot** agents. Project briefing only: what Sentinel is, how to continue, where docs live, live ops facts. **Not a todo list.** Work items go in `docs/todos/YYYY-MM-DD.md` (date = file creation). Do not append a diary. Never write secrets or keys here.

Cloud/Grokbot agents read **this file**, not `bootstrap.md`. Open `bootstrap.md` only for the long architecture brief.

---

## What Sentinel is

Commissioning + technician field-testing for RTI projects. Ingest `.apex` → extract contract JSON → generate static technician HTML → append-only PASS/FAIL per `targetKey` → commissioning console. Technicians have no login; they use an opaque `techToken` in the URL.

**Mission:** structured, testable, efficient RTI commissioning. Not a live RTI control system, project editor, or visual-polish product.

**Shipped shape:** Python package `sentinel` under `src/sentinel/`. Single-droplet MVP: nginx → Uvicorn → FastAPI. API v1 is additive-only.

---

## How to continue development

1. `AGENTS.md` / `agents.md` — approval scope, blast radius, test-first, agent runs tests.
2. One logical change per cycle, then wait for Jamie (`one-change-wait-results`).
3. `unittest` only (never pytest). After `src/` or `dev_tests/` edits: `python devtools/run_regression_with_venv.py`. UI: Playwright under `dev_tests/ui/`. Jamie does not run tests.
4. Venv must be `.tmp_apex_env` (gitignored). This Mac: already present. Cloud/Grokbot: run `python devtools/bootstrap_tmp_apex_env.py` once, then the same runner.
5. Start in code: `src/sentinel/server/app/main.py` → router (`commissioning.py` or `testing.py`) → `repositories.py` / `queries.py` → `pipeline.py` if upload/regenerate → `render_core.py` / `extractor_core.py` only if output shape changes.
6. Do not mix `.apex`-derived data with Sentinel UI config in one shape. Silent partial failure is forbidden. `targetKey` stability is sacred. Regenerate must not erase DB test history.
7. Before deploy: Intent Check Gate in `AGENTS.md` must be Pass. Then follow **Deploy** — do not invent a path.

---

## Where to look

| Need | Read |
|---|---|
| Process / approval / test-first / deploy-when-Jamie-says-deploy | `AGENTS.md` / `agents.md` |
| Mission, scope, invariants | `docs/directives/mission.md`, `scope.md`, `invariants.md` |
| Architecture (product + device testing + live-update) | `docs/directives/architecture_overview.md`, `docs/architecture/` |
| Official deploy + local/droplet workflow | `docs/directives/dev_environment_and_workflow.md` |
| Deploy “Jamie said deploy” | `.cursor/rules/deploy-commit-scope.mdc` |
| Testing philosophy | `docs/directives/testing_strategy.md` |
| API / data / WS contracts | `docs/api_contract_v1.md`, `docs/data_contracts.md`, `docs/contracts/ws_events.md` |
| Extract/UI schema | `src/sentinel/contracts/apex_project_structure_v4.json`, `app_ui_structure.json` |
| Security / runbook | `docs/directives/commissioning_security_model.md`, `runbook.md` |
| Dated work lists (not this file) | `docs/todos/` |
| Long brief / file map (optional) | `bootstrap.md`, `codebase_map.md` |

---

## Architecture (enough to navigate)

- **Flow:** `.apex` upload → `pipeline.regenerate_project` → extract + generate subprocesses → atomic promote into `generated/{projectId}/` → DB + WS. Technician: `GET /testing/{techToken}` serves generated HTML; mutations via `/api/v1/testing/{techToken}/…`.
- Extract/generate are subprocesses (`SENTINEL_PROGRESS` on stdout). Persistence: no `DATABASE_URL` → `InMemoryRepository`; else Postgres + migrations. Events: in-process `ProjectEventBroker`. SSE `/events` is **410** — use WS.
- Technician UI is static generated HTML (`render_core.py`), not a SPA. Authoritative targets: `*_project_data.json` + DB. Test history is append-only. Single process, single droplet.

| Area | Role |
|---|---|
| `src/sentinel/server/` | FastAPI, API, persistence, pipeline |
| `src/sentinel/extraction/` | `.apex` → `*_project_data.json` |
| `src/sentinel/generation/` | JSON → HTML (`render_core.py` is large/fragile) |
| `src/sentinel/contracts/` | Schema + UI rules |
| `src/sentinel/ui/commissioning/` | Operator console |
| `dev_tests/regression/` · `dev_tests/ui/` | unittest · Playwright |
| `devtools/` · `migrations/` | Venv/runner · forward-only SQL |

**Misleading names:** `server/api/events.py` is empty/reserved. “generation” = HTML (`generation/`) vs DB `generation_runs`. Two `002_*.sql` files — lexical full-filename sort.

---

## Deploy

**Source of truth:** `docs/directives/dev_environment_and_workflow.md`. Commit + push, then on the droplet `git fetch` + `reset --hard origin/<branch>` in `/opt/sentinel/app`, prove `HEAD` and a marker, restart `sentinel.service`. Keep `uploads/`. Do not use `git archive` / `scp` / `deployment/deploy_from_head.ps1` unless Jamie asks.

Cloud/Grokbot VMs cannot see Jamie’s Mac `~/.ssh`. Local Mac agents can `ssh sentinelServer`.

---

## Now

- **Updated:** 2026-09-06
- **Branch:** `main`
- **Repo HEAD:** `3f6e1eb` (Mac = GitHub `main`)
- **Droplet HEAD:** `3f6e1eb` at `/opt/sentinel/app` — service restarted, `/health` ok
- **Live DB:** wiped empty 2026-09-06. `uploads/` empty. `generated/` only `.staging`.
- **Live:** `http://24.199.106.213/commissioning/` · `http://24.199.106.213/management/` · health `http://24.199.106.213/health`
- **Work list:** `docs/todos/2026-09-06.md` (morning list done; not this file)

---

## Facts (ops)

- Two droplets, two keys. **Not** interchangeable.
  - Landing: Host `my-do-server` → `161.35.236.81` as `root`, key `~/.ssh/id_ed25519`
  - Sentinel: Host `sentinelServer` → `24.199.106.213` as `root`, key `~/.ssh/id_ed25519_sentinel`
- Droplet: app `/opt/sentinel/app`, venv `/opt/sentinel/venv`, `sentinel.service` (Uvicorn `127.0.0.1:8000`), nginx → that port. Running code is `src/`. Keep `uploads/`. Tree may look dirty (old extract leftovers).
- Do not commit `.tmp_apex_env/`, `generated/`, `uploads/`. Mac `.tmp_apex_env` only. Python ≥3.11; CI uses 3.12.

---

## Do not

- Treat `161.35.236.81` / `my-do-server` as Sentinel, or reuse one SSH key for both droplets.
- Ask Jamie to run tests. Commit venv/`generated/`/`uploads/`. Use `git archive` / `scp` / `deploy_from_head.ps1` unless Jamie asks.
- Assume pytest, in-process extract, or that `events.py` works. Assume `create_app()` always hits Postgres (InMemory if no `DATABASE_URL`).
- Put secrets, keys, or todos in this file.
