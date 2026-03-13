# RTI `.apex` Page Item Resolution: Verrier iPad (#1) Page 1

Working note for `apex_project_structure_v2.json`:
- the `source` section was removed from the v2 contract
- reason: `source.file` and `source.extractedAtUtc` are extraction metadata created by Sentinel, not file-backed `.apex` data
- therefore `source` is out of scope for this resolving document
- `userFacing` fields in the v2 contract may include derived presentation fields when they are produced by a documented, repeatable method grounded in `.apex` data
- examples include section titles, grouping labels, and resolved action summaries for technician-facing display

---

## V2 Locked Methods: System Events

This section tracks approved methods for the `events.system.items[]` shape in `apex_project_structure_v2.json`.

### User-Facing Row Format

Status: `approved`

Homepage/system-event display format:
- `<description> | <resolvedTrigger>, run macro <macroName>`

Approved trigger style inside that row:
- sense events use `When ...`
- scheduled events use `On ...`
- startup events use `On ...`

### Description

Status: `locked`

Method:
- use `Events.Description`
- if `Events.Description` is empty, leave description empty
- do not invent a fallback description

### Resolved Trigger: Sense Events

Status: `locked for internal controller sense inputs`

Source fields:
- `Events.SensePort`
- `Events.SenseAction`
- `Events.SenseExpanderId`
- `PortLabels`
- `SenseModeMap`

Method:
1. treat `SenseExpanderId = -1` as an internal controller sense input
2. resolve the port name from `PortLabels` at `RTIAddress = 0`
3. use the proven internal sense label mapping:
   - `port_number = (LabelKey & 65535) - 512 + 1`
   - `sense_port_index = port_number - 1`
   - match `sense_port_index = Events.SensePort`
4. resolve sense mode from `SenseModeMap` where `RTIAddress = 0` and `ExpanderId = -1`
5. decode mode:
   - mask bit `1` -> `Sense Closure`
   - mask bit `0` -> `Sense Voltage`
6. decode action wording by mode:
   - `Sense Closure`
     - `SenseAction = 0` -> `closes`
     - `SenseAction = 1` -> `opens`
   - `Sense Voltage`
     - `SenseAction = 0` -> `goes high`
     - `SenseAction = 1` -> `goes low`

Audience-specific output:
- `userFacing.resolvedTrigger`
  - use the port name and resolved action wording only
  - for sense events, prefix with `When`
  - example: `When Gate opens`
- `diagnostics.resolvedTrigger`
  - include full locating detail
  - example: `When Sense Port 1 (Gate) opens`

Notes:
- the user does not need port numbers
- diagnostics does need port numbers
- this method is currently proven for internal controller sense inputs, not expander inputs

### Resolved Trigger: Scheduled Events

Status: `locked for proven fixed and astronomical cases`

Source fields:
- `Events.DailyAstronomical`
- `Events.DailyStartTime`
- `Events.DailyDayMask`

Approved rules so far:
- scheduled trigger data is file-backed in `Events`
- astronomical schedule subtype mapping is approved:
  - `DailyAstronomical = 1` and `DailyStartTimeHex ...0000` -> `On sunrise`
  - `DailyAstronomical = 1` and `DailyStartTimeHex ...0001` -> `On sunset`

#### Fixed scheduled triggers

Status: `approved for proven day-mask values`

Method:
1. require:
   - `EventType = 3`
   - `DailyAstronomical = 0`
2. read `Events.DailyDayMask`
3. use currently proven day-group mappings:
   - `62` -> `Weekdays`
   - `65` -> `Weekends`
   - `127` -> `Every day`
4. unpack `Events.DailyStartTime` as eight little-endian unsigned 16-bit values
5. use:
   - element 5 -> `hour24`
   - element 6 -> `minute`
6. convert `hour24` and `minute` to 12-hour AM/PM formatting
7. build the resolved trigger:
   - `On {dayGroup lowercase} at {h:mm AM/PM}`

Validated examples:
- `On weekdays at 7:35 AM`
- `On weekends at 9:45 PM`
- `On every day at 9:00 AM`

Rule boundary:
- the fixed scheduled trigger method is currently locked only for the proven `DailyDayMask` values above
- other day-mask values remain unresolved until proven

#### Astronomical scheduled triggers

Status: `approved`

Method:
- if `DailyAstronomical = 1`
- inspect `DailyStartTimeHex`
- decode:
  - suffix `...0000` -> `On sunrise`
  - suffix `...0001` -> `On sunset`

