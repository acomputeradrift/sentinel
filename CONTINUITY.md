# Continuity

Single start file for **local agents** and **cloud/Grokbot agents**. Read this first. It is the project briefing, how to continue development, and where every other doc lives. Update **Now** in place when live state changes. Do not append a diary. Never write secrets, keys, passwords, or env values here.

Cloud/Grokbot agents read **this file**, not `bootstrap.md`. Open `bootstrap.md` only if you need the long architecture brief after this one.

---

## What Sentinel is

Commissioning + technician field-testing for RTI projects. Ingest an `.apex` file → extract contract-shaped JSON → generate static technician HTML → record append-only PASS/FAIL per deterministic `targetKey` → show progress on a commissioning console. Technicians have no login; they use an opaque `techToken` in the URL.

**Mission:** structured, testable, efficient RTI commissioning. Not a live RTI control system. Not an RTI project editor. Not visual polish over clarity.

**Shipped shape:** Python package `sentinel` under `src/sentinel/`. Single-droplet MVP: nginx → Uvicorn → FastAPI. API v1 is additive-only.

---

## How to continue development

1. Follow `AGENTS.md` / `agents.md` — approval scope before edits, blast-radius classification, test-first, agent runs tests.
2. One logical change per cycle, then wait for Jamie (`one-change-wait-results`).
3. Tests: `unittest` only (never pytest). After `src/` or `dev_tests/` edits, run `python devtools/run_regression_with_venv.py`. UI changes: Playwright under `dev_tests/ui/`. Jamie does not run tests.
4. Tests need a venv named `.tmp_apex_env` (gitignored — never commit it).
   - **This Mac:** already present. Run `python devtools/run_regression_with_venv.py`.
   - **Cloud/Grokbot:** you cannot see this Mac’s venv. On the VM run `python devtools/bootstrap_tmp_apex_env.py` once, then the same runner. That script creates `.tmp_apex_env`, installs the package with `[dev]`, and installs Playwright Chromium.
5. Start in code: `src/sentinel/server/app/main.py` → router (`commissioning.py` or `testing.py`) → `repositories.py` / `queries.py` → `pipeline.py` if upload/regenerate → `render_core.py` / `extractor_core.py` only if output shape changes.
6. Do not mix `.apex`-derived data with Sentinel UI config in one shape. Silent partial failure is forbidden. `targetKey` stability is sacred. Regenerate must not erase DB test history.
7. Before deploy: Intent Check Gate in `AGENTS.md` must be Pass. Then follow **Deploy** below — do not invent a path.

---

## Where to look

| Need | Read |
|---|---|
| Standing process / approval / test-first / deploy-when-Jamie-says-deploy | `AGENTS.md` / `agents.md` |
| Mission, non-goals | `docs/directives/mission.md` |
| In / out of scope | `docs/directives/scope.md` |
| Invariants | `docs/directives/invariants.md` |
| Architecture (product rules) | `docs/directives/architecture_overview.md` |
| Device testing architecture | `docs/architecture/device_testing_architecture.md` |
| Live-update / no-strand (not a deploy script) | `docs/architecture/live_update_no_strand_strategy.md` |
| Official deploy + local/droplet workflow | `docs/directives/dev_environment_and_workflow.md` |
| Deploy “Jamie said deploy” | `.cursor/rules/deploy-commit-scope.mdc` |
| Testing philosophy + local execution | `docs/directives/testing_strategy.md` |
| API v1 contract (additive) | `docs/api_contract_v1.md` |
| Data contracts | `docs/data_contracts.md` |
| WS event types | `docs/contracts/ws_events.md` |
| Extract/UI schema source of truth | `src/sentinel/contracts/apex_project_structure_v4.json`, `src/sentinel/contracts/app_ui_structure.json` |
| Long architecture brief (optional; not the start file) | `bootstrap.md` |
| File-level map (optional, not required at start) | `codebase_map.md` |
| Security model | `docs/directives/commissioning_security_model.md` |
| Runbook | `docs/directives/runbook.md` |

---

## Architecture (enough to navigate)

