# codebase_map.md

## Root / Workspace

[Workspace Root]

- `agents.md`
  - Role: workspace operating rules.
  - Contains: policy document.
  - Uses: governs all work in this repo.

- `bootstrap.md`
  - Role: compact operating brief.
  - Contains: workflow/rules summary.
  - Uses: fresh-thread context document.

## Source Package

[Sentinel Package]

- `src/sentinel/__init__.py`
  - Role: package marker.
  - Contains: docstring.
  - Uses: Python package root.

## Contracts

[Contract Files]

- `src/sentinel/contracts/apex_project_structure_v4.json`
  - Role: extracted project-data shape contract.
  - Contains: top-level keys `source`, `events`, `devices`.
  - Uses: extraction flow (`extract_project_data.py` -> `extractor_core.py`).

- `src/sentinel/contracts/app_ui_structure.json`
  - Role: UI structure/config contract.
  - Contains: top-level keys `appUiStructureVersion`, `layout`, `uiHierarchy`, `header`, `appNavigation`, `zoomControls`, `viewportNavigation`, `layerPanel`, `testingPopup`, `buttonPresentation`, `viewportPresentation`, `state`.
  - Uses: generation flow (`generate_html.py` -> `render_core.py`).

## Extraction

[Extraction Modules]

- `src/sentinel/extraction/__init__.py`
  - Role: package marker.
  - Contains: docstring.
  - Uses: extraction package boundary.

- `src/sentinel/extraction/extract_project_data.py`
  - Role: extraction CLI entrypoint.
  - Contains: `parse_args`, `main`.
  - Uses: `ExtractContext`, `extract_project_data`, `validate_contract_shape`, `EventLogger`.

- `src/sentinel/extraction/extractor_core.py`
  - Role: extraction core implementation.
  - Contains: `ExtractContext`, `validate_contract_shape`, `extract_project_data`, `_resolve_button`, `_resolve_viewport_frames` plus helper functions.
  - Uses: `sqlite3`, `xml.etree.ElementTree`, regex utilities; called by `extract_project_data.py`.

## Generation

[Generation Modules]

- `src/sentinel/generation/__init__.py`
  - Role: package marker.
  - Contains: docstring.
  - Uses: generation package boundary.

- `src/sentinel/generation/generate_html.py`
  - Role: generation CLI entrypoint.
  - Contains: `parse_args`, `main`.
  - Uses: `render_core` exports (`render_project_home_html`, `render_single_device_html`, payload/filename helpers), `EventLogger`.

- `src/sentinel/generation/render_core.py`
  - Role: HTML/payload rendering core.
  - Contains: `render_project_home_html`, `render_single_device_html`, `build_device_payload`, `build_project_manifest`, many page/viewport/button helpers.
  - Uses: loaded by `generate_html.py`; consumes project data + app UI contract.

## Logging

[Logging Utilities]

- `src/sentinel/logging/event_logger.py`
  - Role: stdout event logger.
  - Contains: `EventLogger`, methods `info`, `warn`, `success`, `fail`.
  - Uses: extraction and generation CLI scripts.

## Server Package

[Server Package Markers]

- `src/sentinel/server/__init__.py`
  - Role: package marker.
  - Contains: docstring.
  - Uses: server package root.

- `src/sentinel/server/api/__init__.py`
  - Role: API package marker.
  - Contains: docstring.
  - Uses: API route module package.

- `src/sentinel/server/persistence/__init__.py`
  - Role: persistence package marker.
  - Contains: future import only.
  - Uses: persistence package boundary.

- `src/sentinel/server/services/__init__.py`
  - Role: not present.
  - Contains: n/a.
  - Uses: n/a.

## Server App

[FastAPI App]

- `src/sentinel/server/app/main.py`
  - Role: app factory and router wiring.
  - Contains: `create_app`, HTTP exception handler, `health`, module-level `app`.
  - Uses: API routers (`commissioning`, `events`, `testing`), repositories (`InMemoryRepository`, `PostgresRepository`), static mount `/commissioning`.

## Server API

[Commissioning API]

- `src/sentinel/server/api/commissioning.py`
  - Role: commissioning endpoints + websocket + snapshot/rollup helpers.
  - Contains: helpers (`_repo`, `_broker`, `_commissioning_snapshot`, `_fails_from_latest`, etc.), HTTP routes, websocket route.
  - Uses: `errors.http_error`, services (`pipeline`, `progress`, `ws_broker`), `Repository`.

[Testing API]

- `src/sentinel/server/api/testing.py`
  - Role: technician HTML/files, test result posting, testing websocket, target status.
  - Contains: file/HTML helpers, snapshot/event builders, HTTP and websocket handlers.
  - Uses: `errors.http_error`, `progress`, `ws_broker`, `Repository`.

