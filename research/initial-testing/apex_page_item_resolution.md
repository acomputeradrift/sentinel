# RTI `.apex` Page Item Resolution: Verrier iPad (#1) Page 1

This document starts a standalone page-resolution track focused on:
- identifying what item types exist on a page for a device
- proving each item type from schema + row evidence

Sample used:
- `Verrier Home FEENY EDIT v49.apex`
- device: `iPad (#1)` (`Devices.DeviceId=82`)

---

## Device + First Page Resolution

Resolved device:
- `Devices.DeviceId=82`
- `Devices.DisplayName='iPad (#1)'`
- `RTIDeviceData.RTIAddress=4`

First page on that device (`PageOrder` minimum for `RTIAddress=4`):
- `RTIDevicePageData.PageId=509`
- `PageOrder=0`
- `PageName='Feeny Room Select'`
- `SourceDeviceId=1`

---

## What Items Exist On A Page In A Device

The following item classes are the schema-backed page composition items for this workflow.

| Item Class | Primary Schema Path | Exists on Page 509 | Evidence |
|---|---|---|---|
| Page record | `RTIDeviceData(DeviceId -> RTIAddress)` -> `RTIDevicePageData(RTIAddress)` | yes | `RTIAddress=4`, `PageId=509`, `PageOrder=0`, `PageName='Feeny Room Select'` |
| Page title/name | `RTIDevicePageData.PageNameId -> PageNames.PageName` | yes | `PageNameId=498 -> 'Feeny Room Select'` |
| Layers on page | `Layers.PageId -> SharedLayers` | yes | `LayerId 7282`, `6154`, `7287` on `PageId=509` |
| Layer visibility state | `Layers.IsVisible`, `Layers.VisibilityVariable` | yes | `LayerId=7287` has `IsVisible=0`, `VisibilityVariable='{EA6067BE-AE4B-4DBF-A2A8-F925C34FA889}@64861'` |
| Buttons on layer/page | `LayerButtons.LayerId` (or `RTIDeviceButtonData` + layer join) | yes | `36` `LayerButtons` rows across page layers |
| Button label text (literal) | `LayerButtons.Text` | yes | examples: `Master Bedroom`, `Kitchen & Dining`, `Connecting...` |
| Button tag names | `LayerButtons.ButtonTagName` / `ButtonTagId -> ButtonTagNames` | yes | examples: `Room: Master Bedroom`, `POWER - (All) AudioVideo OFF` |
| Button macro links | `LayerButtons.GlobalMacroId` / `LayerButtons.DeviceMacroId` | yes | `GlobalMacroId` present on `19` buttons; `DeviceMacroId` present on `0` buttons |
| Button variable links | `LayerButtons.GlobalVariableId` / `LayerButtons.DeviceVariableId` | no (on this page) | both are `NULL/0` for page-509 buttons |
| Explicit page links | `LayerButtons.PageLinkId -> PageLinkView` | no (on this page) | all `PageLinkId` are `NULL/0` |
| List items | `AllListItems`/`ButtonsAndListItems` by `RTIAddress` + `PageId` | no (on this page) | no `AllListItems` rows for `RTIAddress=4`, `PageId=509` |

---

## Page 509 Layer Inventory

Locked format:

| LayerId | Layer Name | Source | Room | IsVisible | Shared | Visibility Variable |
|---|---|---|---|---|---|---|
| 7282 | NAV - Room Select v2 | Home (`SourceId=1`) | Global (`RoomId=0`) | `1 (Visible)` | `0 (Not Shared)` | *(empty)* |
| 6154 | POWER - (All) AudioVideo OFF | Home (`SourceId=1`) | Global (`RoomId=0`) | `1 (Visible)` | `1 (Shared)` | *(empty)* |
| 7287 | DISPLAY - Connecting... (Room Select) | Home (`SourceId=1`) | Global (`RoomId=0`) | `0 (Hidden)` | `0 (Not Shared)` | `{EA6067BE-AE4B-4DBF-A2A8-F925C34FA889}@64861` |

