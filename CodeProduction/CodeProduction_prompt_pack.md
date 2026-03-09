# CodeProduction Prompt Pack

These prompts are designed for use by the CodeProduction AI Agent.
They assume the agent has already loaded:

- project-root agents.md
- CodeProduction/agents.md
- testing_strategy.md

These prompts DO NOT restate authority or restriction rules.

All prompts below are listed in the order they should be used.

---

## Prompt 0 — Session Startup (Authoritative Inputs)

Use this ONCE at the start of a CodeProduction session.

```md
SESSION CONTEXT PROMPT

Component Name:
<<<COMPONENT_NAME>>> 

Authoritative Component Documents:
- /components/<<<COMPONENT_NAME>>>/discovery.md
- /components/<<<COMPONENT_NAME>>>/constraints.md
- /components/<<<COMPONENT_NAME>>>/design.md
- /components/<<<COMPONENT_NAME>>>/proven_findings.md

Authoritative Project Documents:
- /agents.md
- /mission.md
- /scope.md
- /invariants.md
- /data_contracts.md
- /testing_strategy.md

These documents define all allowable behavior for this session.
Acknowledge and confirm before proceeding.
```

---

## Prompt 1 — Pre-Implementation Readiness Check

Use this prompt before any code or tests are written.

```md
Review the authoritative documents loaded for this session.

Your task:
1. Confirm that the component behavior is sufficiently specified to proceed.
2. Identify any ambiguities, conflicts, or missing details that would block test creation.

Output:
- A clear READY or NOT READY decision.
- If NOT READY, list the blocking questions only.

Do NOT write tests or code.
Do NOT suggest solutions.
```

---

## Prompt 2 — Test-First Design

Use this prompt once the component is READY.

```md
Using only the authoritative documents:

1. Identify the behaviors that must be proven by tests.
2. Propose a test plan that maps each behavior to one or more tests.

Rules:
- Tests must directly correspond to documented requirements or constraints.
- Prefer deterministic, repeatable tests.
- Do not write code.
- Do not assume undocumented behavior.

Output:
- A structured list of tests with purpose and expected outcome.
```

---

## Prompt 3 — Write Tests Only

Use this prompt to create tests before implementation.

```md
Using the approved test plan:

1. Write the tests required to validate the documented behavior.
2. Ensure tests fail against the current implementation.

Rules:
- Do not write or modify production code.
- Do not introduce helper logic that implements behavior.
- Tests must be minimal and explicit.

Output:
- Test code only.
```

---

## Prompt 4 — Implement to Satisfy Tests

Use this prompt after tests exist and are failing.

```md
Your task is to modify production code so that all existing tests pass.

Rules:
- Do not change the tests.
- Do not introduce new behavior.
- Make the smallest possible changes.
- Follow existing patterns and conventions.

Output:
- Code changes only.
```

---

## Prompt 5 — Record Implementation Notes

Use this prompt immediately after tests pass.

```md
Based on coding and testing work just completed:

1. Create or overwrite the following file:
   /CodeProduction/ImplementationNotes/<<<COMPONENT_NAME>>>_implementation_notes.md

2. Record:
   - Observed runtime behavior
   - Edge cases encountered
   - Incorrect assumptions discovered
   - Constraints confirmed by tests

Rules:
- Facts only.
- No summaries or redesign.
- No future plans.
```

---

## Prompt 6 — Post-Implementation Sanity Check (Optional)

Use this prompt to ensure no authority violations occurred.

```md
Review the work just completed.

Confirm:
- All changes were driven by tests.
- No undocumented behavior was introduced.
- No authority documents were modified.
- Implementation notes were written correctly.

Output:
- Confirmation or list of violations.
```




# Component Update Prompt — Implementation Notes Ingestion

This prompt is used by the **Component AI Agent** after CodeProduction work
has completed for a component.

It assumes the agent has already loaded:
- project-root agents.md
- component-level agents.md
- the component documentation files

This prompt does NOT restate authority rules.

---

## Prompt — Update Proven Findings From Implementation Notes

Use this prompt when a new implementation notes file exists.

```md
SESSION CONTEXT

Component Name:
<<<COMPONENT_NAME>>>

Implementation Evidence Location:
/CodeProduction/ImplementationNotes/<<<COMPONENT_NAME>>>_implementation_notes.md

Component Knowledge Files:
- /components/<<<COMPONENT_NAME>>>/proven_findings.md
- /components/<<<COMPONENT_NAME>>>/open_questions.md

Your task:

1. Read the implementation notes file listed above.
2. Identify **narrow, factual statements** that are:
   - Directly observed during coding or testing
   - Clearly supported by the evidence
   - Specific enough to stand alone

3. Update `proven_findings.md` by:
   - Copying only those factual statements
   - Writing them as concise, testable facts
   - Preserving existing content

Rules:
- Do NOT summarize or generalize.
- Do NOT combine multiple observations into a rule.
- Do NOT invent conclusions.
- Do NOT remove or rewrite existing proven findings.
- If evidence contradicts existing findings, STOP and report.

Optional:
- If implementation notes resolve any previously listed unknowns,
  note which open questions are now answered.

Output:
- Updated `proven_findings.md` content only.
- No commentary.
```

## Usage Notes

- This prompt is run **after** CodeProduction testing is complete.
- It is safe across agent refresh.
- Human review is expected by reading the updated file.
- No additional promotion ceremony is required.

---

## Usage Notes

- Prompts are intentionally atomic.
- Use exactly one prompt per step.
- Safe across agent refresh.
- Humans remain in control of promotion to proven findings.