Validated examples:
- `EventId=126` -> `On sunrise`
- `EventId=127` -> `On sunset`

### Resolved Trigger: Startup Events

Status: `approved`

Source field:
- `Events.StartupType`

Approved rule:
- startup trigger data is file-backed in `Events.StartupType`
- current approved resolved trigger wording:
  - `On system startup`

Rule boundary:
- `StartupType` is the file-backed source field
- current sample evidence does not yet prove meaningful user-facing startup subtype distinctions
- do not invent subtype wording beyond `On System Startup` until proven

### Macro Name: System Events

Status: `partially locked`

The event user's `macroName` is not the same thing as a `ButtonTagName`.
Tags are containers and may carry macros, variables, or text-variable behavior.
They must not be treated as canonical macro names by default.

#### Direct method

Status: `approved when present and useful`

Candidate source:
- event-linked macro row
- `Events.MacroId -> Macros.MacroId`
- then a usable naming path on that macro row itself

Note:
- a direct tag-backed name may be usable for some event macros
- but it is not universal and should not be treated as a general rule that tag name equals macro name

#### Fallback method for untagged system macros

Status: `approved`

Proven example set:
- `Sung Residence v207.2.apex`
- event-linked macros:
  - `4660`
  - `4662`
  - `4664`
  - `4658`
  - `4659`

Method:
1. start from the event-linked macro row:
   - `Events.MacroId -> Macros.MacroId`
2. if that macro row does not yield a usable direct macro name
3. search `Macros` for related rows where:
   - `Macros.SystemMacroId = <event-linked Macros.MacroId>`
4. if a related row has a usable `ButtonTagId`
5. resolve:
   - `Macros.ButtonTagId -> ButtonTagNames.ButtonTagName`
6. use that resolved name as the fallback `macroName`

Validated examples:
- event macro `4660` -> related macro row `5083` -> `VACATION MODE - Hallway/Stairs ON`
- event macro `4662` -> related macro row `5085` -> `VACATION MODE - Kitchen ON`
- event macro `4664` -> related macro row `5087` -> `VACATION MODE - Living ON`
- event macro `4658` -> related macro row `5092` -> `VACATION MODE - All Rooms Except Hallway Morning OFF`
- event macro `4659` -> related macro row `5093` -> `VACATION MODE - All Included Rooms Evening OFF`

Rule boundary:
- this fallback method is proven for these system-event macro families
- it should be used when the related `SystemMacroId` row exists and yields a usable name
- it is not yet treated as a universal macro-name rule for every event macro

### Test Targets: System Events

Status: `approved for the current proven sample set`

Source evidence:
- enabled system events checked in:
  - `Sung Residence v207.2.apex`
  - `Verrier Home FEENY EDIT v49.apex`
- all enabled system events in those files:
  - have a trigger
  - have a `MacroId`

Approved rule:
- `userFacing.testTargets.Trigger = true`
- `userFacing.testTargets.Macro = true`

Reasoning:
- the technician tests whether the system-event trigger occurred
- the technician also tests whether the intended macro ran

Rule boundary:
- this is locked for the current proven sample set
- do not generalize beyond the proven enabled system-event samples until a counterexample is found or broader evidence is reviewed

## V2 Working Shape: Driver Events

This section tracks the approved target shape for `events.driver.items[]` in `apex_project_structure_v2.json` while driver-event resolution methods are investigated.

Approved working shape:
- `userFacing.eventType`
- `userFacing.driverName`
- `userFacing.resolvedTrigger`
- `userFacing.macroName`
- `userFacing.testTargets`

Current intent:
- driver events remain separate from system events
- user-facing driver events should show the driver identity, the resolved trigger, and the macro name
- test targets are expected to follow the same technician-facing pattern as system events unless a driver-event exception is proven

### Driver Name

Status: `approved`

Method:
1. join:
   - `Events.DriverId -> Devices.DeviceId`
2. read:
   - `Devices.DisplayName`
   - `Devices.Name`
3. resolve the preferred name:
   - use `Devices.DisplayName` when it is non-empty
   - otherwise fall back to `Devices.Name`

Usage:
- `userFacing.driverName`
- `diagnostics.driverName`

Note:
- keep both raw fields available during resolution if needed
- but the main resolved `driverName` should always prefer `DisplayName`

### Resolved Trigger

Status: `approved for the current proven sample set`

