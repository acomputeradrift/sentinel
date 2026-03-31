# Testing Strategy

## Philosophy
1. Sentinel testing must prove that extraction and generation remain faithful to the approved JSON contracts and to the RTI project data they are derived from.
2. Unit testing is focused on Sentinel's own development quality, not on commissioning the RTI project itself.
3. The generated HTML interface must be treated as contract-driven output, not as a loose visual approximation.
4. If a button or UI element represented in the extracted project data is missing, misplaced, misclassified, or generated with incorrect testing-target information, the relevant tests must fail.
5. Testing should favor deterministic, repeatable verification over subjective visual judgment.
6. Testing artifacts must be isolated from application files so test runs can be cleaned up completely without risking project code, approved documents, or source assets.

## Required Test Layers
1. Unit tests for extraction logic that maps `.apex` source data into project-specific JSON shaped by `apex_project_structure_v4.json`.
2. Unit tests for generation logic that combines project-specific JSON with Sentinel UI rules from `app_ui_structure.json`.
3. Contract tests that verify generated project JSON conforms to the approved project structure format.
4. Contract tests that verify Sentinel-only UI elements and interface behavior defined by `app_ui_structure.json` are rendered and behave as configured.
5. UI fidelity tests that verify generated buttons, UI elements, categories, coordinates, viewport content, and testing-target information match the extracted project-specific JSON where applicable.
6. Render-verification tests that fail when browser-rendered or computed button sizes and positions differ from the RTI-derived coordinates and dimensions represented in the generated project-specific JSON.
7. End-to-end tests that verify the expected flow from `.apex` upload to project-specific JSON generation to interface generation.
8. Regression tests that protect previously approved extraction rules, rendering behavior, and output structure from silent drift.

## Rule
1. New extraction or generation behavior is not complete until it is covered by tests that prove the intended contract and output.
2. A change that breaks contract structure, UI fidelity, or testing-target accuracy must be treated as a test failure even if the app still runs.
3. Tests must fail when generated HTML does not match the UI structure or testing-target information extracted from the `.apex` file.
4. Tests must fail when rendered or computed HTML sizes and positions differ from the RTI-derived button data that Sentinel is supposed to represent.
5. Deterministic outputs and traceable failures are required so regressions can be identified quickly.
6. Test coverage does not justify violating approved data contracts or weakening output accuracy.
7. All test outputs, temporary files, generated fixtures, and review artifacts must live in tightly separated testing-only locations so they can be removed safely without touching app files.
8. Test cleanup must be part of the testing method, and stale artifacts must not be allowed to accumulate in project folders in ways that can affect later test results.

---

