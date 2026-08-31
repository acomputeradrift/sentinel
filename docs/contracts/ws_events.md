# WebSocket event contracts (Sentinel)

This document summarizes **stable JSON message types** exchanged over project-scoped WebSockets. Payloads are JSON objects; the server assigns monotonic `seq` on persisted broker events where noted.

## Commissioning — `GET ws` `/api/v1/commissioning/projects/{projectId}/ws`

### Client → server

| type           | Fields | Purpose |
|----------------|--------|---------|
| `sync.request` | `lastAppliedSeq` (int) | Request `replay.batch` or a fresh `commissioning_snapshot` if the gap cannot be replayed. |

### Server → client

| type                    | Notes |
|-------------------------|--------|
| `commissioning_snapshot` | Includes `seq`, `projectId`, `progress`, `rollups`, `activities`, `fails`, `activeUpload`, `testingTypeSettings`. `activities` rebuild from latest-per-target as individual `test_result` rows. Group-pass items keep `batchId` / `source=GROUP` for reports. Progress/fails/pies exclude disabled testing types. |
| `replay.batch`         | `afterSeq`, `latestSeq`, `events[]` (each event includes `seq` when sourced from the broker ring buffer). |
| `generation_phase`     | Transient progress; `status`, `percent`, optional `uploadId` / `originalFilename` / `activeUpload`. |
| `generation`           | Terminal generation envelope (`status: READY`, etc.). |
| `fail_tag_updated`     | Emitted after fail-tag mutation. |
| `test_result`          | One recorded outcome; commissioning pies follow on `commissioning_rollups`. |
| `test_results.batch`   | Group pass/fail: `count`, `targetKeys[]`, `batchId`, `source=GROUP`. Pies follow on `commissioning_rollups`. Snapshot rebuild uses the same `batchId` on stored rows. |
| `testing_type_settings` | Per-project type toggles: `disabledTypes[]`, `types[]`, `offBehavior=exclude`. Followed by `commissioning_rollups` so pies match. |
| `keepalive`            | `{}` with `type: keepalive` only. |
| `error`                | `code` such as `PROJECT_NOT_FOUND`, `UNKNOWN_MESSAGE`. |

### Ordering

Clients should apply broker events in **`seq` ascending** order and treat `commissioning_snapshot` as authoritative when the server signals a non-replayable gap (`replayableFromSeq` semantics on the server).

## Testing — `GET ws` `/api/v1/testing/{techToken}/ws`

### Server → client

| type                | Notes |
|---------------------|--------|
| `testing_snapshot`  | `seq`, `projectId`, `results[]` (latest-per-target projection, including `batchId` and `source`), `testingTypeSettings` (`disabledTypes[]`; missing means all types ON). |
| `test_result`       | Includes optional embedded `progress` and `rollups` for technician UI. |
| `test_results.batch` | Compact ack after `test_result.submit_batch`: `outcome`, `count`, `targetKeys[]`, `results[]`, `batchId`, `source`. Commissioning Live Status fans each result into its own row. Does not embed per-row progress; `commissioning_rollups` follows. |
| `testing_type_settings` | Same payload as commissioning; technician pages drop disabled types from popups, group select, and pass/fail rings without hiding drawn controls. |
| `keepalive`         | Same as commissioning. |
| `error`             | e.g. `TECH_LINK_REVOKED`. |

Technician HTTP `POST /api/v1/testing/{techToken}/results` accepts optional header **`Idempotency-Key`**; duplicate keys return the first stored JSON body without inserting a second row.

Technician client → server on the same testing socket:

| type | Fields | Purpose |
|------|--------|---------|
| `test_result.submit` | `target`, `outcome`, optional `failNote` | Record one result. |
| `test_result.submit_batch` | `targets[]`, `outcome`, optional `failNote` | Record many results in one message (group pass). FAIL still requires a note. |
