# Titles branch review (`titles`)

**Purpose:** Postmortem and **reimplementation guide**. Keep this file on a branch that is **not** tied to the titles feature code (commit it separately from `src/` title changes) so it survives if the titles branch is reverted again.

**Base:** `main` at `06aca3c`  
**First implementation commits (reference only):**

| Commit | Summary |
|--------|---------|
| `7510eeb` | Commissioning title templates across UI surfaces |
| `c0b72fd` | Readable tech link URLs (path-based routing + migration) |
| `2bc8dd6` | Migration 007 dedupe fix (slug collisions) |

**Later reimplementation on clean base:** `fee09c4` (local; may differ from table above)

**Second reimplementation (perf-safe titles):** `309e239` on `titles` — deployed to droplet 2026-05-28 (`readCommissioningTitles` / `testingApiBaseFromLocation` markers verified on remote).

**Jamie field note (first deploy):** Page header breadcrumb worked. Tech links, test popup / results, project home were weak until regen; device open became **unacceptably slow**.

**Jamie field note (second deploy, `309e239`):** Device open delay **identical** to the two prior title attempts — titles/perf fix treated as **FAIL** for the latency requirement.

---

## What Jamie actually asked for (scope)

Four **display / URL** changes only. Formatting and spacing unchanged.

| # | Area | Desired outcome |
|---|------|-----------------|
| 1 | **Tech links** | Human-readable URLs: `/testing/{client-slug}/{project-slug}/{path-key}` (not 32-char hex). Commissioning list/create shows real URL. Legacy hex tokens still work. |
| 2 | **Test popup** | Title: `{category} - {identity}`. Row line: `Passed by {techLabel}: {timestamp}`. |
| 3 | **Project home** | Two lines: client, then project. `Current File: {basename}` only (no full path). |
| 4 | **Page titles** | Breadcrumb: `{client} -> {project} -> {device} -> {page}`. |

**Not in scope:** slower device open, serve-time full-file reads, WS replay floods, commissioning progress events on technician pages.

**Added constraint (approved before second reimplementation):** The four title changes **must not** increase:

1. **Device open** — Project Home device click → device framework ready (`__sentinelRuntimeReady` / shell overlay hidden).
2. **Snapshot apply** — runtime ready → `testing_snapshot` applied in device JS (`__sentinelPerfMarks.testingSnapshotApplied`).

Jamie said benchmark tests could follow later; the agent still must not ship without understanding what is being gated. **A server-only serve test is not sufficient for (1) or (2).**

---

## Summary by area (first field test)

| Area | Coded? | Unit tests | Live (Holtby) | Main blocker |
|------|--------|------------|---------------|--------------|
| Page header breadcrumb | Yes | Yes | **Yes** | None |
| Tech links (readable URL) | Yes | Yes | **Partial** | Stale generated device HTML; WS path wrong until regen |
| Test popup (title + row status) | Yes | Yes (generated HTML) | **No** until WS works | WS + replay; row status needs snapshot |
| Project home (client, project, file) | Yes | Yes | **Not verified** | Serve-time meta + regen |
| **Device open speed** | Regressed | — | **Broken UX** | Serve-time `read_text` + DB on `?runtime=source` |

---

## Why it felt so slow (simple)

Two problems **not required** for title text:

### A. Opening ISR-4 (15+ seconds)

**`main`:** Shell fetches device HTML with `FileResponse` — stream from disk, no DB.

**Titles branch:** Every `?runtime=source` request:

1. `read_text()` entire device HTML (multi‑MB on Holtby)
2. Postgres: project, client, `list_active_tech_links`
3. Patch `<head>` meta
4. Return body

Done so client/project/tech names could update **without regenerating**. Valid goal; **wrong mechanism** for large files.

### B. Sluggish pass/fail after open

Technician WS sends `sync.request` with `lastAppliedSeq: 0`. Broker replays up to **500** events. After regenerations, buffer is mostly **`generation_phase`** (one per progress line). Device JS processes/logs each on the main thread. Technicians never need those events.

