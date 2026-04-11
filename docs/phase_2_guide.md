# Phase 2 Guide (Static Shell Injection)

Purpose: prevent Phase 2 drift and ensure migration from old runtime behavior to static shell is clean, testable, and reversible.

## Target Outcome

1. Keep Phase 1 routing/shell behavior stable.
2. Preserve old device runtime behavior exactly.
3. Inject only approved dynamic content/state into static shell placeholders.
4. Avoid helper-heavy rewrites that duplicate runtime logic.

## Non-Negotiable Rules

1. Do not reimplement old runtime layout/zoom/orientation math in ad-hoc helper code.
2. Do not patch behavior repeatedly in API response strings as a long-term approach.
3. Keep old runtime behavior as source of truth; adapt hooks/containers only.
4. If a fix changes behavior semantics, stop and re-scope before coding.
5. Log every failed attempt before trying the next fix.
6. If the page being tested is still old runtime, stop and prove exactly which runtime/file path is being served before making another change.
7. Do not assume `?runtime=shell` is serving static-shell output; verify with served HTML/source checks first.
8. Phase 1 and Phase 2 are one progressive implementation path. Phase 1 is not a fallback branch.
9. Phase 2 must extend Phase 1 behavior in the same runtime path; it must never replace, bypass, or disable Phase 1 path behavior.
10. If implementation introduces a branch where `runtime=shell` can choose `Phase1-only` vs `Phase2` as alternatives, that implementation is invalid and must be rejected before deploy.

## What Failed Before (Do Not Repeat)

1. Parallel deploy steps caused stale code to remain active.
2. Home link rewriting with the wrong base dropped token/path context.
3. Incremental helper injections produced partial visuals but drifted behavior.
4. “Looks better” patches passed local checks but did not solve user-visible issues.
5. Over-agreement delayed technical pushback on weak implementation paths.

## Approved Phase 2 Method

1. Start from known-good Phase 1 baseline.
2. Implement deterministic adapter mapping from old hooks to static hooks.
3. Keep runtime logic intact; only remap targets/containers.
4. Validate one concrete user-visible scenario before broader rollout.
5. Deploy sequentially with explicit on-server code verification.

## Phase 2 Reset Plan (From This Thread)

This section replaces the helper-heavy path and is now the required implementation plan.

### Problem Statement

1. Phase 1 was stable.
2. Phase 2 regressions came from API-layer helper injection in `testing.py`.
3. The required outcome is old runtime behavior unchanged, rendered inside static shell structure.

### Architecture Decision (Locked)

1. `testing.py` must not contain behavioral layout/runtime reconstruction for device pages.
2. Phase 2 implementation belongs in generation/runtime output (`render_core.py`) and static shell markup/CSS.
3. Keep one runtime codepath for device behavior; add only a deterministic hook adapter.
4. Explicit anti-misunderstanding rule: do not model migration as "Phase 1 fallback, Phase 2 optional path."
5. Correct model: "Phase 1 base + Phase 2 injection on top" in one composed path.

### Banned Misunderstanding (Do Not Repeat)

1. Wrong: treat Phase 1 as fallback and Phase 2 as a separate optional branch.
2. Right: treat Phase 1 as the base implementation slice and Phase 2 as the next layer in the same path.
3. Wrong behavior indicator: user sees shell route regress to Phase 1-only output and loses Phase 2 injection work.
4. Required response if this appears:
   - stop
   - verify served route/file path
   - restore single composed Phase1+Phase2 path
   - add/update regression tests before redeploy

### Current Runtime Hooks (Verified)

Old runtime selectors in generated device page:
1. `#appCanvas`
2. `#topControls`
3. `#orientationToggle`
4. `#zoomControls` with `.zoom-dec/.zoom-reset/.zoom-inc`
5. `#layerPanel` and `#layerList`
6. `#rtiCanvas`, `#rtiContent`, `#rtiDeviceCanvas`
7. `#bottomControls`

Static shell target hooks:
1. `#appCanvas`
2. `#topControlsStatic`
3. `.orientationToggleStatic` / `.orientationBtnStatic`
4. `.zoomBtnDec/.zoomBtnReset/.zoomBtnInc`
5. `#deviceLayerControlsCanvas` with `.layer-panel` / `.layer-list`
6. `#rtiUsableCanvas`, `#rtiDeviceCanvas`, `#rtiDeviceContent`
7. `#deviceFooterCanvas`

### Required Implementation Sequence

1. Remove Phase 2 behavior helpers from `testing.py` (keep Phase 1 routing behavior only).
2. Create a single hook adapter layer in generation/runtime code:
   - map old hook names to static hook names once,
   - no duplicated layout math, no second runtime implementation.
3. Render static shell structure directly from generation path.
4. Inject only approved dynamic content/state:
   - header text,
   - layers list/state,
   - RTI device content container.
5. Keep old runtime script behavior flow intact:
   - orientation handling,
   - zoom flow,
   - RTI fit/scale,
   - page switches,
   - popup/testing/ws behavior.

### Hard Red Lines

