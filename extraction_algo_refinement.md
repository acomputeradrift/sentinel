# extraction_algo_refinement.md

## Purpose
Create a focused working document for improving large-file Apex extraction performance while preserving output correctness and producing reliable user-visible progress updates.

## Session Scope and Constraints
- Investigation has been run in review-first mode with explicit approvals before edits.
- Findings here are derived from the files reviewed in this thread:
  - `AGENTS.md`
  - `bootstrap.md`
  - `codebase_map.md`
  - `docs/temp_fix_attempts.md`
  - `src/sentinel/extraction/extractor_core.py`
  - `src/sentinel/extraction/extract_project_data.py`
  - `src/sentinel/server/services/pipeline.py`
- Goal: isolate and fix large-file extraction slowdown/timeouts without relying on repeated unbounded probes.

## Problem Statement
- Small Apex files extract successfully.
- Large Apex files show severe slowdown and may time out or appear stalled.
- Prior validation attempts sometimes used unbounded long-running probes, which delayed diagnosis.

## Confirmed/Documented Observations (From This Thread)
- Bottlenecks are concentrated in extraction core hot paths rather than the CLI wrapper.
- The per-button path performs repeated macro-step lookups from `MacroStepsView`.
- Button rows are repeatedly fetched from `RTIDeviceButtonData` by `SharedLayerId` in both page and viewport paths.
- Viewport processing multiplies heavy work because child frame buttons re-enter the same expensive button-resolution path.
- Pipeline orchestration does not enforce an internal subprocess timeout in `_run_subprocess_with_progress`; long runs depend on external bounding.
- Disabling per-button `MacroStepsView` ID resolution in the button hot path produced a major extraction speedup and query-count reduction on Dash.

## Relevant Files for Refinement Work
1. `src/sentinel/extraction/extractor_core.py`
   - Main extraction loops and per-button/per-viewport resolution.
2. `src/sentinel/extraction/extract_project_data.py`
   - Extraction entrypoint, progress output formatting, validation/write stages.
3. `src/sentinel/server/services/pipeline.py`
   - Subprocess orchestration, progress stream handling, single-flight guard behavior.

## Baseline Metrics (Top 6)
These are the six metrics approved for baseline tracking and improvement decisions.

1. Total Extraction Time
- Definition: wall-clock seconds from extraction start to extraction completion/failure.
- Why it matters: primary user-visible efficiency metric.
- Baseline capture: median and P95 over repeated bounded runs on representative large input(s).
- Improvement target: reduce median and P95 while preserving output integrity.

2. Throughput (Work Processed per Second)
- Definition: effective processing rate (for example, buttons/layers processed per second) during extraction work stage.
- Why it matters: distinguishes true algorithmic efficiency gains from superficial progress behavior.
- Baseline capture: average throughput and low-watermark segments by stage/device/viewport-heavy sections.
- Improvement target: raise sustained throughput and reduce severe throughput dips.

3. Total SQL Query Count
- Definition: total number of SQL statements executed during extraction.
- Why it matters: direct indicator of repeated work and query amplification in hot loops.
- Baseline capture: total count per run.
- Improvement target: reduce total query count without changing output correctness.

4. Distinct SQL Query Shapes
- Definition: number of distinct normalized SQL statement shapes executed during extraction.
- Why it matters: shows breadth/fragmentation of query workload and helps detect query-pattern churn.
- Baseline capture: distinct normalized query shape count per run.
- Improvement target: reduce avoidable shape fragmentation where possible.

5. SQL Latency Profile for Top Repeated Queries
- Definition: mean/P95/max latency for top repeated normalized query shapes.
- Why it matters: separates “many cheap queries” from “few expensive queries” and highlights tail-latency hotspots.
- Baseline capture: top repeated query shapes with count, totalMs, avgMs, p95Ms, maxMs.
- Improvement target: reduce avg/P95/max on hotspot shapes and lower total time spent in those shapes.

6. Unique testTarget Count per Device (Scope-Aware)
- Definition: count of unique testTargets per device after scope-aware dedupe, not raw page/layer occurrences.
- Rule: a Global target repeated across many pages/layers is still one unique target for that device.
- Why it matters: validates that optimization and status marking logic are measuring true target workload.
- Current state: existing progress derivation already computes per-device deduped expected target sets.

## Baseline Run Results
### Filename: `Assets/TEST - System Manager v11.3.apex`
- Apex size bytes: `2867200`
- Probe: `temp/extraction_algo_refinement_probe.py`

1. Total Extraction Time
- `1.699s`

2. Throughput (Work Processed per Second)
- Work units processed: `1275`
- Work units/sec: `750.429`

3. Total SQL Query Count
- `682`

4. Distinct SQL Query Shapes
- `41`

