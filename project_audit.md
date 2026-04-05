# Project Audit

## Pass 1: Repo and Folder Structure

### Scope

Reviewed only repo/folder structure and near-top-level grouping:
- root folders/files in `y:\Desktop\Development\Sentinel`
- first-level structure under `src`, `src/sentinel`, and key adjacent folders (`docs`, `dev_tests`, `research`, `output`, `archives`, `Assets`, `Project Structure`)
- entry-point discoverability from layout (not internal behavior)

### Findings

**Title:** Production code and artifact/workspace folders are mixed at root  
**Severity:** High  
**Principle involved:** Clear top-level separation  
**Observed issue:** Root includes source, docs, tests, archives, temp, outputs, research, and ad-hoc asset folders together without clear domain boundaries.  
**Evidence:** `src/`, `docs/`, `dev_tests/`, `archives/`, `output/`, `research/`, `Assets/`, `Project Structure/`, `temp/`, `tmp/`, `.tmp_apex_env/`, `.tmp_preview_*`  
**Why it matters:** New developers cannot quickly identify canonical product code vs disposable/generated content.  
**Recommended target state:** Top-level structure split into clear domains (for example: `src/`, `tests/`, `docs/`, `tools/`, `artifacts/`), with temporary/generated content isolated outside core roots.  
**Suggested priority:** Now

**Title:** Naming conventions are inconsistent across peer folders  
**Severity:** Medium  
**Principle involved:** Consistent naming conventions  
**Observed issue:** Mixed case, spaces, underscores, and temporary prefixes coexist in sibling root folders.  
**Evidence:** `Assets/`, `Project Structure/`, `dev_tests/`, `tmp/`, `temp/`, `.tmp_preview_uploads/`  
**Why it matters:** Inconsistent naming reduces predictability and increases path/friction in scripts, docs, and onboarding.  
**Recommended target state:** One folder naming convention (typically lowercase + hyphen or lowercase + underscore) and no spaces in canonical directories.  
**Suggested priority:** Soon

**Title:** Temporary/staging directories are duplicated and ambiguous  
**Severity:** Medium  
**Principle involved:** No orphan or ambiguous folders  
**Observed issue:** Multiple temp-like roots exist with unclear ownership and lifecycle.  
**Evidence:** `tmp/`, `temp/`, `.tmp_apex_env/`, `.tmp_preview_generated/`, `.tmp_preview_uploads/`  
**Why it matters:** Ambiguous scratch locations lead to drift, stale data, and accidental dependency on transient files.  
**Recommended target state:** Single clearly named staging/temp root with explicit retention policy and git-ignore policy.  
**Suggested priority:** Soon

**Title:** Asset and historical content are mixed with active project structure at root  
**Severity:** Medium  
**Principle involved:** Logical grouping by responsibility  
**Observed issue:** Archive/history/reference artifacts and active resources appear side-by-side without boundary.  
**Evidence:** `archives/` (historical), `output/` (generated), `research/` (exploratory), `Assets/` (mixed binary and specs), plus root JSON blobs like `Verrier Home FEENY EDIT v49_project_data.json`  
**Why it matters:** Harder to tell what is authoritative and what is legacy/reference output.  
**Recommended target state:** Separate active inputs from generated outputs and historical archives under explicit lifecycle namespaces.  
**Suggested priority:** Soon

**Title:** Hidden/system files are present in source roots  
**Severity:** Low  
**Principle involved:** Predictable structure  
**Observed issue:** OS-generated files appear inside project/source folders.  
**Evidence:** `.DS_Store` at root and under `src/sentinel/` and `src/sentinel/ui/`  
**Why it matters:** Noise in tree navigation and potential accidental commits.  
**Recommended target state:** Enforce ignore/cleanup for OS artifacts across repository roots.  
**Suggested priority:** Later

### Strengths

- Core application code is at least centralized under `src/sentinel/`.
- Responsibility-based backend grouping exists under `src/sentinel/server/` (`api/`, `services/`, `persistence/`, `app/`).
- UI has a clearly identifiable entry file path (`src/sentinel/ui/commissioning/index.html`).
- Contracts are grouped under `src/sentinel/contracts/`.
- Documentation has a dedicated top-level `docs/` folder.

