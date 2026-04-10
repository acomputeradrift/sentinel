# Project Device Static Page Implementation Plan

## Purpose
Define a safe staged plan to move to a static device page shell without breaking current user-visible behavior.

## Primary Goal
Use providecd device page framework HTML and CSS, then inject device-specific content into approved areas only.

## Non-Goals
1. Do not remove or replace the existing project home page (events/devices/system events/driver events).
2. Do not change default runtime routing for `/testing/{token}`.
3. Do not introduce new UI sections not explicitly requested.
4. Do not deploy prototype placeholders into production default flows.

## Source-of-Truth Layout Contract
Approved named areas:
1. browserViewportCanvas
2. deviceHeaderCanvas
3. deviceFooterCanvas
4. deviceViewControlsCanvas
5. deviceLayerControlsCanvas
6. rtiUsableCanvas
7. rtiDeviceCanvas
8. rtiDeviceContent

Area rules:
1. Left panel: orientation, device zoom, text zoom plus labels only. Full sized controls and minimized controls ok
2. Right panel: layers only.
3. No page list in left panel.
4. No device list in right panel.
5. No debug/status footer text unless explicitly requested.
6. No sample color blocks in production output.

## Static vs Injected Contract
Static:
1. Shell structure and named area containers.
2. Collapse toggle controls.
3. Base CSS tokens for sizing/spacing/button consistency.

Injected:
Device title/header text.
1. Layer controls in deviceLayerControlsCanvas.
2. View-control state in deviceViewControlsCanvas.
3. RTI content inside rtiDeviceContent (not rtiDeviceCanvas).

Conditional rules:
1. In device single-orientation cases, hide orientation controls both minimized and full sized.
2. If no layers, hide layer placeholders.

## Routing and Runtime Safety Contract
1. Existing default route behavior remains unchanged until parity is confirmed and explicitly approved.
2. New shell runtime stays opt-in (`?runtime=shell`) during development.
3. Any default switch is a separate approved scope.
4. Default switch scope must include rollback instructions.

## Must Preserve Device Runtime Contract
The following behavior is required parity for device pages and must remain functional after static-shell migration.

### Entry, Navigation, and Page Lifecycle
1. Keep project home as the default `/testing/{techToken}` entry point.
2. Keep explicit `Project Home` nav link on every generated device page.
3. Keep device row click behavior from project home into device page HTML.
4. Keep in-device page-link navigation (`.page-link-hit`) and lazy page materialization.
5. Keep active page reset behavior (zoom reset, viewport index reset, scroll reset) on page switches.

### Core Device Controls
1. Keep dynamic header sync (`deviceName - pageName`) behavior.
2. Keep orientation controls and orientation switching rules.
3. Keep zoom controls (`decrease`, `reset`, `increase`) and center-preserving zoom behavior.
4. Keep layer panel rendering, layer toggle behavior, and no-layer hide behavior.
5. Keep layer visibility persistence in session storage (page scope and viewport scope).

### RTI Canvas and Layout
1. Keep RTI fit/scale/layout math and control-boundary placement behavior.
2. Keep button/viewport coordinate scaling and font-size scaling behavior.
3. Keep hover-scrollbar behavior where configured by app UI contract.
4. Keep ready-baseline reporting flow (`/api/v1/testing/{techToken}/ready`) conditions.

### Testing Popup and Result Submission
1. Keep test popup open/close behavior from `.test-btn` rows.
2. Keep per-target Pass/Fail controls and fail-note-required enforcement for FAIL.
3. Keep Pass All queue semantics and posting lock behavior.
4. Keep post-status and row-status rendering behavior.
5. Keep target payload construction behavior and key-shape compatibility (`tt2`, `tt_ui`, `vpbtn`, `btn`, `event`).

### WebSocket and Status Sync
1. Keep testing websocket connection lifecycle (connect, reconnect, sync request, snapshot apply, incremental apply).
2. Keep sequence handling and sync recovery behavior.
3. Keep cached status application to rows and visual refresh across button surfaces.
4. Keep button-state trim/counter rendering based on latest status state.

### Viewport Mode and Popup Runtime
1. Keep viewport focus mode entry and exit behavior.
2. Keep viewport popup rendering and cloned-button interaction behavior.
3. Keep popup navigation modes (page mode vs vertical mode) and frame indicators.
4. Keep popup zoom/layout logic and center/scroll stability behavior.
5. Keep viewport-layer visibility application inside popup content.
6. Keep close behavior via explicit close control and existing non-close backdrop/escape policy.

### Runtime Hook and ID/Class Compatibility
1. Preserve runtime behavior and hook coverage by mapping JS bindings to the static standard IDs/classes (browserViewportCanvas, topControlsStatic, deviceViewControlsCanvas, deviceLayerControlsCanvas, rtiUsableCanvas, rtiDeviceCanvas, rtiDeviceContent) while keeping popup and test-modal IDs functional.
2. Preserve runtime boot sequence: orientation render/apply, initial layout apply, button binding, viewport binding, websocket init, and event-handler wiring.
3. No runtime function removal in device-page script path; migration may rehost structure but cannot delete behavior.

