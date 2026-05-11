# Project Identity

- **Name:** `sentinel` (Python package under `src/sentinel/`, pyproject `0.1.0`).
- **Purpose:** Commissioning + technician field-testing server: ingest RTI `.apex` projects, extract contract-shaped JSON, generate static technician HTML, persist append-only test history, expose commissioning console + token-scoped technician APIs.
- **Domain problem:** Operationalize RTI project commissioning—upload → validate/extract → render test surfaces → record PASS/FAIL per deterministic `targetKey` → aggregate progress/diagnostics—without technician logins (opaque `techToken` in URL path).
- **Maturity:** MVP / production-shaped single-droplet deployment (nginx → Uvicorn → FastAPI); contracts versioned (`docs/api_contract_v1.md`, additive-only v1 rule). **Confidence:** high for shipped shape; product maturity inferred from docs.
- **Constraints:** `DATABASE_URL` absent ⇒ `InMemoryRepository` (tests/local); present ⇒ Postgres + migrations on `PostgresRepository` init. Deploy ships **`git archive HEAD src` only**—repo must still commit full change set per workspace policy. Migrations: **no dollar-quoted SQL** in `migrations/*.sql` unless splitter extended (`docs/directives/dev_environment_and_workflow.md`). Python **≥3.11** declared; CI uses **3.12**. UNC/SMB workspace: agent shells may need `SENTINEL_REPO_ROOT` / `SENTINEL_VENV_PYTHON` (`repo_paths.py`).

# System Architecture

- **Style:** Monolithic FastAPI app + **subprocess pipeline** for extract/generate (not in-process libraries for those phases). Dual persistence backends behind `Repository` protocol.
- **Runtime boundaries:** Browser ↔ nginx ↔ Uvicorn ↔ FastAPI routers; FastAPI ↔ `Repository` (Postgres **or** memory); FastAPI ↔ disk (`SENTINEL_UPLOAD_ROOT`, `SENTINEL_GENERATED_ROOT`); pipeline ↔ `python …/extract_project_data.py` / `generate_html.py` with `PYTHONPATH=src`.
- **Flow:** `.apex` upload → staged file → `pipeline.regenerate_project` → staged `*_project_data.json` + generated HTML → atomic promote into `generated/{projectId}/` → DB records uploads/active upload/project status → WS publishes `generation_phase` / rollups. Technician: `GET /testing/{techToken}` serves **generated** HTML; mutations via `/api/v1/testing/{techToken}/…` (results, layer locks, ready baseline, etc.).
- **IPC/events:** In-process `ProjectEventBroker` (threading + `queue.Queue`): seq’d events + replay buffer; commissioning project WS + technician WS consume same broker pattern (replay on gap). HTTP responses for snapshots; JSON text over WebSocket. **No separate message bus.**
- **State:** Authoritative: Postgres (or in-memory dicts mirroring same rules). Ephemeral: broker history (capped replay), `_RESOLVED_TARGETS_CACHE` in `progress.py` (module-level, **mtime-based** invalidation—stale risk if file touched oddly). UI state: browser-side commissioning JS + generated page scripts.
- **Persistence:** Relational schema (`001`…`006` + two `002_*.sql` files—lexical sort order matters); JSON files on disk for extracted project + rendered artifacts; `test_results` append-only; idempotency key table for safe retries.
- **Sync:** Commissioning WS: initial `commissioning_snapshot`, then `sync.request` / `replay.batch` / full snapshot if gap too large. Technician side: analogous replay pattern in `testing.py`. Debounced `commissioning_rollups` refresh (100ms timer per project) after rapid posts to coalesce DB+rollup work.
- **Rendering:** Offline HTML generation in `render_core.py` (large string-builder); technician UI is **static output**, not a SPA framework.
- **Modularity:** `Repository` swappable; `server/api/events.py` is an **empty router** (reserved prefix). Deprecated SSE is explicitly rejected on **`GET /api/v1/commissioning/projects/{projectId}/events`** (`410 SSE_REMOVED`—use WS). Rollup logic intentionally shared: `commissioning_rollups.py` vs `progress.py` vs `commissioning_snapshots.py`—overlap is **intentional dedup** (see `AGENTS.md` / service comments).
- **Multi-user:** Technicians: many `tech_link` rows / concurrent tokens per project. Commissioning console: **`COMMISSIONING_STUB_USER_ID`** until real auth; Postgres clients scoped per `user_id` (`006_users_scoped_clients.sql`).

