# Sentinel API v1 Contract (Project + Technician Link + Results)

Status: Approved contract draft (2026-03-19)

This document defines the **minimum shared contract** that lets the server, Technician Testing UI, and Diagnostics/Commissioning Console be developed in parallel.

## Decisions locked for v1

1) Technician UI is served as **static generated HTML** (server delivers the generated artifact).
2) **No technician logins, ever.** Access is via emailed **technician link token** that lasts for the project.
3) Technician link **rotation is allowed** (revoke old token, issue new token for the same tester/project).
4) Test history is **append-only** and must remain queryable across regenerations.
5) `targetKey` is **deterministic** from extracted stable IDs + a non-inferred `targetName`.

## Contract pack (v1)

The contract pack is the minimum set of agreed artifacts that lets panels and server be built independently.

- Canonical contract: `docs/api_contract_v1.md` (this document)
- Canonical examples: `docs/contract_pack_examples_v1.json`

Compatibility rule (normative):
- v1 changes must be additive-only (new fields optional, new routes ok, no enum meaning reuse).

## Shared identifiers + enums (v1 minimum)

Identifiers (stable across the system):
- `clientId`, `projectId`, `uploadId`, `extractionRunId`, `generationRunId`
- `techLinkId`, `techToken`
- `targetKey`, `testResultId`

Enums (shared meanings; never reuse meanings within v1):
- `ProjectStatus`: `EMPTY|STALE|READY|FAILED`
- `RunStatus`: `QUEUED|RUNNING|SUCCEEDED|FAILED|CANCELED`
- `Outcome`: `PASS|FAIL`
- `ActorRole`: `TECHNICIAN|PROGRAMMER`
- `TargetKind`: `EVENT|BUTTON|VIEWPORT_BUTTON`
- `FailTag`: `TARGET|SCOPE|DATA|RESOLUTION|UNKNOWN`

## Surfaces

- **Technician Testing UI**: single active session, no diagnostics displayed.
- **Diagnostics/Commissioning Console**: manage projects, upload `.apex`, trigger regeneration, review results and failures.

## Authentication model (token links; no logins)

- Technician UI entrypoint is a descriptive URL: `GET /testing/{techToken}`.
- A project may have **multiple active technician links** at once (one per tester).
- `techToken` remains valid for the entire project unless rotated for that tester.
- Rotation creates a new `techToken` for the same tester/project and revokes the old one.
- Technician-scoped APIs use the token in the path: `/api/v1/testing/{techToken}/...`.

Revoked token behavior:
- `GET /testing/{revokedTechToken}` returns `410` with `error.code = TECH_LINK_REVOKED`.

## Common conventions

### Timestamps
- All timestamps are RFC3339/ISO8601 UTC strings ending in `Z` (e.g. `2026-03-19T12:05:00Z`).

### Standard error envelope
```json
{
  "error": {
    "code": "STRING_ENUM",
    "message": "human-readable",
    "details": {},
    "traceId": "string|null"
  }
}
```

## Core entities

### `Client`
One client/customer. Projects belong to a client.
```json
{
  "clientId": "uuid",
  "name": "string",
  "createdAtUtc": "2026-03-19T12:00:00Z"
}
```

### `Project`
One multi-day commissioning/testing project. Repeated uploads/extractions/generations happen under the same project, and the append-only test history is retained across days.
```json
{
  "projectId": "uuid",
  "clientId": "uuid",
  "name": "string",
  "createdAtUtc": "2026-03-19T12:00:00Z",
  "status": "EMPTY|STALE|READY|FAILED",
  "activeUploadId": "uuid|null",
  "activeExtractionRunId": "uuid|null",
  "activeGenerationRunId": "uuid|null",
  "activeTechLinkIds": ["uuid"]
}
```

### `TechLink`
Represents one tester (you, onsite tech, remote support) and the current token link used by that tester.
```json
{
  "techLinkId": "uuid",
  "projectId": "uuid",
  "label": "string|null",
  "token": "opaque-string",
  "issuedAtUtc": "2026-03-19T12:02:00Z",
  "revokedAtUtc": "2026-03-19T13:00:00Z|null"
}
```

### `Upload` (`.apex`)
```json
{
  "uploadId": "uuid",
  "projectId": "uuid",
  "receivedAtUtc": "2026-03-19T12:01:00Z",
  "originalFilename": "project.apex",
  "sha256": "hex",
  "bytes": 123456,
  "contentType": "application/octet-stream"
}
```