- **Flow:** `.apex` upload → staged file → `pipeline.regenerate_project` → extract subprocess + generate subprocess → atomic promote into `generated/{projectId}/` → DB records + WS `generation_phase` / rollups. Technician: `GET /testing/{techToken}` serves **generated** HTML; mutations via `/api/v1/testing/{techToken}/…`.
- **Extract/generate are subprocesses**, not in-process libraries. Progress via stdout `SENTINEL_PROGRESS` lines.
- **Persistence:** `DATABASE_URL` absent → `InMemoryRepository` (tests/local). Present → Postgres + migrations on `PostgresRepository` init. Dual backends behind `Repository`.
- **Events:** in-process `ProjectEventBroker` (seq + replay). No separate message bus. SSE on `GET /api/v1/commissioning/projects/{id}/events` is **410** — use WS.
- **Technician UI** is static generated HTML (`render_core.py`), not a SPA.
- **Authoritative targets:** generated `*_project_data.json` + DB results. Test history is append-only.
- **Not horizontally scaled.** Single process, single droplet.

| Area | Role |
|---|---|
| `src/sentinel/server/` | FastAPI, API, persistence, pipeline orchestration |
| `src/sentinel/extraction/` | `.apex` → `*_project_data.json` |
| `src/sentinel/generation/` | JSON → HTML + manifests (`render_core.py` is large/fragile) |
| `src/sentinel/contracts/` | Schema + UI rules |
| `src/sentinel/ui/commissioning/` | Operator console (static JS/CSS/HTML) |
| `dev_tests/regression/` | unittest discovery |
| `dev_tests/ui/` | Playwright |
| `devtools/` | venv + regression runner |
| `docs/directives/` | Normative workflow + architecture |
| `deployment/` | Deploy scripts (use the documented one only) |
| `migrations/` | Forward-only SQL; no dollar-quoted SQL unless splitter extended |

**Misleading names:** `server/api/events.py` is an empty reserved router. “generation” = Sentinel HTML (`generation/`) vs DB `generation_runs`. Two `002_*.sql` files — lexical full-filename sort, not numeric prefix only.

---

## Deploy

**Source of truth:** `docs/directives/dev_environment_and_workflow.md`. Official path: commit + push, then on the droplet `git fetch` + `reset --hard origin/<branch>` in `/opt/sentinel/app`, prove `HEAD` and a marker, restart `sentinel.service`. Keep `uploads/`. Do not use `git archive` / `scp` / `deployment/deploy_from_head.ps1` unless Jamie asks for that old path.

Cloud/Grokbot VMs cannot see Jamie’s Mac `~/.ssh`. Local Mac agents can `ssh sentinelServer`.

---

## Now

- **Updated:** 2026-09-01
- **Branch:** `cursor/select-group-chrome-ff08`
- **Repo HEAD:** `ddc9919` (Mac = GitHub; briefing commit may be one ahead)
- **Droplet HEAD:** `ddc9919` at `/opt/sentinel/app` — service `active`
- **Live:** `http://24.199.106.213/commissioning/` · health `http://24.199.106.213/health`
- **Open:** Device rows match event `#1e5f86`. Select Multiple on the base page no longer grabs viewport buttons; open viewport mode first, then select inside. Live. Existing technician pages need a regenerate.
- **Next:** continue from this file; do not rediscover SSH/droplets or the product.

---

## Facts (ops)

- Two droplets, two keys. **Not** interchangeable.
  - Landing: Host `my-do-server` → `161.35.236.81` as `root`, key `~/.ssh/id_ed25519`
  - Sentinel: Host `sentinelServer` → `24.199.106.213` as `root`, key `~/.ssh/id_ed25519_sentinel`
- Droplet: app `/opt/sentinel/app`, venv `/opt/sentinel/venv`, `sentinel.service` (Uvicorn `127.0.0.1:8000`), nginx → that port. Running code is `src/`. Keep `uploads/`. Working tree may look dirty (old extract leftovers).
- Do not commit `.tmp_apex_env/`, `generated/`, `uploads/`. Windows venv is gone; this machine uses the Mac `.tmp_apex_env` only.
- Python ≥3.11 declared; CI uses 3.12.

---

## Do not

- Treat `161.35.236.81` / `my-do-server` as Sentinel.
- Reuse one SSH key for both droplets.
- Ask Jamie to run tests to “verify.”
- Commit `.tmp_apex_env/`, `generated/`, or `uploads/`.
- Use `git archive` / `scp` / `deploy_from_head.ps1` unless Jamie explicitly asks for that old path.
- Assume pytest, in-process extract, or that `events.py` does work.
- Assume `create_app()` always hits Postgres (InMemory if no `DATABASE_URL`).
- Refactor WS + snapshot + rollups separately without tracing end-to-end message order.
- Put secrets or private keys in this file.