**Coupled:** Routers ↔ `Repository` + broker + `pipeline` paths hardcoded to repo `src/sentinel/...` scripts and contracts. **Decoupled:** Extract/generate as subprocesses (crash isolation, progress via stdout regex `SENTINEL_PROGRESS …`). **Complexity concentrates:** `render_core.py` (generation + layout), `extractor_core.py`, WS replay + snapshot assembly, `PostgresRepository`/`queries.py` surface area.

# Tech Stack

| Piece | Role | Core? |
|--------|------|--------|
| **FastAPI + Starlette** | HTTP/WS, static mount `/commissioning`, exception JSON envelope | Core |
| **Uvicorn** | ASGI server (prod: systemd on droplet) | Core |
| **Pydantic v2** | Request bodies (`schemas.py`), validation | Core |
| **pg8000** | Postgres driver; sync DB access from async routes | Core for persisted deploy |
| **setuptools** | Packaging; `package-data` includes `ui/**/*.js|css|html` | Core build |
| **unittest** | All automated tests (**no pytest** in policy) | Core |
| **Playwright** (optional `[dev]`) | Runtime UI tests under `dev_tests/ui/` | Core for UI changes |
| **nginx** | TLS/edge, WS upgrade proxy | Deploy env |
| **PostgreSQL** | Primary store when `DATABASE_URL` set | Core in production |

Replaceable: driver (pg8000 → psycopg could work with query rewrite); in-memory backend for tests only.

# Repository Structure

| Area | Purpose | Importance | Role | Risk / notes |
|------|-----------|------------|------|----------------|
| `src/sentinel/server/` | FastAPI app, middleware, API, persistence, services | **Critical** | Request handling, orchestration | WS timeouts, auth middleware order |
| `src/sentinel/extraction/` | `.apex` → `*_project_data.json` | **Critical** | Trust boundary for external input | Contract drift |
| `src/sentinel/generation/` | JSON → HTML + manifests | **Critical** | Technician-visible output | `render_core.py` size/fragility |
| `src/sentinel/contracts/` | `apex_project_structure_v4.json`, `app_ui_structure.json` | **Critical** | Schema + UI rules source of truth | Must stay aligned with extractors/renderers |
| `src/sentinel/ui/commissioning/` | Static commissioning console | High | Operator UX | JS + WS client assumptions |
| `src/sentinel/logging/` | CLI `EventLogger` for scripts | Medium | Trace extract/generate | Not unified with uvicorn logging |
| `dev_tests/regression/` | unittest discovery (`test_*.py`) | **Critical** | CI + regression guard | Many tests skip without `DATABASE_URL` |
| `dev_tests/ui/` | Playwright | High | End-user flows | Slower; needs venv + browser |
| `devtools/` | venv bootstrap, regression runner, diagram PDF render | Medium | Agent/dev ergonomics | `last_regression_run.txt` gitignored |
| `docs/directives/` | Normative workflow + architecture | **Critical** | Human+agent policy | Overrides casual assumptions |
| `docs/diagrams/*.mmd` | System/in-process diagrams | Medium | Mental model | PDFs optional |
| `deployment/` | Scripts, verify hash, cleanup | Medium | Droplet ops | Path/host specific |
| `docs/api_contract_v1.md`, `docs/data_contracts.md` | External contract docs | High | API stability | Additive-only v1 |

**Generated / gitignored:** `.tmp_apex_env/`, `uploads/`, `generated/`, egg-info, deploy zips, `devtools/last_regression_run.txt`. **Legacy / stub:** `server/api/events.py` (empty router); commissioning user stub. **High churn:** `render_core.py`, `extractor_core.py`, `commissioning.py` / `testing.py`, migrations when schema changes.

# Critical Execution Flows

1. **App startup:** `main.create_app()` → middleware (`TraceId`, `CommissioningAuth` for `/api/v1/commissioning` if env key set) → `app.state.repo` = `PostgresRepository` (**runs `apply_migrations`**) or `InMemoryRepository` → lazy `app.state.project_event_broker` → routers + optional `/commissioning` static. **Mutation:** none beyond migrations on first Postgres connect per process.