1. No inline string-built JS in API handlers to mimic runtime behavior.
2. No iframe/embed runtime fallback for Phase 2 final implementation.
3. No duplicated coordinate/layout algorithm outside existing runtime path.
4. No deploy if user-visible RTI behavior differs from old runtime in chosen validation scenario.

### File Scope for Clean Phase 2

1. `src/sentinel/generation/render_core.py`
   - primary implementation location for shell + runtime adapter.
2. `src/sentinel/ui/commissioning/project_device_static_layout.html`
   - static shell structure updates only as needed for hook coverage.
3. `src/sentinel/ui/commissioning/project_device_static_layout.css`
   - static shell presentation only.
4. `src/sentinel/server/api/testing.py`
   - Phase 1 routing only; no Phase 2 behavior helpers.

### Test Gates (Must Pass Before Deploy)

1. Regression:
   - route behavior unchanged for default and shell opt-in.
2. Playwright runtime:
   - same device/page in old runtime vs shell runtime:
     - device outline present,
     - centered RTI device,
     - controls functional (orientation/zoom/layers),
     - page-link navigation behavior unchanged.
3. Visual evidence:
   - screenshot pair for approved scenario.

## Implementation Checklist (Per Attempt)

1. Declare exact user-visible defect to fix.
2. Identify smallest file scope needed.
3. Add/update tests first.
4. Implement single focused change.
5. Run temp-env regression + UI tests (no skips).
6. Record result in failure log section below.
7. Deploy sequentially:
   - archive
   - copy
   - extract
   - restart
   - health check
   - on-server source verification

## Failure Log (Append-Only)

### Entry Template
1. Date/Time:
2. Goal:
3. Change Attempted:
4. Why It Seemed Valid:
5. Observed Result:
6. Evidence (test/screenshot/log):
7. Disposition (kept/reverted/follow-up):

### 2026-04-10 - Parallel deploy sequencing failure
1. Date/Time: 2026-04-10
2. Goal: Deploy shell runtime link behavior.
3. Change Attempted: Copy and extract steps executed in parallel.
4. Why It Seemed Valid: Both commands are valid independently.
5. Observed Result: Stale code remained active on server.
6. Evidence (test/screenshot/log): On-server grep still showed old runtime mode rewrite.
7. Disposition (kept/reverted/follow-up): Re-deploy sequentially only; enforce sequencing in workflow.

### 2026-04-10 - Token/path break from link rewrite
1. Date/Time: 2026-04-10
2. Goal: Preserve shell mode from home to device links.
3. Change Attempted: URL resolution against `window.location.href`.
4. Why It Seemed Valid: Added `runtime=shell` to links.
5. Observed Result: Invalid path/token in some navigations (`TECH_LINK_REVOKED`).
6. Evidence (test/screenshot/log): User reproduction + API error response.
7. Disposition (kept/reverted/follow-up): Corrected base handling; added regression guard.

### 2026-04-10 - Helper-heavy RTI injection drift
1. Date/Time: 2026-04-10
2. Goal: Show RTI content in shell.
3. Change Attempted: Inline helper scripts for RTI positioning/scaling/orientation.
4. Why It Seemed Valid: Fast incremental visual progress.
5. Observed Result: Blank/partial/tiny/off-center content and repeated regressions.
6. Evidence (test/screenshot/log): Multiple user screenshots and “no change” reports.
7. Disposition (kept/reverted/follow-up): Reverted Phase 2 code to Phase 1 baseline.

## Final Quality Gate for Phase 2

1. User-visible result must match old runtime behavior for tested device/page flow.
2. No duplicated runtime math in new helper code.
3. No unresolved failure entries for active attempt.
4. Deploy is blocked unless all above are true.

## Conduct Rules for This Guide

1. If an approach increases helper code in `testing.py`, stop and redesign before implementation.
2. If a fix is speculative, mark it as speculative and do not deploy it.
3. If a user-visible mismatch remains after one deploy, log failure, narrow scope, and fix only the mismatch path.
4. Do not validate Phase 2 by shell structure markers alone.
5. Phase 2 is only valid when real runtime content/state is injected into `rtiDeviceContent`.
6. Do not use Phase-1-only shell serving as a substitute for Phase 2 behavior.
7. Use a single runtime path for device pages during this migration.
8. Do not implement or maintain multiple alternative runtime branches for the same shell route.
9. If a route decision exists, simplify back to one deterministic runtime path before further Phase 2 work.

## Additional Failure Records (2026-04-10)

### Marker-only false positive
1. Mistake: validated shell IDs/classes instead of validating injected runtime content.
2. Impact: reported progress while user-visible output remained static placeholders.
3. Prevention: require proof of injected content inside `rtiDeviceContent` before calling Phase 2 successful.

### Phase bypass while stabilizing route
1. Mistake: reintroduced Phase-1-only shell template serving on `runtime=shell` device route.
2. Impact: Phase 2 output path was bypassed and injection was effectively disabled.
3. Prevention: keep one composed runtime path where Phase 2 extends Phase 1, never replaces it.

### Phase model misunderstanding
1. Mistake: treated Phase 1 and Phase 2 as alternate branches during remediation.
2. Impact: decisions optimized for route stability but regressed injection goals.
3. Prevention: enforce progressive model in every scope review: Phase 1 base + Phase 2 injection in same path.
