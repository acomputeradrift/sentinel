# Scope Definition

## In Scope
1. Generating a project-specific JSON file from a project's `.apex` file using the `apex_project_structure.json` template, and generating the user testing interface from that project-specific JSON using the `app_ui_structure.json` template.
2. Supporting two user-facing testing areas within that interface: event testing and device testing.
3. Generating a diagnostics interface for `.apex` upload, project-data regeneration, test-environment regeneration, live monitoring of results, and troubleshooting support.
4. Preserving testing continuity across updated `.apex` uploads so commissioning can continue after project fixes.
5. Recording pass/fail results, timestamps, fail notes, and append-only test history for each test target.
6. Producing device testing views that reflect the RTI project structure closely enough to support practical commissioning and validation.
7. Providing navigation through generated device pages in a way that follows the structure of the RTI project.
8. Supporting layer visibility controls when needed to inspect overlapping buttons or crowded UI pages.

## Out of Scope
1. Acting as the live RTI control system for end users.
2. Replacing RTI programming tools or becoming a full RTI project editor.
3. Fancy graphics, high-fidelity visual simulation, or presentation polish beyond what is needed for effective commissioning.
4. Unnecessary workflow complexity, complicated wording, or features that do not directly support testing and troubleshooting.
5. Manual recreation of project testing structure when it can be generated from the `.apex` file.

## Deferred
1. Final decisions on the exact tech stack for browser clients, server components, and APIs.
2. The exact collaboration model for local onsite users and remote support users working at the same time.
3. Session-link and upload-flow details for multi-upload commissioning sessions.
4. The exact shape of diagnostics task management for follow-up programming work.

---
Scope changes require explicit human approval.
