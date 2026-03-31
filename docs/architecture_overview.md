# Architecture Overview

## System Summary
1. Sentinel follows a staged pipeline: uploaded `.apex` file -> project-specific JSON shaped by `apex_project_structure_v4.json` -> generated event testing and device testing interfaces shaped by `app_ui_structure.json`.
2. The system is split between project-derived data and Sentinel-owned interface behavior so extracted RTI structure and Sentinel overlay/navigation rules remain clearly separated.
3. The user interface and diagnostics interface are two distinct surfaces over shared session data, generated project data, and append-only test history.
4. Event logging is a first-day architectural requirement across extraction, generation, session actions, and failure handling so every critical step is traceable.
5. Sentinel must never continue silently after a failure. When a failure leaves the app unable to guarantee a stable and truthful state, the user must be stopped with an explicit failure path, including aborting the load or closing the app when necessary.
6. Sentinel should prefer concise, reusable modules and shared functions so extraction, generation, and supporting workflows remain maintainable, consistent, and repeatable.

## Trust Boundaries
1. Uploaded `.apex` files are the source for project-derived data, but they must still be treated as external input and validated through the approved extraction contract.
2. `apex_project_structure_v4.json` is the controlling contract for generated project-specific JSON and must not be bypassed by ad hoc extraction behavior.
3. `app_ui_structure.json` is the controlling contract for Sentinel-owned UI behavior, overlay elements, and navigation behavior and must remain separate from `.apex`-derived data.
4. Test history, pass/fail records, timestamps, and fail notes are session data and must remain traceable to the targets and generations they belong to.
5. Event logs are operational evidence and must capture critical actions and failures without becoming a substitute for source project data or test-result data.
6. If Sentinel cannot guarantee a stable state after a failure, the current operation must stop rather than allowing the app to continue in a partially valid or unknown condition.

## Forbidden Patterns
1. Mixing `.apex`-derived project data with Sentinel-owned UI configuration in a way that hides which parts come from the source project and which parts come from Sentinel.
2. Silent fallback behavior that produces partial, guessed, or contract-breaking project JSON or generated interfaces.
3. Allowing regenerated project data to overwrite or erase append-only test history.
4. Hidden test artifacts, temporary files, or generated review files living alongside app files in ways that create cleanup risk or future test contamination.
5. Treating event logging as optional for critical flows such as upload, extraction, generation, persistence, regeneration, and failure handling.
6. Allowing the app to continue after a critical failure when state integrity, contract validity, or generated-output correctness can no longer be trusted.
7. Hiding critical failures behind warnings, passive messages, or dismissible notices when the correct action is to abort the load or stop the app.
8. Duplicating logic across extraction, generation, rendering, or session handling when a single shared function or module can enforce the behavior correctly.

## Deployment topology (MVP)

1. A single Sentinel server is the MVP deployment target:
   - Commissioning/diagnostics APIs under `/api/v1/commissioning/...`
   - Technician testing APIs under `/api/v1/testing/{techToken}/...`
   - Technician entrypoint HTML under `/testing/{techToken}`
2. The commissioning UI and technician UI are web surfaces that may be served:
   - directly by the Sentinel server, or
   - by your public website while reverse-proxying requests to the Sentinel server (so URLs remain on your domain).
3. Interoperability is contract-first:
   - canonical contract: `docs/api_contract_v1.md`
   - canonical examples: `docs/contract_pack_examples_v1.json`
   - compatibility rule: additive-only changes for v1

---

