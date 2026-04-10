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

