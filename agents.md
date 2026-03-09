# agents.md

## Investigation and Discovery Workflow

During investigation or discovery sessions, the process must follow this workflow:

1. A working `.md` document will be created or explicitly referenced.
2. The user will ask a question or give a command.
3. The AI must display the results directly on screen for the user to examine.
4. The user may correct, modify, or refine the output.
5. After any user modification, the updated result must again be displayed on screen for review.
6. This review cycle continues until the user confirms the result.

Information may **only be added to the working document after explicit user confirmation**, such as statements including:

- “lock it down”
- “add it to the doc”

Until such confirmation is given, results must remain **temporary and displayed only for review**, not committed to the document.

---

## Verified Source Requirement

Before making any change to:

- output formats  
- investigation methods  
- discovery procedures  
- resolution methods  

the AI **must first reference the working `.md` document** to verify the currently approved information.

The working document is the **source of truth for verified knowledge** and must always be consulted before modifications are proposed or implemented.

---

## Proven Method Requirement

All methods must be based on **proven techniques**, not inference or guessing.

When a method has been demonstrated, reviewed, and approved by the user, it becomes the **standard method** for similar situations and must continue to be used unless the user explicitly changes it.

This requirement does **not prevent exploration in uncharted areas**. When no approved method exists, the AI may investigate and propose methods for review following the investigation workflow.

The AI must follow these rules:

- Use **proven code** when extracting or processing data.
- Use **only the files provided by the user** when performing analysis or extraction.
- Do **not infer missing information**.
- Do **not guess values or behavior**.
- Do **not fill in missing information**.
- Do **not reformat or reinterpret data** unless the user explicitly instructs it.

All outputs must be derived strictly from **verified inputs and approved methods**.