### C. Shell boot still parses the full device HTML (unchanged on `main` and after `309e239`)

Device open from Project Home is **not** “open one HTML file.” It is:

1. Load **shell** (`runtime=shell`) — `project_device_static_layout.html` (small) + DB title inject on shell/home routes.
2. Shell `fetch(sourceUrl)` where `sourceUrl` is `…/files/{device}.html?runtime=source`.
3. Browser: `res.text()` → **`DOMParser.parseFromString(html)`** → mount DOM slices → **`runScripts(sourceDoc)`**.

File: `src/sentinel/ui/commissioning/project_device_static_layout.html` (lines ~721–734).

**New understanding:** Restoring server `FileResponse` for `?runtime=source` only removes the **titles v1 server regression** (`read_text` + DB + rewrite per request). It does **not** remove download size, string allocation, parse, or script execution on the **client**. On Holtby-scale multi‑MB device HTML, that main-thread work may dominate `deviceOpenMs` and can feel **identical** across deploys if the server was never the only bottleneck.

**Implication:** Passing `test_testing_source_serve_latency` does **not** prove Jamie’s device-open requirement. Proving (1) requires Playwright (or manual) measurement through the **shell** path on a **large** fixture or Holtby after regen.

---

## Mistakes to avoid (mandatory for reimplementation)

### 1. Do not rewrite the whole device HTML on every open

| Do | Don't |
|----|--------|
| Keep `FileResponse` for `GET .../files/{device}.html?runtime=source` | `read_text()` + mutate full HTML per request |
| Bake `sentinel-client-name` / `sentinel-project-name` / `sentinel-tech-label` at **generation**, or inject **only** `<meta>` via a tiny prefix (bytes in front of `</head>`) with one DB query cached per session | Load megabytes of HTML to change three meta tags |

**Blast radius:** Every technician device open on every large project.

### 2. Do not put commissioning-only events in technician WS replay

| Do | Don't |
|----|--------|
| `publish_transient` for `generation_phase` (live to commissioning only), **or** filter replay server-side for technician sessions | `broker.publish` every `SENTINEL_PROGRESS` line into replay history |
| Early-return `generation_phase` / `generation` in device `_applyTechPayload` | Replay hundreds of events on `sync.request` at seq 0 |

**Symptom:** Console filled with `[tech-ws] recv generation_phase`; UI jank after snapshot.

### 3. Do not conflate “titles” with “architecture changes”

| Required for scope | Optional / separate PR |
|--------------------|----------------------|
| `app_ui_structure.json` templates | Serve-time full HTML pipeline |
| `render_core.py` template strings + `testingApiBaseFromLocation()` | Debounced rollup changes |
| Migration `007` + path routes + `tech_link_paths.py` | `deploy_from_head.ps1` push behavior |
| `commissioning.js` show API `techUrl` | Editing root `agents.md` |

### 4. Deploy ships `src/` only — plan regen explicitly

| Do | Don't |
|----|--------|
| After deploy: **regenerate project** on droplet (updates embedded `testingApiBaseFromLocation` in device HTML) | Assume readable URL in browser bar fixes in-page WS |
| Document regen in deploy checklist for this feature | Deploy and test only commissioning console |

### 5. Migration `007` must dedupe before unique indexes

First deploy crashed on duplicate `path_key` (e.g. two `jamie` links). Hotfix `2bc8dd6`: allocate `jamie-2`, `jamie-3` on collision.

### 6. Test the two user-visible latencies — and run the right test

| Metric | Start | End |
|--------|--------|-----|
| `deviceOpenMs` | Click device row on project home | `__sentinelRuntimeReady` + shell overlay hidden |
| `snapshotAfterReadyMs` | Runtime ready | `__sentinelPerfMarks.testingSnapshotApplied` |

**Tests (repo):**

