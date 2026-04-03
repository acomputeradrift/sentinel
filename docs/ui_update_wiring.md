# UI Update Wiring

## Phase 1: Recovery (Get Runtime Working Again)

Purpose:
- Restore Commissioning + Diagnostics runtime behavior after static HTML/CSS preview changes.
- Do not add new features in this phase.

Scope files (recovery):
- `src/sentinel/ui/commissioning/index.html`
- `src/sentinel/ui/commissioning/diagnostics_tab.js`
- `src/sentinel/ui/commissioning/commission_tab.js` (only if selector/column wiring requires it)
- `src/sentinel/ui/commissioning/commissioning.js` (only if tab/default flow wiring requires it)

Out of scope (Phase 1):
- New sorting behavior logic.
- Tech Notes popup behavior.
- New pie-chart business logic.

---

## Verified Current Breakpoints

1) JS disabled in `index.html`
- Current state: all script tags are commented out.
- Impact: no live tab behavior, no websocket/store rendering, no live table/pie updates.

2) Diagnostics table header order changed, but JS row construction order is legacy
- HTML current Diagnostics order:
  - `Status`, `Timestamp`, `Device`, `Page Name`, `Layer`, `Viewport`, `Button Identity`, `Test Target`, `Effective Scope`, `Tech Notes`
- `diagnostics_tab.js` currently appends row cells in this order:
  - `Status`, `Timestamp`, `Device`, `Page`, `Layer`, `Viewport`, `Button`, `Target`, `Resolved/Note`, `Scope`
- Impact: live data will land in wrong columns (`note` and `scope` swapped vs current headers).

3) Static preview overrides are controlling visibility
- `panel-commission`/`panel-diagnostics` are manually toggled for preview in HTML.
- Runtime expects JS tab-state control.

4) CSS rename completed
- Base stylesheet now `sentinel_console.css`.
- `index.html` already references the new filename.
- No further filename fix required here.

---

## Phase 1 Recovery Plan (Execution Order)

1. Re-enable runtime scripts in `index.html`
- Un-comment:
  - `commissioning.js`
  - `commission_tab.js`
  - `diagnostics_tab.js`
- Remove static-only assumptions where needed (manual tab forcing should not block JS tab control).

2. Align Diagnostics live row mapping to current table header order
- In `diagnostics_tab.js`, update `tr.appendChild(...)` order and row-update mapping so data lands in:
  - `... Test Target, Effective Scope, Tech Notes`
- Keep current header labels/content unchanged.

3. Validate required IDs/classes used by JS still exist in HTML
- Must remain present:
  - Tabs/panels: `tab-*`, `panel-*`
  - Diagnostics: `diagnosticsSummary`, `diagnosticsTaskBody`, `diagnosticsStatus`
  - Commissioning: `commissionPies`, `commissionActivityBody`, `commissionActivity`
  - Manage selectors: `clientSelect`, `projectSelect`

4. Verify tab activation ownership
- Ensure initial tab selection is controlled by JS flow, not hard-coded preview state.
- Keep the current tab list/content labels intact.

5. Smoke-check live hydration path
- On load with a selected project:
  - Commissioning activity table populates.
  - Diagnostics task list populates with columns aligned correctly.
  - Pie cards render from runtime data without selector errors.

---

## Minimum "Working Again" Definition (Phase 1 Exit Criteria)

Pass criteria:
1. JS loads without missing-element exceptions in browser console.
2. Clicking `Commissioning` and `Diagnostics` switches panels normally.
3. Commissioning table rows render live data into correct columns.
4. Diagnostics table rows render live data into correct columns (including `Effective Scope` and `Tech Notes` positions).
5. Diagnostics and Commissioning pies update from runtime data (no static-only lockout).

Fail criteria:
- Any runtime data appearing under wrong column header.
- Tabs not switching due to static HTML lock.
- Scripts not running because tags remain commented.

---

## Phase 2 Placeholder (Not Executed Yet)

After Phase 1 passes, document and implement:
- Header-click sorting behavior.
- `Show` button behavior contract for Tech Notes popup.
- Final pie data contracts (source fields, aggregation, category mapping).

---

## Placeholder Replacement Rules (Documented)

### Context Group Box (`Client -> Project -> Filename`)

Rule:
- Replace existing placeholder text only.
- Do not add extra context elements.

Target:
- `.panel-context-title` in each tab context group box.

Default text:
- `Client -> Project -> Filename`

Live format:
- `{ClientName} -> {ProjectName} -> {Filename}`

Verified source points in current code:
- `ClientName` / `ProjectName`:
  - selected option text from `clientSelect` / `projectSelect`
  - already used by `setPanelContext()` in `commissioning.js`