2. **Upload → ready pipeline:** Commissioning route saves bytes (`pipeline.save_upload`), DB `record_upload` / `set_project_active_upload`, background/async work calls `regenerate_project` (per `commissioning.py` patterns—**read call sites** for thread vs async). Subprocess extract → subprocess generate → promote files → `prune_project_upload_dir_to_single_file` → project status updates + broker `generation_phase` events. **Hidden dep:** `_repo_root()` assumes file layout `src/sentinel/server/services/pipeline.py` → parents[4] = repo root. **Single-flight:** `_ACTIVE_REGENERATE_PROJECT_IDS` per `projectId`.

3. **Technician test result POST:** `testing.py` validates body → `repo.append_test_result` → idempotency keys (scope/key) → `broker.publish` `test_result` → `_schedule_commissioning_rollups_refresh` (debounced thread timer) → `broker.publish` `commissioning_rollups`. **Order:** DB before optimistic WS; rollups eventual.

4. **Commissioning WS:** Accept → `broker.subscribe` (last event replayed) → send `commissioning_snapshot` → loop: queue wait / keepalive → client `sync.request` with `lastAppliedSeq` → replay batch or full snapshot if `replayableFromSeq > lastApplied+1` (gap policy). **Mutation:** none in broker from client messages except read replay.

5. **Progress / diagnostics reads:** `progress.py` reads latest `*_project_data.json` from `generated/{projectId}/` (mtime-sorted glob), optional resolved targets file, merges `get_latest_results_for_project` from repo. **Cache:** `_RESOLVED_TARGETS_CACHE` keyed by project + path mtime.

6. **Health / deploy verify:** `/health` JSON; deploy script greps known markers on remote tree before `systemctl restart sentinel`.

# Data Model

- **Core entities:** `User` (stub seed), `Client` (per `userId`), `Project`, `TechLink` + hashed `tech_link_tokens`, `UploadRecord`, `GenerationRun` (nullable link from results), `TestResult` (target snapshot + outcome + fail_note), fail tags, layer lock rows, target first-test outcomes, idempotency store.
- **Ownership:** Project → client → user; results → project + tech link; uploads → project. **Technician token** resolves to `projectId` for all testing routes.
- **Lifecycle:** Test history **append-only** (clearing is explicit `clear_project_testing_data` for reset flows). Regenerate **must not** erase DB history (architecture directive); replaces disk artifacts under `generated/{projectId}/`.
- **Persistence boundaries:** Durable: Postgres tables + JSON on disk. **Authoritative for targets/progress baseline:** generated `*_project_data.json` + DB results. **Derived:** commissioning snapshots, rollups, resolved targets JSON, pie aggregates in UI payloads.
- **Intentional duplication:** Target metadata copied into each `test_results` row (denormalized for history). Replay buffers duplicate recent events in broker memory.
- **Serialization:** JSON REST/WS; `refs` jsonb in Postgres; ISO-ish UTC strings in API (contract specifies `Z` suffix norm).
- **Schema evolution:** Only forward SQL migrations; two files share `002_` prefix—**rely on full filename sort**, not only numeric prefix. **Concern:** dollar-quoted literals unsupported in splitter.

# State Management

- **Lives:** DB (sessions per connection in pg8000), `InMemoryRepository` dicts + lock, `app.state` (repo, broker, debounce timers), broker seq/history, module cache in `progress.py`, client-side commissioning store (`commission_tab.js` patterns).
- **Owners:** `Repository` implementations own transactional rules; routers own HTTP/WS orchestration; broker owns fan-out + ordering.
- **Mutators:** Routers + services (`pipeline`, `commissioning_rollups`); subprocesses write only to staging then atomic promote.
- **Sync rules:** WS seq monotonic per project; client tracks `lastAppliedSeq`. Debounced rollups **may lag** test_result events briefly.
- **Risks:** **Race:** concurrent regenerate for same `projectId` blocked; concurrent uploads—check commissioning handlers. **Stale:** `_RESOLVED_TARGETS_CACHE` if filesystem clock skew or direct file edit without mtime change. **Expensive:** `compute_progress_and_testing_rollups` on every debounced fire after bursts; full snapshot on large replay gap.

# Integration Surface

