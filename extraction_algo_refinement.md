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
- Button-path macroStep target semantics were restored without reintroducing per-button macroStepId SQL lookups (using macro-level fallback keying).
- Remaining major hotspot is event macro resolution (`_resolve_driver_action`) still issuing expensive `MacroStepsView` queries on large projects.

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

### Filename: `Assets/Sung Residence v207.2.apex` (Post-button-path optimization)
- Apex size bytes: `72531968`
- Probe: `temp/extraction_algo_refinement_probe.py`

1. Total Extraction Time
- `28.155s` (first post-change probe)
- `33.169s` (post macroStep-target restore probe)

2. Throughput (Work Processed per Second)
- `31366` work units
- `1114.034` units/sec (first post-change probe)
- `945.633` units/sec (post macroStep-target restore probe)

3. Total SQL Query Count
- `6140`

4. Distinct SQL Query Shapes
- `44`

5. SQL Latency Profile for Top Repeated Queries
- `select * from RTIDeviceButtonData where SharedLayerId = ? ...`
  - count: `4974`, totalMs: `2613.318` to `2724.855`, avgMs: `0.525` to `0.548`
- `select count(*) from MacroStepsView where MacroId = ?`
  - count: `63`, totalMs: `9248.603` to `11085.534`, avgMs: `146.803` to `175.961`
- `select CommandTagId from MacroStepsView where MacroId = ? and Type = 14 ...`
  - count: `63`, totalMs: `8154.918` to `9527.879`, avgMs: `129.443` to `151.236`

6. Unique testTarget Count per Device (Scope-Aware)
- First post-change probe:
  - Device `89` (`Entry KA11`): `6000`
  - Device `2` (`XP-8v`): `0`
  - Device `88` (`iPhone (David)`): `6463`
  - Device `156` (`Family/Kitchen/Office/Master Bed T4x`): `914`
  - Device `92` (`Rec Room / Gym T2i`): `478`
  - Device `214` (`Theater T2i`): `522`
- Post macroStep-target restore probe:
  - Device `89` (`Entry KA11`): `8850`
  - Device `2` (`XP-8v`): `0`
  - Device `88` (`iPhone (David)`): `9607`
  - Device `156` (`Family/Kitchen/Office/Master Bed T4x`): `1938`
  - Device `92` (`Rec Room / Gym T2i`): `1369`
  - Device `214` (`Theater T2i`): `1430`

### Server Baseline Log Snapshots (`REGEN_BASELINE`) for Sung
- Historical stable range observed: `~48.9s` to `~49.1s` extraction.
- Outlier observed: `2998.566s` extraction (known long-run failure period).
- Latest deployed-server Sung extraction observed in logs: `76.552s`.

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
- Current extraction path no longer performs per-button macroStepId SQL lookups; macroStep target semantics were restored via macro-level fallback keying.
- PageLink resolving remains intact for macro-step-driven routes.
- Event macro resolution still incurs expensive `MacroStepsView` query costs and is now the primary remaining macroStep-related hotspot.

## MacroStep Handling Decision (Agreed)
- We should preserve `macroStep`/`macroSteps` test target signaling.
- We should avoid per-button macro-step ID resolution queries in the hot path.
- The accepted approach is to determine macro-step cardinality (none / one / many) from already preloaded macro metadata (for example, precomputed per-macro step counts) rather than fetching per-button `MacroStepId` lists.
- `macroStepIds` detailed lists are not required for the optimization phase if target semantics and pageLink behavior remain correct.
- Generation/progress keying uses macro-level fallback `mstepmacro:<macroId>` when detailed `macroStepIds` are absent.

## Initial Refinement Direction (From Current Evidence)
- Prioritize elimination of repeated hot-path work before adding complexity elsewhere:
  - Cache macro-step ID resolution for repeated macro-id sets.
  - Cache `RTIDeviceButtonData` by `SharedLayerId` and reuse across page/viewport traversals.
