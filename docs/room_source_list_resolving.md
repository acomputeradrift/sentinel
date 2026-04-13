# Room list resolution down to `pageLink`

This document describes how to go from the **controller room list** and **room-select button tags** to a **resolved navigation target** (the same information as `resolvedPageLink` / `testTargets.pageLink` in extraction), and how **generation** should place **synthetic row buttons** so they behave like real buttons afterward. Use it when building **synthetic rows** (for example a generated scrolling list) where each row must behave like pressing the room’s select tag on that device.

**Scope:** room lists and **`resolutionPath: "roomSelectEvent"`**. **Source** lists use **`activityEvent`** and **`Activities` → `PagelinkMacroId`**; only the room path is detailed here.

---

## 1. Ordered rooms for the device (the room list)

**Table:** `ControllerRoomList`  
**Join:** `Rooms` on `RoomId`  
**Filter:** `RTIAddress` = the panel’s effective address (non-clone controllers use their own `RTIAddress`; clone inheritance is a separate edge case documented in research notes).

**Order:** `ControllerRoomOrder`, then `RoomId`.

**Output:** An ordered list of `{ roomId, roomName }` for that controller. This is the canonical **device-level** room order (see `extractor_core` diagnostics `diagnostics.rooms`).

Reference query pattern (same idea as extraction):

```sql
select cr.RoomId, rm.Name
from ControllerRoomList cr
join Rooms rm on rm.RoomId = cr.RoomId
where cr.RTIAddress = ?
order by cr.ControllerRoomOrder, cr.RoomId
```

Implementation reference: `extract_project_data` in `src/sentinel/extraction/extractor_core.py` (diagnostics room list query).

---

## 2. Room-select button tag per `RoomId`

Room navigation is driven by macros whose steps include **Select Room** (type **24**). Tags live on **`Macros.ButtonTagId`** and resolve to names via **`ButtonTagNames`**.

**Join path:**

1. `MacroSelectRoom` — links `MacroStepId` to **`SelectRoomId`** (this is the **`RoomId`** in project space).
2. `MacroSteps` — `MacroStepId`, **`Type = 24`** (select room step).
3. `Macros` — **`MacroId`**, **`ButtonTagId`**.
4. `ButtonTagNames` — **`ButtonTagName`** (e.g. `Room: Kitchen`, `Room: Foyer`).

**Heuristic for “the” room label tag:** prefer tags whose name starts with **`Room:`** (RTI convention in project docs). The same room may appear in multiple macros; **`ButtonTagId`** is stable across duplicates. Some rooms may only appear on **NAVIGATION**-style macros that also carry a type-24 step; then there may be no `Room:` tag in this join—handle as a product edge case (fallback matching on `Rooms.Name`, `LayerButtons`, etc.).

---

## 3. Per-room navigation targets: `room_event_targets_by_room`

Before any button resolves **`roomSelectEvent`**, extraction builds a map:

**`roomId` → list of `(pageId, rtiAddress)`** (ordered, not deduped by page id).

Construction (same order as `extractor_core`):

1. **`macro_step_targets_by_macro`** — from **`MacroStepsView`**: type **8** steps contribute **`MacroPageLinkView`** targets as **`(TargetPageId, TargetRTIAddress)`** pairs (CSV expansion via `_csv_page_targets`).
2. **`select_sources_by_macro`** — type **26** (select source) for activity wiring.
3. **`activity_target_pages_by_room_and_device`** — from **`Activities`**: first row per **`(RoomId, DeviceId)`** uses **`PagelinkMacroId`** to attach **`macro_step_targets_by_macro[pagelink_macro_id]`** to that key.
4. **`RoomEvents`** — for each **`RoomId`** with **`SelectedMacroId`**:
   - Append all **`macro_step_targets_by_macro[selected_macro_id]`** targets to that room’s list.
   - For each **select-source** pair on that macro, append **`_activity_target_page_ids(...)`** using the **`Activities`** map above.

So **`room_event_targets_by_room[roomId]`** is the full set of **page + RTI** pairs that “selecting” that room can imply after **RoomEvents** and activity wiring—not only raw macro page links.

