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
9. Tests must not be the sole measure of safe change.
10. Changes affecting shared UI, layout, or styling must include explicit validation of unaffected areas, even if tests pass.

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

## Local execution (Windows + PowerShell)

**Goal:** run the same dependency stack for HTTP/FastAPI tests and Playwright UI tests, without relying on “whatever `python` is on PATH” (IDE agents often use a different interpreter than your activated venv).

### One-time: create `.tmp_apex_env` and install deps

From the repo root:

```powershell
python devtools/bootstrap_tmp_apex_env.py
```

This creates `.tmp_apex_env` if missing, then runs `pip install -U pip`, `pip install -e ".[dev]"` (core deps + Playwright), and `playwright install chromium`. The directory is gitignored.

### Regression suite (matches CI intent)

```powershell
python devtools/run_regression_with_venv.py
```

This invokes `.tmp_apex_env\Scripts\python.exe` with `PYTHONPATH=src` and discovers `dev_tests/regression`. It also writes `devtools/last_regression_run.txt` (gitignored) so tools that do not capture stdout can still read full output.

GitHub Actions runs the same discovery: `python -m unittest discover -s dev_tests/regression -p "test_*.py"` after `pip install -e ".[dev]"`.

### Optional: Postgres-backed tests

Several regression tests require **`DATABASE_URL`** (PostgreSQL connection string) to be set in the environment. If it is unset, those tests **skip**—not fail. Set it when you need to exercise persistence locally, for example:

```powershell
$env:DATABASE_URL = "postgresql://user:pass@localhost:5432/sentinel"
python devtools/run_regression_with_venv.py
```

### UI / Playwright tests

Use the same venv Python so Chromium and imports match:

```powershell
$env:PYTHONPATH = "src"
.\.tmp_apex_env\Scripts\python.exe -m unittest dev_tests.ui.test_testing_result_posting -v
```

Broader UI discovery is possible but slower; prefer targeted modules during development.

### Playwright Cursor skill (reference, not a repo copy)

**Decision:** Sentinel does **not** vendor a duplicate of the Playwright skill inside this repository. The canonical instructions live in the **Playwright** skill configured in Cursor (see **Cursor Settings → Skills** for the resolved path to `SKILL.md`). On typical Codex-style layouts the same file is also at `%USERPROFILE%\.codex\skills\playwright\SKILL.md`.

**When agents must apply it**

- Before doing **CLI-first** Playwright work from the terminal (`playwright-cli` / the skill’s wrapper script): **read that `SKILL.md` first** and follow its workflow (open → snapshot → interact by ref → re-snapshot, artifact locations, guardrails).
- When **debugging or reproducing** UI behavior outside a committed `unittest` module (ad hoc navigation, screenshots, traces): use the skill’s patterns and, for artifacts in this repo, prefer **`output/playwright/`** as described in the skill.

**What the skill does not replace**

- **Automated test gates** stay **`python devtools/run_regression_with_venv.py`** and targeted **`.tmp_apex_env\Scripts\python.exe -m unittest dev_tests.ui…`** as above. Those use the Python Playwright API and pinned deps; passing them is still the project’s definition of “tests pass” for committed UI tests.

---

