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
| `commissioning_snapshot` | Includes `seq`, `projectId`, `progress`, `rollups`, `activities`, `fails`, `activeUpload`. |
| `replay.batch`         | `afterSeq`, `latestSeq`, `events[]` (each event includes `seq` when sourced from the broker ring buffer). |
| `generation_phase`     | Transient progress; `status`, `percent`, optional `uploadId` / `originalFilename` / `activeUpload`. |
| `generation`           | Terminal generation envelope (`status: READY`, etc.). |
| `fail_tag_updated`     | Emitted after fail-tag mutation. |
| `keepalive`            | `{}` with `type: keepalive` only. |
| `error`                | `code` such as `PROJECT_NOT_FOUND`, `UNKNOWN_MESSAGE`. |

### Ordering

Clients should apply broker events in **`seq` ascending** order and treat `commissioning_snapshot` as authoritative when the server signals a non-replayable gap (`replayableFromSeq` semantics on the server).

## Testing — `GET ws` `/api/v1/testing/{techToken}/ws`

### Server → client

| type                | Notes |
|---------------------|--------|
| `testing_snapshot`  | `seq`, `projectId`, `results[]` (latest-per-target projection). |
| `test_result`       | Includes optional embedded `progress` and `rollups` for technician UI. |
| `keepalive`         | Same as commissioning. |
| `error`             | e.g. `TECH_LINK_REVOKED`. |

Technician HTTP `POST /api/v1/testing/{techToken}/results` accepts optional header **`Idempotency-Key`**; duplicate keys return the first stored JSON body without inserting a second row.