| Surface | Stability | Contract | Failure risk |
|---------|-----------|----------|--------------|
| `/api/v1/commissioning/*` | v1 additive | `docs/api_contract_v1.md` | 401 if `SENTINEL_COMMISSIONING_API_KEY` mismatch; `GET …/projects/{id}/events` always **410** (historical SSE path) |
| `/api/v1/testing/{techToken}/*` | v1 additive | same + generated HTML coupling | 410 revoked token; path token leaks if logged |
| WebSocket commissioning + testing | evolving but tested | JSON message `type` discriminated | send timeout closes socket (code 1011) |
| Static `/commissioning/*` | medium | packaged relative to package `__file__` | wrong cwd if not installed as package |
| `.apex` input | external | `apex_project_structure_v4.json` validation | malformed XML / contract violations |
| Disk `uploads/`, `generated/` | env-configurable | sentinel-defined layout | disk full, permissions, SMB latency |
| Postgres | stable once migrated | SQL in `queries.py` | connection timeout 5s; migration failure blocks boot |

**No third-party SaaS integrations** identified in core path (**confidence:** high from dependency list + code skim).

# Performance Characteristics

- **Bottlenecks:** Full extract+generate subprocess pair per regeneration; large `render_core` string assembly; WS broadcast O(subscribers); rollup DB reads after bursts (mitigated: debounce).
- **Scaling:** Single-process broker + in-memory replay—**not horizontally safe** without sticky sessions + shared broker (not implemented). **Assumption:** single droplet MVP.
- **Memory:** Broker history capped (`replay_capacity` default 500); `render_core` holds large HTML strings per device.
- **Lazy loading:** UI loads JSON snapshots / incremental replay; generated technician pages load assets per project layout (**confidence:** medium—pattern from static HTML).
- **Concurrency:** Threading.Timer for debounce; broker `queue.Full` drops oldest then retries—**possible event loss under overload** for slow consumers.

# Testing Strategy

- **Philosophy:** Contract-first, deterministic output; tests fail on coordinate/layout drift vs extracted data (`docs/directives/testing_strategy.md`). Test-first required by workspace `AGENTS.md`.
- **Unit:** Extraction, generation, persistence, rollups, idempotency, auth middleware, WS behaviors—`dev_tests/regression/`.
- **Integration:** FastAPI `TestClient` / async tests mixed; Postgres paths gated on `DATABASE_URL` (**skip**, not fail, when unset).
- **UI:** Playwright in `dev_tests/ui/`; requires `[dev]` install + `playwright install chromium`.
- **Regression:** Broad unittest discovery matches CI (`ci.yml`).
- **Fragile:** Ordering/timestamp-sensitive tests; WS timing; anything depending on real filesystem layout under UNC.
- **Gaps (inferred):** Full multi-browser matrix absent; some Postgres branches only run with URL—**agents should run with `DATABASE_URL` when touching `queries.py` or migrations**.

# Development Workflow

- **Setup:** `python devtools/bootstrap_tmp_apex_env.py` → editable install + Playwright browser. Use `devtools/run_regression_with_venv.py` (sets `PYTHONPATH`, handles UNC cwd).
- **Build:** `pip install -e ".[dev]"`; no compiled assets pipeline.
- **Codegen:** None for app runtime; optional `devtools/render_*_pdf.py` for diagrams.
- **Migrations:** Add `NNN_description.sql`; run against dev DB; PostgresRepository applies on startup.
- **Debug:** `uvicorn.error` logger heavily used; trace id in `request_context` + error JSON. **Intent Check Gate** before deploy (human policy in `AGENTS.md`).
- **Logging:** Structured ad hoc strings to uvicorn logger; CLI scripts use `EventLogger`.
- **Feature flags:** **None found** (**confidence:** medium—no central flag module grep’d).
- **Envs:** `DATABASE_URL`, `SENTINEL_COMMISSIONING_API_KEY`, `SENTINEL_UPLOAD_ROOT`, `SENTINEL_GENERATED_ROOT`, `PYTHON`, `SENTINEL_REPO_ROOT`, `SENTINEL_VENV_PYTHON`, optional `SENTINEL_DEPLOY_TIP`.

# Known Architectural Debt

