# Data Contracts

## Allowed Inputs
1. An RTI project `.apex` file used as the source for extraction.
2. A template `apex_project_structure_v4.json` that defines the required generated project-data format for any extracted RTI project.
3. A template `app_ui_structure.json` that defines how generated project data is turned into the event testing and device testing interfaces.
4. User testing actions, including pass, fail, timestamps, and required fail notes for failed results.
5. Updated `.apex` files for regeneration within the same commissioning session.

## Allowed Outputs
1. A project-specific JSON file generated from the uploaded `.apex` file and shaped according to the `apex_project_structure_v4.json` template.
2. Event testing and device testing interfaces generated from the project-specific JSON file together with the `app_ui_structure.json` template.
3. Generated project data that includes source metadata, events, and devices derived from the uploaded `.apex` file.
4. User-facing device data that includes display names, device UI information, pages, button categories, viewports, and test targets.
5. Diagnostics data that includes event details, device/page context, button identity, viewport structure, and troubleshooting-relevant target details.
6. Persistent test-result records that preserve append-only commissioning history across regeneration.

## Forbidden Data Behavior
1. Writing inferred or guessed data into generated project JSON when that data is not directly supported by the source `.apex` file.
2. Producing project-specific JSON that breaks the structure defined by the `apex_project_structure_v4.json` template.
3. Producing generated interfaces that do not follow the rendering and behavior rules defined by `app_ui_structure.json`.
4. Accepting or storing a failed test result without the notes required to make that failure useful for troubleshooting.
5. Generating outputs that lose traceability back to the uploaded `.apex` file and the generation session that produced them.
6. Deleting, replacing, or collapsing prior historical test results when new results are recorded.

## Derived Read Models
1. Current test state is derived from append-only test history, not stored as a separate mutable truth.
2. For each `targetKey`, the latest record determines `currentOutcome`, `lastTestedAtUtc`, and `lastFailNote`.
3. Commissioning `progress` and `fails` views are read models derived from the latest extracted project model plus the latest result per target.
4. The commissioning fail/task-list view may surface `tag`, `target metadata`, `scope`, `resolvedData`, `currentOutcome`, `lastTestedAtUtc`, `lastFailNote`, and `recordedBy` for operator triage.
5. `FailTag` is a stable v1 classification enum; clients must treat it as the source of truth for filtering and grouping fail tasks.
6. Page-level progress is optional/future; current implementation requires device-level and event-section rollups at minimum.

---