High-level method:
1. start from:
   - `Events.DriverExtraString`
   - `Events.DriverId`
2. join:
   - `Events.DriverId -> DriverData.DeviceId`
3. parse:
   - `DriverData.SystemEvents`
4. match the `<event ...>` node where:
   - `event @tag = Events.DriverExtraString`
5. start the trigger template from the matched XML `name` attribute
6. expand any `%%VariableName%%` placeholders in that template using:
   - `DriverData.DriverDeviceId -> DriverConfig.Name / DriverConfig.Value`
7. if the resolved template is still generic and the event tag ends with an integer suffix:
   - inspect `DriverData.ConfigItems` for a proven numbered user-facing name family
   - if an exact same-index config variable exists and is clearly the event-name companion for that family, append or enrich the trigger with that resolved name
   - otherwise keep the generic resolved template
8. if no safe enrichment is proven, keep the trigger explicit and unresolved rather than guessing

Universal rule boundary:
- the system goal is one generic driver-event trigger pipeline
- do not add hand-authored driver profiles when the event template, config values, and config-item metadata already provide the necessary resolution path
- prefer leaving a trigger generic or unresolved over inventing a family-specific rule that is not proven from the driver metadata

Current sample-set result:
- all enabled driver-event tokens in:
  - `Sung Residence v207.2.apex`
  - `Verrier Home FEENY EDIT v49.apex`
  matched a `DriverData.SystemEvents` event definition
- no enabled driver-event triggers in those files remained unresolved after the approved generic steps above

#### Proven example families

These examples are evidence cases for the generic pipeline above, not separate custom-profile rules.

##### Clipsal C-Bus `APP38GROUP...`

Method used:
- match `Events.DriverExtraString` to `DriverData.SystemEvents @tag`
- use the matched XML `name` directly

Validated examples:
- `APP38GROUP01ON` -> `App 56, Group 1 On`
- `APP38GROUP01OFF` -> `App 56, Group 1 Off`
- `APP38GROUP3CON` -> `App 56, Group 60 On`
- `APP38GROUP3COFF` -> `App 56, Group 60 Off`

##### DSC PowerSeries `ZONE...`

Method used:
- match `Events.DriverExtraString` to `DriverData.SystemEvents @tag`
- start from XML `name`
- expand `%%ZoneNameN%%` placeholders through `DriverConfig`

Validated examples:
- `ZONEOPEN002` -> `Garage West DOOR Opened`
- `ZONECLOSED002` -> `Garage West DOOR Closed`
- `ZONEOPEN010` -> `Garage East DOOR Opened`
- `ZONECLOSED010` -> `Garage East DOOR Closed`

##### Venstar `OPSTATECHANGE...`

Method used:
- match `Events.DriverExtraString` to `DriverData.SystemEvents @tag`
- start from XML `name`
- expand `%%StatNameNNN%%` placeholders through `DriverConfig`

Validated example:
- `OPSTATECHANGE002` -> `Garage (Stat 2) - Operating State Change`

##### Schedule Manager `SCHEDULESTART...` / `SCHEDULEEND...`

Method used:
- match `Events.DriverExtraString` to `DriverData.SystemEvents @tag`
- start from XML `name` (`Schedule Start` / `Schedule End`)
- use the numeric suffix from the event tag
- use `DriverData.ConfigItems` + `DriverConfig` to prove the numbered companion name variable family:
  - `scheduleNameN`
- enrich the generic trigger with the same-index schedule name

Validated examples:
- `SCHEDULESTART1` + `scheduleName1='(Gate 1) Morning'` -> `Schedule Start - (Gate 1) Morning`
- `SCHEDULEEND1` + `scheduleName1='(Gate 1) Morning'` -> `Schedule End - (Gate 1) Morning`
- `SCHEDULESTART10` + `scheduleName10='(Zone 5) Evening'` -> `Schedule Start - (Zone 5) Evening`
- `SCHEDULEEND14` + `scheduleName14='(Pool Room) Evening'` -> `Schedule End - (Pool Room) Evening`

##### Layer Switch `stUp`

Method used:
- match `Events.DriverExtraString` to `DriverData.SystemEvents @tag`
- use the matched XML `name`

Validated example:
- `stUp` -> `Startup`

### Macro Name

Status: `approved for the current proven sample set`

High-level method:
1. resolve the driver-event wrapper macro strictly through:
   - `Events.MacroId -> Macros.SystemMacroId`
   - and require:
     - `Macros.DeviceId = Events.DriverId`