Locked resolving method for this layer table:
- `LayerId`, `LayerOrder`, `SourceId`, `RoomId`, `IsVisible`, `VisibilityVariable`, `SharedLayerId` from `Layers`
- `Layer Name`, `Shared` from `SharedLayers` (`Name`, `IsShared`)
- `Source` from `Devices` by `Layers.SourceId`
- `Room` from `Rooms` by `Layers.RoomId`
- `IsVisible` rendered as combined raw+resolved value:
  - `1 (Visible)`
  - `0 (Hidden)`
- `Shared` rendered as combined raw+resolved value:
  - `1 (Shared)`
  - `0 (Not Shared)`

---

## Page 509 Button Summary

Counts from `LayerButtons` joined by `LayerId IN (7282,6154,7287)`:
- total buttons: `36`
- buttons with literal `Text`: `18`
- buttons with `ButtonTagName`: `18`
- buttons with `GlobalMacroId`: `19`
- buttons with `DeviceMacroId`: `0`
- buttons with `PageLinkId`: `0`
- buttons with variable links (`GlobalVariableId` or `DeviceVariableId`): `0`

Representative rows:
- `ButtonId=48991`: `ButtonTagName='POWER - (All) AudioVideo OFF'`, `GlobalMacroId=6155`
- `ButtonId=57431`: `ButtonTagName='Room: Master Bedroom'`
- `ButtonId=57435`: `Text='Master Bedroom'`, `GlobalMacroId=7533`
- `ButtonId=58527`: `Text='Connecting...'`, on hidden layer `LayerId=7287`

---

## Notes For Next Page-Pass

High-value next steps for this page:
1. Resolve `GlobalMacroId` targets (`6155`, `7533`, and room-select tags) to command-level actions.
2. Determine button pairing pattern on this page (`Room: <name>` tagged button + adjacent text/macro button).
3. Resolve whether room-select triggers use `MacroSelectRoom` (`Type 24`) or alternate step types in assigned macros.
4. TODO: resolve `Visibility Variable` token `{EA6067BE-AE4B-4DBF-A2A8-F925C34FA889}@64861` to a concrete variable/source path for `LayerId=7287`.

---

## Locked Fully Resolved Button Table Method

Status: `confirmed extractable now`

Locked table headings for non-text buttons:

| ButtonId | Layer | ButtonTagName | Tag Scope | Maco/Command |
|---|---|---|---|---|

### Locked resolving method

1. Target set:
- use `LayerButtons` rows for the page's `LayerId` set
- filter to non-text buttons (`Text` empty)

2. Resolve `Layer`:
- `LayerButtons.LayerId -> Layers.SharedLayerId -> SharedLayers.Name`
- output layer as name only (no numeric suffix when name exists)

3. Resolve `ButtonTagName`:
- use `LayerButtons.ButtonTagName`

4. Resolve effective macro for each button:
- first use direct button wiring if present:
  - `LayerButtons.GlobalMacroId`
  - `LayerButtons.DeviceMacroId`
- if both are null, resolve by tag + scope match:
  - `LayerButtons.ButtonTagId -> Macros.ButtonTagId`
  - scope priority for this page workflow:
    - source scope match (`Macros.RoomId = LayerButtons.RoomId` and `Macros.DeviceId = LayerButtons.SourceId`)
    - then `Global + Source` (`Macros.RoomId = 0` and `Macros.DeviceId = LayerButtons.SourceId`)
    - then room/global-only fallbacks only if needed and explicitly flagged

5. Resolve `Tag Scope` (RTI wording):
- if macro scope is global-source: `Source: Global <SourceName>`
- if macro scope is global-only: `Global`
- if macro scope is room-specific: `Room: <RoomName>`

6. Resolve `Maco/Command`:
- parse `MacroSteps` for selected macro
- for `Type 24`: `Select Room: <RoomName>` via `MacroSelectRoom.SelectRoomId`
- for `Type 27`: `Room Off (RoomOffId=<value>)` via `MacroRoomOff.RoomOffId`
- for other types: use explicit type + payload table values; do not infer wording

