# Project Structure Resolving Methods

Locked baseline date: 2026-03-09
Status: Approved by user
Scope: Methods used to populate JSON data in `project_structure.md` from `.apex` data.

## Change Control
- This file is updated only when a new method is explicitly approved by the user.
- Current baseline includes all methods approved to date.

## Source
### `source.file`
- Set to the exact `.apex` input path used for extraction.

### `source.extractedAtUtc`
- Extraction timestamp recorded by extractor runtime.

## Events
### `events.system[]`
User-facing fields:
- `eventType`
- `resolvedTrigger`

Apex-direct method:
1. Read from `Events`.
2. Filter `Enabled = 1` (only enabled events are included in user-facing output).
3. Filter system class: `DriverId IS NULL`.
4. Map event type from `Events.EventType`:
- `1 -> Sense`
- `3 -> Scheduled`
- `4 -> Startup`
5. Set `resolvedTrigger` from `Events.Description` (raw text from DB).

### `events.driver[]`
User-facing fields:
- `eventType`
- `resolvedTrigger`

Apex-direct method:
1. Read from `Events`.
2. Filter `Enabled = 1`.
3. Filter driver class: `EventType = 5 AND DriverId IS NOT NULL`.
4. Set `eventType = Driver`.
5. Set `resolvedTrigger` from `Events.Description` (fallback to `DriverExtraString` only if `Description` is empty).

## Devices
### `devices[].userFacing.displayName`
Apex-direct method:
1. Read controller rows from `RTIDeviceData`.
2. Join `Devices` on `Devices.DeviceId = RTIDeviceData.DeviceId`.
3. Use `Devices.DisplayName`.
4. Non-cloned controller selection uses `COALESCE(CloneRTIAddress, -1) <= 0`.

### `devices[].userFacing.deviceUI`
#### `deviceUI.portrait.supported`
#### `deviceUI.landscape.supported`
#### `deviceUI.portrait.resolution`
#### `deviceUI.landscape.resolution`
Apex-direct method:
1. For each controller RTI address, read page layers:
- `RTIDevicePageData (RTIAddress=controller) -> Layers (PageId) -> SharedLayers (SharedLayerId)`.
2. Use `SharedLayers.ScreenPortraitWidth/ScreenPortraitHeight` for portrait resolution.
3. Use `SharedLayers.ScreenLandscapeWidth/ScreenLandscapeHeight` for landscape resolution.
4. `supported = true` when width and height are both non-zero for that orientation.

## Pages
### `devices[].userFacing.pages[].pageName`
Apex-direct method:
1. Determine effective RTI address per controller:
- if `CloneRTIAddress > 0`, use `CloneRTIAddress`
- else use `RTIAddress`
2. Read pages from `RTIDevicePageData` where `RTIAddress = effectiveAddress`.
3. Join `PageNames` on `RTIDevicePageData.PageNameId = PageNames.PageNameId`.
4. Use `PageNames.PageName` as `pageName`.
5. Order by `RTIDevicePageData.PageOrder`.

## Buttons
### Source path for page buttons
Apex-direct method:
1. For each page, read `Layers` where `Layers.PageId = RTIDevicePageData.PageId`.
2. Join `LayerButtons` on `LayerButtons.LayerId = Layers.LayerId`.

Viewport extension path:
1. Identify viewport container buttons on the page by `ButtonId`.
2. Read child layers from `Layers` where `Layers.ViewPortButtonId = viewportButtonId`.
3. Join child-layer buttons from `RTIDeviceButtonData` by `SharedLayerId`.
4. Group child buttons by `FrameNumber`.

### `buttonIdentity`
#### `buttonIdentity.buttonTagName`
- From `LayerButtons.ButtonTagName`.

#### `buttonIdentity.text`
- From `LayerButtons.Text`.

#### `buttonIdentity.buttonType`
Apex-direct method:
- Derived from `LayerButtons.ButtonStyle`:
  - `9 -> Slider`
  - `7 -> Toggle`
  - `11 -> LevelIndicatorBar`
  - all other styles -> `null` in user-facing output.

### `buttonUI`
#### `buttonUI.fontSize`
- From button text size field in `.apex` (`RTIDeviceButtonData.TextSize`).