2. inspect the wrapper macro in step order using `MacroStepsView`
3. resolve `macroName` by the first safe naming path below

#### Preferred path: named command function calls

Method:
- if any wrapper step uses:
  - `MacroStepsView.Type = 14`
  - with a non-null `CommandTagId`
- resolve:
  - `CommandTagId -> ButtonTagNames.ButtonTagName`
- if one command tag name is resolved:
  - use it as `macroName`
- if multiple command tag names are resolved:
  - join them in step order as a readable summary

This is the dominant pattern in the current sample set.

Validated examples:
- `ZONEOPEN010` -> `GARAGE DOOR - East is OPEN`
- `APP38GROUP01ON` -> `LIGHTS - West Bed Accent ON`
- `SCHEDULESTART1` (`Gate Schedule Manager`) -> `SCHEDULE - ACCESS Gate 1 [OPEN/HOLD]`
- `SCHEDULEEND1` (`Irrigation Schedule Manager`) -> `SCHEDULE - IRRIGATION Zone 1 [OFF]`

#### Secondary path: wrapper tag name

Method:
- if no command-tag function call name is available
- and the wrapper macro row has a usable `ButtonTagId`
- resolve:
  - `Macros.ButtonTagId -> ButtonTagNames.ButtonTagName`
- use that as `macroName`

#### Fallback path: direct command decoding

Method:
- if the wrapper contains direct command steps:
  - `MacroStepsView.Type = 1`
- use the target command device's driver metadata:
  - `MacroStepsView.DeviceId -> DriverData.DeviceId -> DriverData.SystemFunctions`
- locate the `<function ...>` definition where:
  - `function @export = MacroStepsView.Function`
- map the stored step parameters to the function parameter definitions
- if a parameter choice label contains placeholders, expand them through that target driver's `DriverConfig`
- build a readable command summary from the resolved target/action fields

Validated examples:
- `SetDimmerLevel:QSDimmer` on Lutron:
  - Integration ID `13` -> `__IDName013`
  - resolved summary can be built from the function metadata and config values
- `SwitchCmd:Switch` on Lutron:
  - Integration ID `13`
  - command choice `2 -> On`, `3 -> Off`
  - resolved summary can be built from the function metadata and config values
- `setSelLyr:1` on Layer Switch:
  - function metadata plus config-backed group/layer names provide a readable direct-command summary path

#### Fallback path: comment / explicit action summary

Method:
- if no cleaner name is available from function calls, wrapper tag name, or direct command decoding
- inspect explicit action steps and comment text in step order
- build a concise summary only from proven step data

Validated example:
- `OPSTATECHANGE002` wrapper macro includes:
  - variable test on `state002001`
  - comments:
    - `Close the XP-8 relay`
    - `Open the XP-8 relay`
  - relay actions on internal relay port 8
  - internal relay label:
    - `Garage Boiler Trigger`
- this provides a file-backed summary path without inventing a custom driver profile

Rule boundary:
- prefer the earliest safe naming path above
- if none produces a trustworthy human-readable name, leave `macroName` unresolved rather than guessing
- the goal is one generic macro-resolution pipeline, not a growing list of driver-specific profiles

Current sample-set result:
- all enabled driver-event macros in:
  - `Sung Residence v207.2.apex`
  - `Verrier Home FEENY EDIT v49.apex`
  had at least one safe naming path through the approved generic method above

### Test Targets

Status: `approved for the current proven sample set`

Source evidence:
- enabled driver events checked in:
  - `Sung Residence v207.2.apex`
  - `Verrier Home FEENY EDIT v49.apex`
- all enabled driver events in those files:
  - have a trigger token
  - have an assigned event macro

Approved rule:
- `userFacing.testTargets.Trigger = true`
- `userFacing.testTargets.Macro = true`

## V2 Locked Methods: Devices User Facing

This section tracks approved methods for the `devices[].userFacing` shape in `apex_project_structure_v2.json`.

### Display Name

Status: `locked`

Method:
1. read non-clone controller rows from `RTIDeviceData`
2. join:
   - `RTIDeviceData.DeviceId -> Devices.DeviceId`
3. read:
   - `Devices.DisplayName`
   - `Devices.Name`
4. resolve the preferred name:
   - use `Devices.DisplayName` when it is non-empty
   - otherwise fall back to `Devices.Name`