7. Output discipline:
- use names instead of indexes where names are resolved
- keep unresolved elements explicit; do not guess

### Text-label extraction + empty-macro check (locked)

Use this method when inventorying a layer before resolved action mapping:

1. Extract all rows from `LayerButtons` for target `LayerId`.
2. Derive label type:
- `Text` when `Text` is non-empty and `ButtonTagName` is empty
- `Tag` when `ButtonTagName` is non-empty and `Text` is empty
- `Tag + Text` when both are non-empty
3. For text-label review:
- text-label rows are `Label Type = Text`
4. Empty macro check (if any macro id is attached):
- for each referenced macro (`GlobalMacroId` / `DeviceMacroId`), count steps in `MacroSteps` by `MacroId`
- if step count is `0`, tag macro as `empty`
- if step count is `>0`, tag macro as `not empty`
5. Presentation rule:
- after text-label review, hide `Label Type = Text` rows from main non-text action table

---

## Locked Button Test Schema (Per Button)

Status: `confirmed extractable now` (structure + fields)

Each button record used for technician workflows must be split into exactly two parts:

1. `User Facing` (what to test)
2. `Failure Diagnostics` (where to look when a test fails)

### 1) User Facing schema

Required fields:
- `ButtonTagName`
- `Test Targets`

`Test Targets` is a set populated only from what exists on that button:
- `Label` (only for pure label rows: text shown, no non-empty macro, no variable, no page link)
- `Macro`
- `Variable`
- `Text Variable`
- `Page Link`

Technician rule:
- only show targets that exist for that specific button

### 2) Failure Diagnostics schema

Locked output format (single diagnostics string):
- `Layer "<Layer Name>" - Room: <Layer Room>, Source: <Layer Source>, Visibility Variable: <Layer Visibility Variable or None> | Macro: <Macro Scope> -> <Resolved Macro/Command> | Variables: <Variable Scope> -> <Exact Variable Field> -> <Resolved Variable Name> | Text Variable: <Resolved Variable Name>: format (<FalseLabel>/<TrueLabel>)`

Rules:
- use this exact section order in output: `Layer | Macro | Variables | Text Variable`
- if a section does not exist for a button, output that section as `None`
- do not output tag-scope text in diagnostics output
- keep exact variable-field distinction in `Variables` section (`ObjectData`, `ReversedData`, `InactiveData`, `VisibleData`)
- resolve names where available; keep raw token/value only where name is not available
- if macro exists but has zero steps, show `Macro: <scope> -> empty`

Locked example:
- `Layer "CONTROL - Lights" - Room: Global, Source: Lights/Home (Master), Visibility Variable: None | Macro: Global -> Immediate Switch on Clipsal C-Bus: Function=Toggle, Group=74, Application=56 (lighting) | Variables: Global -> ReversedData -> App ID 56, Group 74 state | Text Variable: App ID 56, Group 74 state: format (Disabled/Enabled)`

Current RTI-ID template (locked as current button resolve method):
- `Layer "{SharedLayers.Name}" (Layers.LayerId={LayerId}) - Room: {Global|Rooms.Name} (Layers.RoomId={LayerRoomId}), Source: {Devices.DisplayName} (Layers.SourceId={LayerSourceId}), Visibility Variable: {None|Layers.VisibilityVariable} | Macro: {Global|Source|Room|Controller} -> ({Devices.DisplayName @ MacroStepsView.DeviceId}) App ID {AppId}, Group {GroupId} {FunctionName}: {FunctionChoice} (LayerButtons.GlobalMacroId/DeviceMacroId -> Macros.MacroId={MacroId}; MacroStepsView.MacroStepId={MacroStepId}; Type={Type}; Function={Function}; Parameter1={P1}; Parameter2={P2}; Parameter3={P3}) | Variables: {Global|Source|Room|Controller} -> {ObjectData|ReversedData|InactiveData|VisibleData} -> ({Devices.DisplayName @ token DeviceId}) App ID {AppId}, Group {GroupId} state (LayerButtons.GlobalVariableId/DeviceVariableId -> Variables.VariableId={VariableId}) | Text Variable: {Global|Source|Room|Controller} -> ({Devices.DisplayName @ token DeviceId}) App ID {AppId}, Group {GroupId} state: ({FalseLabel}/{TrueLabel}) (Variables.ButtonText)`