- **Stub commissioning user** hardcoded UUID—must match migration seed.
- **Empty `events.py` router** still mounted—confusing next to commissioning routes; real “events” traffic is **WS**, not that module.
- **`render_core.py` / `extractor_core.py` monoliths**—high edit blast radius.
- **Subprocess coupling** to script paths + `PYTHONPATH`—brittle if package layout changes.
- **SQL migration splitter** cannot handle dollar-quoted strings—limits Postgres features.
- **Two `002_*.sql`**—lexical ordering works but surprises humans/tools expecting strict numeric sequence.
- **Module-level progress cache**—easy to miss on changes to resolution rules.
- **Broker queue drop** under backpressure—transient loss possible.

# AI Agent Guidance

- **Start:** `src/sentinel/server/app/main.py` (wiring) → affected router (`commissioning.py` or `testing.py`) → `server/services/repositories.py` + `persistence/queries.py` for data changes → `pipeline.py` if upload/regenerate → `render_core.py` / `extractor_core.py` only if output shape changes.
- **High leverage:** `contracts/*.json`, `repositories.py` / `queries.py`, `commissioning_snapshots.py`, `commissioning_rollups.py`, `pipeline.py`, `testing.py` (WS + POST paths).
- **Misleading:** `server/api/events.py` (no routes) vs `commissioning.py` `…/events` **410 route**; filename “events” vs project JSON `events` subtree; duplicate `002_` migrations; **“generation”** meaning RTI generation vs Sentinel HTML generation—disambiguate by path (`generation/` vs DB `generation_runs`).
- **Safe-ish to modify:** New commissioning endpoints following existing `http_error` patterns; additive Pydantic fields if contract allows; new regression tests.
- **Fragile:** WS replay gap logic (`commissioning_project_ws.py`, `testing.py` mirrors); idempotency semantics; **anything touching `targetKey` stability**; SQL migrations + splitter; `COMMISSIONING_STUB_USER_ID` sync with SQL seed; static file paths packaged via setuptools.
- **Hallucination traps:** Assuming pytest; assuming in-process extract (it is subprocess); assuming `events` router does work; assuming CI runs Postgres tests; assuming `create_app()` always hits DB (InMemory default without env).
- **Naming:** `projectId` camelCase in JSON/API vs `project_id` in SQL; `techToken` vs hashed DB column.
- **Implicit rules:** Additive-only `api_contract_v1`; never mix `.apex`-derived data with Sentinel UI config in one shape (`architecture_overview.md`); silent partial failure forbidden—prefer hard errors.
- **Before modifying `render_core.py`, understand:** `app_ui_structure.json`, `apex_project_structure_v4.json`, and existing regression HTML/layout tests.
- **Before modifying `extractor_core.py`, understand:** contract JSON and `extract_project_data.py` CLI expectations (`SENTINEL_PROGRESS` lines).
- **Do not refactor WS + snapshot + rollups separately without tracing:** end-to-end message order seen by `commission_tab.js` and technician HTML injected scripts (`render_core` WS client blocks).
- **This subsystem appears duplicated but is intentionally separate:** `commissioning_rollups` vs `progress.commissioning_progress` vs snapshot builders—consolidate only with full regression + UI proof.

**Workspace policy (not optional for humans):** `AGENTS.md` requires approval scope before edits, agent-run tests, deploy commit rules—**may conflict with autonomous agent defaults**; resolve by following user thread instructions.

**Supplementary index (optional second read):** `codebase_map.md`—file-level map; **omit** if task is localized.

# Glossary

- **`.apex`:** RTI project export ZIP/XML input; untrusted external file.
- **`targetKey`:** Deterministic stable key for a testable unit; ties DB results to extracted targets.
- **`techToken` / `techLink`:** Opaque URL token mapping to a project + technician link row; rotation revokes old hash.
- **`Repository`:** Persistence abstraction (`InMemoryRepository` vs `PostgresRepository`).
- **`ProjectEventBroker`:** In-proc pub/sub for WS clients with seq + bounded replay.
- **`regenerate_project`:** Subprocess-backed extract+generate+promote pipeline keyed by `projectId`.
- **`commissioning_snapshot`:** Server-built JSON state for commissioning UI (progress, uploads, failures, seq).
- **`resolved_targets`:** JSON sidecar from extraction pipeline consumed by progress/rollups.
- **`COMMISSIONING_STUB_USER_ID`:** Fixed UUID for sole commissioning console user until real auth.
- **`SENTINEL_PROGRESS`:** Stdout line protocol from subprocesses for phase % reporting.