| Test | Measures | Gates Jamie (1)? | Gates Jamie (2)? | Large / Holtby? | In `run_regression_with_venv.py`? |
|------|----------|------------------|------------------|-----------------|-----------------------------------|
| `dev_tests/ui/test_device_open_latency.py` | Playwright full stack + `wsGenerationPhaseCount` | **Yes** | **Yes** | **No** — tiny generated fixture | **No** — must run explicitly |
| `dev_tests/regression/test_testing_source_serve_latency.py` | TestClient `?runtime=source` serve ms only | **No** | **No** | ~1 MiB padding only | **Yes** (regression discover) |
| `devtools/playwright_measure_device_open.py` | Same metrics vs live `--base-url` | **Yes** | **Yes** | Yes if aimed at droplet/Holtby | Manual only |

**Do not** ship title changes without **`test_device_open_latency` (or Holtby manual probe) passing** on a **large** fixture or post-regen Holtby smoke. A green `test_testing_source_serve_latency` alone is **not** approval for deploy.

**Do not** treat loose ceilings as proof: `test_device_open_latency` allows up to **12 s** device open / **4 s** snapshot on a **small** fixture — Holtby can still fail in the field while CI passes.

### 7. Agent / process mistakes (second pass — cherry-pick)

- Restored entire `origin/titles` bundle without splitting **must-have** vs **caused regression**.
- Added perf marks/tests (OK for measurement) but did not land **FileResponse revert** or **replay fix** before deploy.
- Deploy succeeded while health check timed out once — service was up; still shipped slow path.
- Stashed local `agents.md` edits — unrelated to titles; do not mix into title commits.

### 8. Agent / process mistakes (third pass — `309e239` deploy)

- **Mis-stated Intent Check:** Reported Pass based on `test_testing_source_serve_latency` (~27 ms on 1 MiB serve). That does **not** validate shell `DOMParser` + `runScripts` on Holtby-sized HTML or snapshot-after-ready.
- **Did not run** `python -m unittest dev_tests.ui.test_device_open_latency -v` before deploy (checklist Phase 6 item 2 was skipped).
- **Did not wire** `test_device_open_latency` into `devtools/run_regression_with_venv.py` (runner only runs `dev_tests/regression/*` + `test_synthetic_list_scroll_runtime`).
- **Deploy markers** proved strings in `render_core.py` (`readCommissioningTitles`, `testingApiBaseFromLocation`), not that `testing.py` still uses `FileResponse` for `?runtime=source` (grep remote `FileResponse` + `SOURCE_RUNTIME_MODE` would be stronger).
- **Assumed** FileResponse fix = Jamie-fast; field result was **identical** delay → bottleneck likely shell client path, WS replay, and/or missing Holtby regen — not proven before next change.
- **Regen** after deploy was documented but not confirmed; stale generated device HTML leaves old JS (no `generation_phase` ignore, old WS base URL).

### 9. What `309e239` actually changed (for latency)

| Change | Intended effect | Proves fast device open in field? |
|--------|-----------------|-----------------------------------|
| `FileResponse` for `?runtime=source` in `testing.py` | Revert titles v1 server read+DB on source fetch | **Partial** — network/stream only |
| Meta baked at regen (`--client-name` / `--project-name` on `generate_html.py`) | Avoid serve-time full-file mutation for names | No — does not shrink device HTML |
| `publish_transient` for `generation_phase` | Stop **new** phases entering replay buffer | Partial — old buffer events may still replay |
| Ignore `generation_phase` / `generation` in device `_applyTechPayload` | Skip handling on technician WS | Only in **regenerated** device HTML |
| Shell/home still `_apply_commissioning_titles_to_html` | DB: project, client, `list_active_tech_links` for tech label | Small HTML only; not the multi‑MB source step |

---

## Area notes (what worked / what didn’t)

### 1. Page header — `client -> project -> device -> page`

