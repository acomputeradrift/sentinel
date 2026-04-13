# Sentinel Bootstrap (Low-Token)

Use this file as the first read in new chats.

## Read First

1. `docs/diagrams/sentinel_system_context.mmd`
2. `docs/diagrams/sentinel_inprocess_architecture.mmd`
3. `docs/directives/dev_environment_and_workflow.md`
4. `AGENTS.md`

**Optional (navigation-heavy tasks):** for a file-by-file index of paths and module roles, read `codebase_map.md`. Skip it for small, localized changes where the area is already known.

## Initial Response Contract

After reading, respond with exactly 8 bullets:

- runtime flow
- key routers
- core services
- persistence + migrations
- commissioning UI wiring
- testing flow (HTTP + WS)
- test strategy
- deploy guardrails + top risks

Then proceed with the user task.

## Prompt Template (for new threads)

`Read bootstrap.md, then do: <task>`

## Optional Task Scope Add-On

When needed, append:

- Backend only: `Focus on src/sentinel/server/**`
- UI only: `Focus on src/sentinel/ui/commissioning/** and src/sentinel/generation/render_core.py`
- Deploy only: `Follow docs/directives/dev_environment_and_workflow.md strictly`