### `ExtractionRun`
```json
{
  "extractionRunId": "uuid",
  "projectId": "uuid",
  "uploadId": "uuid",
  "startedAtUtc": "2026-03-19T12:01:10Z",
  "endedAtUtc": "2026-03-19T12:01:20Z|null",
  "status": "QUEUED|RUNNING|SUCCEEDED|FAILED|CANCELED",
  "contractRef": {
    "path": "src/sentinel/contracts/apex_project_structure_v3.json",
    "version": "string"
  },
  "outputRef": "model://projects/{projectId}/extractions/{extractionRunId}",
  "failure": { "code": "string", "message": "string", "details": {} }
}
```

### `GenerationRun` (static HTML artifact)
```json
{
  "generationRunId": "uuid",
  "projectId": "uuid",
  "extractionRunId": "uuid",
  "startedAtUtc": "2026-03-19T12:01:25Z",
  "endedAtUtc": "2026-03-19T12:01:30Z|null",
  "status": "QUEUED|RUNNING|SUCCEEDED|FAILED|CANCELED",
  "uiContractRef": {
    "path": "src/sentinel/contracts/app_ui_structure.json",
    "version": "1.0.0"
  },
  "artifactRef": "artifact://projects/{projectId}/generations/{generationRunId}/testing-ui",
  "failure": { "code": "string", "message": "string", "details": {} }
}
```

### `Target` + `targetKey`
Results are recorded against a deterministic `targetKey` derived from **extracted stable IDs** and a `targetName` derived from extracted `testTargets` (no inference).

#### Target kinds and required refs
- `EVENT`: `eventId`
- `BUTTON`: `deviceId`, `pageId`, `buttonId`
- `VIEWPORT_BUTTON`: `deviceId`, `pageId`, `viewportButtonId`, `frameId`, `buttonId`

#### `Target`
```json
{
  "targetKey": "string",
  "kind": "EVENT|BUTTON|VIEWPORT_BUTTON",
  "refs": {
    "eventId": 0,
    "deviceId": 0,
    "pageId": 0,
    "buttonId": 0,
    "viewportButtonId": 0,
    "frameId": 0
  },
  "targetName": "string"
}
```

#### `targetKey` formats (normative)
- Event: `event:{eventId}:{targetName}`
- Button: `btn:{deviceId}:{pageId}:{buttonId}:{targetName}`
- Viewport button: `vpbtn:{deviceId}:{pageId}:{viewportButtonId}:{frameId}:{buttonId}:{targetName}`

#### `targetName` derivation rules (normative; no inference)
Given an extracted `testTargets` structure:
- `Macro` iff `testTargets.macro.isEmpty == false`
- `MacroSteps` iff `testTargets.macroSteps` is a non-empty list
- `Var.{VarName}` for each `testTargets.variableDetails.{VarName}.enabled == true`
- `PageLink` iff `testTargets.pageLink.targetPageId != null`
- For events: include each label in `userFacing.testTargets` where value is `true` (e.g. `Trigger`, `Macro`, `Macros`, `MacroStep`, `MacroSteps`, `Command`, `Commands`)

## Test result storage (append-only)

### `TestResultRecord`
```json
{
  "testResultId": "uuid",
  "projectId": "uuid",
  "generationRunId": "uuid",
  "recordedAtUtc": "2026-03-19T12:05:00Z",
  "recordedBy": { "role": "TECHNICIAN|PROGRAMMER", "techLinkId": "uuid|null" },
  "target": { "targetKey": "string", "kind": "EVENT|BUTTON|VIEWPORT_BUTTON", "refs": {}, "targetName": "string" },
  "outcome": "PASS|FAIL",
  "failNote": "string|null"
}
```

Rule (normative):
- If `outcome == "FAIL"`, `failNote` is required and non-empty. Reject with `error.code = FAIL_NOTE_REQUIRED`.

## Derived current status + progress (normative)

The server is the source of truth for test state by storing **append-only** history and deriving current state from it.

### Per-target current state

For a given `projectId + targetKey`:
- `currentOutcome` is the outcome of the most recent `TestResultRecord` by `recordedAtUtc`.
- If no record exists for that `targetKey` within the project, `currentOutcome = UNTESTED`.
- `lastTestedAtUtc` is the `recordedAtUtc` of the most recent record (or `null` if untested).

Tie-breaker rule:
- If two records have the same `recordedAtUtc`, the server uses `testResultId` as a deterministic tie-breaker.

### Progress rollups (device/project + event sections)

Progress is computed from:
1) the **latest active extracted model** for the project (defines the set of expected targets), and
2) the derived per-target current state above.

