# Sentinel Agent Rules

## Scope
These rules apply to all work in this workspace unless the user explicitly overrides them.

## Change Control
- Never update `project_structure.json` without explicit user approval in the current thread.
- Never update `app_ui_structure.json` without explicit user approval in the current thread.
- If either file needs changes, stop and ask for approval before editing.
- No silent assumption changes:
  - If a resolving rule changes (for example test-target mapping), require explicit user approval before applying.
- Doc-lock rule:
  - Treat `project_structure.md`, `app_ui_structure.json`, and `project_structure_resolving_methods.md` as locked unless the user explicitly unlocks them.

## Development Method
- Use test-first methodology for all new scripts and major logic changes:
  1. Define/implement tests first.
  2. Implement code to satisfy tests.
  3. Re-run tests and report results.
- Enforce strict separation of concerns by file:
  - Keep extraction, transformation/inference, rendering, and I/O in separate modules/files.
  - Avoid mixing business logic and presentation logic in the same file.
- Prefer reusable modules/functions whenever possible.
- Keep implementations concise with minimal lines of code while preserving readability and testability.
- Deterministic outputs:
  - Keep generated JSON stable and repeatable (consistent key ordering/naming) to produce clean diffs.
- Validation gates:
  - Fail generation when schema/structure validation fails or required sections are missing.
- Regression check:
  - Always run tests and provide a concise diff summary of output changes before reporting done.

## Event Logging Standard
- Add event logs at every critical step in extraction/render workflows.
- Every log line must include:
  - Timestamp
  - Severity tag: `[INFO]`, `[WARN]`, `[SUCCESS]`, or `[FAIL]`
  - Message
- Example format:
  - `2026-03-10T12:34:56Z [INFO] Opened apex database`
  - `2026-03-10T12:34:58Z [SUCCESS] Wrote project JSON output`
- Traceability:
  - Generated files should include metadata with source apex filename, generation timestamp, and script version/commit when available.

## Safety
- Prefer file-backed truth over inference for project data.
- If behavior depends on inference, isolate and label it clearly in resolving logic/documentation.
- No inferred data in project JSON:
  - Keep project JSON as pure file-mapped data.
  - Place inference only in rendering/runtime logic and label it explicitly as inferred.
