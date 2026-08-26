# Sentinel briefing (from code on `hard_keys`)

This note describes what the running software **does**, as implemented. It is not a product plan. Where the code does not say, this document says **unknown**.

Package name: `sentinel` (`pyproject.toml`, version `0.1.0`). Python ≥ 3.11.

---

## 1. What it is, how it runs, who uses it

### What it is

Sentinel is a **commissioning and field-testing server** for **RTI** (Remote Technologies Inc.) control-system projects. An RTI project is stored as a `.apex` file. Sentinel:

1. Accepts that file.
2. Reads it as a **SQLite database** (`sqlite3.connect` on the `.apex` path in `src/sentinel/extraction/extractor_core.py`).
3. Writes project JSON and technician HTML.
4. Lets a person on site mark each verification point **PASS**, **FAIL**, or **UNTESTED**.
5. Shows progress and failures in a separate console.

The generated technician pages **mirror** the programmed remote/device screens so a person can walk the same pages as the real installation. The server records outcomes. The code does **not** contain a live RTI control protocol (no driver that talks to processors or remotes). What the technician physically presses on the real system is outside this app.

### How it is deployed and run

**Production shape in the repo’s ops docs and app wiring:**

- One FastAPI app (`src/sentinel/server/app/main.py`), served by Uvicorn.
- Ops notes describe a single droplet: systemd unit `sentinel.service`, Uvicorn on `127.0.0.1:8000`, nginx on port 80 proxying to it (`docs/directives/dev_environment_and_workflow.md`). The systemd unit file itself is **not** in this repository.
- Deploy of application code is `git archive … HEAD src` into `/opt/sentinel/app`, then restart. That ships **only** `src/`.
- If environment variable `DATABASE_URL` is set (Postgres URL), the app uses `PostgresRepository` and runs SQL migrations on startup. If it is unset, the app uses `InMemoryRepository` (data dies with the process).
- Uploaded `.apex` files land under `SENTINEL_UPLOAD_ROOT` (default `uploads/`). Generated JSON/HTML land under `SENTINEL_GENERATED_ROOT` (default `generated/`).
- Local/dev: same FastAPI app; optional Playwright is only for developer UI tests (`pyproject.toml` extra `dev`).

There is **no** Redis, Celery, or other job queue in `src/`. Extract and generate run as **child Python processes** started by the API request.

### Who uses it

The code has **two browser surfaces**, not three named product roles:

| Surface | URL | Who, in the code |
|---|---|---|
| Commissioning console | `/commissioning` (static files from `src/sentinel/ui/commissioning/`) plus `/api/v1/commissioning/…` | A single stub user. Display name **Jamie**, fixed UUID in `src/sentinel/server/services/commissioning_user.py` and SQL seed `006_users_scoped_clients.sql`. The header chip says “Signed in as Jamie”. There is **no** login, password, or multi-user session. Optional shared secret: `SENTINEL_COMMISSIONING_API_KEY`. |
| Technician testing | `/testing/{techToken}` plus `/api/v1/testing/{techToken}/…` | Anyone with an unrevoked opaque URL token. No technician account. Tokens are stored hashed (SHA-256). Console can create, rotate, and revoke “tech links.” Placeholder label text: “e.g. Onsite Tech”. |

Data hierarchy in the console: **Client → Project**. “Client” is a named grouping for projects owned by the stub user. It is **not** labeled dealer, integrator, or customer in code.

**Dealer:** unknown. That word does not appear as a role, route, or table.

**Jamie:** the hardcoded commissioning-console identity until real authentication exists (the module docstring says so). Whether that is only the product owner in production, or every operator of the console, is **unknown** from code—the software cannot tell operators apart.

---

## 2. What a “test” is, and what a “test target” is

Two different meanings of “test” exist in this repo. Mixing them is how the count becomes confusing.

### A. Developer tests (not the product)

`dev_tests/regression/` and `dev_tests/ui/` are **unittest** (and Playwright) checks that Sentinel’s own code still extracts and renders correctly. They are for people changing the software. They are **not** what technicians run on a job, and they are **not** the “thousands” number.

### B. Commissioning test targets (the product)

In this product, the thing that is counted, stored, and marked PASS/FAIL is a **test target**.

A test target is **one verification point** derived from the `.apex` project:

- On a **button / control** (screen button, screen label, hard key, UI item, viewport child): flags such as Text, System Macro, Macro Step, Variable – Text/Reversed/Inactive/Visible/Value/State/Command/Image/List, Bitmap, Icon, Page Link.
- On a **system or driver event**: Event Trigger (always on when the event is extracted), plus System Macro / Macro Step when macros exist.