Rule boundary:
- clones are irrelevant duplicates for this section
- exclude clone rows from the device-level user-facing device list
- do not add clone-aware inheritance logic here

### Device UI: Portrait Support + Resolution

Status: `locked`

Source fields:
- `RTIDeviceData.ScreenPortraitWidth`
- `RTIDeviceData.ScreenPortraitHeight`

Method:
1. use `ScreenPortraitWidth` as `userFacing.deviceUI.portrait.resolution.width`
2. use `ScreenPortraitHeight` as `userFacing.deviceUI.portrait.resolution.height`
3. set `userFacing.deviceUI.portrait.supported = true` only when both values are greater than `0`
4. otherwise set `supported = false`

### Device UI: Landscape Support + Resolution

Status: `locked`

Source fields:
- `RTIDeviceData.ScreenLandscapeWidth`
- `RTIDeviceData.ScreenLandscapeHeight`

Method:
1. use `ScreenLandscapeWidth` as `userFacing.deviceUI.landscape.resolution.width`
2. use `ScreenLandscapeHeight` as `userFacing.deviceUI.landscape.resolution.height`
3. set `userFacing.deviceUI.landscape.supported = true` only when both values are greater than `0`
4. otherwise set `supported = false`

### Button UI: Orientation-Aware Geometry

Status: `locked for primary/alt geometry mapping; visibility mask partially locked`

Approved user-facing shape:
- `buttonUI.fontSize`
- `buttonUI.orientations.portrait.visible`
- `buttonUI.orientations.portrait.coordinates`
- `buttonUI.orientations.landscape.visible`
- `buttonUI.orientations.landscape.coordinates`

Proven source fields:
- `RTIDeviceButtonData.VisibleOrientations`
- primary geometry:
  - `RTIDeviceButtonData.ButtonTop`
  - `RTIDeviceButtonData.ButtonLeft`
  - `RTIDeviceButtonData.ButtonHeight`
  - `RTIDeviceButtonData.ButtonWidth`
- alternate geometry:
  - `RTIDeviceButtonData.ButtonTopAlt`
  - `RTIDeviceButtonData.ButtonLeftAlt`
  - `RTIDeviceButtonData.ButtonHeightAlt`
  - `RTIDeviceButtonData.ButtonWidthAlt`

Geometry mapping:
1. use the primary geometry fields for `buttonUI.orientations.portrait.coordinates`
2. use the alternate geometry fields for `buttonUI.orientations.landscape.coordinates`

Proven evidence:
- `Dash OS v54.4 iPhone.apex`
  - device `RTiPanel (iPhone X or newer)`:
    - portrait resolution `1242 x 2454`
    - landscape resolution `2424 x 1179`
  - representative button rows fit this mapping consistently:
    - base geometry fits portrait bounds
    - alt geometry fits landscape bounds
- `Dash OS v54.4 iPhone.apex`
  - device `KA11`:
    - portrait resolution `1080 x 1920`
    - landscape resolution `1920 x 1080`
  - representative button rows fit the same mapping consistently

Visible-orientation method:
- `VisibleOrientations = 3`
  - `buttonUI.orientations.portrait.visible = true`
  - `buttonUI.orientations.landscape.visible = true`
- `VisibleOrientations = 2`
  - `buttonUI.orientations.portrait.visible = true`
  - `buttonUI.orientations.landscape.visible = false`

Current rule boundary:
- `VisibleOrientations = 3` and `VisibleOrientations = 2` are proven from the current sample evidence
- `VisibleOrientations = 1` is a strong working inference for landscape-only but is not yet locked here
- if a visibility-mask value is not proven, preserve the geometry and leave the unresolved visibility mapping explicit rather than guessing

Locked method boundary:
- the v2 contract must preserve per-orientation visibility and per-orientation geometry for future testing workflows
- `VisibleOrientations` is the file-backed orientation visibility source
- the primary and alternate geometry field families are the file-backed orientation geometry sources
- do not collapse orientation-specific geometry into one flat `coordinates` block
- do not guess unproven visibility-mask values beyond what is explicitly proven by the file-backed evidence

### Viewport UI: Orientation-Aware Geometry

Status: `locked for primary/alt geometry mapping and navigation-mode threshold; visibility mask partially locked`

Approved user-facing shape:
- `viewportUI.navigationMode`
- `viewportUI.orientations.portrait.visible`
- `viewportUI.orientations.portrait.coordinates`
- `viewportUI.orientations.landscape.visible`
- `viewportUI.orientations.landscape.coordinates`