### Open Questions

- Are `output/`, `archives/`, `research/`, and `Assets/` intended as permanent first-class roots, or transitional working areas?
- Should this repo be a single app repo or a multi-domain/monorepo-style workspace (which would justify broader top-level segmentation)?
- Is there an agreed naming standard already documented (for example kebab-case vs snake_case) that should be enforced uniformly?

### Pass Summary

- Structural quality is mixed: core code organization is reasonably clear inside `src/sentinel`, but root-level layout is crowded and lifecycle boundaries are not explicit.
- Overall rating: **Acceptable**

## Pass 2: Backend Architecture

### Scope

Reviewed backend architecture only for:
- layering (`app`/`api`/`services`/`persistence`)
- responsibility placement (controller vs service vs data/infrastructure)
- dependency direction and coupling
- business-logic location

Reviewed modules under `src/sentinel/server` and direct backend dependencies only.

### Findings

**Title:** Controller layer contains substantial business/data-shaping logic  
**Severity:** High  
**Principle involved:** Business logic not placed in controllers or transport layers  
**Observed issue:** API route modules include non-trivial aggregation/snapshot/failure-rollup logic instead of delegating to a domain/application service layer.  
**Evidence:** `src/sentinel/server/api/commissioning.py` (`_rollups_from_repo`, `_fails_from_latest`, `_commissioning_snapshot`), `project_rollups`; `src/sentinel/server/api/testing.py` (`_compute_progress_and_rollups`)  
**Why it matters:** Harder to test business behavior independently of HTTP/WebSocket transport; controller modules become high-churn and tightly coupled.  
**Recommended target state:** Move rollup/snapshot/progress composition into dedicated application/domain service(s); keep API handlers thin (validate/map/request-response).  
**Suggested priority:** Now

**Title:** Controller layer reaches data repository directly across many endpoints  
**Severity:** High  
**Principle involved:** Clear layering (controller -> service -> domain -> data/infrastructure)  
**Observed issue:** Many routes call repository operations directly, bypassing a cohesive service/application layer for use-case orchestration.  
**Evidence:** `src/sentinel/server/api/commissioning.py` routes using `_repo(request)`; `src/sentinel/server/api/testing.py` (`post_result`) direct repo writes; `src/sentinel/server/services/repositories.py` (`Repository` protocol + impls)  
**Why it matters:** Use-case rules spread across endpoints, making behavior duplication and drift more likely.  
**Recommended target state:** Introduce explicit application services per use case (projects, tech links, results, rollups), with controllers delegating.  
**Suggested priority:** Now

**Title:** Domain boundary is implicit; domain + application + infra concerns are partially co-located  
**Severity:** Medium  
**Principle involved:** Clear boundaries between domain logic and infrastructure  
**Observed issue:** No explicit `domain` layer/package; core models/repository contract and concrete Postgres adapter wiring are in the same `services/repositories.py` module.  
**Evidence:** `src/sentinel/server/services/repositories.py` (`Repository`, `InMemoryRepository`, `PostgresRepository`); Postgres adapter imports persistence inside class init.  
**Why it matters:** Blurs abstraction boundaries and increases coupling between business-facing interfaces and infrastructure details.  
**Recommended target state:** Separate domain entities/contracts from infrastructure adapters (for example `domain/`, `application/`, `infrastructure/`).  
**Suggested priority:** Soon

**Title:** IO responsibilities are mixed into API transport modules  
**Severity:** Medium  
**Principle involved:** Separation between IO (DB, APIs) and business logic  
**Observed issue:** API modules handle filesystem path resolution, static/generated file serving, websocket replay and event composition in addition to transport concerns.  
**Evidence:** `src/sentinel/server/api/testing.py` (`testing_html`, `testing_file`, websocket flow), `src/sentinel/server/api/commissioning.py` websocket snapshot/replay flow.  
**Why it matters:** Transport modules accumulate infrastructure and policy concerns, reducing maintainability and test isolation.  
**Recommended target state:** Push non-transport IO orchestration into services/infrastructure adapters; keep API modules focused on protocol translation.  
**Suggested priority:** Soon

