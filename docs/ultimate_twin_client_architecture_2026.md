# Ultimate Twin-Client Web App Architecture Guide (2026)

*(Integrated baseline: structure + code quality + real-time systems)*

------------------------------------------------------------------------

## 1. Product Intent & Boundaries

-   Define what each client can and cannot do
-   Server is the source of truth for rules and validation
-   Non-goals prevent architectural drift
-   Permissions enforced server-side only

------------------------------------------------------------------------

## 2. System Shape & Separation of Concerns (SRP)

-   UI, state, networking, backend are strictly separated
-   Each module has one responsibility (SRP)
-   Backend = modular monolith unless proven otherwise
-   No cross-layer shortcuts

------------------------------------------------------------------------

## 3. Contracts & Data Integrity (DRY)

-   All APIs and events use versioned schemas
-   **DRY here:** one canonical definition of payloads and errors (generate or verify types for server + both clients)
-   Commands vs queries are distinct
-   Invalid data rejected early on the server

------------------------------------------------------------------------

## 4. Identity, Sessions & Trust Boundaries

-   Server verifies identity on every request and WS connection
-   Secure, short-lived sessions/tokens
-   Multiple clients/tabs treated independently
-   Authorization is never UI-driven

------------------------------------------------------------------------

## 5. Real-Time Architecture (OCP + DIP)

-   WebSocket is transport only
-   System is event-driven and extensible (OCP)
-   Clients depend on event contracts, not implementations (DIP)
-   Reconnect via snapshot/cursor, not blind replay

------------------------------------------------------------------------

## 6. Deterministic State & Update Ordering

-   One authoritative path applies domain state transitions (usually server-side handlers)
-   **Ordering:** assign sequence numbers or causal ordering so clients and WS streams apply updates in a defined order
-   **Idempotency:** commands tolerate retries and double-submits without duplicate effects
-   Clients hold **projected** state only; they react to server facts/events, not parallel “second sources” of truth

------------------------------------------------------------------------

## 7. Coupling, Cohesion & Structure (ISP + LSP)

-   Low coupling via clear interfaces
-   High cohesion: related logic grouped
-   Interfaces are small and focused (ISP)
-   Implementations remain interchangeable (LSP)

------------------------------------------------------------------------

## 8. Controlled Side Effects (SRP + DIP)

-   External actions (API, WS, DB) are isolated
-   Core logic remains pure
-   Side effects behind well-defined interfaces (DIP)
-   No hidden mutations

------------------------------------------------------------------------

## 9. Quality, Testing & Consistency

-   Unit tests for logic, contract tests for APIs, minimal E2E
-   Tests validate contracts and state behavior
-   One pattern per concern across the codebase
-   Types and validation enforced in CI

------------------------------------------------------------------------

## 10. Observability, Errors & Evolution (OCP)

-   Structured logs with correlation across HTTP + WS
-   Errors are explicit and traceable
-   System evolves by adding, not modifying core paths (OCP)
-   Backward-compatible changes only

------------------------------------------------------------------------

# Core Principles

-   DRY → Single source of truth for **contracts and shared types**; single path for **state transitions** (see §3 and §6)
-   SRP → Each module has one responsibility
-   OCP → Extend behavior without breaking existing systems
-   LSP → Replace components without side effects
-   ISP → Small, focused interfaces
-   DIP → Depend on abstractions, not implementations
