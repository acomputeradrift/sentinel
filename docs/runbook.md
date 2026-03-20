# Operational Runbook

## Supported Environments
1. A browser-based user interface used during live RTI commissioning.
2. A browser-based diagnostics interface used for upload, regeneration, monitoring, and troubleshooting during the same commissioning session.
3. A server-side environment that accepts `.apex` uploads, regenerates test structures, stores test history, and distributes live updates between interfaces.
4. Local onsite and remote support workflows where different people may need access to Sentinel during the same session.

## Normal Operation
1. A commissioning session is created and the current project `.apex` file is uploaded through the diagnostics interface.
2. Sentinel extracts a project-specific JSON file from the uploaded `.apex` file using the `apex_project_structure.json` template.
3. Sentinel generates or regenerates the event testing and device testing interfaces from the project-specific JSON file using the `app_ui_structure.json` template.
4. The user interface is used to execute tests across event testing and device testing areas.
5. Test results are recorded live as pass or fail, with timestamps captured for every result and fail notes required for failed targets.
6. The diagnostics interface receives live test activity, shows commissioning progress, and presents troubleshooting context for failed targets.
7. When project fixes are made, an updated `.apex` file is uploaded and the testing environment is regenerated without discarding prior test history.
8. Previously failed targets can be retested and updated while preserving append-only historical results.

## Failure & Recovery
1. If `.apex` generation fails, the failure must be visible in the diagnostics interface so the user knows the testing environment is not current.
2. If extraction cannot produce valid project-specific JSON or generation cannot proceed from the required JSON contracts, the failure must be visible in the diagnostics interface and must not silently produce a partial testing environment.
3. If uploaded project data changes after fixes, Sentinel must regenerate the testing structure while preserving prior recorded test history.
4. If a target that previously failed later passes, the new result updates current status but does not erase the earlier failure record.
5. If one interface becomes unavailable during a session, recorded test history and diagnostics context must remain recoverable when the session reconnects.
6. Recovery should favor fast continuation of commissioning work rather than requiring the entire testing process to restart.

## Development workflow (parallel work; non-conflicting)

1. The canonical interoperability contract is `docs/api_contract_v1.md` plus examples in `docs/contract_pack_examples_v1.json`.
2. Each sub-agent or major task must work in its own branch and worktree to avoid polluting `main`.
   - Branch naming convention: `codex/<agent>-<task>`.
   - Worktree location convention: `.worktrees/<agent>-<task>/`.
3. Work is merged back to `main` only after tests pass and the contract remains compatible (additive-only changes).

## Deployment workflow (single-server MVP; website-friendly)

1. The Sentinel server hosts:
   - the API under `/api/v1/...`
   - the technician entrypoint HTML under `/testing/{techToken}`
   - generated testing artifacts per project (served as static files)
2. Your public website can still “host” the panels by reverse-proxying to the Sentinel server (or by using a dedicated subdomain such as `sentinel.<domain>`).

---
