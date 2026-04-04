# bootstrap.md

## Project Identity

- Product: Sentinel
- Purpose: Turn uploaded RTI `.apex` projects into a contract-valid testing environment.
- Purpose: Provide two coordinated surfaces for commissioning: testing UI and diagnostics UI.
- Purpose: Preserve and expose append-only testing history across regenerations.

## Hard Operating Rules

- Do not edit any file without explicit user approval.
- Present scoped change plan before edits; do not exceed approved file scope.
- Use test-first implementation; write tests before code changes.
- Use existing project test framework; do not switch frameworks ad hoc.
- Use Playwright runtime UI tests for HTML UI behavior.
- Do not infer, guess, or fill missing data.
- Do not silently continue after unstable, partial, or untrusted failures.
- Keep `.apex`-derived data separate from Sentinel-owned UI configuration.
- Keep test history append-only; never erase or collapse history on regeneration.
- Keep testing artifacts separated from app files.

## Workflow Rules

- Investigation mode: state workflow status at response start; show findings for review; keep outputs temporary until explicit confirmation (`approved`, `lock it down`, `add it to the doc`).
- Investigation mode: answer the asked question directly; provide a concrete next step/scope in the same response.
- Execution mode: edit only approved files and complete approved scope without unrelated changes.
- Stop and re-scope if additional files become necessary.
- Follow proven approved methods; do not replace them without user direction.
- Before deploy, run Intent Check Gate with required exact question and evidence format.

## Architectural Boundaries

- Pipeline boundary: `.apex` upload -> extracted project JSON (contracted) -> generated testing UI (contracted).
- Contract boundary: `apex_project_structure_v4.json` governs project-derived JSON.
- Contract boundary: `app_ui_structure.json` governs Sentinel UI behavior.
- Trust boundary: uploaded `.apex` is external input and must be validated through approved contracts.
- Data boundary: session/test-result history is append-only and separate from source project data.
- Failure boundary: abort/stop operations when state integrity cannot be guaranteed.
- API compatibility boundary: v1 contract changes are additive-only.

## File Usage Rules

- Root directives: `agents.md`.
- Directive parity: directive files under `docs/` are equal authority to root directives.
- Canonical API contract: `docs/api_contract_v1.md`.
- Canonical API examples: `docs/contract_pack_examples_v1.json`.
- Use approved working `.md` as source of truth for current investigation/discovery decisions.
- Treat unsupported or unverified claims as non-authoritative; exclude until proven from authoritative sources.
- If authoritative directives conflict, stop and request user resolution before changes.

## Naming and Formatting Rules

- Branch naming convention: `codex/<agent>-<task>`.
- Technician UI route pattern: `/testing/{techToken}`.
- API route families: `/api/v1/commissioning/...` and `/api/v1/testing/{techToken}/...`.
- Timestamp format: RFC3339/ISO8601 UTC with `Z`.
- `targetKey` must be deterministic from stable extracted IDs plus non-inferred `targetName`.
- Fail results must include non-empty fail notes.

## Validation Rules

- Required layers: extraction unit tests, generation unit tests, contract tests, UI fidelity tests, render verification, E2E/regression coverage.
- Tests must fail on contract drift, missing/misplaced targets, or UI/output mismatch with extracted data/contracts.
- Verify the active test framework before writing/running tests.
- Run UI runtime checks with Playwright.
- Record Intent Check Gate evidence exactly:
- `Original problem: ...`
- `Test run that directly reproduces it: ...`
- `Observed before: ...`
- `Observed after: ...`
- `Pass/Fail: ...`
- Do not deploy unless Intent Check Gate is explicitly `Pass`.