#### `buttonUI.coordinates.top`
- From `LayerButtons.ButtonTop`.

#### `buttonUI.coordinates.left`
- From `LayerButtons.ButtonLeft`.

#### `buttonUI.coordinates.height`
- From `LayerButtons.ButtonHeight`.

#### `buttonUI.coordinates.width`
- From `LayerButtons.ButtonWidth`.

### `testTargets`
#### `testTargets.text`
- `true` when button text contains literal display text.
- `false` when button text is token-only (`$%TAG!...%$` with no literal text), because this is treated as text-variable-only.

#### `testTargets.macro`
- `true` when either:
- `LayerButtons.GlobalMacroId != 0`, or
- `LayerButtons.DeviceMacroId != 0`, or
- tag-scoped macro resolution succeeds from `Macros` using `LayerButtons.ButtonTagId`.
- user-facing validity gate:
  - if `buttonIdentity.buttonTagName` is null/empty, force `testTargets.macro = false` (no valid macro target to test).

Diagnostics macro scope method:
1. Resolve macro in this order:
- direct `GlobalMacroId`
- direct `DeviceMacroId`
- tag-scoped fallback (`Macros.ButtonTagId = LayerButtons.ButtonTagId`) with scope-priority match against layer context.
2. Scope-priority match order:
- exact: `Macros.RoomId = Layers.RoomId` and `Macros.DeviceId = Layers.SourceId`
- global-room + source: `Macros.RoomId = 0` and `Macros.DeviceId = Layers.SourceId`
- room + global-device: `Macros.RoomId = Layers.RoomId` and `Macros.DeviceId = -1`
- global + global-device: `Macros.RoomId = 0` and `Macros.DeviceId = -1`
3. Set diagnostics fields:
- `scope` from resolved `(RoomId, DeviceId)` mapping:
  - `(0, -1) -> Global`
  - `(>0, -1) -> Room`
  - `(0, >=0) -> Source`
  - `(>0, >=0) -> Controller`
- `scopeType = "Global | Room | Source | Controller"`

#### `testTargets.variables`
Apex-direct method (approved refinement):
1. Collect variable IDs from:
- `LayerButtons.GlobalVariableId`
- `LayerButtons.DeviceVariableId`
2. If direct IDs are empty, resolve tag-scoped fallback from `Variables.ButtonTagId = LayerButtons.ButtonTagId` using the same scope-priority order as macro resolution.
3. Read variable fields from resolved `Variables.VariableId` rows.
4. Output booleans in user-facing JSON.

Default boolean shape:
- `Text` from either:
  - `ButtonTextTags.ButtonId = LayerButtons.ButtonId`, or
  - resolved `Variables.ButtonText` non-empty
- `Reversed` from `Variables.ReversedData` non-empty
- `Inactive` from `Variables.InactiveData` non-empty
- `Visible` from `Variables.VisibleData` non-empty
- `Value` from object variable token class:
  - `Variables.ObjectData` suffix `@DDL###` -> `Value = true` (directly file-backed through driver variable type)
- `State` from object variable token class:
  - `Variables.ObjectData` suffix `@DDS###` -> `State = true` (directly file-backed), or
  - for `@DDL###`, paired-state exists when matching `@DDS###` token is present for the same driver/device index
- `Command` from object control evidence:
  - `@DDL###` with `LayerButtons.ButtonStyle = 9` and driver dimmer function support (`DriverData.SystemFunctions` includes dimmer command family) -> `Command = true`
  - `@DDS###` with style `7`/toggle macro steps (`MacroStepsView` function family such as `SwitchCmd:Switch`) -> `Command = true`

Fallback shape when `ObjectData` exists but subtype cannot be resolved:
- `Reversed`
- `Inactive`
- `Visible`
- `Object` (from `Variables.ObjectData` non-empty)

Diagnostics variable scope method:
- each diagnostics variable entry includes:
  - `scope` from resolved variable `(RoomId, DeviceId)` using the same mapping used for macro scope
  - `scopeType = "Global | Room | Source | Controller"`

