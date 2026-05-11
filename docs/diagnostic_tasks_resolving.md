# Diagnostic Tasks Resolving

## Scope

This document captures what was proven during the investigation session on April 2, 2026 for resolving diagnostics task fields from the Carlos `.apex` file.

Primary test file used:
- `Assets/Carlos OBryans v6.3.1 (tag cleanup).apex`

Environment used:
- `C:\Development\Sentinel\.tmp_apex_env\Scripts\python`

## Required Diagnostics Headings

Diagnostics output must always include these headings:
- `Timestamp`
- `Device`
- `Page Name`
- `Layer`
- `Viewport`
- `Button Identity`
- `Test Target`
- `Effective Scope`
- `Current`

## Required Field Formats

- `Layer`: name only.
- `Viewport`: only `No` or `Frame N`.
  - RTI stores frame numbers as 0-based indexes.
  - Diagnostics display must convert to human 1-based numbering.
  - Example: RTI frame `0,1,2` must display as `Frame 1, Frame 2, Frame 3`.
- `Effective Scope`: `Room -> Source` using resolved names, not IDs.
  - Example: `Global -> Home`
- `Current`:
  - Do not repeat the button tag name.
  - For page links: destination page name only.
  - For macro-step/driver command: resolve to driver and command path + resolved parameters.
    - Example style: `Lutron Caseta / RA2 Select | Switch Commands | Pool Table Lights | Toggle`

## Proven Resolution Methods

## 1) Button Identity Lookup

Resolve button tag first:
- `ButtonTagNames.ButtonTagName -> ButtonTagId`

Then locate button rows:
- `RTIDeviceButtonData` by `ButtonTagId`

## 2) Layer Name Resolution

Resolve layer name via:
- `RTIDeviceButtonData.SharedLayerId -> SharedLayers.Name`

## 3) Page Name Resolution (Including Viewport Frame Buttons)

For normal page buttons:
- `Layers.PageId -> PagesView.PageName`

For viewport frame buttons where `Layers.PageId` is `NULL`:
1. Use `Layers.ViewPortButtonId` to identify the host viewport button.
2. Resolve host viewport button in `RTIDeviceButtonData`.
3. Resolve that host button's layer row in `Layers`.
4. Use host layer `PageId -> PagesView.PageName`.

This method is required for controls like `LIGHTS - Load 9 TOGGLE` that live in viewport frames.

## 4) Effective Scope Resolution (`Room -> Source`)

Use layered precedence:
1. Layer scope when present (`Layers.RoomId`, `Layers.SourceId`)
2. Else page defaults (`PagesView.RoomId`, `PagesView.SourceDeviceId`)

Resolve names:
- Room name from `Rooms.Name`
- Source name from `Devices.DisplayName`/`Devices.Name`

Output as:
- `{RoomName} -> {SourceName}`

Macro applicability rule (required):
- If multiple macros exist for a shared tag, select the macro whose scoped `DeviceId`/source context matches the button's effective scope.
- Do not list all same-tag macros when scope picks one active branch.

## 5) Test Target Resolution

Use extracted target capability for each button:
- Variables: `testTargets.variables.*`
- Macro steps: `testTargets.macroSteps`
- Page links: `testTargets.pageLink`

Important finding for Carlos:
- `testTargets.macros` count was `0`
- `testTargets.macroSteps` count was nonzero
- Therefore macro behavior should be resolved through macro steps for this file.

## 6) Current Value Resolution

## PageLink Current

Resolve destination page from:
- `PageLinks.PageId -> PagesView.PageName`

Output:
- destination page name only.

## Variable Current

Resolve configured variable details from:
- `Variables` rows by `ButtonTagId`
- Use fields such as `ObjectData`, `ReversedData`, `VisibleData`, etc.

Current status:
- Configured variable bindings are resolvable.
- Live runtime variable value is not stored in extracted diagnostics payload.

## MacroStep/Driver Command Current

Resolve command details from:
1. `Macros` by `ButtonTagId`
2. `MacroStepsView` by `MacroId` (command steps, function export, params)
3. `DriverData.SystemFunctions` XML
4. `DriverConfig` token values (`%%token%%`) for expansion
5. Resolve parameter choices from function XML `<choice>` nodes

Rebuild output as:
- `{DriverName} | {FunctionGroup} | {ResolvedTarget} | {ResolvedAction}`

If a system macro name exists:
- Format: `{SystemMacroName} -> {resolved step list}`

If no system macro name:
- Use direct resolved macro step list.

Non-command macro steps must also be interpreted when known mappings exist.

Proven mapping for room-off step semantics:
- Backing fields:
  - `MacroSteps.Type = 27`
  - `MacroRoomOff.RoomOffId`
- Naming (from validated research mapping):
  - `RoomOffId = -2` -> `Room Off: All Rooms Off`
  - `RoomOffId = -1` -> `Room Off: Current Room`
- Source reference:
  - `research/initial-testing/apex_data_extraction_scope_for_codex.md` (`MacroRoomOff.RoomOffId semantic naming`)

## Proven Examples From This Session

## Example A: `CONTROL - Cable Box 3`

Resolved:
- Page link only (no macro rows, no variable rows)
- Page resolved to `Home`
- Layer resolved to `CTR - Source Select`
- Effective scope resolved to `Global -> Home`
- Current resolved to destination page name: `Cable Box 3`

## Example B: `LIGHTS - Load 4 TOGGLE`

Resolved:
- Layer: `CTRL - Devices pg2, 3, 4, 5`
- Effective scope: `Global -> Home`
- Variable binding present (`VariableId 54`, object binding)
- Macro step command resolved:
  - `SwitchCmd:Switch(4, 1, 1)` (raw form)

## Example C: `LIGHTS - Load 9 TOGGLE`

Resolved:
- Viewport-frame control; page required viewport host resolution
- Page resolved to `Lights`
- Layer resolved to `CTRL - Devices pg2, 3, 4, 5`
- Effective scope resolved to `Global -> Home`
- Current resolved driver/command form:
  - `Lutron Caseta / RA2 Select | Switch Commands | Pool Table Lights | Toggle`

## Example D: `Guide` button on page `Cable Box 1`

Resolved:
- Control is on a viewport frame.
- Page is resolved through viewport host (`ViewPortButtonId`) to `Cable Box 1`.
- RTI frame index is `1`; diagnostics display frame is `Frame 2` (human indexing).
- Scope resolves to `Global -> Cable Box 1 (Global)`.
- Multiple same-tag macros exist, but scope filtering selects only the `DeviceId=14` branch.
- Current resolves to:
  - `Cable Box 1 (Global) | GUIDE`

## Example E: `PRESETS - All Off` on page `Presets`

Resolved:
- Layer: `CTR - Source Select`
- Viewport: `No`
- Effective scope: `Global -> Home`
- Current includes:
  - command macro step:
    - `Lutron Caseta / RA2 Select | Phantom Keypad Button (ID 1) | 7 | Press`
  - non-command room-off step:
    - `Room Off: All Rooms Off` (resolved from `Type 27` + `RoomOffId = -2`)

Canonical `Current` cell example for this button:
- `Lutron Caseta / RA2 Select | Phantom Keypad Button (ID 1) | 7 | Press ; Room Off: All Rooms Off`

## Known Constraints

- Some controls do not expose `macros` target directly but do expose `macroSteps`; those should still be treated as macro-programmed controls for diagnostics current-resolution.
- Live runtime values are not available from static extraction alone; extraction resolves configured programming, not dynamic value state.
