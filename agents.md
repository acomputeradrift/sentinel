# agents.md

## Scope

These rules apply to all work in this workspace unless the user explicitly overrides them.

---

## Investigation and Discovery Workflow

During investigation or discovery sessions, the process must follow this workflow:

1. A working `.md` document will be created or explicitly referenced.
2. The user will ask a question or give a command.
3. The AI must display the results directly on screen for the user to examine.
4. The user may correct, modify, or refine the output.
5. After any user modification, the updated result must again be displayed on screen for review.
6. This review cycle continues until the user confirms the result.

Information may only be added to a working document after explicit user confirmation, including statements such as:
- `lock it down`
- `add it to the doc`
- `approved`

Until such confirmation is given, results must remain temporary and displayed only for review, not committed to the document.

---

## Request Handling

- Answer the user's actual question directly before proposing adjacent work.
- Do not treat a question as permission to edit files.
- If the user asks for analysis, review, explanation, or suggestions, remain in review mode until explicit approval to edit is given.
- Do not redirect the task into a different task the AI assumes is more useful without first getting approval.

---


## Forward Progress Rule

When an investigation or discovery thread reaches a concrete, evidence-backed next step, the AI must proactively move the thread forward by presenting the next minimal change scope for approval.

The AI must not wait for an extra user prompt such as:
- `proceed`
- `go ahead`
- `what next`

if the next scoped action is already clear from the investigation.

Required behavior:
- after presenting investigation findings, the AI should immediately offer the smallest reasonable approval scope that would implement or document the next step
- the scope must still follow all existing approval rules
- the AI must not make edits without approval
- the AI must not skip scope presentation
- the AI should only stop without offering scope when:
  - the user explicitly says they want analysis only
  - the next step is genuinely unclear
  - multiple materially different paths exist and need user choice first

Example expected behavior:
1. investigate and display findings
2. identify the most likely proven next step
3. immediately present the scoped file list and purpose
4. wait for `approved`


## Approval Scope

- Before making edits, the AI must present the proposed change scope.
- The proposed change scope must include:
  - the purpose of the change
  - the files proposed for editing
  - the reason each file is included
  - any relevant context that makes those files necessary
- Approval of that proposed scope counts as approval for all listed files within that change.
- The AI must not expand beyond the approved file scope without returning for approval.
- If new files become necessary during implementation, the AI must stop and present the expanded scope before editing them.

---

## Scoped Execution

- Once the user approves a proposed change scope, the AI should complete that scoped work without asking for repeated per-file approvals.
- The AI must not make unrelated edits, cleanup changes, or opportunistic improvements outside the approved scope.
- If the user request is analysis, review, brainstorming, or discovery only, no edit scope should be assumed.

---

## Edit Boundaries

- Change only the files required for the approved task.
- Never modify neighboring files, cleanup unrelated issues, or apply “while I’m here” changes unless the user explicitly approves that broader scope.
- Never rewrite or replace existing documents or code outside the approved target without explicit confirmation.
- If a requested change appears to require additional files, show the user the exact expanded scope before editing.

---

## Verified Source Requirement

Before making any change to:
- output formats
- investigation methods
- discovery procedures
- resolution methods

the AI must first reference the relevant working `.md` document to verify the currently approved information.

The working document is the source of truth for verified knowledge and must always be consulted before modifications are proposed or implemented.

---

## Proven Method Requirement

All methods must be based on proven techniques, not inference or guessing.

When a method has been demonstrated, reviewed, and approved by the user, it becomes the standard method for similar situations and must continue to be used unless the user explicitly changes it.

This requirement does not prevent exploration in uncharted areas. When no approved method exists, the AI may investigate and propose methods for review following the investigation workflow.

The AI must follow these rules:
- Use proven code when extracting or processing data.
- Use only the files provided by the user when performing analysis or extraction.
- Do not infer missing information.
- Do not guess values or behavior.
- Do not fill in missing information.
- Do not reformat or reinterpret data unless the user explicitly instructs it.

All outputs must be derived strictly from verified inputs and approved methods.

---

## Communication Rules

- Keep responses concise and directly relevant to the request.
- Default to short answers unless the user explicitly asks for depth.
- Do not produce long multi-step plans unless they are necessary for the task.
- Avoid padded explanations, unnecessary recap, or broad unsolicited advice.
- Proposed changes should be presented briefly, with enough context to support a single approval decision.

---

## No Assumption Changes

- Do not infer missing user intent and begin making changes from that inference.
- When intent is unclear, present the smallest reasonable temporary draft or ask a short clarifying question.
- Do not convert ambiguous direction into implementation without confirmation.

---

## Change Control

- No document or code file may be edited until the user gives explicit approval.
- Locked files or user-designated source-of-truth documents must not be changed without explicit approval in the current thread.
- If an approved rule, contract, or workflow would be changed by a new request, the AI must call out that impact before editing.

---
