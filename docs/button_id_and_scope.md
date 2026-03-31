# RTI Button ID And Scope

## Confirmed: RTI Button Uniqueness

- RTI stores buttons in `RTIDeviceButtonData`.
- `RTIDeviceButtonData.ButtonId` is defined as `INTEGER PRIMARY KEY`.
- Across investigated `.apex` files, `ButtonId` had no nulls and no duplicates.
- `ButtonTagId` and `Text` are not unique and should not be treated as button identity keys.

## Non-Global Pages

The sections below describe the current proven model for non-global pages (`PagesView.RoomId != 0`).

## Scope Model (APEX Tables)

- Page scope fields:
  - `PagesView.RoomId`
  - `PagesView.SourceDeviceId`
  - `PagesView.RTIAddress`
- Layer scope fields:
  - `Layers.RoomId`
  - `Layers.SourceId`
  - `Layers.PageId`
  - `Layers.SharedLayerId`
- Button identity + placement:
  - `RTIDeviceButtonData.ButtonId`
  - `RTIDeviceButtonData.ButtonTagId`
  - `RTIDeviceButtonData.SharedLayerId`
- Scoped behavior sources:
  - `Variables` keyed by `ButtonTagId` with scope fields (`RoomId`, `DeviceId`)
  - `Macros` keyed by `ButtonTagId` with scope fields (`RoomId`, `DeviceId`)
  - `MacroStepsView` keyed by `MacroId`

### Cross-APEX Schema Compatibility (Assets Verification)

Verified across all `.apex` files in `Assets/`:

- Tag table: `ButtonTagNames` (canonical in this corpus)
- ~~Tag table: `ButtonTags`~~ (not present in tested asset files)
- Consistent resolver path objects:
  - `PagesView`
  - `Layers`
  - `RTIDeviceButtonData`
  - `Macros`
  - `Variables`
  - `SharedLayers`
  - `RTIDevicePageData`
  - `PageNames`

Tested asset files:

- `Carlos OBryans v6.3.1 (tag cleanup).apex`
- `Dash OS v55.2 iPhone.apex`
- `Sung Residence v207.2.apex`
- `TEST - System Manager v11.3.apex`
- `Verrier Home FEENY EDIT v49.apex`

## Proven Scope Behavior (Generic)

- A single button tag can appear on multiple button instances (`ButtonId`s).
- A single page can carry multiple layers with different room/source scope values.
- Tag/text alone is not sufficient to uniquely select one runtime behavior record.
- Scoped resolution data is represented in `Variables` and `Macros` using tag + scope fields.

## Runtime Resolution Path (Data-Model View)

1. Resolve active button instance (`ButtonId`) from `RTIDeviceButtonData`.
2. Resolve that button's tag (`ButtonTagId`) and layer link (`SharedLayerId`).
3. Resolve active layer context (`Layers.RoomId`, `Layers.SourceId`, `PagesView.RTIAddress`).
4. Resolve scoped behavior records:
   - Variables from `Variables` by tag + scope.
   - Macros from `Macros` by tag + scope.
   - Macro steps from `MacroStepsView` via resolved `MacroId`.

## Notes On Defaults

- Layer scope values may be explicit or unset (`NULL`) depending on the layer record.
- For non-global pages (`PagesView.RoomId != 0`), the page record provides default room/source anchors via:
  - `PagesView.RoomId`
  - `PagesView.SourceDeviceId`
- In investigated `.apex` files with non-global pages, these page-level fields were populated (not null).
- When source labels are needed for display, they come from `SourceLabels` (`RTIAddress`, `LabelIndex`, `LabelName`).

## Tag PageLink Behavior

- Tag-based page links are device-global for that tag.
- Practically: wherever the same page-link tag appears on that device runtime, it resolves to the same page-link target.
- This is treated as tag-global behavior, not a per-instance scoped resolution path.

## Query Checklist (Any APEX)

Use this sequence when investigating any project:

1. Locate page in `PagesView` (`PageId`, `RoomId`, `RTIAddress`).
2. List page layers from `Layers` + `SharedLayers` (`LayerId`, `RoomId`, `SourceId`, `SharedLayerId`).
3. List buttons for each layer from `RTIDeviceButtonData` by `SharedLayerId`.
4. For each target tag, inspect scoped `Variables` and `Macros`.
5. If macro-driven, inspect `MacroStepsView` by resolved `MacroId`.

## Scoped Test Target Identity (APEX-Derived)

### Goal

Ensure test results apply only to the exact runtime scope where a button was tested, even when multiple buttons share the same tag/text.

### Source of Truth

Use only `.apex` fields:

- Button identity: `RTIDeviceButtonData.ButtonId`, `ButtonTagId`
- Page context: `PagesView.PageId`, `RoomId`, `SourceDeviceId`, `RTIAddress`
- Layer context: `Layers.LayerId`, `RoomId`, `SourceId`, `SharedLayerId`
- Behavior records: `Macros(RoomId, DeviceId, ButtonTagId)`, `Variables(RoomId, DeviceId, ButtonTagId)`

### Scope Resolution Rules

1. Resolve page defaults:
   - `defaultRoomId = PagesView.RoomId`
   - `defaultSourceDeviceId = PagesView.SourceDeviceId`

2. Resolve effective scope using extracted contract fields:
   - `effectiveRoomId = apexScopeSource.viewportLayer.roomId if not NULL else apexScopeSource.pageLayer.roomId if not NULL else defaultRoomId`
   - `effectiveSourceId = apexScopeSource.viewportLayer.sourceId if not NULL else apexScopeSource.pageLayer.sourceId if not NULL else defaultSourceDeviceId`