- Add bounded, focused instrumentation tied to the six baseline metrics.
- Keep pipeline verification bounded and fail-fast for overlong runs with diagnostic context.
- Near-term correction after recent optimization:
  - Completed: restored `macroStep`/`macroSteps` target signaling without reintroducing per-button macro-step ID lookup.
  - Completed: verified macro-step-driven pageLink resolution behavior remained unchanged.
  - Next focus: reduce event macro resolution (`_resolve_driver_action`) query cost while preserving event macroStep target semantics.

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
- Keep generation/progress alignment via `mstepmacro:<macroId>` fallback when `macroStepIds` are intentionally absent.

## Next Minimal Implementation Scope (For Future Approval)
- Add tests first for baseline instrumentation and hot-path regression checks.
- Implement targeted extractor caching in approved files only.
- Add/confirm bounded runtime guard behavior for extraction subprocess execution.
- Re-run bounded measurements and compare against baseline metrics.

## New Baseline Snapshot (Post macroStep button changes) - 2026-04-06
Historical baseline entries above are intentionally preserved.

### Filename: `Assets/TEST - System Manager v11.3.apex`
- Apex size bytes: `2867200`
- Probe: `temp/extraction_algo_refinement_probe.py`

1. Total Extraction Time
- `0.134s`

2. Throughput (Work Processed per Second)
- Work units processed: `1275`
- Work units/sec: `9483.926`

3. Total SQL Query Count
- `324`

4. Distinct SQL Query Shapes
- `37`

5. SQL Latency Profile for Top Repeated Queries
- `select * from RTIDeviceButtonData where SharedLayerId = ? ...`
  - count: `262`, totalMs: `47.36`, avgMs: `0.181`, p95Ms: `0.244`, maxMs: `0.528`
- `select * from Layers where PageId = ? ...`
  - count: `21`, totalMs: `4.0`, avgMs: `0.19`, p95Ms: `0.221`, maxMs: `0.422`

6. Unique testTarget Count per Device (Scope-Aware)
- Device `6` (`RTiPanel (iPhone X or newer)`): `1493`
- Device `2` (`XP-3`): `0`
- Device `37` (`T2i (Global)`): `34`

### Filename: `Assets/Carlos OBryans v6.3.1 (tag cleanup).apex`
- Apex size bytes: `7585792`
- Probe: `temp/extraction_algo_refinement_probe.py`

1. Total Extraction Time
- `0.07s`

2. Throughput (Work Processed per Second)
- Work units processed: `430`
- Work units/sec: `6174.978`

3. Total SQL Query Count
- `112`

4. Distinct SQL Query Shapes
- `38`

5. SQL Latency Profile for Top Repeated Queries
- `select * from RTIDeviceButtonData where SharedLayerId = ? ...`
  - count: `56`, totalMs: `10.728`, avgMs: `0.192`, p95Ms: `0.298`, maxMs: `0.391`
- `select * from Layers where PageId = ? ...`
  - count: `9`, totalMs: `1.737`, avgMs: `0.193`, p95Ms: `0.228`, maxMs: `0.228`

6. Unique testTarget Count per Device (Scope-Aware)
- Device `12` (`IST-5 (Global)`): `493`
- Device `2` (`XP-6s`): `0`

### Filename: `Assets/Dash OS v55.2 iPhone.apex`
- Apex size bytes: `62275584`
- Probe: `temp/extraction_algo_refinement_probe.py`

1. Total Extraction Time
- `0.277s`

2. Throughput (Work Processed per Second)
- Work units processed: `2165`
- Work units/sec: `7810.518`

3. Total SQL Query Count
- `652`

4. Distinct SQL Query Shapes
- `38`

5. SQL Latency Profile for Top Repeated Queries
- `select * from RTIDeviceButtonData where SharedLayerId = ? ...`
  - count: `529`, totalMs: `111.412`, avgMs: `0.211`, p95Ms: `0.262`, maxMs: `0.454`
- `select * from Layers where ViewportButtonId = ? ...`
  - count: `28`, totalMs: `6.547`, avgMs: `0.234`, p95Ms: `0.274`, maxMs: `0.467`

6. Unique testTarget Count per Device (Scope-Aware)
- Device `5` (`RTiPanel (iPhone X or newer)`): `453`
- Device `2` (`XP-8s`): `0`
- Device `7` (`KA11`): `313`
- Device `41` (`T4x`): `6`