Implementation reference: `extract_project_data` in `extractor_core.py` (queries on `MacroStepsView`, `Activities`, `RoomEvents`), and helpers `_activity_target_page_ids`, `_csv_page_targets`.

---

## 4. Pick one page on the current device: `_pick_target_for_rti`

Given **`targets: list[(pageId, rtiAddress)]`** and **`current_rti_address`**:

- Prefer the first pair whose **`rtiAddress`** equals **`current_rti_address`**.
- Otherwise use the first pair’s **`pageId`** (fallback).

This yields a single **`targetPageId`** for the panel you are rendering.

Implementation: `_pick_target_for_rti` in `extractor_core.py`.

**Page name:** from **`PagesView`** (or extraction’s `page_name_by_page_id`): **`targetPageName`** for display.

---

## 5. How this becomes `resolvedPageLink` on a button (`roomSelectEvent`)

When a **button** is wired to macros that include a **type 24** step listing **`select_room_id`**, extraction tries **`roomSelectEvent`** after direct page links and **`macroStep`**:

- For each **candidate `macro_id`** attached to the button (explicit or tag-scoped **`Macros`**):
  - For each **`select_room_id`** in **`select_rooms_by_macro[macro_id]`** (from type-24 rows on that macro):
    - **`room_target_page_id = _pick_target_for_rti(room_event_targets_by_room[select_room_id], current_rti_address)`**
    - If non-null, set **`resolvedPageLink`** with **`resolutionPath: "roomSelectEvent"`**.

So for a **synthetic row** “as if” the user chose **`RoomId` R** on device **D** with **`RTIAddress` A**:

1. Ensure you use the same **`room_event_targets_by_room[R]`** built as in extraction.
2. **`targetPageId = _pick_target_for_rti(room_event_targets_by_room[R], A)`**.
3. Emit **`{ targetPageId, targetPageName, resolutionPath: "roomSelectEvent" }`** (or your UI’s equivalent).

Implementation reference: `_resolve_button` in `extractor_core.py` (room-select loop and `testTargets.pageLink`).

---

## 6. List control vs. row semantics (UI)

The **on-screen list chrome** (browser/list control) is identified separately:

- **`RTIDeviceButtonData.ButtonStyle = 8`** with **`Variables.ObjectData`** for the list token (user-facing **`testTargets.variables.List`**).
- That control often does **not** carry a single **`resolvedPageLink`** on the list widget itself; navigation is on **per-room** semantics above.

For a **generated scrolling list**, you supply **one resolved target per room row** using sections 1–5, not the list button’s own tag unless it is also a navigation control. **Where and how** those rows are drawn is covered in **§7**.

---

## 7. Generation: synthetic buttons inside the list

After extraction and resolution (sections 1–5), **generation** lays out **row buttons** that are not copied from Apex `RTIDeviceButtonData` geometry the way the rest of the UI is.

**Placement**

- Emit **buttons inside the list control’s coordinate space**, on the **same layer** as the list (the layer that hosts the style‑8 list / viewport).
- Row geometry comes from **layout math** (list bounds, row height, scroll offset), not from Apex button records for those rows.

**Shared layers**

- If the list lives on a **shared layer**, that layer appears on **every page** that references it. Generated row buttons must appear in the **correct place on each such page**, not only on a single page instance—same logical layer, same list box, repeated per page where the shared layer is used.

**Different from “normal” Apex-driven generation**

- **Most of the UI:** positions and sizes come from **actual Apex** (`RTIDeviceButtonData` and related layout).
- **List rows:** **generated differently**—computed inside the list—but once emitted they should match whatever structure the renderer already uses for a **button** (hit targets, identity, navigation payload).

**After generation: first-class buttons**

- Once generated, each row button should be treated **like any other button** for:
  - **Testing** (same test-target and interaction model as real buttons).
  - **Navigation** via **`pageLink` / `resolvedPageLink`** (same runtime path as a physical Apex button that would have resolved to the same target).

No separate “synthetic-only” navigation path is required after the generated model carries the same fields as a resolved real button.

**CSS and DOM parity (same as any other RTI button)**

