# Generation Structure Migration (One-Time)

## Purpose

This document defines a one-time migration from project-specific full HTML generation to a shared runtime shell plus project payload JSON.

This is intentionally not part of `docs/dev_environment_and_workflow.md`.

## Current State (As-Is)

Generation currently emits full standalone HTML pages per project:

1. `src/sentinel/generation/generate_html.py`
   - Writes project home HTML.
   - Writes per-device HTML.
2. `src/sentinel/generation/render_core.py`
   - `_render_document(...)` returns full `<!doctype html>...`.
   - `render_project_home_html(...)` returns full `<!doctype html>...`.
   - `render_single_device_html(...)` builds full per-device pages.
3. `src/sentinel/server/services/pipeline.py`
   - Runs extraction then generation scripts.
4. `src/sentinel/server/api/testing.py`
   - Serves generated HTML files directly from project output directory.

## Problem

When full runtime code is baked into generated project HTML, runtime behavior can become stale across older generated files. Regenerating content also regenerates full page/runtime markup repeatedly.

## Target State (To-Be)

Use a shared runtime shell (code-owned) plus project payload files (project-owned):

1. Shared shell (static app code, deployed with server):
   - `testing_shell.html`
   - `testing_runtime.js`
   - `testing_styles.css`
2. Generated project payload (per project run):
   - `project_manifest.json`
   - `device_<n>.json` payloads
   - optional event payload file(s)

## Data Ownership Rules

1. Shared shell contains generic UI/runtime behavior only.
2. Project payload contains all project/device/page content and metadata.
3. `layers` are project specific and must remain in generated project payload JSON.
4. Per-button stacking metadata must remain in project payload JSON:
   - `userFacing.pages[*].(layers[*].buttonCategories|buttonCategories).*.buttonUI.stack.layerOrder`
   - `userFacing.pages[*].(layers[*].buttonCategories|buttonCategories).*.buttonUI.stack.buttonOrder`
   - `userFacing.pages[*].(layers[*].buttonCategories|buttonCategories).*.buttonUI.stack.frameNumber`
5. Diagnostics button records must retain matching source stack metadata (`layerId`, `sharedLayerId`, `layerOrder`, `buttonOrder`, `frameNumber`) so rendering and troubleshooting can trace true RTI draw order.
6. User-facing button test targets must preserve graphics asset checks separately from variable-derived image state:
   - `userFacing.pages[*].(layers[*].buttonCategories|buttonCategories).*.testTargets.graphics.bitmap`
   - `userFacing.pages[*].(layers[*].buttonCategories|buttonCategories).*.testTargets.graphics.icon`

## Backward-Compatible Migration Plan (No-Risk First)

1. Dual-write phase:
   - Keep existing full HTML generation unchanged.
   - Add payload JSON generation in parallel.
2. Dual-serve phase:
   - Keep current HTML-serving path as default.
   - Add opt-in shared-shell path (feature flag or query toggle).
3. Parity phase:
   - Validate shared-shell mode against legacy HTML mode on same projects.
   - Compare: page navigation, viewport behavior, layers, WS updates, zoom behavior.
4. Controlled cutover:
   - Make shared-shell mode default only after parity passes.
   - Keep legacy fallback for one release window.
5. Cleanup:
   - Remove legacy full-HTML generation only after stable burn-in.

## Go/No-Go Gates

1. Functional parity passes on representative small and large projects.
2. No regressions in test recording, sync/replay, and fail-tag workflows.
3. No increased crash/hang behavior in extraction/generation pipeline.
4. Rollback path is verified (legacy HTML mode still available until cleanup phase).