### Filename: `Assets/Verrier Home FEENY EDIT v49.apex`
- Apex size bytes: `36159488`
- Probe: `temp/extraction_algo_refinement_probe.py`

1. Total Extraction Time
- `3.847s`

2. Throughput (Work Processed per Second)
- Work units processed: `16325`
- Work units/sec: `4243.377`

3. Total SQL Query Count
- `5236`

4. Distinct SQL Query Shapes
- `44`

5. SQL Latency Profile for Top Repeated Queries
- `select * from RTIDeviceButtonData where SharedLayerId = ? ...`
  - count: `3999`, totalMs: `695.842`, avgMs: `0.174`, p95Ms: `0.241`, maxMs: `3.703`
- `select count(*) from MacroStepsView where MacroId = ?`
  - count: `61`, totalMs: `713.798`, avgMs: `11.702`, p95Ms: `12.953`, maxMs: `13.451`
- `select CommandTagId from MacroStepsView where MacroId = ? and Type = 14 ...`
  - count: `61`, totalMs: `716.748`, avgMs: `11.75`, p95Ms: `13.826`, maxMs: `23.419`

6. Unique testTarget Count per Device (Scope-Aware)
- Device `81` (`iPhone (Sean)`): `7183`
- Device `197` (`RK3-V (Bedroom2)`): `184`
- Device `196` (`RK3-V (Bedroom1)`): `182`
- Device `2` (`XP-8v`): `0`
- Device `82` (`iPad (#1)`): `10278`

### Filename: `Assets/Sung Residence v207.2.apex`
- Apex size bytes: `72531968`
- Probe: `temp/extraction_algo_refinement_probe.py`

1. Total Extraction Time
- `12.125s`

2. Throughput (Work Processed per Second)
- Work units processed: `31366`
- Work units/sec: `2586.841`

3. Total SQL Query Count
- `6140`

4. Distinct SQL Query Shapes
- `44`

5. SQL Latency Profile for Top Repeated Queries
- `select * from RTIDeviceButtonData where SharedLayerId = ? ...`
  - count: `4974`, totalMs: `1078.413`, avgMs: `0.217`, p95Ms: `0.285`, maxMs: `9.806`
- `select count(*) from MacroStepsView where MacroId = ?`
  - count: `63`, totalMs: `3876.458`, avgMs: `61.531`, p95Ms: `64.683`, maxMs: `79.329`
- `select CommandTagId from MacroStepsView where MacroId = ? and Type = 14 ...`
  - count: `63`, totalMs: `3567.838`, avgMs: `56.632`, p95Ms: `66.81`, maxMs: `75.56`

6. Unique testTarget Count per Device (Scope-Aware)
- Device `89` (`Entry KA11`): `8850`
- Device `2` (`XP-8v`): `0`
- Device `88` (`iPhone (David)`): `9607`
- Device `156` (`Family/Kitchen/Office/Master Bed T4x`): `1938`
- Device `92` (`Rec Room / Gym T2i`): `1369`
- Device `214` (`Theater T2i`): `1430`

## Bottom Benchmark Matrix (Worst Extraction Time by Phase)
Single worst benchmark per phase/project to keep the comparison compact.

| Project | Original Worst (s) | macroStep Worst (s) | Shared Layer Worst (s) |
| --- | ---: | ---: | ---: |
| TEST - System Manager v11.3 | 1.699 | 0.134 | 0.212 |
| Carlos OBryans v6.3.1 | 0.768 | 0.07 | 0.143 |
| Dash OS v55.2 iPhone | 2.652 | 0.339 | 0.593 |
| Verrier Home FEENY EDIT v49 | 8.823 | 3.847 | 9.27 |
| Sung Residence v207.2 | 2998.566* | 33.169 | 29.117 |

Notes:
- Values are the worst observed extraction-time benchmarks recorded in this thread for each phase.
- `*` Sung `Original` worst comes from `REGEN_BASELINE` historical logs (known long-run failure outlier period).