5. SQL Latency Profile for Top Repeated Queries
- `select MacroStepId from MacroStepsView where MacroId in (?) ...`
  - count: `286`, totalMs: `726.596`, avgMs: `2.541`, p95Ms: `3.542`, maxMs: `50.203`
- `select * from RTIDeviceButtonData where SharedLayerId = ? ...`
  - count: `262`, totalMs: `299.076`, avgMs: `1.142`, p95Ms: `1.216`, maxMs: `98.368`

6. Unique testTarget Count per Device (Scope-Aware)
- Device `6` (`RTiPanel (iPhone X or newer)`): `1493`
- Device `2` (`XP-3`): `0`
- Device `37` (`T2i (Global)`): `34`

### Filename: `Assets/Carlos OBryans v6.3.1 (tag cleanup).apex`
- Apex size bytes: `7585792`
- Probe: `temp/extraction_algo_refinement_probe.py`

1. Total Extraction Time
- `0.768s`

2. Throughput (Work Processed per Second)
- Work units processed: `430`
- Work units/sec: `559.968`

3. Total SQL Query Count
- `305`

4. Distinct SQL Query Shapes
- `41`

5. SQL Latency Profile for Top Repeated Queries
- `select MacroStepId from MacroStepsView where MacroId in (?,?,?) ...`
  - count: `117`, totalMs: `276.873`, avgMs: `2.366`, p95Ms: `6.363`, maxMs: `13.169`
- `select * from RTIDeviceButtonData where SharedLayerId = ? ...`
  - count: `56`, totalMs: `93.549`, avgMs: `1.671`, p95Ms: `5.287`, maxMs: `6.394`

6. Unique testTarget Count per Device (Scope-Aware)
- Device `12` (`IST-5 (Global)`): `493`
- Device `2` (`XP-6s`): `0`

### Filename: `Assets/Dash OS v55.2 iPhone.apex` (Before/After per-button macroStepId lookup removal)
- Apex size bytes: `62275584`
- Probe: `temp/extraction_algo_refinement_probe.py`

1. Total Extraction Time
- Before: `2.652s`
- After: `0.339s`

2. Throughput (Work Processed per Second)
- Before: `2165` work units, `816.276` units/sec
- After: `2165` work units, `6378.564` units/sec

3. Total SQL Query Count
- Before: `1253`
- After: `652`

4. Distinct SQL Query Shapes
- Before: `40`
- After: `38`

5. SQL Latency Profile for Top Repeated Queries
- Before top hot query:
  - `select MacroStepId from MacroStepsView where MacroId in (?) ...`
  - count: `573`, totalMs: `1712.855`, avgMs: `2.989`, p95Ms: `3.83`, maxMs: `55.649`
- After:
  - this per-button `MacroStepsView ... in (?)` query no longer appears in top repeated queries.

6. Unique testTarget Count per Device (Scope-Aware)
- Before:
  - Device `5` (`RTiPanel (iPhone X or newer)`): `453`
  - Device `2` (`XP-8s`): `0`
  - Device `7` (`KA11`): `313`
  - Device `41` (`T4x`): `6`
- After:
  - Device `5` (`RTiPanel (iPhone X or newer)`): `309`
  - Device `2` (`XP-8s`): `0`
  - Device `7` (`KA11`): `219`
  - Device `41` (`T4x`): `3`

### Filename: `Assets/Verrier Home FEENY EDIT v49.apex`
- Apex size bytes: `36159488`
- Probe: `temp/extraction_algo_refinement_probe.py`

1. Total Extraction Time
- `8.823s`

2. Throughput (Work Processed per Second)
- Work units processed: `16325`
- Work units/sec: `1850.339`

3. Total SQL Query Count
- `5236`

4. Distinct SQL Query Shapes
- `44`

5. SQL Latency Profile for Top Repeated Queries
- `select * from RTIDeviceButtonData where SharedLayerId = ? ...`
  - count: `3999`, totalMs: `1765.837`, avgMs: `0.442`, p95Ms: `0.527`, maxMs: `91.985`
- `select count(*) from MacroStepsView where MacroId = ?`
  - count: `61`, totalMs: `1738.824`, avgMs: `28.505`, p95Ms: `68.763`, maxMs: `125.154`
- `select CommandTagId from MacroStepsView where MacroId = ? and Type = 14 ...`
  - count: `61`, totalMs: `1554.36`, avgMs: `25.481`, p95Ms: `49.495`, maxMs: `72.085`

6. Unique testTarget Count per Device (Scope-Aware)
- Device `81` (`iPhone (Sean)`): `3747`
- Device `197` (`RK3-V (Bedroom2)`): `107`
- Device `196` (`RK3-V (Bedroom1)`): `110`
- Device `2` (`XP-8v`): `0`
- Device `82` (`iPad (#1)`): `5592`

