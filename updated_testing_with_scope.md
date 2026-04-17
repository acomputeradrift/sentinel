# Updated testing with scope

Sentinel is a testing platform for RTI Integration Designer projects. Large deployments can expose tens of thousands of **test targets** (buttons, labels, links, and other programmable surfaces). When a control has a **tag**, the tag is only part of the story: **scope** decides which macro and variable definitions actually apply in that moment. Testing must record and replay that scope, or results will not line up with what the processor does at runtime.

---

## Why the tag alone is not enough

A **tag** (`ButtonTagId`) names a family of programming. The same tag can appear on **many** button instances across pages, rooms, sources, and viewports. Those instances can differ in:

- **Workspace scope** (where the page lives in the tree: room and source anchors from the page).
- **Page layer** and **viewport layer** overrides (default vs explicit room/source on layers).

So the tag does **not** identify a single command set. It identifies a *pool* of possible macro and variable rows; **runtime scope** is what picks which rows matter for a given placement.

---

## Is `buttonId` enough?

`ButtonId` is usually a strong anchor for *which physical control* you pressed, because it ties to one row in the button table and one placement path through layers.

But **scope still matters** for two reasons:

1. **The tag’s programming is scope-qualified.** Under one tag there can be multiple macro rows and multiple variable rows (Global, Source, Room, Controller, etc.). The integration runtime resolves which of those apply using the scope chain (viewport → page layer → workspace, with defaults falling through as in `rti_scope_doc.md`); the probe reports the result as **runtime scope**.

2. **The same `ButtonId` is not always one conceptual “target” forever.** If a project is edited so that a button moves layers or pages, `ButtonId` might be reused or the meaning of its scope context can change. For **stable test identity**, you want **button identity + the resolved scope context** you used when the test was recorded.

So: **`buttonId` is necessary but not sufficient** if your goal is “this exact macro/variable behavior in this exact runtime context.”

---

## How scoped macros and variables should be isolated (conceptual model)

Think in **layers of identity**:

### 1) Placement identity (where the control lives)

- Which **device** (processor / panel / client).
- Which **page** (and page name for humans).
- Which **button instance** (`ButtonId`).
- Optionally **layer ids** if you need to disambiguate duplicate placements during debugging.

This fixes *which control* was exercised.

### 2) Runtime scope (what context applies)

Resolve the three apex scope levels and the derived **runtime scope** (as in `apex_scope_doc.md` / the probe):

- **Workspace scope** — from the page’s workspace anchors.
- **Page layer scope** — from the hosting page layer (or default).
- **Viewport layer scope** — from the child layer when the button is inside a viewport (or default).

**Runtime scope** is what the processor uses to choose among scoped tag definitions.

### 3) Programming identity (what fired)

Under the tag, macros and variables are **not** a single blob. You isolate them by:

- **Macro ids** and **variable ids** from the database rows that are **in play** for that tag **after** scope resolution.
- Where multiple levels exist on the same tag (Global vs Source vs Room vs Controller), apply the product’s **level priority** (`rti_scope_doc.md`): higher-precedence level wins for the same tag.

So a **test target key** for a tagged control should combine:

- **Placement** (at least `ButtonId` + device + page),
- **Runtime scope** (room + source dimensions at minimum, as resolved),
- **The specific macro/variable (or step)** you are asserting against, when the test is about programming rather than pure UI.

That is how you separate “Circuit 6 - Toggle on this tile in Master Bath under this source” from “the same tag on another tile with different runtime scope,” even when the label looks identical.

---

## Practical rule of thumb

- **Tag** → names the programming family.
- **ButtonId** → names the control instance.
- **Runtime scope** → names *which* macro and variable rows from that family actually apply.
- **MacroId / VariableId (and sometimes macro step)** → names *which* concrete definition you tested.

If any of placement, scope, or programming id is wrong or missing, automated tests will look flaky or will validate the wrong behavior.

---

## Shared layers

A **shared layer** (`SharedLayerId`) is a reusable layer *definition*: one stack of graphics and controls that can be **placed** more than once. Each placement is a separate **`Layers`** row with its own `LayerId`, `PageId`, stacking order, and (when relevant) viewport linkage.

**Scope is resolved per placement**, not from `SharedLayerId` alone. That matters because:

- The same shared stack on **different pages** can sit under **different workspace scope** (page room/source from the tree).
- The same shared stack inside **different viewports** (or different hosts) can sit under **different page-layer and viewport-layer** chains.

So two buttons can share a tag and even share a **shared layer design**, yet still be **different test targets** if their resolved **runtime scope** differs.

For testing identity: **`SharedLayerId` is not a substitute for `ButtonId` + runtime scope.** It helps you understand *reuse* in the project file; it does not uniquely identify *which* macro/variable context applies until you resolve placement and scope for that instance.

---

## Revision history

| Date | Notes |
| ---- | ----- |
| (initial) | Why scope matters for Sentinel-style RTI testing; tag vs buttonId vs runtime scope; how to think about isolating scoped macros and variables without relying on tag alone. |
| (revision) | Shared layers: reuse vs per-placement scope; why `SharedLayerId` does not replace placement + runtime scope for test identity. |