#### `testTargets.variables.Text`
Apex-direct method (renamed from prior textVariable target):
- `true` if either condition is true:
1. Variable-backed text:
- linked variable exists and `Variables.ButtonText` is non-empty
2. Text-tag mapping exists:
- button has a row in `ButtonTextTags` (`ButtonTextTags.ButtonId = LayerButtons.ButtonId`)

Token-only refinement:
- when `buttonIdentity.text` is token-only (`$%TAG!...%$`), force:
  - `variables.Text = true`
  - `text = false`

Diagnostics text-variable scope method:
1. If variable-backed text is present (`Variables.ButtonText`), scope is taken from that resolved variable row `(RoomId, DeviceId)`.
2. If text-variable is from text-tag only (`ButtonTextTags`) and no variable-backed text is resolved, keep scope default as `Global`.
3. Set `scopeType = "Global | Room | Source | Controller"`.

#### `testTargets.pageLink`
- `true` when `LayerButtons.PageLinkId != 0`.

## Button Categories
### `buttonCategories.screenLabels`
Apex-direct rule set:
1. Button is not in hard-button designation.
2. `pageLink = false`.
3. Label behavior is display-oriented:
- text-only (`text = true` and no linked variable), or
- text + text-variable (`text = true` and `textVariable = true`), or
- text-variable-only (`textVariable = true` and `text = false`).
4. Macro behavior:
- allowed when `macro = false`, or
- allowed when `macro = true` and resolved diagnostics macro is empty (`isEmpty = true`).
5. Non-empty macros keep the button in `screenButtons`.
6. `buttonTagName = null` is label-eligible when display-oriented and not a `uiItem`.

### `buttonCategories.screenButtons`
Apex-direct rule set:
- Any non-hard button not classified as `screenLabels`.

### `buttonCategories.hardButtons`
Approved designation used for this file set:
- `LayerButtons.ButtonHeight = 0 AND LayerButtons.ButtonWidth = 0`.

Observed evidence in approved sample:
- T2i designated physical/remote keys are represented with zero-size button geometry on a dedicated layer.

## Viewports
### `devices[].userFacing.pages[].viewports[]`
Apex-direct method:
1. On each page, find candidate viewport container button IDs.
2. A button is treated as a viewport when at least one `Layers` row exists with:
- `Layers.ViewPortButtonId = ButtonId`.
3. User-facing viewport fields:
- `viewportIdentity.viewportButtonId` from container `ButtonId`
- `viewportUI.coordinates` from container button geometry.

### `devices[].userFacing.pages[].viewports[].frames[]`
Apex-direct method:
1. Read child buttons from viewport-linked layers.
2. Group by `RTIDeviceButtonData.FrameNumber` as `frameId`.
3. Apply the same user-facing button extraction rules per frame:
- `buttonIdentity`
- `buttonUI`
- `testTargets`
- category split (`screenLabels`, `screenButtons`, `hardButtons`).

### `devices[].diagnostics.pages[].viewports[]`
Apex-direct method:
1. `viewportButtonId` from container button.
2. `source.viewPortVerticalScroll` and `source.visibleOrientations` from container button row.
3. `layerLinks[]` from layers where `ViewPortButtonId = viewportButtonId`:
- `layerId`, `sharedLayerId`, `layerOrder`, `sourceId`, `roomId`.
4. `frames[]` from child buttons grouped by `FrameNumber` with full diagnostics `buttons[]` payload.

## Diagnostics
- Diagnostics are now populated for devices/pages/buttons in the current extractor output.

### `diagnostics.pages[].uiItems`
Apex-direct rule set:
1. Candidate rows come from the same page button traversal (`Layers` + `LayerButtons`).
2. A row is a `uiItem` when all are true:
- `ButtonTagName` is empty/null
- `Text` is empty/null
- no text-variable signal:
  - no `Variables.ButtonText` for resolved variable rows
  - no `ButtonTextTags` row for that `ButtonId`
3. `uiItems` are excluded from user-facing button categories.
4. `uiItems` are kept in diagnostics with:
- `buttonId` only.

## Validation Notes
- Methods use direct `.apex` schema fields and joins only.
- No guessed values are introduced.
- Unknown/unresolved values stay empty/null per existing JSON behavior.