- `Filename`:
  - current generated-file label source used by `setLastGeneratedLabel()` / `lastGeneratedLabel` in `commissioning.js`

Update triggers:
- `clientSelect` change
- `projectSelect` change
- post upload/regenerate completion when generated filename changes

---

## Table Contracts (Approved)

### 1) Effective Scope Source Contract

Source of truth:
- `Y:\Desktop\Development\Sentinel\docs\button_id_and_scope.md`

Implementation note:
- Existing code path is mostly working and should be reused.
- Do not replace with a new method unless a specific defect is confirmed.

### 2) Tech Notes `Show` Popup Contract

Behavior:
- `Show` button opens a centered popup.
- Popup styling must match existing test popup styling.
- Popup close behavior must reuse/copy the existing test popup close mechanism.

Popup content:
- `<tech name> says: "<tech note>."`

Notes:
- This keeps long notes out of table cell layout.
- Table row height should remain stable regardless of note length.

### 3) Sorting Contract (Both Tables)

Default:
- chronological order
- newest first

Implementation note:
- Header click sorting follows industry-standard toggle behavior per column.
- Timestamp default sort should be descending on initial render.

---

## Diagnostics Task List Mapping Contract (Approved)

Final column order:
1. `Status`
2. `Timestamp`
3. `Device`
4. `Page Name`
5. `Layer`
6. `Viewport`
7. `Button Identity`
8. `Test Target`
9. `Effective Scope`
10. `Tech Notes`

Mapping and formatting:
- `Status`:
  - backend enum can remain `NOT_STARTED` / `IN_PROGRESS` / `DONE`
  - UI label must display `Not Started` / `In Progress` / `Complete` (not `Done`)
- `Timestamp`:
  - display in computer local timezone
  - format: `YYYY-MM-DD HH:MM`
- `Device`: keep current deployed behavior
- `Page Name`: keep current deployed behavior
- `Layer`: keep current deployed behavior
- `Viewport`: keep current deployed behavior
- `Button Identity`: keep current deployed behavior (no behavior change)
- `Test Target`: keep current deployed behavior
- `Effective Scope`:
  - keep current deployed behavior
  - scope resolution remains sourced from `docs/button_id_and_scope.md`
- `Tech Notes`:
  - table cell remains a `Show` button
  - popup contract as defined in this document

Constraint:
- Other than status label text and timestamp display timezone/format, keep deployed mapping behavior unchanged.

---

## Commissioning Live Status Mapping Contract (Approved)

Final column order:
1. `Timestamp`
2. `Device`
3. `Page Name`
4. `Layer`
5. `Viewport`
6. `Button Identity`
7. `Test Target`
8. `Pass/Fail`

Mapping and formatting:
- `Timestamp`:
  - source: event `recordedAtUtc` / `tsUtc`
  - display in computer local timezone
  - format: `YYYY-MM-DD HH:MM`
- `Device`:
  - source: `refs.deviceName`
- `Page Name`:
  - source: `refs.pageName`
- `Layer`:
  - source: resolved layer name in event refs/payload
- `Viewport`:
  - source: explicit viewport/frame from payload when available
  - fallback: `No`
- `Button Identity`:
  - source: `refs.buttonName`
- `Test Target`:
  - source: `targetName`
  - fallback: `targetKey`
- `Pass/Fail`:
  - source: `outcome` / `currentOutcome`
  - display normalized to `Pass` / `Fail`

---

## Sorting Behavior Contract (Approved)

Applies to both tables unless column-specific rules are listed below.

1) Timestamp sorting
- Compare by actual datetime value (not display text).
- Default initial sort: descending (`newest first`).

2) Text column sorting
- Columns:
  - `Device`, `Page Name`, `Layer`, `Viewport`, `Button Identity`, `Test Target`, `Effective Scope`
- Behavior:
  - case-insensitive lexical compare
  - empty values sort last

3) Diagnostics Status sorting
- Column: `Status` (dropdown display labels)
- Semantic order:
  - `Not Started` < `In Progress` < `Complete`
- Descending reverses this order.

4) Commissioning Pass/Fail sorting
- Column: `Pass/Fail`
- Semantic order:
  - ascending: `Fail` < `Pass`
  - descending: `Pass` < `Fail`

5) Header click behavior
- Clicking a column header toggles sort direction for that column.
- Only one active sort column at a time.
- Non-active columns return to neutral sort state/icon.

6) Tie-break behavior
- When primary sort values are equal, apply secondary tie-break:
  - `Timestamp` descending.

---

## Tech Notes Popup + Tech Link Label Integrity Contract (Approved)

### A) Tech Link Label Integrity (Creation-time enforcement)