### Strengths

- Clear physical package split exists: `app`, `api`, `services`, `persistence`.
- Dependency flow is mostly one-way: app -> api/services; api -> services; services (Postgres adapter) -> persistence; persistence does not import api/services.
- No obvious circular imports in reviewed backend modules.
- Persistence responsibilities are clearly concentrated in `src/sentinel/server/persistence/db.py` and `src/sentinel/server/persistence/queries.py`.

### Open Questions

- Is the current architecture intentionally "service-lite" (controller + repository) for MVP speed, or is a layered domain/application split expected now?
- Should progress/rollup computation be treated as domain logic or API-specific projection logic?
- Is websocket event shaping considered part of transport only, or intended as reusable application behavior across interfaces?

### Pass Summary

- Backend has a decent package skeleton and mostly clean dependency direction, but key use-case/business composition lives in API controllers and repository coupling is high.
- Overall rating: **Acceptable**

## Pass 3: Frontend Architecture

### Scope

Reviewed only frontend architecture in `src/sentinel/ui/commissioning`:
- UI vs logic separation
- state handling patterns
- component/module responsibility boundaries
- frontend folder/module organization

### Findings

**Title:** State management is split across multiple ad-hoc stores  
**Severity:** High  
**Principle involved:** State management is consistent and not scattered randomly  
**Observed issue:** Frontend state is managed in three patterns at once: local mutable `state`, global shared store on `window`, and diagnostics runtime object.  
**Evidence:** `src/sentinel/ui/commissioning/commissioning.js` (`state` object), `src/sentinel/ui/commissioning/commission_tab.js` (`ensureSharedProjectStore`), `src/sentinel/ui/commissioning/diagnostics_tab.js` (`diagRt`)  
**Why it matters:** Increases drift risk and makes data flow harder to reason about/debug.  
**Recommended target state:** One canonical state model for project/session data, with module-local UI state only for presentation concerns.  
**Suggested priority:** Now

**Title:** UI modules contain heavy domain/business interpretation logic  
**Severity:** High  
**Principle involved:** No heavy business logic inside UI rendering  
**Observed issue:** Diagnostics/commission files parse domain target keys, derive scope semantics, classify failures, and compute dashboard metrics directly in UI modules.  
**Evidence:** `src/sentinel/ui/commissioning/diagnostics_tab.js` (`parseIdentity`, `formatEffectiveScope`, failure derivation helpers), `src/sentinel/ui/commissioning/commission_tab.js` (`reduceProjectStore`)  
**Why it matters:** Business behavior becomes coupled to DOM modules and harder to test/reuse.  
**Recommended target state:** Move domain transforms/derivations into dedicated pure logic modules; keep UI files focused on rendering and user interaction wiring.  
**Suggested priority:** Now

**Title:** Side effects are broadly distributed across modules  
**Severity:** Medium  
**Principle involved:** Side effects are isolated  
**Observed issue:** Fetch, websocket lifecycle, localStorage, and DOM event wiring are interleaved throughout multiple files with immediate bootstrapping calls.  
**Evidence:** `src/sentinel/ui/commissioning/commissioning.js` (`run()` bootstrapping), `src/sentinel/ui/commissioning/commission_tab.js` (shared websocket manager), `src/sentinel/ui/commissioning/diagnostics_tab.js` (`initDiagnosticsTab()` bootstrapping)  
**Why it matters:** Makes side-effect behavior harder to isolate and mock in tests; increases coupling across tabs.  
**Recommended target state:** Centralize effect orchestration (network/ws/subscriptions) behind dedicated effect/service modules.  
**Suggested priority:** Soon

