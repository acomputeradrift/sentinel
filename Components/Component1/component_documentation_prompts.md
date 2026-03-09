# Component Documentation Prompt Pack

These prompts are designed to be used AFTER a fact-finding conversation.
They assume the Component Agent has already loaded:
- project-root agents.md
- component-level agents.md
- the component document templates

These prompts DO NOT restate agent rules.

---

## Prompt 1 — Guided Information Gathering (Interactive)

Use this prompt when the component documents are empty or partially filled
and you want the agent to ask you for the missing information.

```md
You have access to the component documentation templates:
- discovery.md
- constraints.md
- design.md
- open_questions.md

Your task is NOT to fill them yet.

Instead:
1. Read the templates.
2. Identify all placeholders that require human-provided information.
3. Ask me targeted questions to gather ONLY that information.

Rules:
- Ask questions section by section.
- Do not assume or infer answers.
- Do not suggest solutions or designs.
- Do not fill any document yet.

Wait for my answers before proceeding.
```

---

## Prompt 2 — Fill Component Documents From Collected Answers

Use this prompt AFTER Prompt 1 has been completed and answered.

```md
Using only the answers I have provided:

1. Fill out the following documents:
   - discovery.md
   - constraints.md
   - design.md
   - open_questions.md

2. Replace placeholders completely.
3. Do not add any information not explicitly stated.
4. Preserve the structure of the templates.

Output:
- Provide the full contents of each document separately.
- Do not merge documents.
- Do not add commentary.

If any placeholder cannot be filled due to missing information, STOP and ask.
```

---

## Prompt 3 — Incremental Update (Multi-Day Discovery)

Use this prompt when discovery spans multiple sessions.

```md
The following component documents already exist:
- discovery.md
- constraints.md
- design.md
- open_questions.md

New information has been learned during discussion.

Your task:
1. Ask me which document(s) are allowed to be updated in this session.
2. Ask targeted questions only for those documents.
3. Propose exact text changes, not summaries.

Rules:
- Do not rewrite existing content unless explicitly instructed.
- Do not remove historical information.
- Do not update proven_findings.md.
```

---

## Prompt 4 — Consistency Check (Optional)

Use this prompt to sanity-check component docs before code work begins.

```md
Review the following component documents for internal consistency:
- discovery.md
- constraints.md
- design.md

Check for:
- Contradictions
- Scope leakage
- Design statements violating constraints

Output:
- A list of issues, if any.
- No corrections.
- No rewriting.
```

---

## Usage Notes

- These prompts are intentionally narrow.
- They rely on agents.md for behavior control.
- They are safe across context refreshes.
- They keep humans in control of truth.