In commissioning HTML, real buttons are not “raw” `<button>` elements alone. They are emitted by **`_render_button_control`** in `src/sentinel/generation/render_core.py`, which produces a fixed structure so **shared CSS** and **client JS** (testing popup, page-link hit areas, pass totals, orientation, layer visibility) all attach the same way.

Generated room-list row buttons **must** go through that same path (or emit **identical** markup and `class` / `data-*` attributes), including:

| Piece | Role |
|--------|------|
| Outer **`div.btn-wrap`** | Absolute position, `data-left` / `data-top` / `data-width` / `data-height` / `data-font-size` / `data-visible` / `data-button-category`, orientation `data-*`, optional `data-button-tag`, diagnostics `data-diag-*` when applicable, `z-index` for layer order. |
| Inner **`button.test-btn`** | Fills the wrap (`position:absolute; inset:0` in CSS); carries **`data-meta`** JSON (`category`, `identity`, `targets`, optional `apexScopeSource`) used by the testing UI. |
| **`div.btn-pass-total`** | Sibling after the button; populated by JS for per-target counts. |
| **`a.page-link-hit`** + **`span.page-link-icon`** | When **`appNavigation.pageLinks.enabled`** and the button has a resolved page link—same as Apex buttons. |

The stylesheet in `render_core.py` defines appearance on **`.btn-wrap`** and **`.test-btn`** (e.g. fill color via `--btn-fill-color`, rounded corners, inset border). Scripts query **`document.querySelectorAll('.test-btn')`**, **`.btn-wrap`**, and related selectors. If synthetic rows omit the wrap, omit **`test-btn`**, or hand-roll different classes, they will **not** pick up the same look or behavior.

**Implementation rule:** For each generated row, build a **minimal `btn` dict** that satisfies **`_render_button_control`** (or refactor that helper to accept an explicit “synthetic” flag while preserving output shape): include **`buttonUI`** with **computed** `left` / `top` / `width` / `height` / `fontSize` / visibility and orientation blocks consistent with the active orientation, **`buttonIdentity`** (label text, `buttonTagName` from the room-select tag where useful), **`testTargets`** (including **`pageLink: true`** when **`resolvedPageLink`** is set), **`resolvedPageLink`**, and **`apexScopeSource`** as needed for meta. Pass **`left` / `top`** as list-relative coordinates plus the same layer offsets used for sibling Apex buttons on that layer. Optional **`extra_classes`** / **`extra_style`** must remain compatible with existing rules (e.g. viewport helpers **`vp-btn`** where the list lives inside a viewport).

Visually, a wireframe such as stacked rounded rectangles inside the **“NAVIGATION - Room List Dropdown”** area maps to **one `btn-wrap` per row**, each wrapping a **`test-btn`**, aligned inside the list container’s box on the same layer as the list chrome.

---

## 8. Checklist (probe / implementation)

| Step | Input | Output |
|------|--------|--------|
| Room list | `RTIAddress` | Ordered `RoomId`s from `ControllerRoomList` |
| Tag(s) per room | `RoomId` | `ButtonTagId` / `ButtonTagName` via `MacroSelectRoom` + type 24 + `Macros` + `ButtonTagNames` (prefer `Room: …`) |
| Page targets per room | DB same as extract | `room_event_targets_by_room[roomId]` as `(pageId, rtiAddress)[]` |
| One page for this panel | `targets`, device `RTIAddress` | `_pick_target_for_rti` → `targetPageId` (+ name) |
| Product shape | — | Same fields as **`resolvedPageLink`** with **`resolutionPath: "roomSelectEvent"`** where applicable |

---

## 9. Related docs

- `research/initial-testing/apex_project_structure_resolution_v2.md` — locked rules for **`testTargets.pageLink`** and **`resolvedPageLink`**.
- `api_contract_v1.md` — **`PageLink`** when **`testTargets.pageLink.targetPageId`** is non-null.
- `src/sentinel/generation/render_core.py` — **`_render_button_control`** (button HTML), embedded **`.btn-wrap` / `.test-btn`** CSS, and commissioning JS selectors.
