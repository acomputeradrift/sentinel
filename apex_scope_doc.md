# Apex scope (data model)

Companion to `rti_scope_doc.md` (Integration Designer behavior). This file records **what appears in the `.apex` SQLite file** and how it relates to tags, buttons, and scope.

---

## One tag, many buttons

The most important structural fact: **`ButtonTagId` is not one-to-one with on-screen controls.**

- **`ButtonTagId`** — identity of the *tag* (name in `ButtonTagNames`).
- **`ButtonId`** — primary key of a single *button instance* in `RTIDeviceButtonData`.

The same **`ButtonTagId`** can appear on **many** rows in `RTIDeviceButtonData`. Each row is a different **`ButtonId`** (different placement, page, layer, device, etc.). The tag is reused; the instances are not.

---

## When scope is global — same commands for every instance

If the macro/variable rows for that tag use **global** scope in the database (**`RoomId = 0`** and **`DeviceId = -1`** on those rows), every button instance with that tag refers to the **same** macro/variable definitions; only placement differs.

**Example — `Sung Residence v207.2.apex`, tag `CLIMATE - Garage Status` (`ButtonTagId` 835)** (from `devtools/probe_apex_tag_scope.py`):

- **Macros**: one row, `RoomId` 0, `DeviceId` -1.
- **Variables**: one row, `RoomId` 0, `DeviceId` -1.
- **PageLinks**: none for this tag.
- **Button instances**: multiple `ButtonId`s on different pages/devices; placement (room/source) varies, but the stored macro/variable rows are global.

---

## How to reproduce (approved example)

From the repo root:

```bat
python devtools\probe_apex_tag_scope.py --apex "Assets\Sung Residence v207.2.apex" --tag-name "CLIMATE - Garage Status"
```

---

## Extracting button scope from `.apex`

For each tagged button (`RTIDeviceButtonData.ButtonTagId > 0`), resolve scope at the button-placement level first, then attach that scope to macro/variable ids for that button.

### 1) `workspaceScope`

From the resolved page:

- room: `PagesView.RoomId`
- source: `RTIDevicePageData.SourceDeviceId` for the same `PageId`/address context

Output labels:

- room name from `Rooms.Name` (`RoomId > 0`)
- source name from `Devices.DisplayName` (fallback `Devices.Name`)
- room `0` on Global pages is reported as `Selected Room` (runtime-selected room behavior from `rti_scope_doc.md`)

### 2) `pageLayerScope`

From the page layer that hosts the button context:

- non-viewport button: the button's own page layer row in `Layers`
- viewport child button: the parent page layer that hosts the viewport button

Fields:

- room: `Layers.RoomId`
- source: `Layers.SourceId`

If either field is unset on that layer (`NULL`), report:

- `Default Room`
- `Default Source`

### 3) `viewportLayerScope`

Only for viewport-child button placements (button row lives on a child layer with `ViewPortButtonId` set):

- room: child `Layers.RoomId`
- source: child `Layers.SourceId`

If unset (`NULL`), report `Default Room` / `Default Source`.

For non-viewport buttons, viewport layer scope is effectively default/fall-through.

### 4) `runtimeScope` (determined scope)

Determine room and source independently using precedence from `rti_scope_doc.md`:

1. viewport layer setting
2. if viewport setting is default, page layer setting
3. if page layer is default, workspace scope

This is the scope used by the probe output as `runtimeScope`.

---

## Page links and scope (`rti_scope_doc.md`)

Page links are **not** the same as normal macro/variable scope in every case. Per `rti_scope_doc.md`:

### Dedicated **Page Link** row in the Tag Editor (not under Macro)

- **Rule 11:** That branch is **global automatically** — not scoped by Source / Room / Controller **unless** the product handles it elsewhere.

For testing: do not assume the same **runtime scope** chain that applies to scoped macros/variables applies to this page-link row unless you have confirmed behavior in the tool or project.

### **Page Link** as a **macro command** (inside the Macro tree)

- **Rule 12:** Page Link is available under **Global / Source / Room / Controller** like any other macro at that level. It follows the **same rules as other scoped macros** at that level: **runtime scope** (workspace → page layer → viewport layer, with defaults) and **level priority** (Controller → Room → Source → Global) when multiple levels exist on the same tag.

For testing: treat like any other **scoped macro** at that level — **device + placement + runtime scope** still matter for which definition applies.

---

## Revision history

| Date | Notes |
| ---- | ----- |
| (initial) | One tag → many `ButtonId`s; global-row case + Sung `CLIMATE - Garage Status` probe summary. |
| (revision) | Added extraction recipe for `workspaceScope`, `pageLayerScope`, `viewportLayerScope`, and derived `runtimeScope`. |
| (revision) | Page links: dedicated Tag Editor branch vs Page Link as macro command (`rti_scope_doc.md` rules 11–12); testing notes. |