## Improvement Targets and Guardrails
- Any optimization must preserve extracted output contract conformance.
- No fake progress behavior: progress must reflect real extraction work.
- Verification runs must be bounded; avoid unbounded blocking probes.
- Status and diagnostics must be actionable enough to identify where time is being spent.
- `macroStep` / `macroSteps` must remain valid test targets in output behavior.
- PageLink resolution must remain correct, including links resolved via macro-step-driven flows.

## Progress Emitter Efficiency Requirement (Status Bar)
The updated extraction algorithm must include highly efficient progress emitters for the commissioning status bar with these requirements:
- Emit progress from real extraction work events, not synthetic/fake movement.
- Keep emitter overhead minimal so reporting does not become a measurable bottleneck.
- Provide smooth, frequent, user-visible updates during long work spans.
- Preserve monotonic percent behavior and stage-aware mapping.
- Ensure progress cadence remains informative in large-file scenarios, especially during heavy loop sections.

## Contract Boundary Decision (Agreed)
- `apex_project_structure` remains Apex-faithful only.
- It should contain:
  1. organizational headers
  2. fields that map directly to extracted Apex data points
- It must not include Sentinel-derived caches/precomputed target indexes.

## Contract Delta: Apex-Faithful Scope Inputs
To make scope resolution efficient without introducing Sentinel-derived data in the Apex contract, extracted button records should consistently include these raw fields (null when not present, never omitted):
- `rtiAddress`
- `pageId`
- `pageRoomId`
- `pageSourceDeviceId`
- `layerId`
- `sharedLayerId`
- `layerRoomId`
- `layerSourceId`
- `hostViewportButtonId`
- `frameNumber`
- `buttonId`
- `buttonTagId`
- `macroIds[]`
- `macroStepIds[]`
- `variableIds[]`
- `pageLinkId`
- `targetPageId`

## Derived Data Placement (Agreed)
- Scope/target precompute artifacts belong in Sentinel-owned data, separate from Apex-derived contract payloads.
- Generation/progress should use this Sentinel-owned artifact as primary when present, with back-compat fallback behavior for older outputs.

## Current-State Efficiency Note
- Current per-device unique target counting is correctness-oriented but recomputes from full `project_data` during progress derivation.
- A precomputed Sentinel-owned scoped-target artifact is the preferred optimization path to reduce repeated matching/derivation cost.
- Current extraction optimization trial removed per-button `macroStepIds` list lookup and improved runtime significantly, but this also reduced emitted macro-step target counts and must be corrected.

## MacroStep Handling Decision (Agreed)
- We should preserve `macroStep`/`macroSteps` test target signaling.
- We should avoid per-button macro-step ID resolution queries in the hot path.
- The accepted approach is to determine macro-step cardinality (none / one / many) from already preloaded macro metadata (for example, precomputed per-macro step counts) rather than fetching per-button `MacroStepId` lists.
- `macroStepIds` detailed lists are not required for the optimization phase if target semantics and pageLink behavior remain correct.

## Initial Refinement Direction (From Current Evidence)
- Prioritize elimination of repeated hot-path work before adding complexity elsewhere:
  - Cache macro-step ID resolution for repeated macro-id sets.
  - Cache `RTIDeviceButtonData` by `SharedLayerId` and reuse across page/viewport traversals.
- Add bounded, focused instrumentation tied to the six baseline metrics.
- Keep pipeline verification bounded and fail-fast for overlong runs with diagnostic context.
- Near-term correction after recent optimization:
  - Restore `macroStep`/`macroSteps` target signaling without reintroducing per-button macro-step ID lookup.
  - Verify macro-step-driven pageLink resolution behavior remains unchanged.

## Working Decisions Captured in This Thread
- Focus on performance diagnosis using proven evidence from code and prior attempt logs.
- Use exactly six baseline metrics:
  1. total extraction time
  2. throughput
  3. total SQL query count
  4. distinct SQL query shapes
  5. SQL latency profile for top repeated query shapes
  6. unique testTarget count per device (scope-aware dedupe)
- Include progress-emitter efficiency as an explicit design requirement in algorithm updates.
- Keep `apex_project_structure` Apex-faithful and store Sentinel-derived precompute data separately.
- Keep macroStep test target semantics intact while removing wasteful per-button macro-step ID extraction.
- Preserve pageLink resolution behavior, including macro-step-influenced page targets.

## Next Minimal Implementation Scope (For Future Approval)
- Add tests first for baseline instrumentation and hot-path regression checks.
- Implement targeted extractor caching in approved files only.
- Add/confirm bounded runtime guard behavior for extraction subprocess execution.
- Re-run bounded measurements and compare against baseline metrics.
