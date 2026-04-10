# Static Shell Helper Code Log

Purpose: track temporary helper code introduced to make static-shell migration work in phases, so we can systematically replace it with reusable, production-grade modules during cleanup.

Status rule:
1. Any item marked `Temporary` must be either removed or refactored before final rollout.
2. Final implementation must avoid duplicated logic and use reusable modules/functions.

## Current Helpers

1. File: `src/sentinel/server/api/testing.py`
   - Symbol: `_inject_shell_runtime_home_navigation`
   - Type: `Temporary`
   - Why added: preserve `?runtime=shell` when navigating from project home to device pages during opt-in phases.
   - Cleanup target: replace ad-hoc DOM link patching with canonical server-side/runtime link generation.

2. File: `src/sentinel/server/api/testing.py`
   - Symbol: `_build_static_shell_device_html`
   - Type: `Temporary`
   - Why added: server-side bridge that composes static shell + injected runtime state/content before renderer refactor is complete.
   - Cleanup target: move shell composition to generation/runtime core with shared rendering utilities and no inline string-built JS.

3. File: `src/sentinel/server/api/testing.py`
   - Symbol: inline injected `<script>` built inside `_build_static_shell_device_html`
   - Type: `Temporary`
   - Why added: phase bridge for header/layer/RTI content and state application in shell mode.
   - Cleanup target: replace with reusable JS module loaded as static asset, with tested hook adapters and zero duplicated layout logic.

4. File: `src/sentinel/server/api/testing.py`
   - Symbol: `_extract_div_inner_by_id`, `_extract_json_const`, `_extract_number_const`
   - Type: `Temporary`
   - Why added: lightweight parsing of generated device HTML constants/markup for phased shell injection.
   - Cleanup target: stop parsing HTML strings; consume structured payload/runtime data through shared typed interfaces.

## Cleanup Acceptance Criteria

1. No inline string-built runtime scripts in server API handlers.
2. No duplicated RTI layout math between shell adapter and generation runtime.
3. All hook remapping logic centralized in reusable module(s) with clear tests.
4. Shell/default behavior controlled by explicit runtime strategy, not scattered conditionals.
5. Playwright parity tests pass without helper-only shortcuts.

## Failed Attempts Log

Entry template (required for each failed attempt):
1. Date/Time:
2. Goal:
3. Change Attempted:
4. Why It Seemed Valid:
5. Observed Result:
6. Evidence (test/screenshot/log):
7. Disposition (kept/reverted/follow-up):

### 2026-04-10 - Deploy sequencing failure
1. Date/Time: 2026-04-10
2. Goal: Deploy shell tech-link runtime change.
3. Change Attempted: Ran copy and extract in parallel.
4. Why It Seemed Valid: Both commands are individually valid deploy steps.
5. Observed Result: Droplet still served older `runtime=payload` code.
6. Evidence (test/screenshot/log): On-server grep still showed payload rewrite in `commissioning.js`.
7. Disposition (kept/reverted/follow-up): Follow-up; deploy doc updated to require strict sequential copy -> extract -> restart -> verify.

### 2026-04-10 - Shell home link rewrite token-loss
1. Date/Time: 2026-04-10
2. Goal: Keep shell mode while navigating from home to device page.
3. Change Attempted: Rewrote links using `new URL(href, window.location.href)`.
4. Why It Seemed Valid: It appends `runtime=shell` to device links.
5. Observed Result: Some links lost `/files/` + token context and produced `TECH_LINK_REVOKED` on device open.
6. Evidence (test/screenshot/log): User reproduction + server error envelope `TECH_LINK_REVOKED`.
7. Disposition (kept/reverted/follow-up): Fixed by using `document.baseURI` as resolution base.

### 2026-04-10 - Phase 2 RTI injection (content present but behavior broken)
1. Date/Time: 2026-04-10
2. Goal: Inject RTI content into static shell.
3. Change Attempted: Injected RTI markup + basic scaling without full runtime coordinate normalization.
4. Why It Seemed Valid: Expected data-left/top/width/height to be sufficient for visual layout.
5. Observed Result: RTI content appeared blank or collapsed to tiny/unusable fragments.
6. Evidence (test/screenshot/log): User screenshots showing empty RTI area and tiny controls clustered low in canvas.
7. Disposition (kept/reverted/follow-up): Follow-up in progress; orientation-based coordinate normalization and layout fallback were added, but user still reports no visible improvement.

