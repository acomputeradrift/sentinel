# Generation Algorithm Refinement

## Status
- Working discovery document for generation/startup/zoom performance.
- Entries are investigation notes and may be refined as new evidence is collected.

## Problem Statement
- Apex projects with large data sets are slow to start.
- Zoom `+` and `-` interactions are slow during runtime.

## Current Theories
1. Runtime zoom path is scaling too many DOM nodes per interaction.
   - In generated runtime JS, `applyRtiLayout()` iterates over all `.device-page .vp-box` and all `.device-page .btn-wrap` on each layout pass.
   - `updateZoom()` schedules `applyRtiLayout()` for every zoom step, so each click reflows/rescales all page elements, not just active/visible ones.

2. Generation path repeats expensive page payload work.
   - `generate_html.py` calls both `render_single_device_html(...)` and `build_device_payload(...)` for each device.
   - Both functions call `_page_payload(...)` for every page, duplicating button/viewport iteration and serialization work.

3. Initial load cost grows with total pages because full page DOM is emitted up front.
   - `render_single_device_html(...)` builds markup for all pages and toggles active page visibility at runtime.
   - Large projects therefore pay high parse/layout/memory cost before first interaction.

4. Existing tests are strict about runtime contract and generated JS text.
   - Integration tests assert specific emitted JS fragments.
   - Playwright runtime tests heavily validate viewport popup and zoom behavior.
   - Any optimization must preserve user-visible behavior and existing contract guarantees.

## Primary Suspect Files
- `src/sentinel/generation/render_core.py`
- `src/sentinel/generation/generate_html.py`
- `src/sentinel/server/services/pipeline.py`

## Investigation Notes
- `pipeline.py` already records extract/generate timing fields (`extractSec`, `generateSec`, `totalSec`) in regenerate result payload.
- The dominant current risk appears to be in generated runtime JS layout loops and duplicated payload generation logic.
- Confirmed behavior: device HTML is pre-generated at regeneration time, but large-project delay when selecting a device from Project Home is still high because browser parse/execute/layout cost is paid on device-page load.
- Server path for device selection is not regenerating the page on click; testing file route serves generated artifact directly, so click-delay bottleneck is client-side render workload.

## Probe Definition
- Probe name: `generation_algo_refinement_probe.py`
- Scope:
  - Benchmark `preload` on the real commissioning UI path using server timing from the same upload/regenerate run (`generation.timings.generateSec`).
  - Benchmark `redraw on project-menu selection` on the real testing route (`/testing/{techToken}`) from device-row click until usable render.
- UI timing markers:
  - Preload (`preload_sec`): server `generation.timings.generateSec` from same run.
  - Display (`display_sec`): device-row click -> `#rtiCanvas` exists and active-page `.btn-wrap` exists.
  - Supporting paint markers: first paint / first contentful paint (navigation-relative).
- Output:
  - Per-file run list with:
    - `preload_sec`
    - `display_sec`
  - Summary with `p50`, `p95`, and mean for both metrics.
  - Extraction remains outside this probe and is sourced from extraction probe and server `REGEN_BASELINE extractSec`.

## Evidence Log Template
Use this section for each benchmark/experiment.

### Entry Template
- Date:
- Scenario:
- Input project:
- Environment:
- Command/Test run:
- Observed before:
- Observed after:
- Delta:
- Interpretation:
- Next minimal step:

## Open Questions
1. Can active-page-only layout updates reduce zoom latency without breaking viewport popup behavior?
2. Can `_page_payload(...)` outputs be reused between HTML and payload generation for the same device/page?
3. Should large-page rendering be partially deferred (while preserving current behavior contracts)?

## Baseline Results (Real UI Flow)
- Date: 2026-04-06
- Method: `generation_algo_refinement_probe.py` using real commissioning/testing routes.
- Historical note: this baseline used legacy field names (`preload_generation_sec`, `click_to_usable_render_sec`) and legacy preload semantics.
- Metrics:
  - `preload_generation_sec`: `Load File` click -> `Uploaded:` visible in manage panel.
  - `click_to_usable_render_sec`: device row click on Project Home -> usable device UI (`#rtiCanvas` + active page button wrappers present).

### File Baseline (Runs=1)
- `TEST - System Manager v11.3.apex`
  - `preload_generation_sec`: `5.868`
  - `click_to_usable_render_sec`: `1.310`
- `Carlos OBryans v6.3.1 (tag cleanup).apex`
  - `preload_generation_sec`: `3.122`
  - `click_to_usable_render_sec`: `0.804`
- `Dash OS v55.2 iPhone.apex`
  - `preload_generation_sec`: `10.017`
  - `click_to_usable_render_sec`: `1.317`
- `Verrier Home FEENY EDIT v49.apex`
  - `preload_generation_sec`: `63.977`
  - `click_to_usable_render_sec`: `3.367`
- `Sung Residence v207.2.apex`
  - `preload_generation_sec`: `80.670`
  - `click_to_usable_render_sec`: `3.299`

### Probe Artifacts
- `output/generation_algo_refinement_probe_realflow_verify.json`
- `output/generation_algo_refinement_probe_sung_run1.json`
- `output/generation_algo_refinement_probe_baseline_rest.json`

## Post-Phase-2 Baseline (Real UI Flow, Lazy Materialization)
- Date: 2026-04-07
- Method: `generation_algo_refinement_probe.py` using real commissioning/testing routes.
- Notes:
  - Main pass used `runs=3`, `headless`, `timeout-ms=240000` across all `assets/*.apex`.
  - `Sung Residence v207.2.apex` required a dedicated rerun with `timeout-ms=600000`.

### Consolidated Summary (p50 / p95)
- `Carlos OBryans v6.3.1 (tag cleanup).apex`
  - `preload_generation_sec`: `3.591 / 4.250`
  - `click_to_usable_render_sec`: `1.001 / 3.216`
- `Dash OS v55.2 iPhone.apex`
  - `preload_generation_sec`: `17.697 / 18.794`
  - `click_to_usable_render_sec`: `1.207 / 1.911`
- `TEST - System Manager v11.3.apex`
  - `preload_generation_sec`: `10.199 / 12.378`
  - `click_to_usable_render_sec`: `2.042 / 4.430`
- `Verrier Home FEENY EDIT v49.apex`
  - `preload_generation_sec`: `47.420 / 68.006`
  - `click_to_usable_render_sec`: `1.590 / 2.089`
- `Sung Residence v207.2.apex` (extended-timeout pass)
  - `preload_generation_sec`: `125.952 / 144.221`
  - `click_to_usable_render_sec`: `2.898 / 4.578`

### Post-Phase-2 Probe Artifacts
- `output/generation_algo_refinement_probe_post_phase2_run1.json`
- `output/generation_algo_refinement_probe_post_phase2_run3.json`
- `output/generation_algo_refinement_probe_post_phase2_sung_run3_timeout600.json`

## Server Baseline Capture (Preload + Ready)
- Date: 2026-04-07
- Project: `e0861032-ce48-4754-945a-822d6070ef73` (`Sung Residence v207.2.apex`)
- Source: Sentinel server logs (`REGEN_BASELINE` + `READY_BASELINE`)

### Captured Values
- `Preload`:
  - `preloadSec=6.401` at `2026-04-07 19:14:20`
  - Same run context: `extractSec=75.167`, `totalSec=81.589`
- `Ready`:
  - `readySec=3.627` at `2026-04-07 19:15:08`
  - `readySec=3.703` at `2026-04-07 19:15:27`