---

## Session Findings (Tagged)

### 1) Layer diagnostics composition

Status: `confirmed extractable now`

- Layer display segment can be rebuilt from:
  - `LayerButtons.LayerId -> Layers.SharedLayerId -> SharedLayers.Name`
  - `LayerButtons.LayerId -> Layers.SharedLayerId -> SharedLayers.IsShared` (`1=Shared`, `0=Not Shared`)
- Locked resolved example (`ButtonId=58614`):
  - `Layer (Not Shared) "CONTROL - Lights"`

### 2) Room/Source layer context segment

Status: `confirmed extractable now`

- Room/Source segment can be rebuilt from:
  - `LayerButtons.LayerId -> Layers.RoomId` (`0 => Global`, else `Rooms.Name`)
  - `LayerButtons.LayerId -> Layers.SourceId -> Devices.DisplayName`
- Example (`ButtonId=58614`):
  - `Room: Global, Source: Lights/Home (Master)`

### 3) Button 58614 full variable/text-variable token resolution

Status: `confirmed extractable now`

- `LayerButtons.ButtonId=58614`:
  - `GlobalVariableId=1571`
- `Variables.VariableId=1571`:
  - `ReversedData={EC82485C-AF0B-4BF0-9DB1-22B290C8B814}#24@App38Group4A`
  - `ButtonText=$%VARIABLE!{EC82485C-AF0B-4BF0-9DB1-22B290C8B814}#24@App38Group4A!B:Disabled:Enabled!false%$`
- Resolved via `DriverData(DeviceId=24).SystemVariables`:
  - `App ID 56, Group 74 state`
- Boolean text labels from `Variables.ButtonText` format segment:
  - `Disabled/Enabled`

### 4) Shared layer behavior on `CONTROL - Volume` (LayerId 2827)

Status: `confirmed extractable now`

- Layer facts:
  - `SharedLayers.IsShared=1`
  - `Layers.RoomId=NULL`
  - `Layers.SourceId=NULL`
  - `Layers.VisibilityVariable={20186C86-446C-4FC6-89E1-1931718A169B}#61440@Room0On`
- Button rows on this layer (e.g., `Volume Up`, `Mute`, `AudioGauge`) have no direct `GlobalMacroId`/`GlobalVariableId`.
- Resolved behavior is obtained through `ButtonTagId` bindings in:
  - `Macros` (many room/room+source-scoped rows per tag)
  - `Variables` (many room/room+source-scoped rows per tag)

### 5) Placeholder expansion required for human-readable resolution

Status: `confirmed extractable now`

- Macro/variable names frequently include placeholders like `%%ZoneNameN%%`.
- Placeholders are resolvable from `DriverConfig` using the target driver's `DriverDeviceId`.
- Proven example:
  - `%%ZoneName1%%` -> `Master Bedroom [Zone 1]` (Audio Matrix driver config)

### 6) `ObjectData` semantics split (`Value`/`State`/`Command`)

Status: `partially supported / incomplete`

- `ObjectData` is widely populated and resolves to named driver variables.
- Across current sample files, resolved names/types strongly show state/level/status/volume patterns.
- A distinct `command` class was not proven in current samples.
- Keep extraction file-backed:
  - show exact field used (`ObjectData`/`ReversedData`/`InactiveData`/`VisibleData`)
  - resolve token name separately
  - do not infer `Value` vs `State` vs `Command` unless explicitly proven.