One physical control can produce **several** targets. Example: the same button can require Text **and** System Macro **and** Variable – Visible **and** Bitmap. Each of those is a separate row the technician can Pass or Fail.

The technician UI opens a popup of those rows (`Pass` / `Fail` + required fail note). “Pass All” walks the rows of **that popup**, one after another—not the whole project.

### Where the count comes from

After extraction, `src/sentinel/extraction/extract_project_data.py` writes:

- `{apex_stem}_project_data.json` — full extracted project.
- `{apex_stem}_resolved_targets.json` — the official list of expected target keys (`format: sentinel-resolved-targets-v1`), built by `build_resolved_targets` in `src/sentinel/server/services/progress.py`.

Progress (`totalTargets`, pass/fail/untested, percent complete) is:

1. Load that resolved list (or rebuild it from project JSON if the sidecar is missing).
2. Load the **latest** recorded outcome per `targetKey` from the database.
3. Count matches.

The commissioning pies and “X/Y tested” numbers are that set. Placeholder “12/20” text in `index.html` is dummy markup, not a real count.

Target identity is a string `targetKey`, not a row in the `.apex` file. Typical shapes:

- Events: `event:{eventId}:{label}` e.g. `event:42:Event Trigger`
- Tagged buttons (scoped): `tt2:{rtiAddress}:{GLOBAL|ROOM}:{roomId}:{sourceId}:{buttonTagId}:{programRef}:{targetName}`
- Untagged UI items: `tt_ui:{rtiAddress}:{SHARED|LOCAL}:{layerId}:{buttonId}:{targetName}`
- Older fallbacks still in generators: `btn:…` and `vpbtn:…`

Results are stored **append-only** in `test_results` (Postgres or memory). Latest outcome is “current status.” An earlier FAIL is not deleted if a later PASS is recorded. First-ever outcome per target is kept separately (`target_first_test_outcomes`) for “first-time fail” pies.

### What “thousands of tests” would mean **here**

It would mean **thousands of test targets inside one uploaded `.apex` / one Sentinel project** (one job’s RTI file).

It would **not** mean:

- thousands of developer unit tests
- thousands of servers or RTI processors running in parallel
- a synthetic test-case generator (the list is **derived from whatever is programmed in that file**)

Scale comes from **project size**: devices × pages × layers × buttons × enabled flags, plus events. A large house project with many remotes, pages, and richly programmed buttons produces a large resolved-target list. How large a typical live job is, in numbers, is **unknown** from this repo (no production metrics in code). A comment in a working note (`updated_testing_with_scope.md`) mentions “tens of thousands”; that is not measured by the application.

---

## 3. End-to-end path (real modules)

Operator and technician, in order:

### 1. Console: client, project, upload

- UI: `src/sentinel/ui/commissioning/index.html` + `commissioning.js`
- APIs: `src/sentinel/server/api/commissioning.py`
  - `POST /api/v1/commissioning/clients`
  - `POST /api/v1/commissioning/clients/{clientId}/projects`
  - `POST /api/v1/commissioning/projects/{projectId}/upload-and-regenerate` (File tab “Load File”)

The browser POSTs the `.apex` as multipart field `apex`. The HTTP request **stays open** until extract + generate finish (`asyncio.to_thread(pipeline.regenerate_project, …)`).

### 2. Save the file

- `src/sentinel/server/services/pipeline.py` → `save_upload`
- Disk: `uploads/{projectId}/{uploadId}__{filename}.apex`
- DB: upload row + later “active upload”

### 3. Extract JSON (subprocess)

- Script: `src/sentinel/extraction/extract_project_data.py`
- Core: `src/sentinel/extraction/extractor_core.py` (`extract_project_data`)
- Shape contract: `src/sentinel/contracts/apex_project_structure_v4.json`
- Progress lines on stdout: `SENTINEL_PROGRESS EXTRACTING {percent}`
- Outputs into a staging directory, then promoted to `generated/{projectId}/`

### 4. Generate technician HTML (second subprocess, after extract)

- Script: `src/sentinel/generation/generate_html.py`
- Renderer: `src/sentinel/generation/render_core.py` (~6,400 lines)
- UI rules contract: `src/sentinel/contracts/app_ui_structure.json`
- Hard-key remote layouts (this branch): `src/sentinel/generation/hard_keys/registry.py` + HTML templates under `src/sentinel/ui/testing/hard_keys/` for ProductId **102 (T4x), 110 (ISR-2), 111 (ISR-4)** only
- Writes, per project:
  - `{stem}__project-home.html` — system events, driver events, links to devices
  - one `{stem}__device-{n}-{name}.html` **per device that has pages** (all that device’s pages live in that one file)
  - matching `__payload.json` per device and a `__project-manifest.json`