[Events API]

- `src/sentinel/server/api/events.py`
  - Role: events router declaration.
  - Contains: `router`.
  - Uses: `APIRouter`.

[API Error Helper]

- `src/sentinel/server/api/errors.py`
  - Role: standard error envelope constructor.
  - Contains: `http_error`.
  - Uses: `HTTPException`.

## Server Services

[Pipeline Service]

- `src/sentinel/server/services/pipeline.py`
  - Role: upload storage and extract/generate subprocess orchestration.
  - Contains: path helpers, `save_upload`, `_run_subprocess_with_progress`, `regenerate_project`.
  - Uses: extraction/generation scripts, contract files, filesystem staging.

[Progress Service]

- `src/sentinel/server/services/progress.py`
  - Role: derive commissioning progress from latest project data + latest results.
  - Contains: `commissioning_progress` and many target-derivation helpers.
  - Uses: generated project-data files, `TestResultRecord`.

[Repository Service]

- `src/sentinel/server/services/repositories.py`
  - Role: repository models/protocol and in-memory/postgres implementations.
  - Contains: dataclasses (`Client`, `Project`, `TechLink`, etc.), `Repository` protocol, `InMemoryRepository`, `PostgresRepository`.
  - Uses: persistence layer (`db`, `queries`) for postgres path.

[WebSocket Broker Service]

- `src/sentinel/server/services/ws_broker.py`
  - Role: project event pub/sub with replay buffer.
  - Contains: `ProjectEventBroker`, `wait_for_next`.
  - Uses: queue + JSON delivery; consumed by commissioning/testing APIs.

## Persistence

[DB Adapter]

- `src/sentinel/server/persistence/db.py`
  - Role: DB URL parsing, pg connection, migrations, fetch helpers.
  - Contains: `DbConfig`, `parse_database_url`, `connect`, `apply_migrations`, `fetch_all`, `fetch_one`.
  - Uses: `pg8000.dbapi`, SQL migration files.

[SQL Query Layer]

- `src/sentinel/server/persistence/queries.py`
  - Role: SQL operations for clients/projects/uploads/tech links/results/fail tags.
  - Contains: query functions (`create_client`, `create_project`, `rotate_tech_link_token`, `append_test_result`, etc.) and `DuplicateClientNameError`.
  - Uses: `persistence.db`; called by `PostgresRepository`.

## UI (Commissioning Console)

[UI Entry]

- `src/sentinel/ui/commissioning/index.html`
  - Role: commissioning console shell markup.
  - Contains: sidenav tabs and panel containers (`manage`, `commission`, `diagnostics`) with IDs for JS hooks.
  - Uses: CSS (`sentinel_console.css`, `commission_tab.css`, `diagnostics_tab.css`) and JS (`commissioning.js`, `commission_tab.js`, `diagnostics_tab.js`).

[UI Core Script]

- `src/sentinel/ui/commissioning/commissioning.js`
  - Role: manage-project/client flows, upload/regenerate, tech link management, shared UI state wiring.
  - Contains: many helpers and actions (`refreshClients`, `refreshProjects`, `uploadAndRegenerate`, `createTechLink`, `run`, etc.).
  - Uses: `/api/v1/commissioning/...` endpoints, shared ws/store globals.

[Commission Tab Script]

- `src/sentinel/ui/commissioning/commission_tab.js`
  - Role: commissioning tab rendering and shared store/ws manager ownership.
  - Contains: pie/table renderers, store reducer, ws manager, `runCommissionTab`.
  - Uses: DOM in `index.html`; exposes/uses `window.__sentinelProjectStore`, `window.__sentinelProjectWsManager`.

[Diagnostics Tab Script]

- `src/sentinel/ui/commissioning/diagnostics_tab.js`
  - Role: diagnostics tab rendering, task list/pies, fail-tag updates, notes popup.
  - Contains: diagnostics helpers, render/update functions, `initDiagnosticsTab`.
  - Uses: shared store/ws manager globals; diagnostics DOM and fail-tag endpoint.

[UI Base CSS]

- `src/sentinel/ui/commissioning/sentinel_console.css`
  - Role: global commissioning console styles.
  - Contains: root variables and shared layout/component rules.
  - Uses: classes/IDs in console HTML and tab scripts.

[Commission Tab CSS]

- `src/sentinel/ui/commissioning/commission_tab.css`
  - Role: commission-tab visual/layout styles.
  - Contains: styles for pies/KPIs/activity sections.
  - Uses: commission panel/class hooks.

[Diagnostics Tab CSS]

- `src/sentinel/ui/commissioning/diagnostics_tab.css`
  - Role: diagnostics-tab style overrides/helpers.
  - Contains: diagnostics-specific selectors.
  - Uses: diagnostics panel/class hooks.