- **Contract:** `header.titleTemplate` in `app_ui_structure.json`
- **Generator:** `format_page_header_title()`, `syncHeader()`, `readCommissioningTitles()`
- **Serve:** `_inject_commissioning_meta()` on testing HTML routes
- **Live:** Worked (Jamie confirmed). Breadcrumb can use serve-time meta if template exists in HTML.

### 2. Tech links — `/testing/{client}/{project}/{path_key}`

- **Needs:** `007_tech_link_public_paths.sql`, `slugs.py`, `tech_link_paths.py`, `testing_access.py`, path + legacy routes in `testing.py`, real `techUrl` from `commissioning.py`, `testingApiBaseFromLocation()` in **generated** device JS
- **Failed live until regen:** Old device HTML used first path segment only → WS `/api/v1/testing/blue-ember/ws` → 404 loop
- **Fix:** Regenerate project after deploy

### 3. Test popup — title + row status

- **Templates:** `testingPopup.titleTemplate` → `{category} - {identity}`
- **Row:** `formatRowStatusLine()` + `recordedByTechLabel` from WS snapshot
- **Blocked when:** WS broken or replay flood stalls main thread

### 4. Project home — client, project, basename

- **Markup:** `homeClientName`, `homeProjectName`, `Current File: {basename}`
- **Serve-time meta** for names if HTML generated without client/project args
- **Not fully verified live** on first pass

---

## Cross-cutting: serve-time HTML (`testing.py`)

**Before (`main`):** `?runtime=source` → `FileResponse`.

**After (titles):** `read_text()` + `_apply_commissioning_titles_to_html()` (DB) on every source request.

**Impact:** Shell boot = shell HTML + slow source fetch + `DOMParser` + `runScripts()`. “Preparing device layout…” stays until source step finishes.

**Correct approach for reimplementation:**

1. `FileResponse` for source device files.
2. Client/project/tech names in meta at **generation** (pass client/project into `render_project_home_html` / `render_single_device_html` from commissioning DB at regen time), **or** minimal meta injection without reading full file.
3. Breadcrumb still works if template + meta exist.

---

## Files touched (reference)

| Concern | Primary files |
|---------|----------------|
| Page header / popup / home generation | `render_core.py`, `app_ui_structure.json` |
| Serve-time titles (avoid or minimize) | `testing.py` |
| Tech links | `commissioning.py`, `testing.py`, `testing_access.py`, `tech_link_paths.py`, `slugs.py`, `queries.py`, `repositories.py`, `007_*.sql`, `commissioning.js` |
| Tests | `test_commissioning_titles.py`, `test_tech_link_public_paths.py`, `test_device_open_latency.py`, `test_testing_source_serve_latency.py` |
| Contract doc | `docs/api_contract_v1.md` |

---

## Reimplementation checklist (after revert)

Use this order. **Stop** if a step fails its test.

### Phase 0 — Prep

1. Branch from `main` (or clean base). **Commit this doc first** on `docs/` only.
2. Read `docs/api_contract_v1.md` for path-based tech URL shapes.

### Phase 1 — Tests first

1. Add `test_commissioning_titles.py` (templates, home, breadcrumb wording).
2. Add `test_tech_link_public_paths.py` (slugs, routes, legacy token).
3. Add `test_device_open_latency.py` + `test_testing_source_serve_latency.py`.
4. Run regression — expect failures until implementation exists.

### Phase 2 — Tech links (server)

1. `007_tech_link_public_paths.sql` with **dedupe before unique indexes**.
2. `slugs.py`, `tech_link_paths.py`, `testing_access.py`.
3. `queries.py` / `repositories.py` — path_key, resolve by path, list returns real `techUrl`.
4. `testing.py` — path routes; **keep** `FileResponse` for `?runtime=source`.
5. `commissioning.py` + `commissioning.js` — real URLs only.

### Phase 3 — Titles (generation + contract)