Definitions:
- `totalTargets`: count of expected targets for the scope (project, device, or events section).
- `testedTargets`: count of expected targets whose currentOutcome is `PASS` or `FAIL`.
- `untestedTargets = totalTargets - testedTargets`.
- `percentComplete = testedTargets / totalTargets` (0 when `totalTargets == 0`).
- `lastTestedAtUtc` for a scope is the maximum `lastTestedAtUtc` across targets in that scope (or `null`).

### Progress objects

`Counts`
```json
{
  "totalTargets": 0,
  "testedTargets": 0,
  "pass": 0,
  "fail": 0,
  "untested": 0,
  "percentComplete": 0.0
}
```

`TargetStatus`
```json
{
  "targetKey": "string",
  "currentOutcome": "PASS|FAIL|UNTESTED",
  "lastTestedAtUtc": "2026-03-19T12:05:00Z|null",
  "lastFailNote": "string|null"
}
```

`FailItem`
```json
{
  "failId": "uuid",
  "projectId": "uuid",
  "tag": "TARGET|SCOPE|DATA|RESOLUTION|UNKNOWN",
  "target": {
    "targetKey": "string",
    "kind": "EVENT|BUTTON|VIEWPORT_BUTTON",
    "refs": {},
    "targetName": "string"
  },
  "scope": {
    "scopeType": "PROJECT|DEVICE|PAGE|EVENT_SECTION|TARGET",
    "deviceId": 0,
    "pageId": 0,
    "eventSection": "system|driver|null"
  },
  "resolvedData": {},
  "currentOutcome": "FAIL",
  "lastTestedAtUtc": "2026-03-19T12:05:00Z|null",
  "lastFailNote": "string|null",
  "recordedBy": { "role": "TECHNICIAN|PROGRAMMER", "techLinkId": "uuid|null" }
}
```

`ProjectProgress` (commissioning-scoped shape; current implementation)
```json
{
  "projectId": "uuid",
  "asOfGenerationRunId": "uuid|null",
  "counts": { "totalTargets": 0, "testedTargets": 0, "pass": 0, "fail": 0, "untested": 0, "percentComplete": 0.0 },
  "lastTestedAtUtc": "2026-03-19T12:05:00Z|null",
  "eventSections": {
    "system": {
      "counts": { "totalTargets": 0, "testedTargets": 0, "pass": 0, "fail": 0, "untested": 0, "percentComplete": 0.0 },
      "lastTestedAtUtc": "2026-03-19T12:05:00Z|null"
    },
    "driver": {
      "counts": { "totalTargets": 0, "testedTargets": 0, "pass": 0, "fail": 0, "untested": 0, "percentComplete": 0.0 },
      "lastTestedAtUtc": "2026-03-19T12:05:00Z|null"
    }
  },
  "devices": [
    {
      "deviceId": 0,
      "displayName": "string",
      "counts": { "totalTargets": 0, "testedTargets": 0, "pass": 0, "fail": 0, "untested": 0, "percentComplete": 0.0 },
      "lastTestedAtUtc": "2026-03-19T12:05:00Z|null"
    }
  ]
}
```

Event section rollup rule:
- `eventSections.system` is computed from extracted `events.system`.
- `eventSections.driver` is computed from extracted `events.driver`.
- For each extracted event item, expected targets are the labels in `userFacing.testTargets` with `true` values, producing `event:{eventId}:{label}` targetKeys.

Progress shape note:
- Current implementation exposes commissioning progress only; it omits page-level rollups.
- If a future tech-scoped progress endpoint is added, it should reuse the same core counts and target-state rules.

## API v1 (minimum)

Base: `/api/v1`

### Commissioning Console UI
- Commissioning Console UI is website-hosted or reverse-proxied; Sentinel guarantees the API below.

### Commissioning API (authenticated; used by Commissioning Console UI)
- Prefix: `/api/v1/commissioning/...`

### Clients (Commissioning)
- `POST /api/v1/commissioning/clients` -> create client
  - req: `{ "name": "string" }`
  - resp: `Client`
- `GET /api/v1/commissioning/clients` -> list clients
- `GET /api/v1/commissioning/clients/{clientId}` -> client details

### Projects (Commissioning)
- `POST /api/v1/commissioning/clients/{clientId}/projects` -> create project under client
  - req: `{ "name": "string" }`
  - resp: `Project`
- `GET /api/v1/commissioning/clients/{clientId}/projects` -> list projects for client
- `GET /api/v1/commissioning/projects/{projectId}` -> project details