Proven source fields:
- viewport container button row:
  - `RTIDeviceButtonData.ViewPortVerticalScroll`
  - `RTIDeviceButtonData.VisibleOrientations`
  - `RTIDeviceButtonData.ButtonTop`
  - `RTIDeviceButtonData.ButtonLeft`
  - `RTIDeviceButtonData.ButtonHeight`
  - `RTIDeviceButtonData.ButtonWidth`
  - `RTIDeviceButtonData.ButtonTopAlt`
  - `RTIDeviceButtonData.ButtonLeftAlt`
  - `RTIDeviceButtonData.ButtonHeightAlt`
  - `RTIDeviceButtonData.ButtonWidthAlt`

Geometry mapping:
1. use the primary geometry fields for `viewportUI.orientations.portrait.coordinates`
2. use the alternate geometry fields for `viewportUI.orientations.landscape.coordinates`

Navigation mode method:
- if `RTIDeviceButtonData.ViewPortVerticalScroll != 0`
  - set `viewportUI.navigationMode = verticalScroll`
- if `RTIDeviceButtonData.ViewPortVerticalScroll = 0`
  - set `viewportUI.navigationMode = page`

User-facing meaning:
- `page`
  - the viewport flips between frames
  - technician navigation is left/right
- `verticalScroll`
  - the viewport scrolls vertically
  - technician navigation is up/down

Visible-orientation method:
- `VisibleOrientations = 3`
  - `viewportUI.orientations.portrait.visible = true`
  - `viewportUI.orientations.landscape.visible = true`
- `VisibleOrientations = 2`
  - `viewportUI.orientations.portrait.visible = true`
  - `viewportUI.orientations.landscape.visible = false`

Locked method boundary:
- viewport orientation support must be preserved through the viewport container button row
- the same primary/alt geometry mapping used for buttons also applies to viewport container rows
- `ViewPortVerticalScroll = 0` is page mode
- any non-zero `ViewPortVerticalScroll` value is vertical-scroll mode
- do not collapse viewport orientation-specific geometry into one flat `coordinates` block
- do not invent viewport-only orientation rules separate from the underlying button-row evidence
- `VisibleOrientations = 1` remains outside the locked viewport visibility mapping until it is explicitly proven

### Pages: Page Name

Status: `locked`

Method:
1. read page rows from `RTIDevicePageData` for the device's non-clone `RTIAddress`
2. join:
   - `RTIDevicePageData.PageNameId -> PageNames.PageNameId`
3. use `PageNames.PageName` as `userFacing.pages[].pageName`
4. preserve page order from `RTIDevicePageData.PageOrder`

Rule boundary:
- use the file-backed page name only
- do not invent fallback page titles

### Pages: Button Categories

Status: `locked for the current v2 user-facing shape`

Approved user-facing categories:
- `screenLabels`
- `screenButtons`
- `hardButtons`

Method:
1. resolve page-level button rows from:
   - `RTIDevicePageData.PageId -> Layers.PageId -> RTIDeviceButtonData.SharedLayerId`
2. exclude viewport container buttons from the page-level button categories
3. classify each remaining button row into exactly one category

Category rules:
- `hardButtons`
  - use rows where the primary geometry is zero-sized:
    - `ButtonHeight = 0`
    - `ButtonWidth = 0`
- `screenLabels`
  - require:
    - no enabled page link
    - no macro target
    - some display content exists:
      - literal text or text-variable content
    - `buttonIdentity.buttonType = null`
- `screenButtons`
  - all remaining non-hard user-facing buttons

Rule boundary:
- category assignment is derived from file-backed button structure plus resolved user-facing test targets
- do not place a button in multiple user-facing categories

### Buttons: Identity

Status: `locked`

Approved user-facing fields:
- `buttonIdentity.buttonTagName`
- `buttonIdentity.text`
- `buttonIdentity.buttonType`

#### `buttonIdentity.buttonTagName`

Method:
1. read `RTIDeviceButtonData.ButtonTagId`
2. if `ButtonTagId` is present, join:
   - `ButtonTagNames.ButtonTagId -> ButtonTagNames.ButtonTagName`
3. use the resolved `ButtonTagName`
4. if no tag id is present, leave `buttonTagName = null`

#### `buttonIdentity.text`

Method:
- use `RTIDeviceButtonData.Text`
- preserve the stored text exactly, including empty text