**Title:** Global `window` singletons create tight cross-module coupling  
**Severity:** Medium  
**Principle involved:** Reusable components are not tightly coupled  
**Observed issue:** Shared store/ws manager are discovered and mutated through implicit `window.__sentinel...` contracts.  
**Evidence:** `src/sentinel/ui/commissioning/commissioning.js` (uses globals), `src/sentinel/ui/commissioning/commission_tab.js` (global store/ws creation), `src/sentinel/ui/commissioning/diagnostics_tab.js` (global dependency)  
**Why it matters:** Reuse and module independence are reduced; load-order coupling increases.  
**Recommended target state:** Explicit module imports/exports for shared state/services instead of global runtime contracts.  
**Suggested priority:** Soon

**Title:** Frontend modules are monolithic for their responsibilities  
**Severity:** Medium  
**Principle involved:** Components have single responsibility  
**Observed issue:** Tab JS files are very large and mix rendering, state transforms, sorting, websocket orchestration, and event wiring in single modules.  
**Evidence:** `src/sentinel/ui/commissioning/commission_tab.js` (~1075 lines), `src/sentinel/ui/commissioning/diagnostics_tab.js` (~1073 lines), `src/sentinel/ui/commissioning/commissioning.js` (~787 lines)  
**Why it matters:** Higher cognitive load and higher regression risk when changing isolated behavior.  
**Recommended target state:** Split by responsibility (view renderers, state reducers/selectors, effects/api/ws, feature controllers).  
**Suggested priority:** Soon

### Strengths

- Folder organization is feature-oriented at this scale (`ui/commissioning` with tab-focused JS/CSS files).
- There is a shared reducer/store pattern for project events, which gives a mostly predictable event-driven flow for commission/diagnostics sync.
- Commission and diagnostics tabs both consume the same project event stream/store slice, reducing duplicated network polling paths.

### Open Questions

- Is the current "vanilla JS + global singleton" architecture an intentional long-term constraint, or temporary MVP structure?
- Should target-key parsing/scope derivation live in frontend by design, or be treated as backend-provided view-model data?
- Is there a plan to support additional UI features/modules beyond `commissioning` that would require stronger module boundaries now?

### Pass Summary

- Frontend architecture has a workable feature entry structure, but separation of concerns is weak inside modules: state/effects/domain transforms are mixed with UI rendering and coupled via globals.
- Overall rating: **Weak**

## Pass 4: Shared Utilities and Cross-Cutting Concerns

### Scope

Reviewed only shared utilities and cross-cutting modules for reuse/modularity:
- backend shared utility/service modules (`logging`, API error utility, websocket broker, shared repository abstraction module)
- frontend shared cross-tab helpers and global shared mechanisms
- duplication patterns and cross-layer usage boundaries

### Findings

**Title:** Frontend shared helpers are duplicated instead of centralized  
**Severity:** High  
**Principle involved:** No unnecessary duplication  
**Observed issue:** Core cross-cutting helpers (`$`, API URL building, WS URL building, WS logging wrappers) are redefined per file.  
**Evidence:** `src/sentinel/ui/commissioning/commissioning.js`, `src/sentinel/ui/commissioning/commission_tab.js`, `src/sentinel/ui/commissioning/diagnostics_tab.js`  
**Why it matters:** Changes to shared behavior require multi-file edits and can drift.  
**Recommended target state:** One shared frontend utility module for DOM/API/WS/log helpers consumed by all tab modules.  
**Suggested priority:** Now

**Title:** Shared frontend contracts rely on implicit globals and load-order coupling  
**Severity:** High  
**Principle involved:** Shared code does not create cross-layer coupling  
**Observed issue:** Modules discover dependencies through `window.__sentinel...` globals and fallback checks (`if (typeof api === "function")`).  
**Evidence:** `src/sentinel/ui/commissioning/commission_tab.js` (`window.__sentinelProjectStore`, `window.__sentinelProjectWsManager`), `src/sentinel/ui/commissioning/diagnostics_tab.js` fallback checks, `src/sentinel/ui/commissioning/index.html` script-order dependency  
**Why it matters:** Shared ownership is unclear, and reusability/testability drops due to implicit runtime coupling.  
**Recommended target state:** Explicit import/export ownership for shared store/ws/logger APIs (single owner module).  
**Suggested priority:** Now