### 5. Technician opens the link

- Console: Tech Links tab → `POST /api/v1/commissioning/projects/{projectId}/tech-links` → URL `/testing/{token}`
- Serve: `src/sentinel/server/api/testing.py`
  - `GET /testing/{techToken}` → project home HTML
  - `GET /testing/{techToken}/files/{path}` → generated files
  - Device HTML is wrapped in a **shell** (`src/sentinel/ui/commissioning/project_device_static_layout.html`) unless `?runtime=source`

Status coloring of buttons: `src/sentinel/ui/testing/sentinel_test_status_embed.js` (injected into generated HTML).

### 6. Record PASS / FAIL

Technician taps a control → popup of that control’s targets → Pass or Fail (Fail requires a note).

The generated page sends a WebSocket message `test_result.submit` to `/api/v1/testing/{techToken}/ws`. There is also HTTP `POST /api/v1/testing/{techToken}/results` (same validation). Generated UI uses the **WebSocket** path.

Server: `repositories.append_test_result` → table `test_results`. Then an in-process broker publishes `test_result` so the commissioning console updates live.

### 7. Console watches results

- Commissioning tab pies and activity: `commission_tab.js` over WebSocket `/api/v1/commissioning/projects/{projectId}/ws`
- Diagnostics tab fail list and fail-tags (NOT_STARTED / IN_PROGRESS / DONE): `diagnostics_tab.js` + `PUT /api/v1/commissioning/projects/{projectId}/fail-tags`
- Counts: `src/sentinel/server/services/progress.py` + `commissioning_rollups.py` + `commissioning_snapshots.py`

Re-upload of a new `.apex` regenerates JSON/HTML. It does **not** wipe `test_results` unless someone uses Clear Tests (`POST …/clear-tests`).

---

## 4. Current architecture

```
Browser (console or technician)
    → nginx (ops; not in repo)
    → Uvicorn / FastAPI (one process assumed)
         → Postgres  OR  in-memory dicts
         → disk: uploads/ and generated/
         → subprocess: extract_project_data.py
         → subprocess: generate_html.py
         → in-process ProjectEventBroker (thread + queue) for WebSockets
```

| Topic | What the code does |
|---|---|
| Web framework | FastAPI. Routers: `commissioning.py`, `testing.py`, empty `events.py`. Middleware: trace id; optional commissioning API key. |
| Work execution | **Sequential.** One extract process, then one generate process. Devices rendered in a `for` loop. One regenerate **per project** at a time (`_ACTIVE_REGENERATE_PROJECT_IDS`). HTTP handler waits on that work. |
| Parallelism | **Not** a worker pool. WebSocket send/recv are two asyncio tasks per connection. Rollup refresh is a 100 ms `threading.Timer` debounce. No multi-worker broker (history lives in that process’s memory). |
| Queue | **None** as a product. `queue.Queue` is only the in-process WebSocket fan-out (max 100 messages per subscriber; on overflow the oldest is dropped). |
| Browser vs server | Extract/generate/persist are **server**. Technician and console UIs are **static HTML/JS** in the browser. The technician page is generated ahead of time, not a React/SPA app. |
| Live updates | In-process `ProjectEventBroker` (`src/sentinel/server/services/ws_broker.py`): sequence numbers, replay buffer default **500** events. Gap too large → full snapshot resend. |
| Auth | Console: stub user + optional shared API key. Technician: token in the URL. |

---

## 5. Limits visible in the code (observations only)

These are facts in the implementation, not a change list.

**Timeouts and long requests**

- Postgres connect timeout: **5 seconds** (`src/sentinel/server/persistence/db.py`). No query timeout is set in that file.
- WebSocket send timeout: **5 s**; keepalive every **15 s** (`testing.py`, `commissioning_project_ws.py`). Send timeout closes the socket (code 1011).
- Upload-and-regenerate is a **single HTTP request** covering the whole extract+generate. Ops notes tell nginx to use `proxy_read_timeout 3600s` so large files do not 504. The app itself does not set that.
- `PipelineNotImplementedError` exists in `pipeline.py` and is unused.

**Loops and repeated work**