### Technician link issuance/rotation (Diagnostics)
- `POST /api/v1/commissioning/projects/{projectId}/tech-links`
  - behavior: create a new tech link (new tester) under the project
  - req:
    ```json
    { "label": "string|null" }
    ```
  - resp:
    ```json
    { "techLinkId": "uuid", "techUrl": "/testing/{techToken}" }
    ```

- `POST /api/v1/commissioning/projects/{projectId}/tech-links/{techLinkId}/rotate`
  - behavior: revoke prior token for this `techLinkId`, issue a new token (techLinkId remains stable)
  - resp:
    ```json
    { "techLinkId": "uuid", "techUrl": "/testing/{techToken}" }
    ```

### Uploads + regeneration (Diagnostics)
- `POST /api/v1/commissioning/projects/{projectId}/uploads` (multipart; file part name: `apex`) -> `Upload`
- `POST /api/v1/commissioning/projects/{projectId}/regenerate`
  - req: `{ "uploadId": "uuid" }`
  - resp: `{ "projectId": "uuid", "status": "READY" }`

### Extracted model + generated UI artifact
- `GET /api/v1/commissioning/projects/{projectId}/model` -> extracted project JSON (verbatim; no inference)
- `GET /api/v1/commissioning/projects/{projectId}/testing-ui` -> static HTML for latest generated artifact, or an explicit not-ready shell when no generation exists yet

### Commissioning reads for progress and failed-target triage
- `GET /api/v1/commissioning/projects/{projectId}/fail-tags` -> canonical `FailTag` catalog for the UI
- `GET /api/v1/commissioning/projects/{projectId}/progress` -> derived `ProjectProgress` for the commissioning console (device + event-section rollups; page detail optional/future)
- `GET /api/v1/commissioning/projects/{projectId}/fails` -> current fail/task-list projection for the commissioning console
  - each row is a `FailItem`

### Technician surface (token-scoped)
- `GET /testing/{techToken}` -> returns technician HTML for the project's current generated artifact
- `POST /api/v1/testing/{techToken}/results` -> append a `TestResultRecord`
- `GET /api/v1/testing/{techToken}/target-status?targetKey=...` -> derived `TargetStatus`

Future tech-scoped read endpoints may be added later, but they are not required for the current MVP contract.

### Live progress/events (optional for technician; required for diagnostics)
- `GET /api/v1/commissioning/projects/{projectId}/events` (SSE)

Event envelope:
```json
{
  "eventId": "uuid",
  "projectId": "uuid",
  "tsUtc": "2026-03-19T12:01:15Z",
  "type": "string",
  "scope": { "scopeType": "PROJECT|DEVICE|PAGE|EVENT_SECTION|TARGET", "deviceId": 0, "pageId": 0, "eventSection": "system|driver|null" },
  "target": { "targetKey": "string", "kind": "EVENT|BUTTON|VIEWPORT_BUTTON", "refs": {}, "targetName": "string" },
  "tag": "TARGET|SCOPE|DATA|RESOLUTION|UNKNOWN|null",
  "resolvedData": {},
  "data": {}
}
```

Minimum event types:
- `project.statusChanged` `{ "status": "EMPTY|STALE|READY|FAILED" }`
- `upload.received` `{ "uploadId": "uuid", "filename": "string", "sha256": "hex" }`
- `extraction.started|progress|succeeded|failed` `{ "extractionRunId": "uuid", ... }`
- `generation.started|progress|succeeded|failed` `{ "generationRunId": "uuid", ... }`
- `result.recorded` `{ "testResultId": "uuid", "targetKey": "string", "outcome": "PASS|FAIL" }`
- `fail.tagged` `{ "failId": "uuid", "tag": "TARGET|SCOPE|DATA|RESOLUTION|UNKNOWN", "target": { ... }, "scope": { ... }, "resolvedData": { ... } }`
- `fail.resolved` `{ "failId": "uuid", "tag": "TARGET|SCOPE|DATA|RESOLUTION|UNKNOWN", "target": { ... }, "scope": { ... }, "resolvedData": { ... } }`

## Error codes (minimum set)

- `CLIENT_NOT_FOUND`
- `PROJECT_NOT_FOUND`
- `TECH_LINK_REVOKED`
- `MODEL_NOT_READY`
- `GENERATION_NOT_READY`
- `APEX_UPLOAD_INVALID`
- `EXTRACT_FAILED`
- `GENERATE_FAILED`
- `FAIL_NOTE_REQUIRED`