**Title:** Backend websocket cross-cutting helpers are duplicated across API modules  
**Severity:** Medium  
**Principle involved:** Cross-cutting concerns are consistently handled  
**Observed issue:** Both API modules duplicate timeout constants, send-with-timeout behavior, repo/broker access helpers, and similar WS control patterns.  
**Evidence:** `src/sentinel/server/api/commissioning.py` and `src/sentinel/server/api/testing.py` (WS constants, `_send_text_or_fail`, `_repo`/`_broker` patterns)  
**Why it matters:** Fixes to WS policy/reliability are easy to apply inconsistently.  
**Recommended target state:** Consolidate shared WS policy/helpers into a dedicated shared module used by both APIs.  
**Suggested priority:** Soon

**Title:** Generated-path utility logic is repeated in multiple backend modules  
**Severity:** Medium  
**Principle involved:** Utilities are lightweight and reusable  
**Observed issue:** `_generated_root` / `_project_dir` path utilities exist in multiple places with overlapping responsibility.  
**Evidence:** `src/sentinel/server/services/pipeline.py`, `src/sentinel/server/services/progress.py`, `src/sentinel/server/api/testing.py`  
**Why it matters:** Environment/path behavior can diverge across layers unexpectedly.  
**Recommended target state:** Single shared path utility module for generated/upload roots used by services and APIs.  
**Suggested priority:** Soon

**Title:** Repository shared module is broad and mixes abstraction + concrete infra  
**Severity:** Medium  
**Principle involved:** Shared utilities have narrow, clear responsibilities  
**Observed issue:** One shared module carries domain models, repository protocol, in-memory implementation, and Postgres implementation.  
**Evidence:** `src/sentinel/server/services/repositories.py` (`Repository`, `InMemoryRepository`, `PostgresRepository`)  
**Why it matters:** Shared ownership and boundaries are blurred; coupling risk increases as features grow.  
**Recommended target state:** Split contracts/models from infrastructure implementations with explicit ownership boundaries.  
**Suggested priority:** Soon

### Strengths

- `EventLogger` is focused and lightweight, with clear purpose: `src/sentinel/logging/event_logger.py`.
- API error envelope handling is centralized and consistently used via one helper: `src/sentinel/server/api/errors.py`.
- `ProjectEventBroker` is a coherent cross-cutting primitive for pub/sub + replay and is reused by both commissioning/testing APIs: `src/sentinel/server/services/ws_broker.py`.

### Open Questions

- Should frontend shared utilities remain framework-free globals by design, or is module-based sharing acceptable now?
- Is websocket behavior intended to be identical between commissioning/testing, or intentionally diverging?
- Who owns shared generated-path semantics (`generated`, `uploads`) when service and API both depend on them?

### Pass Summary

- Shared code quality is mixed: there are good focused backend utilities, but notable duplication and implicit global coupling in frontend and repeated cross-cutting helpers in backend APIs.
- Overall rating: **Acceptable**

## Pass 5: Test Architecture

### Scope

Reviewed only test architecture in `dev_tests`:
- test placement and layer organization
- structure and naming
- alignment to architectural boundaries (server/services/ui/scripts)
- determinism/repeatability characteristics from test structure and dependencies

### Findings

**Title:** Layer organization is partially present but inconsistent  
**Severity:** Medium  
**Principle involved:** Tests organized by layer (unit / integration / system)  
**Observed issue:** Directories are `ui`, `integration`, `regression`, but `regression` mixes unit-like checks, API integration tests, and static source-string assertions.  
**Evidence:** `dev_tests/regression/test_server_health.py`, `dev_tests/regression/test_repo_tiebreaker.py`, `dev_tests/regression/test_ws_logging_markers.py`  
**Why it matters:** Makes it harder to know intent/scope of a failing test and slows triage.  
**Recommended target state:** Clear layer buckets (`unit`, `integration`, `system/e2e`) with regression as a tag, not a mixed layer.  
**Suggested priority:** Soon