Rule:
- Tech link label is required at creation.
- Blank/whitespace-only labels are not allowed.

Enforcement points:
1. Client validation (before request submit).
2. API validation (authoritative guard).

Behavior on invalid label:
- Tech link is not created.
- Inline validation/error message is shown to user.

### B) Tech Notes `Show` Popup Data Contract

Primary fields:
- `techName`
- `techNote`

Render format:
- `<tech name> says: "<tech note>."`

Close behavior:
- must match existing test popup close mechanism:
  - close button
  - backdrop click
  - `Esc` key

Fallbacks:
- Because label is creation-required, generic tech-name fallback should not be needed in normal flow.
- If bad historical data is encountered:
  - show integrity message: `Invalid tech link: missing label.`
- If note text is missing:
  - `No note provided.`

---

## Pie Chart Data Contracts (Approved Direction + Verified Current Wiring)

Purpose:
- Define exactly what data populates each pie chart.
- Keep existing shared pie layout/styling; wire data only.

### A) Commissioning Tab Pie Contracts

#### A1. Project Completion
- Chart title: `Project Completion`
- Data source:
  - `progress.counts.pass`
  - `progress.counts.totalTargets`
- Display:
  - center percent = `pass / totalTargets`
  - ratio text = `pass/totalTargets`

#### A2. System Event Completion
- Chart title: `System Event Completion`
- Data source:
  - `progress.eventSections.system.counts.pass`
  - `progress.eventSections.system.counts.totalTargets`
- Display:
  - center percent = `pass / totalTargets`
  - ratio text = `pass/totalTargets`
- Zero-target rule:
  - if `totalTargets = 0`, keep the card/title visible and show `None` centered in the card (no donut)

#### A3. Driver Event Completion
- Chart title: `Driver Event Completion`
- Data source:
  - `progress.eventSections.driver.counts.pass`
  - `progress.eventSections.driver.counts.totalTargets`
- Display:
  - center percent = `pass / totalTargets`
  - ratio text = `pass/totalTargets`
- Zero-target rule:
  - if `totalTargets = 0`, keep the card/title visible and show `None` centered in the card (no donut)

#### A4. Device Rows
- Titles: device display names
- Data source per device:
  - `progress.devices[*].counts.pass`
  - `progress.devices[*].counts.totalTargets`
- Display:
  - center percent + ratio per device
- Visibility/layout rule:
  - show only devices that exist (no placeholder device cards)
  - 4 devices example: 3 cards on first row, 1 card left on second row

Verified in code:
- `src/sentinel/ui/commissioning/commission_tab.js` (`updatePies(progress)`).

### B) Diagnostics Tab Pie Contracts

#### B1. Failure Rate
- Chart title: `Failure Rate`
- Data source/intent:
  - programming failure rate KPI
  - cumulative tested set so far
  - first-time failures so far
- Slices:
  - `Fail` (first-time failures)
  - `Pass` (tested minus first-time failures)
- Center label:
  - fail percentage (`Fail / Total Tested So Far`)
- Count label:
  - `Fail / Total Tested So Far`
- Persistence rule:
  - once a target has passed, it does not count toward first-time-fail accumulation after that

#### B2. Failure Types
- Chart title: `Failure Types`
- Data source:
  - first-time-fail population only
  - grouped by approved target categories
- Category labels (keep as currently shown in placeholder/static view):
  - `text`, `macros`, `macroSteps`, `variables`, `graphics`, `pageLink`
- Rule:
  - percentages are `% of first-time failures by category`
- Center label:
  - no center percent (reserved for possible hover detail later)

#### B3. Task Completion
- Chart title: `Task Completion`
- Approved UI labels:
  - `Not Started`, `In Progress`, `Complete`
- Data source:
  - Diagnostics task tag state (`NOT_STARTED`, `IN_PROGRESS`, `DONE`)
- Slice mapping:
  - `NOT_STARTED` -> `Not Started`
  - `IN_PROGRESS` -> `In Progress`
  - `DONE` -> `Complete`
- Center label:
  - `Complete / Total` percent
- Count label:
  - `Complete / Total`

Verified in code:
- `src/sentinel/ui/commissioning/diagnostics_tab.js`
  - `updateFailureRatePie()`
  - `updateFailureTypesPie()`
  - `updateTaskCompletionPie()`

### C) Known Gaps To Resolve During Wiring

Current Diagnostics runtime implementation:
- Task Completion pie currently renders 2 slices:
  - `Done`
  - `Not done`

Required by approved UI:
- Task Completion must render 3 slices:
  - `Not Started`
  - `In Progress`
  - `Complete`

This is a required wiring update in the enhancement phase.
