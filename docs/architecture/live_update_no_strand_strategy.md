# Live Update No-Strand Strategy

## Purpose

Define how Sentinel should support production updates without stranding ongoing commissioning/testing jobs.

This is a planning document for later implementation.

## Current Risk Summary

1. Service restart disconnects active WebSocket sessions.
2. If persistence is in-memory, restart loses active link/session/job state.
3. Single-instance deploy has an unavoidable interruption window.
4. New code may come up while clients are still on old runtime state.

## Required Operating Guarantees

1. Existing projects and tech links remain valid across deploy.
2. Existing test history and fail tags remain available across deploy.
3. Active users reconnect automatically and recover latest state.
4. Deploy does not silently drop in-flight job context.
5. Rollback can be executed quickly without data loss.

## Target Production Model

### 1) Persistent Source of Truth

1. Postgres is mandatory in production.
2. Startup should fail fast in production mode if `DATABASE_URL` is missing.
3. Job/session-critical state must not rely on process memory only.

### 2) Health and Drain Contract

Add two health modes:

1. `live`: process is running.
2. `ready`: instance can accept new work.

Deploy sequence:

1. Set `ready=false` (drain mode) on one instance.
2. Stop accepting new write/start actions on that instance.
3. Keep existing connections alive for a short drain grace window.
4. Update and restart drained instance.
5. Wait for `ready=true`.
6. Repeat for next instance.

### 3) Client Resume Contract

1. Client auto-reconnect with bounded backoff.
2. On reconnect, client requests project snapshot + latest target statuses.
3. WS replay uses project sequence where available, then snapshot reconcile.
4. UI must show a visible reconnecting/resynced state, not silent failure.

### 4) Zero/Low-Downtime Topology

Preferred:

1. Two Sentinel app instances behind nginx upstream.
2. Rolling restart (one instance at a time).
3. Shared persistent storage for generated project artifacts (or single stable path both instances can read).

Fallback:

1. Single-instance with drain + fast restart + forced client resume.
2. Accept brief interruption but preserve job state via persistence.

## Phased Implementation Plan

### Phase 1: Safety Baseline

1. Enforce Postgres in production.
2. Add startup warning/error policy for in-memory repository in prod.
3. Add explicit operational runbook note: never deploy prod with in-memory repo.

### Phase 2: Readiness + Drain

1. Implement readiness state endpoint/control.
2. Gate new work while drained.
3. Add deploy script/runbook steps for drain-first rollout.

### Phase 3: Resume-First Clients

1. Add reconnect + resync path in testing and commissioning clients.
2. Add explicit "reconnected and synced" UX state.
3. Verify tech-link continuity and target-state continuity after restart.

### Phase 4: Rolling Deploy

1. Introduce dual-instance app service layout.
2. Configure nginx upstream for two backends.
3. Perform one-by-one restart deployment.

## Verification Checklist (Pre-Go-Live)

1. Start long-running active session with open WS connections.
2. Deploy new version with drain/rolling process.
3. Confirm:
   - no lost tech link access
   - no lost test results/fail tags
   - client reconnect occurs automatically
   - progress/target counts reconcile correctly after reconnect
4. Repeat during active writes (test-result posting) and confirm no duplicates/loss.

## Rollback Plan

1. Keep previous app build available.
2. If deploy health fails, route traffic to last healthy instance/build.
3. Do not run destructive cleanup during rollback.
4. After rollback, validate:
   - `/health` and readiness
   - active project access via tech link
   - latest target status retrieval

## Non-Goals (This Document)

1. No schema changes are implemented here.
2. No deployment automation is implemented here.
3. No runtime behavior changes are implemented here.