**Title:** Significant test set is tightly coupled to implementation details  
**Severity:** High  
**Principle involved:** Tests not tightly coupled to implementation details  
**Observed issue:** Multiple tests assert exact source snippets and log-marker strings in code files rather than behavior through public interfaces.  
**Evidence:** `dev_tests/regression/test_server_commissioning_pipeline.py` (read_text/assertIn), `dev_tests/regression/test_ws_logging_markers.py` (read_text/assertIn)  
**Why it matters:** Refactors or benign wording changes cause brittle failures without user-visible regressions.  
**Recommended target state:** Prefer behavioral assertions via API/UI/runtime outcomes; keep source-text assertions minimal and purpose-specific.  
**Suggested priority:** Now

**Title:** Live acceptance tests rely on external network target by default  
**Severity:** High  
**Principle involved:** Deterministic and repeatable tests  
**Observed issue:** Live UI resilience tests default to a remote host and environment-driven runtime behavior.  
**Evidence:** `dev_tests/ui/test_resilience_acceptance_live.py` (default base URL and restart-command gating)  
**Why it matters:** Non-deterministic outcomes, external flakiness, and environment coupling reduce repeatability in CI/local runs.  
**Recommended target state:** Keep live tests explicitly opt-in only, isolated from default suite; default runs should be hermetic/local.  
**Suggested priority:** Now

**Title:** Very large test modules act as broad scenario bundles  
**Severity:** Medium  
**Principle involved:** Clear naming and structure  
**Observed issue:** Some files are multi-thousand lines and combine helpers, fixtures, and many scenarios.  
**Evidence:** `dev_tests/ui/test_viewport_popup_runtime.py` (~2936 lines), `dev_tests/ui/test_commissioning_console_runtime.py` (~1327 lines), `dev_tests/integration/test_scripts.py` (~1164 lines)  
**Why it matters:** Harder maintenance and higher chance of side effects between scenarios.  
**Recommended target state:** Split mega-files by feature/use-case area with shared fixtures/helpers extracted.  
**Suggested priority:** Soon

**Title:** Core logic has unit coverage, but placement is diluted by mixed test layers  
**Severity:** Low  
**Principle involved:** Core logic covered by unit tests  
**Observed issue:** Unit-style tests exist (e.g., extractor/repository logic), but are intermixed under `regression`, reducing discoverability of core-unit coverage.  
**Evidence:** `dev_tests/regression/test_extractor_contract_enforcement.py`, `dev_tests/regression/test_repo_tiebreaker.py`  
**Why it matters:** Coverage exists, but architecture-level test intent is less clear to new contributors.  
**Recommended target state:** Place pure logic tests under explicit unit layer.  
**Suggested priority:** Later

### Strengths

- Consistent framework usage: `unittest` across suite (no mixed `pytest` conventions found).
- Strong API integration coverage via FastAPI `TestClient` for commissioning/testing flows.
- UI runtime automation is present with Playwright-based tests (supports minimal manual testing).
- External interaction paths (DB via `DATABASE_URL`, server endpoints, websocket flows) are represented in integration/regression coverage.

### Open Questions

- Should live acceptance tests be part of normal test runs, or treated as explicitly separate operational checks?
- Is `regression` intended as a true layer, or as a label across multiple layers?
- Do you want `unit` as a first-class directory boundary going forward, or keep current naming and improve metadata/docs only?

### Pass Summary

- Test coverage breadth is strong, but architecture is mixed: layer boundaries are blurred and some suites are brittle due to implementation-coupled assertions and live external defaults.
- Overall rating: **Acceptable**

## Pass 6: Config, Logging, and Error Handling

### Scope

Reviewed only:
- configuration handling and environment usage
- logging patterns and consistency
- error handling/propagation behavior

Inspected `src/sentinel/server/*`, `src/sentinel/logging/*`, extraction/generation entrypoints, and commissioning frontend logging/error paths.

### Findings

**Title:** Configuration is environment-aware but decentralized across modules  
**Severity:** Medium  
**Principle involved:** Configuration is centralized and environment-aware  
**Observed issue:** Environment variable reads and defaults are spread across app, services, and API modules with no single config/settings boundary.  
**Evidence:** `src/sentinel/server/app/main.py`, `src/sentinel/server/services/pipeline.py`, `src/sentinel/server/services/progress.py`, `src/sentinel/server/api/testing.py`  
**Why it matters:** Increases drift risk and makes environment behavior harder to reason about globally.  
**Recommended target state:** Central settings module/object that owns env parsing/defaults/validation, then inject into consumers.  
**Suggested priority:** Soon

