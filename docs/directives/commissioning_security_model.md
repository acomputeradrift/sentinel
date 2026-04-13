# Commissioning security model

## Deployment intent

Sentinel exposes two browser-facing surfaces:

1. **Commissioning console** — `/commissioning` static UI plus `/api/v1/commissioning/*` HTTP and WebSocket.
2. **Technician testing shell** — `/testing/{techToken}` and `/api/v1/testing/{techToken}/*` scoped by rotating technician tokens.

Commissioning routes are **project-scoped by UUID**. Without additional controls, anyone who can reach the network and obtain or guess a `projectId` could read or mutate commissioning data.

## Optional API key (recommended for any shared network)

When the environment variable `SENTINEL_COMMISSIONING_API_KEY` is set to a non-empty string:

- Every HTTP request to `/api/v1/commissioning/*` must include the same value in header `X-Sentinel-Commissioning-Key` (or `Authorization: Bearer <value>`).
- WebSocket upgrades to `/api/v1/commissioning/projects/{projectId}/ws` must include the value as query parameter `commissioningKey` (browsers cannot attach arbitrary headers to `WebSocket`).

When the variable is **unset**, commissioning endpoints accept anonymous access (local development default).

## UI configuration

Operators may store the key once in **localStorage** as `sentinel.commissioning.apiKey`. The commissioning UI sends it on REST calls and appends it to the commissioning WebSocket URL.

## Technician tokens

Technician links use opaque `techToken` values, rotation, and explicit revoke. Invalid or revoked tokens return `410` / `TECH_LINK_REVOKED` on HTTP and WebSocket.

## Reverse proxy

For production, combine application-level commissioning key (or future session auth) with network controls: bind the app to loopback, terminate TLS at nginx, and restrict source IPs as appropriate.
