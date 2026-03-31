# System Invariants

## Non-Negotiable Truths
1. Sentinel must never continue in a silent, unstable, partially valid, or untrusted state.
2. Project-specific JSON must remain traceable to the uploaded `.apex` file and must conform to the approved `apex_project_structure_v4.json` contract.
3. Sentinel-owned interface behavior must remain governed by `app_ui_structure.json` and must not be mixed into `.apex`-derived project data.
4. Test history must be append-only and must not be erased, overwritten, or collapsed by regeneration or retesting.
5. Equivalent approved inputs and configurations must produce consistent and repeatable outputs and behavior.
6. Critical flows must be event-logged from day one so important actions, failures, and transitions are traceable.
7. If a button, UI element, or testing target exists in the extracted project data, Sentinel must not silently omit or misrepresent it in generated output.
8. Testing artifacts must remain tightly separated from app files so cleanup can happen safely without risking application code, approved docs, or source assets.
9. Shared logic must not be reimplemented in conflicting ways when a single reusable function or module can enforce the same behavior correctly.
10. Failure handling must provide verbose, useful information about what failed, where it failed, and why the app cannot safely continue or complete the current operation.
11. A failed test result must always include notes so the failure is useful for troubleshooting and follow-up work.

## Violation Rule
1. Output is invalid if any invariant is broken.
2. Processing must stop when an invariant breach creates an unstable, partial, or untrustworthy state.
3. Failures must be made explicit through logging and user-visible failure handling rather than silent fallback.
4. Critical failures must provide enough detail for the user or developer to understand the cause, affected stage, and required next action.
5. Recovery may continue only after the app returns to a stable and trusted state.
6. Human review is required before accepting results from any flow that previously violated an invariant.

---