- Extractor walks devices → pages → `SELECT * FROM Layers WHERE PageId = ?` per page → buttons. Shared-layer buttons are cached; other lookups are per page/layer.
- Driver-event resolution issues SQLite queries **per candidate macro** (`count(*)` and step selects in `_resolve_driver_action`).
- `_has_non_empty_macro` queries `MacroSteps` per macro id.
- Almost every Postgres helper in `queries.py` **opens and closes a new connection**. There is no pool.
- Building a fail list can call `get_tech_link_label` **per failed target** (another connection each time) in `commissioning_snapshots.fails_from_latest`.
- After each recorded result, rollups recompute from **all** latest results for the project (debounced 100 ms).
- Technician “Pass All” and the `isPosting` flag send **one result at a time** over the socket.

**Rendering and I/O**

- `render_core.py` is one ~6,400-line module that builds HTML as large Python strings. Each device file embeds CSS, JS, layout JSON, and a JSON map of **all pages** for that device (`page_html_by_index`).
- Extract writes pretty-printed JSON (`json.dump(…, indent=2)`), including progress ticks every 256 KiB during the write.
- Generate also pretty-prints manifest and payload JSON (`indent=2`).
- On testing WebSocket connect, the server sends a snapshot of **all** latest results for the project (not paged).
- Commissioning snapshot “activities” are capped at the **50** most recent results (`activities_from_latest`). Full fail list is not capped in that function.
- Broker replay history capped at **500**. Older events are discarded; clients then get a full snapshot.
- Module-level cache `_RESOLVED_TARGETS_CACHE` in `progress.py` is process-local, keyed by file mtime.

**Other**

- HTTP `POST /results` always returns `"generationRunId": null` even though Postgres may store a `generation_runs` row (reused as “latest run for project,” not one run per regenerate).
- `GET /api/v1/commissioning/projects/{projectId}/tech-links` returns `techUrl: ""` (list is intentionally not a token leak). The URL exists only at create/rotate time.
- `GET …/events` (old SSE) returns **410**.
- Slider / Toggle / LevelIndicator controls have a **temporary** extractor rule: they do not emit graphics (bitmap/icon) targets.
- Hard-key **gestures** (FrameNumber 252) are extracted for T4x/ISR models but **not** drawn on the hard-key strip.

---

## 6. What already works vs what is clearly unfinished

### Already wired and used by the live paths

- Upload `.apex` → extract to contract JSON → generate home + per-device HTML → serve via tech token.
- Technician Pass/Fail/Untested with required fail notes; append-only history; live console update over WebSocket.
- Progress totals from resolved targets vs latest results; system vs driver vs per-device pies.
- Diagnostics fail list, fail-tags, first-time-fail counts.
- Tech link create / rotate / revoke; revoked token → 410.
- Layer visibility locks persisted and broadcast (`layer_lock.set`).
- Optional commissioning API key.
- Postgres migrations `001`–`006` (two files share prefix `002_`; order is filename sort).
- Hard-key split layout for the three ProductIds above (this branch). Other remotes stay screen-only.
- Developer regression suite (`python -m unittest discover -s dev_tests/regression`) and Playwright UI tests under `dev_tests/ui/`.

### Clearly unfinished, stubbed, or half-connected

- **Real commissioning login / multi-operator users.** Stub user “Jamie” only. Comment: “until real authentication is implemented.”
- **Reports tab.** UI copy: “Project-specific reports will appear here.” No report generator.
- **`src/sentinel/server/api/events.py`.** Empty router, still mounted.
- **`generationRunId` on the technician HTTP response.** Always `null`.
- **`runtime=payload` technician mode.** If no manifest, a placeholder page; if a manifest exists, code falls through to normal home HTML. Not a separate runtime.
- **SSE.** Removed (410), WebSocket only.
- **Horizontal scale.** Broker, regenerate locks, and caches are **in-process**. Multiple Uvicorn workers would not share that state (the repo does not configure workers).
- **Dealer / customer portal, billing, notifications, RTI live control.** Not present.
- **Exact collaboration model** for several onsite techs plus remote programmers at once: multiple tech tokens per project **are** supported; what the business wants beyond that is **unknown**.

---

## Short glossary

| Term | Meaning in this codebase |
|---|---|
| `.apex` | RTI project file, opened as SQLite. |
| Project | One Sentinel job: one client’s named project, one generated folder, one (current) `.apex`. |
| Device | One RTI controller/remote in that file (touchscreen, phone UI, etc.). |
| Test target | One PASS/FAIL verification point on a control or event. |
| `targetKey` | Stable string id for that point; joins HTML, WS, and DB. |
| Tech token | Secret in the technician URL; hashed at rest. |
| Commissioning console | Jamie’s (stub) operator UI: file, pies, diagnostics, tech links. |
| Developer test | unittest/Playwright in `dev_tests/`; not a commissioning target. |