#### `buttonIdentity.buttonType`

Status: `locked for the currently proven control styles`

Source field:
- `RTIDeviceButtonData.ButtonStyle`

Approved style mapping:
- `9` -> `Slider`
- `7` -> `Toggle`
- `11` -> `LevelIndicatorBar`
- otherwise -> `null`

Rule boundary:
- only the proven style mappings above are currently locked
- do not invent additional control-type labels until proven

### Buttons: UI Font Size

Status: `locked`

Method:
- use `RTIDeviceButtonData.TextSize` as `buttonUI.fontSize`

### Buttons: Test Targets

Status: `locked for the current v2 user-facing shape`

Approved user-facing fields:
- `testTargets.text`
- `testTargets.macro`
- `testTargets.variables.Text`
- `testTargets.variables.Reversed`
- `testTargets.variables.Inactive`
- `testTargets.variables.Visible`
- `testTargets.variables.Value`
- `testTargets.variables.State`
- `testTargets.variables.Command`
- `testTargets.pageLink.enabled`
- `testTargets.pageLink.targetPageId`

#### Text target

Method:
- `testTargets.text = true` only when `RTIDeviceButtonData.Text` is non-empty and is not token-only text

#### Macro target

Method:
1. resolve button tag name through `ButtonTagId -> ButtonTagNames`
2. resolve candidate macros through:
   - `Macros.ButtonTagId = RTIDeviceButtonData.ButtonTagId`
3. inspect `MacroSteps` for each candidate macro
4. `testTargets.macro = true` only when at least one candidate macro is non-empty
5. otherwise `false`

Boundary:
- current extractor path uses tag-backed macro detection for user-facing macro presence
- keep unresolved scope-specific macro matching out of this locked user-facing presence rule

#### Variable targets

Method:
1. resolve candidate variable rows through:
   - `Variables.ButtonTagId = RTIDeviceButtonData.ButtonTagId`
2. populate flags strictly from file-backed fields:
   - `Text`
     - true when any `Variables.ButtonText` is non-empty
     - or `ButtonTextTags` contains the button id
     - or `RTIDeviceButtonData.Text` is token-only text
   - `Reversed`
     - true when any `Variables.ReversedData` is non-empty
   - `Inactive`
     - true when any `Variables.InactiveData` is non-empty
   - `Visible`
     - true when any `Variables.VisibleData` is non-empty
   - `Value`
     - true when any `Variables.ObjectData` token contains `@DDL`
   - `State`
     - true when any `Variables.ObjectData` token contains `@DDS`
   - `Command`
     - true only when:
       - `buttonIdentity.buttonType = Slider`
       - and `Value = true`

Rule boundary:
- variable target flags are presence indicators only
- do not infer more specific user-facing meaning beyond the proven field tests above

#### Page-link target

Method:
1. if `RTIDeviceButtonData.ButtonTagId` is present, resolve:
   - `PageLinks.ButtonTagId = RTIDeviceButtonData.ButtonTagId`
2. if a page-link row exists:
   - `testTargets.pageLink.enabled = true`
   - `testTargets.pageLink.targetPageId = PageLinks.PageId`
3. otherwise:
   - `enabled = false`
   - `targetPageId = null`

### Viewports: Identity + Frames

Status: `locked for the current v2 user-facing shape`

Approved user-facing fields:
- `viewportIdentity.viewportButtonId`
- `frames[].frameId`
- `frames[].buttonCategories`

#### `viewportIdentity.viewportButtonId`

Method:
1. identify viewport container buttons through:
   - `Layers.ViewPortButtonId`
2. use the referenced button id as `viewportIdentity.viewportButtonId`

#### `frames[].frameId`

Method:
1. resolve child layers through:
   - `Layers.ViewPortButtonId = viewportButtonId`
2. resolve child-layer button rows through:
   - `RTIDeviceButtonData.SharedLayerId = Layers.SharedLayerId`
3. group rows by `RTIDeviceButtonData.FrameNumber`
4. use `FrameNumber` as `frames[].frameId`

#### `frames[].buttonCategories`

Method:
- apply the same locked `screenLabels` / `screenButtons` / `hardButtons` categorization rules used for page-level buttons to each frame's grouped button set

Rule boundary:
- viewport frames are reconstructed from child-layer button rows only
- do not invent synthetic frame ids or frame ordering beyond the stored `FrameNumber`

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