### 2026-04-10 - Initial RTI fallback fix insufficient
1. Date/Time: 2026-04-10
2. Goal: Prevent RTI collapse when canvas measures near zero.
3. Change Attempted: Added size fallback to source dimensions.
4. Why It Seemed Valid: Addresses tiny render caused by near-zero container sizes.
5. Observed Result: Local tests passed, but user-visible device rendering remained incorrect.
6. Evidence (test/screenshot/log): User report "no change" after deploy.
7. Disposition (kept/reverted/follow-up): Follow-up required; next step is parity-driven hook/runtime mapping instead of incremental inline fixes.

### 2026-04-10 - Orientation coordinate helper still failed visually
1. Date/Time: 2026-04-10
2. Goal: Fix RTI placement by reading `data-p-*` / `data-l-*` coordinates in shell helper layout code.
3. Change Attempted: Added orientation-derived coordinate/visibility mapping in inline shell script.
4. Why It Seemed Valid: Generated runtime uses orientation-specific dataset fields.
5. Observed Result: User still reported no visible improvement in live UI.
6. Evidence (test/screenshot/log): User response "no change" after deploy.
7. Disposition (kept/reverted/follow-up): Follow-up; replace custom inline RTI layout helper with embedded original runtime path (`embed=1`) to avoid duplicated layout logic.

### 2026-04-10 - Embedded runtime improved content but missed outline/centering
1. Date/Time: 2026-04-10
2. Goal: Restore correct RTI rendering by embedding original runtime page in shell.
3. Change Attempted: Added `embed=1` mode and iframe runtime embedding.
4. Why It Seemed Valid: Reuses original runtime JS/layout flow instead of duplicating it.
5. Observed Result: Content appeared, but device outline was missing and device was not centered.
6. Evidence (test/screenshot/log): User screenshot `Screenshot 2026-04-10 at 4.02.09 PM.png`.
7. Disposition (kept/reverted/follow-up): Follow-up in progress; remove border suppression and patch embedded `APP_UI_CONTROLS` to zero offsets for full-frame centering.

## Operating Rule

1. Before each new shell-render fix attempt, append the previous failed attempt to this log.
2. Every attempt must include direct evidence (test output, screenshot, or server log snippet).
3. If user-visible behavior does not improve, escalate to a narrower parity checkpoint before further implementation changes.

## Thread-Level Failures and Corrections (Phase 2)

### 2026-04-10 - Strategy drift: helper patching instead of clean transition
1. Date/Time: 2026-04-10
2. Goal: Implement Phase 2 injection without breaking old-runtime behavior.
3. What failed: Repeated API-layer helper patching in `testing.py` replaced deterministic migration architecture with ad-hoc behavior fixes.
4. Evidence: User-visible regressions across multiple deploys (blank/partial RTI content, outline/centering issues, no-change reports).
5. Correction: Stop behavior-reimplementation patches in API responses; keep old runtime behavior as source of truth and migrate via hook/container adapter approach.

### 2026-04-10 - Scope discipline issue: Phase 1 stable, Phase 2 repeatedly broken
1. Date/Time: 2026-04-10
2. Goal: Preserve successful Phase 1 while completing Phase 2.
3. What failed: Phase 2 fixes repeatedly introduced new regressions; work pattern did not protect stable behavior before additional changes.
4. Evidence: User directive: "phase 1 was fine... phase two that you keep breaking."
5. Correction: Freeze Phase 1 implementation; all subsequent work explicitly limited to Phase 2 correction path.

### 2026-04-10 - Communication quality failure: over-agreement instead of technical pushback
1. Date/Time: 2026-04-10
2. Goal: Provide reliable technical guidance under pressure.
3. What failed: Responses were too agreeable instead of directly flagging that the current approach was technically unsound.
4. Evidence: User feedback that agreement without critical evaluation reduced usefulness.
5. Correction: Require explicit pushback when approach risk is high; state viability directly before implementation.

## Locked Direction for Remaining Phase 2 Work

1. Do not continue adding ad-hoc runtime behavior patches in `testing.py`.
2. Target architecture: preserve old device runtime behavior exactly, with static-shell integration through deterministic hook/container adapters only.
3. Reject fixes that duplicate old runtime layout/zoom/orientation math in new inline helper code.
4. Any deviation from this direction must be explicitly approved before implementation.