## Implementation Phases
Phase 0 (Guardrails):
1. Finalize plan.
2. Add tests protecting current default route behavior.
3. Add tests for forbidden UI additions.

Phase 1 (Static Shell, opt-in only):
1. Implement static HTML/CSS shell with approved area names.
2. Implement toggle behavior only.
3. Keep behind opt-in runtime flag.

Phase 2 (Injection Wiring):
1. Inject layers to right panel only.
2. Inject view controls to left panel only.
3. Inject RTI content into `rtiDeviceCanvas`.
4. Hide unsupported controls based on payload capability.

Phase 3 (Parity Validation):
1. Verify project home unchanged.
2. Verify generated device behavior parity where required.
3. Verify no extra sections appear.
4. Verify no debug/status/footer leak into production UI.

Phase 4 (Controlled Rollout):
1. Present explicit default-switch scope.
2. Include screenshot diff approval.
3. Enable default only after approval.
4. Keep immediate rollback path ready.

## Required Test Gates
Before deploy:
1. Playwright UI runtime tests for existing project home flow and shell boundaries.
2. Regression tests for routing behavior.
3. Intent Check evidence:
   - `Original problem: ...`
   - `Test run that directly reproduces it: ...`
   - `Observed before: ...`
   - `Observed after: ...`
   - `Pass/Fail: ...`

Deploy blocked unless `Pass/Fail: Pass`.

## Deployment Rules (Hard)
1. No shell-default deploy without explicit approval in that exact scope.
2. No deploy with open parity checklist items.
3. No deploy without screenshot diff approval.

## Rollback Plan
1. Revert runtime/default switch immediately on deviation.
2. Redeploy prior stable `src`.
3. Confirm project home and device flows restored.
4. Resume work in opt-in mode only.

## Incident Learnings
1. Do not convert prototype scaffolding into default runtime behavior.
2. Do not infer extra UI sections from payload convenience.
3. Do not treat one “approved” as blanket approval for adjacent rollout changes.
4. Preserve existing user-visible flows until explicit replacement approval.

## Failure Record (April 9, 2026)
1. Failure summary: AI did not follow user direction and made unapproved implementation decisions.
2. Specific failure:
1. Introduced additional template/injection decisions beyond requested scope.
2. Did not consistently follow deployment warm-up guidance before interpreting first health-check result.
3. Required correction:
1. Revert all unapproved implementation commits before further work.
2. Do not add unapproved structure/injection changes.
3. Follow deployment doc restart validation exactly (including warm-up delay and retry behavior).
4. Enforcement:
1. If direction is explicit, no extra decisions are permitted without user approval.

## Discovery Update (April 10, 2026)

### What Did Not Work

### What Did Work
1. None yet.

### Additional Info

#### Locked Naming Standard
1. Static page naming and structure are the standard for this migration.
2. Runtime behavior must be remapped to static hooks/areas.
3. Do not maintain duplicate near-identical naming as competing standards.

#### Solved Hook Map (Locked)
1. `#appCanvas` -> `#appCanvas` (root viewport container standard).
2. `#topControls` -> `#topControlsStatic`.
3. `.project-home-link` -> `.project-home-link`.
4. Header region container -> `#deviceHeaderCanvas` (controls remain inside this area).
5. `#rtiCanvas` -> `#rtiUsableCanvas`.
6. `#rtiContent` -> `#rtiDeviceCanvas`.
7. `#rtiDeviceCanvas` -> `#rtiDeviceContent`.
8. `#bottomControls` -> `#deviceFooterCanvas`.
9. `#orientationControls` -> orientation controls container inside `#deviceViewControlsCanvas`.
10. `#orientationToggle` -> `.orientationToggleStatic`.
11. `.orientation-btn` -> `.orientationBtnStatic` (including minimized orientation placeholders per static layout).
12. `#zoomControls` -> zoom controls container inside `#deviceViewControlsCanvas`.
13. `.zoom-dec/.zoom-reset/.zoom-inc` -> `.zoomBtnDec/.zoomBtnReset/.zoomBtnInc` (including minimized controls per static layout).
14. `#layerControls` -> `#deviceLayerControlsCanvas`.
15. `#layerPanel` -> `.layer-panel` in the static layer placeholder area.
16. `#layerList` -> `.layer-list` in the static layer placeholder area.

#### Name/Structure Changes To Apply During Implementation
1. Root container class `.projectDeviceStaticLayout` must be replaced by `#appCanvas` as the runtime root hook.
2. RTI naming chain is corrected for clarity:
1. outer window/frame: `rtiUsableCanvas`
2. workspace/canvas: `rtiDeviceCanvas`
3. drawn content layer: `rtiDeviceContent`
3. Static layout remains fixed except approved placeholders:
1. Device/Page title placeholder.
2. Orientation placeholders (full and minimized).
3. Layer content placeholder.