3. Resolve behavior in that effective scope:
   - Find `Macros/Variables` using `ButtonTagId` plus effective scope fields.
   - Do not treat tag/text as unique identity.

### Scope Precedence Contract

This section defines intended runtime scope resolution behavior for documentation and design.

1. Tagged controls (`ButtonTagId` present) must resolve effective scope in this order:
   - viewport child-layer scope (`apexScopeSource.viewportLayer.roomId`, `apexScopeSource.viewportLayer.sourceId`) when explicitly set
   - else parent page-layer scope (`apexScopeSource.pageLayer.roomId`, `apexScopeSource.pageLayer.sourceId`)
   - else page defaults (`PagesView.RoomId`, `PagesView.SourceDeviceId`)

2. Viewport `Default Room` / `Default Source` means:
   - defer to the next scope level in the chain above
   - do not force global scope

Example fallback chain:

- `childLayer(default/default)` -> `parentLayer(room/source)` -> `pageDefaults(room/source)`

3. Tagged `scopedTestTargetID` must always use the fully resolved effective scope from this precedence chain.

4. `uiItems` (untagged) do not use tag scope resolution:
   - identity is `ButtonId`-anchored
   - propagation follows shared vs non-shared layer rules

### Required Test Target ID Dimensions

Updated split rule (authoritative):

- Tagged controls (have `ButtonTagId`) must use effective-scope identity + resolved programming identity for the `scopedTestTargetID`.
- `uiItems` are untagged controls and must use `ButtonId`-anchored identity (tag scope cannot be resolved when no tag exists).
- Every test result is broadcast only to targets with the exact same `scopedTestTargetID`.

### `scopedTestTargetID` Shapes

~~`tt:{rtiAddress}:{pageId}:{layerId}:{buttonId}:{effectiveRoomId}:{effectiveSourceId}:{targetName}`~~

Tagged controls:

`tt2:{rtiAddress}:{scopeType}:{effectiveRoomId}:{effectiveSourceId}:{buttonTagId}:{programRef}:{targetName}`

Untagged `uiItems`:

`tt_ui:{rtiAddress}:{sharedFlag}:{sharedLayerId_or_layerId}:{buttonId}:{targetName}`

### Field Rules

1. `effectiveRoomId`
   - `apexScopeSource.viewportLayer.roomId` when not `NULL`
   - else `apexScopeSource.pageLayer.roomId` when not `NULL`
   - else `PagesView.RoomId`

2. `effectiveSourceId`
   - `apexScopeSource.viewportLayer.sourceId` when not `NULL`
   - else `apexScopeSource.pageLayer.sourceId` when not `NULL`
   - else `PagesView.SourceDeviceId`

3. `scopeType`
   - `GLOBAL` when resolved behavior row uses `RoomId=0`
   - `ROOM` when resolved behavior row uses nonzero room

4. `programRef` (tagged controls only)
   - variable target: `var:{VariableId}`
   - macro target: `macro:{MacroId}`
   - macro-step target: `mstep:{MacroId}:{MacroStepId}`

5. `uiItems` (untagged controls)
   - `sharedFlag`:
     - `SHARED` when the control is on a shared layer
     - `LOCAL` when it is not on a shared layer
   - `sharedLayerId_or_layerId`:
     - use `SharedLayerId` when `sharedFlag=SHARED`
     - use layer instance identity when `sharedFlag=LOCAL`
   - always include `ButtonId`

### Resulting Behavior

- Same tag on different scoped buttons does not share pass/fail.
- A pass is recorded only for the exact resolved runtime scope.
- `uiItems` without tags do not fall back to tag/text identity.
- Broadcast is equality-based: same `scopedTestTargetID` => same result.

### Why This Works

- Tagged controls are keyed by effective scope + resolved programming identity, so duplicate tags do not bleed across different resolved scopes.
- Untagged `uiItems` are keyed by `ButtonId`-anchored identity, so they do not require tag-based resolution.
- Shared `uiItems` can propagate by sharing the same `tt_ui` identity; non-shared `uiItems` remain local.
- Results are propagated strictly by exact `scopedTestTargetID` match.

## Verified Example: Source-Scoped Room Target

Context (investigated case):

- Device family: iPhone runtime (`RTIAddress=2`)
- Page: `Office LG TV`
- Button tag: `Channel Up`

Resolved scope/programming:

- Effective scope: room/source-scoped (`ROOM`)
- Resolved macro: `MacroId=3122`
- Resolved macro step: `MacroStepId=5921`
- Macro step function: `CHANNEL UP`
- Macro step device: `DeviceId=74`

Resolved ID:

`tt2:2:ROOM:2:74:20:mstep:3122:5921:MacroStep`

Observed sharing behavior:

- Other iPhone pages sharing this exact ID: `0`

## Global Pages

This section is intentionally separated for global-page-specific rules and evidence.

Pending investigation items:

1. Global page default room/source behavior and fallback rules.
2. Effective scope resolution when layer room/source are global or unset.
3. Global target propagation rules for shared layers across pages.
4. Canonical `scopedTestTargetID` behavior validation for global-only controls.

### Explicit Unknown (Must Be Proven)

- On global pages, when a layer is set to `Use Default Room` and `Use Default Source`, the exact runtime-resolved room/source is not yet proven.
- Current working hypothesis: effective room may come from runtime `selected room`; effective source may come from a runtime/page default source path.
- This remains unconfirmed until validated with direct runtime evidence tied back to `.apex` records.