1. `app_ui_structure.json` — breadcrumb + popup templates.
2. `render_core.py` — templates, `testingApiBaseFromLocation()`, home two-line header, `formatRowStatusLine`, `_sentinelPerfMark` for tests.
3. **Do not** add serve-time full-file read unless meta cannot be baked at generation.

### Phase 4 — Minimal serve-time (only if needed)

1. If breadcrumb must update when client/project renamed without regen: inject **meta tags only** (small string splice before `</head>` or `StreamingResponse` with prefix).
2. Single DB read per session/request; **never** `list_active_tech_links` on every source fetch unless required.

### Phase 5 — WS hygiene

1. `generation_phase` → `publish_transient` in `commissioning.py`.
2. Device JS: ignore `generation_phase` / `generation` in `_applyTechPayload`.

### Phase 6 — Verify and deploy

1. `python devtools/run_regression_with_venv.py` — all green (regression only; **not** sufficient alone).
2. **`python -m unittest dev_tests.ui.test_device_open_latency -v`** — **mandatory** before deploy; fails gate if skipped.
3. Optional but recommended for Holtby: `python devtools/playwright_measure_device_open.py --base-url … --tech-path …` after droplet regen; record `deviceOpenMs` / `snapshotAfterReadyMs`.
4. Commit `src/` + `dev_tests/` + `docs/api_contract_v1.md`.
5. Deploy `src/` only → verify remote `testing.py` serves source with `FileResponse` (not only `render_core` markers) → **regenerate Holtby** → field test four title areas **and** both latency metrics vs pre-titles baseline.

---

## Suggested fixes (try before full reimplementation)

If the titles branch is still deployed:

1. **Regenerate Holtby** — fixes WS URL in generated JS (required once per deploy).
2. **Revert `?runtime=source` to `FileResponse`** — restore device open speed; keep meta via generation or tiny injection.
3. **Stop replaying `generation_phase` to technicians** — restore UI responsiveness after open.

If (2)+(3) are approved, implement with `test_device_open_latency` and `test_testing_source_serve_latency` as gates.

---

## Intent check (Jamie-reported)

| Original ask | First live result (`7510eeb`…) | Second deploy (`309e239`) |
|--------------|-------------------------------|---------------------------|
| Readable tech link | URL OK in console; in-device WS broken until regen | Not re-verified in thread |
| Popup title + passed-by | Row status empty when WS/replay broken | Not re-verified in thread |
| Project home lines + basename | Not verified | Not re-verified in thread |
| Page breadcrumb | **Works** | Not re-verified in thread |
| Fast device open | **Regressed** (serve-time read + replay) | **Still FAIL** — delay **identical** to prior attempts |
| Snapshot after ready not slower | (part of open jank) | **FAIL** — treated same as open; not isolated in field |

**Agent Intent Check on `309e239` (incorrect at ship time):** Pass — **wrong**. Serve-only test passed; Jamie’s two metrics were not measured end-to-end on Holtby before deploy.

---

## Diagnosing the next bottleneck (evidence before more code)

Split timings on Holtby (DevTools Performance or instrumented marks in shell + device JS):

| Phase | What to measure |
|-------|-----------------|
| T1 | Shell HTML load (`runtime=shell`) |
| T2 | `fetch(?runtime=source)` — network (should be fast with `FileResponse`) |
| T3 | `DOMParser` + `runScripts` — main thread |
| T4 | WS `sync.request` replay count + time until `testingSnapshotApplied` |

If T3 dominates, fixing server `read_text` again will not help; need a different architecture (e.g. smaller payload, incremental mount, or avoid shell double-load). If T4 dominates, focus on replay filter at connect + regen + buffer hygiene.

---

## Document status

- **Guide for reimplementation** — yes
- **Locked project policy** — no; update after Jamie confirms
- **Survives titles branch revert** — yes, if committed on `main` or `docs-only` commit separate from feature code

*Last updated: 2026-05-28 — third-pass postmortem (`309e239` deploy FAIL on latency), shell/DOMParser understanding, test-gate honesty table, checklist hardening.*