**Title:** Missing `DATABASE_URL` silently downgrades persistence mode  
**Severity:** High  
**Principle involved:** Clear separation between config and logic  
**Observed issue:** App automatically switches to in-memory repository when `DATABASE_URL` is missing.  
**Evidence:** `src/sentinel/server/app/main.py`  
**Why it matters:** Misconfiguration can go unnoticed and cause reliability/data-persistence surprises.  
**Recommended target state:** Explicit runtime mode selection and startup-time guardrails for non-dev environments.  
**Suggested priority:** Now

**Title:** Some errors are swallowed or converted to fallback payloads  
**Severity:** High  
**Principle involved:** Errors are not silently swallowed  
**Observed issue:** Frontend has many empty catch blocks, and backend helper paths catch broad exceptions and return synthetic defaults.  
**Evidence:** `src/sentinel/ui/commissioning/commissioning.js`, `src/sentinel/ui/commissioning/commission_tab.js`, `src/sentinel/ui/commissioning/diagnostics_tab.js`, `_safe_progress` in `src/sentinel/server/api/commissioning.py`  
**Why it matters:** Failures can be hidden, reducing debuggability and creating misleading “healthy-looking” behavior.  
**Recommended target state:** Log + classify fallback behavior explicitly, and avoid silent catches unless intentionally non-critical.  
**Suggested priority:** Now

**Title:** Internal exception details are exposed in user-facing 500 responses  
**Severity:** Medium  
**Principle involved:** Clear distinction between user-facing and system errors  
**Observed issue:** Some 500 responses include raw exception text in API error messages.  
**Evidence:** `src/sentinel/server/api/commissioning.py` (`REGENERATE_FAILED` with `message=str(e)`)  
**Why it matters:** Can leak internal details and reduce control over client-facing error contracts.  
**Recommended target state:** Return stable user-safe message + internal correlation ID; keep raw exception details in logs only.  
**Suggested priority:** Soon

**Title:** Logging approach is inconsistent across layers  
**Severity:** Medium  
**Principle involved:** Logging is consistent and structured  
**Observed issue:** Backend uses `logging` with structured-ish markers, CLI uses custom `print` logger, frontend uses console logging with varying formats.  
**Evidence:** `src/sentinel/logging/event_logger.py`, `src/sentinel/extraction/extract_project_data.py`, `src/sentinel/generation/generate_html.py`, `src/sentinel/server/api/testing.py`, `src/sentinel/ui/commissioning/commissioning.js`  
**Why it matters:** Cross-component observability becomes harder to aggregate/filter consistently.  
**Recommended target state:** Define one logging contract (fields/levels/event naming) across backend + scripts; map frontend logs to the same taxonomy where possible.  
**Suggested priority:** Soon

### Strengths

- Error envelope is standardized via `src/sentinel/server/api/errors.py` and global HTTP exception handler in `src/sentinel/server/app/main.py`.
- DB config parsing validates required fields and scheme strictly in `src/sentinel/server/persistence/db.py`.
- WS observability includes explicit event codes and perf markers in backend handlers (`src/sentinel/server/api/commissioning.py`, `src/sentinel/server/api/testing.py`).
- No hardcoded secrets found in `src/sentinel` during this pass.

### Open Questions

- Is in-memory fallback intended outside local/dev usage, or should missing `DATABASE_URL` be startup-fatal in deployed environments?
- Do you want degraded fallback responses (like `_safe_progress`) or strict failure propagation for observability?
- Is there an existing logging sink/schema requirement (JSON logs, trace IDs, etc.) that should be enforced uniformly?

### Pass Summary

- Reliability/observability foundations are present, but config ownership is fragmented, some failures are masked, and logging strategy is inconsistent across layers.
- Overall rating: **Acceptable**
