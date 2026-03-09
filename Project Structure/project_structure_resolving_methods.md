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

### `buttonIdentity`
#### `buttonIdentity.buttonTagName`
- From `LayerButtons.ButtonTagName`.

#### `buttonIdentity.text`
- From `LayerButtons.Text`.

### `coordinates`
#### `coordinates.top`
- From `LayerButtons.ButtonTop`.

#### `coordinates.left`
- From `LayerButtons.ButtonLeft`.

#### `coordinates.height`
- From `LayerButtons.ButtonHeight`.

#### `coordinates.width`
- From `LayerButtons.ButtonWidth`.

### `testTargets`
#### `testTargets.text`
- `true` when `LayerButtons.Text` is non-empty.

#### `testTargets.macro`
- `true` when either:
- `LayerButtons.GlobalMacroId != 0`, or
- `LayerButtons.DeviceMacroId != 0`.

#### `testTargets.variables`
Apex-direct method (approved refinement):
1. Collect variable IDs from:
- `LayerButtons.GlobalVariableId`
- `LayerButtons.DeviceVariableId`
2. Read variable fields from `Variables` for each linked `VariableId`.
3. Output booleans in user-facing JSON.

Default boolean shape:
- `Reversed` from `Variables.ReversedData` non-empty
- `Inactive` from `Variables.InactiveData` non-empty
- `Visible` from `Variables.VisibleData` non-empty
- `Value` currently unresolved in strict file-backed mode
- `State` currently unresolved in strict file-backed mode
- `Command` currently unresolved in strict file-backed mode

Fallback shape when `ObjectData` exists but subtype cannot be resolved:
- `Reversed`
- `Inactive`
- `Visible`
- `Object` (from `Variables.ObjectData` non-empty)

#### `testTargets.textVariable`
Apex-direct method (approved):
- `true` if either condition is true:
1. Variable-backed text:
- linked variable exists and `Variables.ButtonText` is non-empty
2. Text-tag mapping exists:
- button has a row in `ButtonTextTags` (`ButtonTextTags.ButtonId = LayerButtons.ButtonId`)

Note:
- This is schema-direct and does not rely on parsing `$%TAG!...%$` strings.

#### `testTargets.pageLink`
- `true` when `LayerButtons.PageLinkId != 0`.

## Button Categories
### `buttonCategories.screenLabels`
Apex-direct rule set:
1. Button is not in hard-button designation.
2. `macro = false`.
3. `pageLink = false`.
4. Label behavior:
- text-only (`text = true` and no linked variable), or
- text-variable-only (`textVariable = true` and `text = false`).

### `buttonCategories.screenButtons`
Apex-direct rule set:
- Any non-hard button not classified as `screenLabels`.

### `buttonCategories.hardButtons`
Approved designation used for this file set:
- `LayerButtons.ButtonHeight = 0 AND LayerButtons.ButtonWidth = 0`.

Observed evidence in approved sample:
- T2i designated physical/remote keys are represented with zero-size button geometry on a dedicated layer.

## Diagnostics
- Per current approved scope for this output pass, diagnostics sections remain empty placeholders.

## Validation Notes
- Methods use direct `.apex` schema fields and joins only.
- No guessed values are introduced.
- Unknown/unresolved values stay empty/null per existing JSON behavior.
