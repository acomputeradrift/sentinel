# codebase_map.md

Supplement to `bootstrap.md`: file-level navigation and **what lives where**. Not part of the default “Read first” list—use when you need breadth across modules.

## Root / workspace

- `AGENTS.md` — Workspace operating rules (scope, workflow, testing expectations).
- `bootstrap.md` — Low-token brief: Mermaid diagrams, `docs/directives/dev_environment_and_workflow.md`, `AGENTS.md`, 8-bullet response contract, optional scope add-ons.
- `pyproject.toml` — Package metadata; runtime deps (FastAPI, Uvicorn, Pydantic, pg8000).
- `codebase_map.md` — This file (structural index).

## Docs and diagrams

- `docs/directives/` — **Primary** workflow + architecture directives (e.g. `dev_environment_and_workflow.md`, `commissioning_security_model.md`, `architecture_overview.md`).
- `docs/diagrams/` — System context and in-process architecture sources (`.mmd`); PDFs can be regenerated via `devtools/render_*.py`.
- `docs/api_contract_v1.md`, `docs/data_contracts.md` — API and data-shape reference as applicable.

## Tests and CI

- `dev_tests/regression/` — Server, persistence, extraction/generation, auth, idempotency, migrations, etc.
- `dev_tests/ui/` — Playwright/runtime UI tests.
- `dev_tests/fixtures/` — Shared fixture notes or data.
- `.github/workflows/ci.yml` — CI pipeline for the project.

## Deployment and devtools

- `deployment/verify_deploy_hash.py` — Verify deployed tree matches expected git revision (see workflow directive).
- `deployment/cleanup_post_run.ps1` — Post-run cleanup helper.
- `deployment/README.md` — Deploy-related notes if present.
- `devtools/render_sentinel_system_context_pdf.py`, `devtools/render_sentinel_inprocess_pdf.py` — Render diagram PDFs from `.mmd` sources.

---

## Source package `src/sentinel/`

- `__init__.py` — Package marker.

### Contracts

- `contracts/apex_project_structure_v4.json` — Extracted project-data shape (`source`, `events`, `devices`, …).
- `contracts/app_ui_structure.json` — UI structure contract for HTML generation.

### Extraction

- `extraction/extract_project_data.py` — CLI entry: parse args, run extraction, validate contract shape.
- `extraction/extractor_core.py` — Core extraction: `ExtractContext`, `extract_project_data`, validation, ElementTree/resolution helpers.

### Generation

- `generation/generate_html.py` — CLI entry for render pipeline.
- `generation/render_core.py` — HTML/payload rendering: project home, per-device pages, manifest/payload builders.

### Logging

- `logging/event_logger.py` — CLI-oriented `EventLogger` (info/warn/success/fail) for extraction/generation scripts.

### Server — FastAPI app

- `server/app/main.py` — `create_app`: `CommissioningAuthMiddleware`, `TraceIdMiddleware`, repo on `app.state`, HTTP exception handler (propagates `traceId` in JSON errors), `/health`, static mount `/commissioning`, routers for commissioning, events, testing.

### Server — request context and middleware

- `server/request_context.py` — `contextvars` for per-request trace id (`new_trace_id`, `current_trace_id`).
- `server/middleware/trace_middleware.py` — `TraceIdMiddleware`: sets trace id, `X-Request-Id` response header.
- `server/middleware/commissioning_auth_middleware.py` — When `SENTINEL_COMMISSIONING_API_KEY` is set, requires matching key for `/api/v1/commissioning` (HTTP + WebSocket upgrade).

### Server — API routers and helpers

- `server/api/__init__.py` — API subpackage marker.
- `server/api/commissioning.py` — Commissioning HTTP routes (prefix `/api/v1/commissioning`): uploads, tech links, clients/projects, regeneration, diagnostics; composes helpers; delegates project WebSocket to `commissioning_project_ws`, snapshots to `commissioning_snapshots`.
- `server/api/commissioning_snapshots.py` — Shared snapshot/rollup helpers for commissioning (e.g. safe progress computation, fail lists, payload shapes used by HTTP + WS).
- `server/api/commissioning_project_ws.py` — `run_commissioning_project_ws`: commissioning project WebSocket loop, broker integration, keepalive/timeouts.
- `server/api/testing.py` — Technician-facing routes and WebSockets: HTML/file serving, `post_result` with Pydantic bodies, ready-baseline, debounced commissioning rollups for WS events, target/status endpoints.
- `server/api/events.py` — Events router (lightweight declaration).
- `server/api/errors.py` — `http_error`: consistent JSON error envelope for HTTPException detail.
- `server/api/schemas.py` — Pydantic models for key POST bodies (e.g. `PostTestResultBody`, `PostReadyBaselineBody`, `TestResultTargetIn`).

### Server — services

The `server/services/` directory holds **modules** (e.g. `commissioning_rollups.py`, `pipeline.py`, `progress.py`, `repositories.py`, `ws_broker.py`); imports use `from sentinel.server.services import …` per package layout.

- `server/services/pipeline.py` — Upload staging, extract/generate subprocess orchestration, `regenerate_project`.
- `server/services/progress.py` — `commissioning_progress` and target/device rollups from latest results + project data.
- `server/services/commissioning_rollups.py` — Shared rollups/failure breakdown for commissioning HTTP snapshots and testing WS payloads (deduplicated logic vs. routers).
- `server/services/repositories.py` — `Repository` protocol, `InMemoryRepository`, `PostgresRepository`, domain records (clients, projects, results, idempotency, fail tags, etc.).
- `server/services/ws_broker.py` — `ProjectEventBroker`: pub/sub with replay buffer for project-scoped events.

### Server — persistence

- `server/persistence/db.py` — `DATABASE_URL` parsing, `connect`, `apply_migrations` (sorted `migrations/*.sql` with statement splitting), fetch helpers.
- `server/persistence/queries.py` — SQL functions used by `PostgresRepository` (clients/projects/uploads/tech links/test results/fail tags/idempotency/first-test outcomes, etc.).
- `server/persistence/migrations/*.sql` — Incremental schema. Filenames sort lexically (note **two** `002_*.sql`: fail tags and idempotency keys). Includes tables for layer lock state, active upload, target first-test outcomes, etc.

### UI (commissioning console)

- `ui/commissioning/index.html` — Shell: tabs (`manage`, `commission`, `diagnostics`) and panel hooks.
- `ui/commissioning/commissioning.js` — Manage flows, uploads, tech links, shared wiring to `/api/v1/commissioning/...`.
- `ui/commissioning/commission_tab.js` — Commission tab: store, WS manager, `runCommissionTab`, progress UI.
- `ui/commissioning/diagnostics_tab.js` — Diagnostics tab, fail-tag UX, notes.
- `ui/commissioning/sentinel_console.css`, `commission_tab.css`, `diagnostics_tab.css` — Styling for console and tabs.

### Other

- `devtools/generation_algo_refinement_probe.py` — Ad-hoc generation/extraction probe (not production server path).
