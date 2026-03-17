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
- `"<description>" | <resolvedTrigger>, run macro <macroName>`

Approved trigger style inside that row:
- sense events use `When ...`
- scheduled events use `On ...`
- startup events use `On ...`

Driver-event display format:
- `When <resolvedTrigger> happens, run macro <macroName>`
- if no usable macro name is available but a direct command is proven:
  - `When <resolvedTrigger> happens, run command <commandName>`

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
   - for user-facing internal sense labels, prefer the internal negative label-key range:
     - `PortLabels.LabelKey = -65024..-65017`
   - do not use the generic positive `Sense 1` label when a proven internal label such as `Gate` exists
4. resolve sense mode from `SenseModeMap` where `RTIAddress = 0` and `ExpanderId = -1`
5. decode mode per port from the mask:
   - use:
     - `is_closure = bool(Mask & (1 << SensePort))`
   - if `is_closure` is true:
     - `Sense Closure`
   - otherwise:
     - `Sense Voltage`
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

Validated cross-project evidence:
- `Sung Residence v207.2.apex`
  - `SenseModeMap.Mask = 1`
  - only port `0` / input `1` is closure mode
  - software confirms:
    - input `1` = `Sense Closure`
    - inputs `2-8` = `Sense Voltage`
  - proven event fit:
    - `SensePort = 0` (`Gate`) resolves through closure wording
- `Verrier Home FEENY EDIT v49.apex`
  - `SenseModeMap.Mask = 195`
  - `SensePort = 4` is not closure mode because bit `4` is not set
  - software confirms the related septic events are `Sense Voltage`
  - therefore closure wording such as `opens` is incorrect for those events

### Resolved Trigger: Scheduled Events

Status: `locked for proven fixed and astronomical cases`

Source fields:
- `Events.DailyAstronomical`
- `Events.DailyStartTime`
- `Events.DailyDayMask`

Approved rules so far:
- scheduled trigger data is file-backed in `Events`
- astronomical schedule subtype mapping is approved:
  - `DailyAstronomical = 1` and `DailyStartTimeHex ...0000` -> `At Sunrise`
  - `DailyAstronomical = 1` and `DailyStartTimeHex ...0001` or `...0100` -> `At Sunset`

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
  - suffix `...0000` -> `At Sunrise`
  - suffix `...0001` or `...0100` -> `At Sunset`

Validated examples:
- `EventId=126` -> `At Sunrise`
- `EventId=127` -> `At Sunset`

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

#### Direct root-tag method

Status: `not approved as the default for Sung system-event wrappers`

Candidate source:
- event-linked macro row
- `Events.MacroId -> Macros.MacroId`
- then a usable naming path on that macro row itself

Note:
- a direct tag-backed name may be usable for some event macros
- but it is not universal and should not be treated as a general rule that tag name equals macro name
- in the validated Sung system-event wrapper family, the root macro tag was repeatedly the wrong user-facing action name

Validated counterexamples from `Sung Residence v207.2.apex`:
- event `7`
  - root tag: `GARAGE DOOR - West is CLOSED`
  - correct user-facing action: child tag `GATE - is OPEN`
- event `80`
  - root tag: `SHADES - Laundry OPEN`
  - correct user-facing action: child tag `VACATION MODE - Master Bed/Bath ON`

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

#### Preferred method for the proven Sung system-event wrapper family

Status: `approved`

Proven example set:
- `Sung Residence v207.2.apex`
- validated events:
  - `7`
  - `80`
  - `81`
  - `82`
  - `83`
  - `84`
  - `85`
  - `86`
  - `87`
  - `88`
  - `89`
  - `90`
  - `91`
  - `92`
  - `93`
  - `94`
  - `95`
  - `96`
  - `97`
  - `98`
  - `99`
  - `100`
  - `101`
  - `102`
  - `103`
  - `104`

Method:
1. start from the event-linked macro row:
   - `Events.MacroId -> Macros.MacroId`
2. inspect related macro rows where:
   - `Macros.SystemMacroId = Events.MacroId`
3. if a related child row has a usable `ButtonTagId`
4. resolve:
   - `child Macros.ButtonTagId -> ButtonTagNames.ButtonTagName`
5. use that child tag as the user-facing `macroName`

Validated examples:
- event `7` -> child tag `GATE - is OPEN`
- events `80` / `81` / `82` / `83` -> child tag `VACATION MODE - Master Bed/Bath ON`
- events `84` / `85` / `86` / `87` -> child tag `VACATION MODE - Hallway/Stairs ON`
- events `88` / `89` / `90` / `91` -> child tag `VACATION MODE - Kitchen ON`
- events `92` / `93` -> child tag `VACATION MODE - Living ON`
- events `94` / `95` -> child tag `VACATION MODE - All Rooms Except Hallway Morning OFF`
- events `96` / `97` -> child tag `VACATION MODE - All Included Rooms Evening OFF`
- event `98` -> `STARTUP - Vacation OFF & Flags Reset & Garage Boiler OFF`
- event `99` -> `HRV - Master Bath Fan ON`
- event `100` -> `HRV - Master Bath Fan OFF`
- event `101` -> `POWER OFF - Room (All Systems)`
- event `102` -> `POWER OFF - Room (All Systems)`
- event `103` -> `POOL - Spa Mode OFF`
- event `104` -> `POWER - Gym OFF - TEST`

Rule boundary:
- for this proven Sung system-event wrapper family, prefer the child macro tag over the root macro tag
- these event macros behave like system/background wrapper macros and should not be interpreted like ordinary directly tagged button macros
- do not generalize this child-tag preference to every system event until the same structure is proven elsewhere

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
- `userFacing.driverCategory`
- `userFacing.resolvedTrigger`
- `userFacing.firstActionName`
- `userFacing.resolvedActions.macros[]`
- `userFacing.resolvedActions.macroSteps[]`
- `userFacing.macroStepCount`
- `userFacing.testTargets`

Current intent:
- driver events remain separate from system events
- user-facing driver events should show the driver identity, the resolved category, the resolved trigger, and the first resolved action name
- driver events may resolve to one macro, multiple macros, one macro step, or multiple macro steps
- the full proven action set is carried in `resolvedActions`

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

### Driver Category

Status: `approved for the current proven sample set`

Method:
1. start from the same matched driver event node used for `resolvedTrigger`:
   - `Events.DriverExtraString`
   - `Events.DriverId -> DriverData.SystemEvents`
   - match `<event ... tag="Events.DriverExtraString">`
2. inspect the matched event node's parent:
   - `<category name="...">`
3. expand any `%%VariableName%%` placeholders in that category `name` using:
   - `DriverData.DriverDeviceId -> DriverConfig.Name / DriverConfig.Value`
4. write the expanded category name to:
   - `userFacing.driverCategory`

Display rule:
- if `driverCategory` is non-empty, show:
  - `When <driverCategory> / <resolvedTrigger> happens, ...`

Validated examples:
- `Verrier Home FEENY EDIT v49.apex`
  - `Gate Schedule Manager`
    - `SCHEDULESTART1` -> `1:(Gate 1) Morning`
    - `SCHEDULEEND1` -> `1:(Gate 1) Morning`
    - `SCHEDULESTART3` -> `3:(Gate 2) Morning`
    - `SCHEDULESTART2` -> `2:(Gate 1) Evening`
  - `LS - DISPLAY Layers`
    - `stUp` -> `General`

### First Action Name + Resolved Actions

Status: `approved for the current proven sample set`

High-level method:
1. resolve the driver-event wrapper macro strictly through:
   - `Events.MacroId -> Macros.SystemMacroId`
   - and require:
     - `Macros.DeviceId = Events.DriverId`
2. inspect the wrapper macro in step order using `MacroStepsView`
3. resolve the full proven action set by the safe naming paths below
4. preserve action order exactly as proven from wrapper step order
5. set:
   - `userFacing.firstActionName` = the first resolved action in that ordered action set
   - `userFacing.resolvedActions.macros[]` = all resolved macro names in order
   - `userFacing.resolvedActions.macroSteps[]` = all resolved macro-step entries in order
   - `userFacing.macroStepCount` = total step count when macro-step behavior is being surfaced

#### Preferred path: named command function calls

Method:
- if any wrapper step uses:
  - `MacroStepsView.Type = 14`
  - with a non-null `CommandTagId`
- resolve:
  - `CommandTagId -> ButtonTagNames.ButtonTagName`
- if one command tag name is resolved:
  - add it to `resolvedActions.macros[]`
- if multiple command tag names are resolved:
  - add all of them to `resolvedActions.macros[]` in step order

This is the dominant pattern in the current sample set.

Validated examples:
- `ZONEOPEN010` -> `GARAGE DOOR - East is OPEN`
- `APP38GROUP01ON` -> `LIGHTS - West Bed Accent ON`
- `SCHEDULESTART1` (`Gate Schedule Manager`) -> `SCHEDULE - ACCESS Gate 1 [OPEN/HOLD]`
- `SCHEDULEEND1` (`Irrigation Schedule Manager`) -> `SCHEDULE - IRRIGATION Zone 1 [OFF]`
- `APP38GROUP79ON` (`App 56, Group 121 On`) ->
  - `LIGHTS - Back Yard Entertain OFF`
  - `ENTERTAIN - Back Lights are OFF`
- `APP38GROUP3AON` (`App 56, Group 58 On`) ->
  - `LIGHTS - Gym Accent ON`
  - `HRV - Gym Fan ON`

#### Secondary path: wrapper tag name

Method:
- if no command-tag function call name is available
- and the wrapper macro row has a usable `ButtonTagId`
- resolve:
  - `Macros.ButtonTagId -> ButtonTagNames.ButtonTagName`
- add that as the first and only entry in `resolvedActions.macros[]`

#### Fallback path: direct command decoding

Method:
- only use this path when no usable macro name is available
- if the wrapper contains direct command steps:
  - `MacroStepsView.Type = 1`
- if the first wrapper row only page-links or redirects, continue through the proven child macro chain:
  - `Macros.SystemMacroId = <current MacroId>`
- use the target command device's driver metadata:
  - `MacroStepsView.DeviceId -> DriverData.DeviceId -> DriverData.SystemFunctions`
- locate the `<function ...>` definition where:
  - `function @export = MacroStepsView.Function`
- map the stored step parameters to the function parameter definitions
- if a parameter choice label contains placeholders, expand them through that target driver's `DriverConfig`
- build a readable command summary from the resolved target/action fields
- add that summary to `resolvedActions.macroSteps[]` as:
  - `{ "name": "<resolved command summary>", "type": "command" }`

Validated examples:
- `SetDimmerLevel:QSDimmer` on Lutron:
  - Integration ID `13` -> `__IDName013`
  - `DriverConfig(DriverDeviceId=21, Name='__IDName013')='Guest Bed Shelf'`
  - resolved summary can be built from the function metadata and config values
- `SwitchCmd:Switch` on Lutron:
  - Integration ID `13`
  - command choice `2 -> On`, `3 -> Off`
  - `DriverConfig(DriverDeviceId=21, Name='__IDName013')='Guest Bed Shelf'`
  - resolved summary can be built from the function metadata and config values
- `setSelLyr:1` on Layer Switch:
  - function metadata plus config-backed group/layer names provide a readable direct-command summary path

#### Fallback path: undefined macro steps

Method:
- if no cleaner named macro or macro-step command path is available
- inspect the wrapper macro's step count
- set:
  - `userFacing.resolvedActions.macroSteps[]` to a same-length list of:
    - `{ "name": "", "type": "undefined" }`
  - `userFacing.macroStepCount` to the wrapper step count

Validated example:
- `OPSTATECHANGE002` wrapper macro includes:
  - variable test on `state002001`
  - conditional branching
  - relay actions on internal relay port 8
  - wrapper step count = `5`
  - approved placeholder wording target:
    - `run 5 undefined macro steps`

Rule boundary:
- prefer the earliest safe naming path above
- if none produces a trustworthy human-readable action name, leave the relevant action list empty rather than guessing
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
- `Macro = true` only when `resolvedActions.macros.length = 1`
- `Macros = true` only when `resolvedActions.macros.length > 1`
- `MacroStep = true` only when `resolvedActions.macroSteps.length = 1`
- `MacroSteps = true` only when `resolvedActions.macroSteps.length > 1`
- macro and macro-step cases set the appropriate flags independently when both exist

Validated example:
- `App 56, Group 121 On`
  - `firstActionName = LIGHTS - Back Yard Entertain OFF`
  - `resolvedActions.macros = ["LIGHTS - Back Yard Entertain OFF", "ENTERTAIN - Back Lights are OFF"]`
  - `resolvedActions.macroSteps = []`
  - `Trigger = true`
  - `Macros = true`
  - `Macro = false`
  - `MacroStep = false`
  - `MacroSteps = false`

### Display Count Derivation

Status: `approved`

Purpose:
- support shortened homepage wording such as `...+<count> more`

Method:
1. compute:
   - `totalActions = resolvedActions.macros.length + resolvedActions.macroSteps.length`
2. use:
   - `firstActionName` as the visible first action
3. if `totalActions > 1`, compute:
   - `remainingActions = totalActions - 1`
4. display:
   - `...+<remainingActions> more`

Validated example:
- `App 56, Group 121 On`
  - total actions = `2`
  - first action = `LIGHTS - Back Yard Entertain OFF`
  - remaining count = `1`
  - shortened title suffix = `...+1 more`

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
- `RTIDeviceData.SupportedOrientations`
- `RTIDeviceData.ScreenPortraitWidth`
- `RTIDeviceData.ScreenPortraitHeight`
- `RTIDeviceData.ScreenWidth`
- `RTIDeviceData.ScreenHeight`

Method:
1. determine portrait support from `SupportedOrientations`:
   - `1` -> portrait only
   - `2` -> landscape only
   - `3` -> both
2. if the device is portrait-only, allow fallback from missing portrait-specific dimensions to `ScreenWidth` / `ScreenHeight`
3. if the device is dual-orientation and portrait-specific dimensions exist, mark portrait supported
4. if the device is dual-orientation and no portrait-specific or landscape-specific dimensions exist, but one generic `ScreenWidth` / `ScreenHeight` pair exists, treat the device as a single-size device and choose portrait when `ScreenHeight >= ScreenWidth`
5. prefer `ScreenPortraitWidth` / `ScreenPortraitHeight` for portrait resolution

### Device UI: Landscape Support + Resolution

Status: `locked`

Source fields:
- `RTIDeviceData.SupportedOrientations`
- `RTIDeviceData.ScreenLandscapeWidth`
- `RTIDeviceData.ScreenLandscapeHeight`
- `RTIDeviceData.ScreenWidth`
- `RTIDeviceData.ScreenHeight`

Method:
1. determine landscape support from `SupportedOrientations`:
   - `1` -> portrait only
   - `2` -> landscape only
   - `3` -> both
2. if the device is landscape-only, allow fallback from missing landscape-specific dimensions to `ScreenWidth` / `ScreenHeight`
3. if the device is dual-orientation and landscape-specific dimensions exist, mark landscape supported
4. if the device is dual-orientation and no portrait-specific or landscape-specific dimensions exist, but one generic `ScreenWidth` / `ScreenHeight` pair exists, treat the device as a single-size device and choose landscape when `ScreenWidth > ScreenHeight`
5. prefer `ScreenLandscapeWidth` / `ScreenLandscapeHeight` for landscape resolution

Rendering rule:
- if only one orientation is supported, render that orientation with no orientation toggle controls
- if both orientations are supported, show a left-side portrait/landscape toggle
- render button and viewport geometry/visibility from the active orientation, not by falling back to portrait first

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
- `VisibleOrientations = 1`
  - `buttonUI.orientations.portrait.visible = true`
  - `buttonUI.orientations.landscape.visible = false`
- `VisibleOrientations = 2`
  - `buttonUI.orientations.portrait.visible = false`
  - `buttonUI.orientations.landscape.visible = true`

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
- `VisibleOrientations = 1`
  - `viewportUI.orientations.portrait.visible = true`
  - `viewportUI.orientations.landscape.visible = false`
- `VisibleOrientations = 2`
  - `viewportUI.orientations.portrait.visible = false`
  - `viewportUI.orientations.landscape.visible = true`

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

### Diagnostics: Device Rooms

Status: `locked`

Approved diagnostics fields:
- `diagnostics.rooms[].roomId`
- `diagnostics.rooms[].roomName`

Method:
1. start from the controller device's effective RTI address:
   - if `RTIDeviceData.CloneRTIAddress > 0`, use `CloneRTIAddress`
   - otherwise use `RTIDeviceData.RTIAddress`
2. resolve selectable room rows from:
   - `ControllerRoomList.RTIAddress = effective RTI address`
3. preserve controller room ordering from:
   - `ControllerRoomList.ControllerRoomOrder`
4. resolve each room name from:
   - `ControllerRoomList.RoomId -> Rooms.RoomId -> Rooms.Name`
5. emit the device diagnostics room list in that stored controller-room order

Rule boundary:
- this diagnostics room list is device-level controller scope, not page scope
- use `ControllerRoomList` as the primary source
- do not derive this list from page source rooms when `ControllerRoomList` exists
- `diagnostics.rooms[]` is the device's room list
- `diagnostics.rooms[].roomId` is the backing project room id for that device-room entry
- the array order of `diagnostics.rooms[]` is the device room order from `ControllerRoomList.ControllerRoomOrder`
- if no `ControllerRoomList` rows exist, leave `diagnostics.rooms` empty until a fallback method is separately approved

### Pages: Layers

Status: `locked for the current v2 user-facing shape`

Approved user-facing fields:
- `pages[].layers[].layerName`
- `pages[].layers[].layerOrder`
- `pages[].layers[].buttonCategories`
- `pages[].layers[].viewports`

Method:
1. resolve page-level layer rows from:
   - `RTIDevicePageData.PageId -> Layers.PageId`
2. exclude child viewport layers from `pages[].layers[]`:
   - only include rows where `Layers.ViewPortButtonId` is null for page-level layers
3. resolve `pages[].layers[].layerName` from:
   - `Layers.SharedLayerId -> SharedLayers.Name`
4. resolve `pages[].layers[].layerOrder` from:
   - `Layers.LayerOrder`
5. resolve each page layer's button rows from:
   - `Layers.SharedLayerId -> RTIDeviceButtonData.SharedLayerId`
6. exclude viewport container buttons from the owning page layer's `buttonCategories`
7. classify each remaining page-layer button row into exactly one category
8. resolve any viewport container button owned by that page layer into `pages[].layers[].viewports[]`

Approved user-facing categories:
- `screenLabels`
- `screenButtons`
- `hardButtons`

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
- page UI ownership is layer-first:
  - no page-level user-facing button or viewport may exist outside a `pages[].layers[]` entry
- page-layer ordering is file-backed from `Layers.LayerOrder`
- for frontend rendering:
  - keep `layerOrder` as raw file-backed order in extracted JSON
  - display the layer list in descending `layerOrder` so visually top layers appear first
  - paint higher `layerOrder` above lower `layerOrder` in the rendered device view
- generated layer-visibility overrides are frontend session state only:
  - store in `sessionStorage`
  - key by project + device + page + layer
  - survive in-app page changes and cross-device file navigation within the same browser session
  - reset on browser session end
  - do not live in extracted JSON
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
- start from `RTIDeviceButtonData.Text`
- if empty, keep empty text
- for display identity, replace each text token in the stored text while preserving all surrounding literal text:
  - `$%TAG!<value>%$` -> `<Text Tag: <value>>`
  - `$%VARIABLE!<value>%$` -> `<Text Variable: <value>>`
- preserve all non-token literal text exactly as stored, including mixed token+literal strings and line breaks

Validated examples:
- `$%TAG!SYSTEM - Room Name%$`
  - `<Text Tag: SYSTEM - Room Name>`
- `$%TAG!Stat [Temp In]%$°`
  - `<Text Tag: Stat [Temp In]>°`
- `Setpoint: $%TAG!Stat [Setpoint]%$°`
  - `Setpoint: <Text Tag: Stat [Setpoint]>°`

Render requirement:
- when `buttonIdentity.text` is written into HTML output, it must be HTML-escaped before rendering
- otherwise display strings like `<Text Tag: ...>` will be interpreted as markup and appear blank on screen

#### `buttonIdentity.buttonType`

Status: `locked for the currently proven control styles`

Source field:
- `RTIDeviceButtonData.ButtonStyle`

Approved style mapping:
- `5` -> `Slider`
- `6` -> `Image`
- `9` -> `Slider`
- `7` -> `Toggle`
- `10` -> `Toggle`
- `11` -> `LevelIndicatorBar`
- `14` -> `Image`
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
- `testTargets.macros`
- `testTargets.macroSteps`
- `testTargets.variables.Text`
- `testTargets.variables.Reversed`
- `testTargets.variables.Inactive`
- `testTargets.variables.Visible`
- `testTargets.variables.Value`
- `testTargets.variables.State`
- `testTargets.variables.Command`
- `testTargets.variables.Image`
- `testTargets.variables.List`
- `testTargets.pageLink`
- `resolvedPageLink`

#### Text target

Method:
- `testTargets.text = true` only when `RTIDeviceButtonData.Text` is non-empty and is not token-only text

#### Macro targets

Method:
1. resolve button tag name through `ButtonTagId -> ButtonTagNames`
2. resolve explicit attached macros through:
   - `RTIDeviceButtonData.GlobalMacroId`
   - `RTIDeviceButtonData.DeviceMacroId`
3. resolve direct button-step wrappers through:
   - `Macros.ButtonTagId = RTIDeviceButtonData.ButtonTagId`
4. inspect `MacroSteps` only for the direct button-step wrappers
5. `testTargets.macros = true` only when at least one explicit attached macro is present on the button row
6. `testTargets.macroSteps = true` only when at least one direct button-step wrapper is non-empty
7. do not set `testTargets.macroSteps = true` merely because an attached macro contains steps
8. otherwise `false`

Boundary:
- attached macro presence and direct button-step presence are separate user-facing test targets
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
     - true when:
       - `buttonIdentity.buttonType = Slider`
       - and any `Variables.ObjectData` token is non-empty
     - also true when:
       - `buttonIdentity.buttonType = LevelIndicatorBar`
       - and any `Variables.ObjectData` token is non-empty
   - `State`
     - true when:
       - `buttonIdentity.buttonType = Toggle`
       - and any `Variables.ObjectData` token is non-empty
   - `Command`
     - true only when:
       - `buttonIdentity.buttonType = Slider`
       - the button variable resolves through `Variables.VariableId`
       - and a matching `MacroDeviceCommand.VariableId` row exists
       - and `MacroDeviceCommand.MacroStepId` is null
     - this is variable-side command evidence, not macro-step command evidence
   - `Image`
     - true when:
       - `buttonIdentity.buttonType = Image`
       - and any `Variables.ObjectData` token is non-empty
   - `List`
     - true when:
       - `RTIDeviceButtonData.ButtonStyle = 8`
       - and any `Variables.ObjectData` token is non-empty
     - this is a user-facing list/browser presence target only
     - it does not prove the downstream macro-step or diagnostics action chain

Rule boundary:
- variable target flags are presence indicators only
- do not infer more specific user-facing meaning beyond the proven field tests above
- for `ObjectData`, use a strict proven control-type allowlist:
  - `Slider` controls -> `Value`
  - `Toggle` controls -> `State`
  - `LevelIndicatorBar` controls -> `Value`
  - `Image` controls -> `Image`
  - `ButtonStyle = 8` list/browser controls -> `List`
  - all other object types remain unresolved by default
- for variable-side `Command`, use the variable-side command path:
  - `Variables.VariableId -> MacroDeviceCommand.VariableId`
  - require `MacroDeviceCommand.MacroStepId = null`
- do not use driver-specific `ObjectData` wording as the general method
- do not assign `State` to slider controls
- do not assign `State` to `LevelIndicatorBar` controls
- do not use macro-step command rows to prove variable-side `Command`
- do not assign `Command` to `LevelIndicatorBar` controls
- do not assign `Value`, `State`, `Command`, or `List` to unknown future object types by fallback

Validated evidence:
- `Verrier Home FEENY EDIT v49.apex`
  - `Lights/Home (Pool)`
    - `Office Main [Toggle]`
      - RTI shows `Variable -> State`
      - current object is a non-slider control
      - backing `Variables.ObjectData` is non-empty
    - `Office Main [Slide]`
      - RTI shows `Variable -> Value`
      - current object is a slider control
      - backing `Variables.ObjectData` is non-empty
      - backing variable-side command row exists through:
        - `Variables.VariableId = 1270`
        - `MacroDeviceCommand.VariableId = 1270`
        - `MacroDeviceCommand.MacroStepId = null`
    - same split is also present for:
      - `Change Room [Toggle]` vs `Change Room [Slide]`
    - `Change Room [Slide]`
      - backing variable-side command rows exist through:
        - `Variables.VariableId = 343` / `1572`
        - matching `MacroDeviceCommand.VariableId`
        - `MacroDeviceCommand.MacroStepId = null`
  - `AudioGauge`
    - `buttonIdentity.buttonType = LevelIndicatorBar`
    - backing `Variables.ObjectData` is non-empty
    - no matching variable-side `MacroDeviceCommand` row exists
- `Sung Residence v207.2.apex`
  - `NP Progress`
    - `buttonIdentity.buttonType = LevelIndicatorBar`
    - backing `Variables.ObjectData` is non-empty
    - no matching variable-side `MacroDeviceCommand` row exists
  - `NP Cover`
    - `buttonIdentity.buttonType = Image`
    - backing `Variables.ObjectData` is non-empty
  - `Frame Indicator`
    - `buttonIdentity.buttonType = Image`
    - backing `Variables.ObjectData` is non-empty
- `Dash OS v54.4 iPhone.apex`
  - `Condition Graphic`
    - `buttonIdentity.buttonType = Image`
    - backing `Variables.ObjectData` is non-empty
- `Verrier Home FEENY EDIT v49.apex`
  - `Condition Graphic`
    - `buttonIdentity.buttonType = Image`
    - backing `Variables.ObjectData` is non-empty
  - `Browse`
    - `RTIDeviceButtonData.ButtonStyle = 8`
    - backing `Variables.ObjectData` is non-empty
    - user-facing target should be `Variable - List`
    - diagnostics for the downstream action chain remain unresolved
- read-only comparison across Verrier and Sung showed:
    - old slider objects (`ButtonStyle = 5`) follow the same value/command path as current slider objects
    - `Slider` controls are value-backed and command-capable only when the file-backed variable-side command row exists
    - `Toggle` controls are state-backed
    - `LevelIndicatorBar` controls are value-backed and not command-backed
    - `Image` controls are image-backed through `ObjectData`, including both `ButtonStyle = 6` and `ButtonStyle = 14`
    - list/browser controls with `ButtonStyle = 8` are list-backed through `ObjectData` for user-facing test targets only
    - additional `ObjectData` styles still exist and must remain unresolved until proven

#### Page-link target

Method:
1. fully resolve eventual navigation by the locked method in `resolvedPageLink`
2. if `resolvedPageLink` is non-null:
   - `testTargets.pageLink = true`
3. otherwise:
   - `testTargets.pageLink = false`

#### Resolved page link

Status: `locked for normalized singular user-facing navigation output`

This field is broader than direct button page-link detection and is the single user-facing navigation payload for the resolved button instance.

`testTargets.pageLink` answers:
- whether the button eventually resolves to a navigation target

`resolvedPageLink` answers:
- the final resolved navigation target for that properly scoped button instance

Allowed object shape:
- `targetPageId`
- `targetPageName`
- `resolutionPath`

Allowed `resolutionPath` values for the current locked method:
- `directPageLink`
- `macroStep`
- `roomSelectEvent`
- `activityEvent`
- `roomOffEvent`

Locked method:
1. Start with `resolvedPageLink = null`.
2. Resolve direct button page links:
   - first require the current pressed device context:
     - `PageLinks.DeviceId = current device DeviceId`
     - `PageLinks.ButtonTagId = RTIDeviceButtonData.ButtonTagId`
   - only fall back to tag-only matching when no device-scoped row exists for that button tag
   - when the matched direct page-link row has `PageLinks.LinkType = 1`:
     - do not treat `PageLinks.PageId` as the final target page id
     - resolve instead to the current device's first page:
       - lowest `RTIDevicePageData.PageOrder`
       - tie-break by lowest `RTIDevicePageData.PageId`
   - if a valid target is found for the properly scoped button instance, set:
     - `resolvedPageLink.targetPageId`
     - `resolvedPageLink.targetPageName`
     - `resolvedPageLink.resolutionPath = directPageLink`
3. Resolve macro-step page links:
   - only continue if `resolvedPageLink` is still null
   - resolve effective macro for the pressed button
   - inspect raw `MacroPageLink` first for `Type = 8` steps
   - when a `Type = 8` step has `MacroPageLink.Page` equal to a real `RTIDevicePageData.PageId`:
     - treat that raw page id as the exact target page
     - set `resolvedPageLink` from that page id/name with `resolutionPath = macroStep`
   - do not reinterpret that row through `MacroPageLinkView` when the raw `Page` is already a real page id
   - when raw `MacroPageLink.Page` is not a real page id:
     - continue with the existing view-based target handling below
   - when the same macro contains both:
     - `Type = 26` `Select Source`
     - and `Type = 8` page-link targets
   - for rows where `Type = 8`, resolve targets through `MacroPageLinkView`
   - when `MacroPageLinkView.TargetRTIAddress` and `MacroPageLinkView.TargetPageId` contain comma-separated values:
     - treat them as ordered positional pairs
     - preserve duplicate page ids
     - do not deduplicate either list before pairing
   - if a valid target is found for the properly scoped button instance, set `resolvedPageLink` with `resolutionPath = macroStep`
4. Resolve room-selection follow-up links:
   - only continue if `resolvedPageLink` is still null
   - when the pressed button resolves to `Type 24` `Select Room`
   - use `MacroSelectRoom.SelectRoomId`
   - inspect room-level `RoomEvents` macros for the selected room
   - resolve room-event landing targets by either of these proven paths:
     - direct room-event page link:
       - `RoomEvents.SelectedMacroId -> MacroStepsView.Type = 8 -> MacroPageLinkView`
     - room-event selected source followed by activity page link:
       - `RoomEvents.SelectedMacroId -> MacroStepsView.Type = 26 -> MacroSelectSource`
       - `MacroSelectSource.SelectSourceId` + room context -> `Activities.DeviceId` + `Activities.RoomId`
       - `Activities.PagelinkMacroId -> MacroStepsView.Type = 8 -> MacroPageLinkView`
   - when page-link rows expose comma-separated `TargetRTIAddress` and `TargetPageId` values:
     - treat them as ordered positional pairs
     - preserve duplicate page ids
     - select the page id whose paired RTI address matches the current pressed device instance
   - if those room-event macros contain a valid target for the properly scoped button instance, set `resolvedPageLink` with `resolutionPath = roomSelectEvent`
5. Resolve activity-selection links:
   - only continue if `resolvedPageLink` is still null
   - when the pressed button corresponds to an activity-selection control, resolve the pressed instance through `ButtonsAndListItems`
   - use the current page/source context from that `ButtonsAndListItems` row
   - for local room activities, derive current room from the page/source device context
   - resolve candidate tag macros through `Macros.ButtonTagId`
   - scope the activity-selection macro by current room when possible
   - inspect `MacroStepsView`
   - when the scoped macro contains `Type = 26`, use:
   - `SelectSourceId`
   - `SelectSourceRoomId`
 - if `SelectSourceRoomId > 0`, use that room id for the activity lookup
 - if `SelectSourceRoomId = -1`, use the current room context from the pressed page instance for the activity lookup
  - if that current room context resolves to `0` (`Global`) for activity page-link resolution:
    - read the current device's `diagnostics.rooms[]` source path from `ControllerRoomList`
    - choose the lowest non-zero `roomId`
    - use that room id for the activity lookup
    - this fallback applies only to activity page-link resolution
    - do not rewrite extracted page, layer, or diagnostics room truth

Verified direct-link scoping example:

- `Verrier Home FEENY EDIT v49.apex`
  - button tag: `NAVIGATION - to Room Select`
  - device-scoped page-link rows:
    - `DeviceId = 81` -> `PageLinkId = 1178` -> `PageId = 513` (`Room Select`)
    - `DeviceId = 82` -> `PageLinkId = 1175` -> `PageId = 509` (`Feeny Room Select`)
  - the iPad (`DeviceId = 82`) must resolve to `PageId = 509`
  - using tag-only direct page-link matching incorrectly bleeds the iPhone target onto the iPad

Verified `LinkType = 1` direct-link example:

- `Verrier Home FEENY EDIT v49.apex`
  - button tag: `Activity: Home`
  - device-scoped direct-link rows:
    - `DeviceId = 196` -> `LinkType = 1` -> `PageId = 115`
    - `DeviceId = 197` -> `LinkType = 1` -> `PageId = 116`
  - `115` / `116` are not real `RTIDevicePageData.PageId` targets
  - the actual device first pages are:
    - `DeviceId = 196` -> `PageId = 380` -> `PageName = Home`
    - `DeviceId = 197` -> `PageId = 381` -> `PageName = Home`
  - therefore `LinkType = 1` must resolve to the current device first page, not the raw `PageLinks.PageId`

Verified exact raw-page macro-step examples:

- `Verrier Home FEENY EDIT v49.apex`
  - button tag: `Activity: Apple TV 1 (Bed 2)`
  - button macro `7565` contains:
    - `Type = 26` -> `SelectSourceId = 248`, `SelectSourceRoomId = 23`
    - `Type = 8` raw `MacroPageLink` row:
      - `Device = 197`
      - `Page = 397`
  - `RTIDevicePageData.PageId = 397` -> `PageName = Apple TV 1`
  - therefore the correct `macroStep` target is `PageId = 397` (`Apple TV 1`)
- same proven family:
  - `Activity: Sat 1 (Bed 2)` -> raw `MacroPageLink.Page = 396` -> `Sat TV 1`
  - `Activity: Samsung TV (Bed 2)` -> raw `MacroPageLink.Page = 395` -> `TV Controls`
- boundary on the same project:
  - `Activities.PagelinkMacroId` macros for Bed 1 / Bed 2 activities use raw `MacroPageLink.Page = 0`
  - those rows do not directly identify a final page id and must keep using the existing `activityEvent` / `MacroPageLinkView` path
   - resolve the activity row through `Activities.RoomId` + `Activities.DeviceId`
   - inspect that activity row's `PagelinkMacroId`
   - resolve `Type = 8` targets through `MacroStepsView` + `MacroPageLinkView`
   - resolve `targetPageName` from `RTIDevicePageData.PageNameId -> PageNames.PageName`
   - if a valid target is found for the properly scoped button instance, set `resolvedPageLink` with `resolutionPath = activityEvent`
6. Resolve room-off links:
   - only continue if `resolvedPageLink` is still null
   - when the pressed button's effective macro contains `Type = 27`
   - use `MacroRoomOff.RoomOffId`
   - currently proven path:
     - if `RoomOffId = -1`, interpret it as `Current Room`
     - resolve current room from the pressed page instance
     - in `Activities`, find the row for that room where:
       - `Checked = 1`
       - `ActivityOrder = 0`
     - use that row's `PagelinkMacroId`
     - resolve `Type = 8` targets through `MacroStepsView` + `MacroPageLinkView`
     - select the page id whose paired RTI address matches the current pressed device instance
   - if a valid target is found for the properly scoped button instance, set `resolvedPageLink` with `resolutionPath = roomOffEvent`
7. If no proven eventual page target is found, leave `resolvedPageLink = null`.

Output discipline:
- do not fabricate page ids or page names
- keep `testTargets.pageLink` and `resolvedPageLink` separate
- `resolvedPageLink` is user-facing normalized navigation output intended for simulator/app behavior

Validated Verrier examples:
- iPhone `PageId = 518` (`Lights/Home (Master)`), `ButtonId = 50245`, `ButtonTagName = Activity: Apple TV 1`
  - `ButtonsAndListItems.SourceDeviceId = 8` -> current room `RoomId = 6` (`Master Bedroom`)
  - scoped tag macro `MacroId = 5940`
  - `Type = 26` -> `SelectSourceId = 227`, `SelectSourceRoomId = 6`
  - `Activities(RoomId = 6, DeviceId = 227)` -> `PagelinkMacroId = 5934`
  - `Type = 8` target includes iPhone `PageId = 521` -> `AppleTV 1 (Master Bed)`
- iPhone `PageId = 518`, `ButtonId = 50249`, `ButtonTagName = Activity: Samsung TV`
  - scoped tag macro `MacroId = 5943`
  - `Type = 26` -> `SelectSourceId = 121`, `SelectSourceRoomId = 6`
  - `Activities(RoomId = 6, DeviceId = 121)` -> `PagelinkMacroId = 5188`
  - `Type = 8` target includes iPhone `PageId = 525` -> `Samsung TV (Master)`
- iPhone `PageId = 518`, `ButtonId = 50250`, `ButtonTagName = Activity: Climate`
  - scoped tag macro `MacroId = 5962`
  - `Type = 26` -> `SelectSourceId = 229`, `SelectSourceRoomId = 6`
  - `Activities(RoomId = 6, DeviceId = 229)` -> `PagelinkMacroId = 5961`
  - `Type = 8` target includes iPhone `PageId = 519` -> `Climate (Master)`
- iPhone `PageId = 518`, `ButtonId = 57070`, `ButtonTagName = Activity: AV Overview`
  - global tag macro `MacroId = 7005`
  - `Type = 26` -> `SelectSourceId = 314`, `SelectSourceRoomId = -1`
  - approved fallback for this method: use current room context from the pressed page instance
  - `Activities(RoomId = 6, DeviceId = 314)` -> `PagelinkMacroId = 6988`
  - `Type = 8` target includes iPhone `PageId = 761` -> `AV Overview`
- iPhone `Room Select`, `ButtonTagName = Activity: AV Overview`
  - global tag macro `MacroId = 7005`
  - `Type = 26` -> `SelectSourceId = 314`, `SelectSourceRoomId = -1`
  - page source room on `Room Select` is `0` (`Global`)
  - temporary approved testing fallback for this global-page case:
    - use `RoomId = 6`
  - `Activities(RoomId = 6, DeviceId = 314)` -> `PagelinkMacroId = 6988`
  - `Type = 8` target includes iPhone `PageId = 761` -> `AV Overview`
- iPhone `Room Select`, `ButtonTagName = Room: Pool`
  - button macro `MacroId = 5874`
  - `Type = 24` -> `SelectRoomId = 9` (`Pool`)
  - room-event page-link row contains:
    - `TargetRTIAddress = 4,5,9,1,2,3,7`
    - `TargetPageId = 607,607,607,606,606,606,606`
  - these are ordered positional pairs and duplicates are meaningful
  - iPhone current device is `RTIAddress = 3`
  - correct resolved target is iPhone `PageId = 606` -> `Lights/Home (Pool)`
- iPhone `PageId = 521` (`AppleTV 1 (Master Bed)`), `ButtonTagName = POWER - (Room) AudioVideo OFF`
  - global tag macro `MacroId = 5860`
  - `Type = 27` -> `MacroRoomOff.RoomOffId = -1` (`Current Room`)
  - page source room is `RoomId = 6`
  - `Activities(RoomId = 6, Checked = 1, ActivityOrder = 0)` -> `PagelinkMacroId = 5185`
  - `Type = 8` target includes iPhone `PageId = 518` -> `Lights/Home (Master)`
- iPhone `PageId = 606` (`Lights/Home (Pool)`), `ButtonTagName = POWER - (Room) AudioVideo OFF`
  - global tag macro `MacroId = 5860`
  - `Type = 27` -> `MacroRoomOff.RoomOffId = -1` (`Current Room`)
  - page source room is `RoomId = 9`
  - `Activities(RoomId = 9, Checked = 1, ActivityOrder = 0)` -> `PagelinkMacroId = 5440`
  - `Type = 8` target includes iPhone `PageId = 606` -> `Lights/Home (Pool)`
- Sung `Initial Load Page`, `ButtonTagName = To Whole Home Floorplan`
  - button macro `MacroId = 1964`
  - `Type = 24` -> `SelectRoomId = 25` (`Whole House`)
  - `RoomEvents(RoomId = 25)` selected macro `MacroId = 1973`
  - room-event macro does not contain direct `Type = 8`
  - room-event macro contains `Type = 26` -> `SelectSourceId = 127`, `SelectSourceRoomId = 25`
  - `Activities(RoomId = 25, DeviceId = 127)` -> `PagelinkMacroId = 1957`
  - that pagelink macro contains `Type = 8`
  - RTI-specific targets then resolve the device landing page

### Viewports: Identity + Layers + Frames

Status: `locked for the current v2 user-facing shape`

Approved user-facing fields:
- `viewportIdentity.viewportButtonId`
- `viewports[].layers[].layerName`
- `viewports[].layers[].layerOrder`
- `viewports[].layers[].frames[].frameId`
- `viewports[].layers[].frames[].buttonCategories`

#### `viewportIdentity.viewportButtonId`

Method:
1. identify viewport container buttons through:
   - `Layers.ViewPortButtonId`
2. use the referenced button id as `viewportIdentity.viewportButtonId`

#### `viewports[].layers[].layerName`

Method:
1. resolve child viewport layers through:
   - `Layers.ViewPortButtonId = viewportButtonId`
2. resolve each child viewport layer name from:
   - `Layers.SharedLayerId -> SharedLayers.Name`
3. use the resolved shared-layer name as `viewports[].layers[].layerName`

#### `viewports[].layers[].layerOrder`

Method:
1. resolve child viewport layers through:
   - `Layers.ViewPortButtonId = viewportButtonId`
2. use `Layers.LayerOrder` as `viewports[].layers[].layerOrder`

Rule boundary:
- viewport child UI is layer-owned
- do not flatten viewport child buttons directly onto the viewport root when a child layer exists
- viewport child-layer ordering is file-backed from `Layers.LayerOrder`

#### `viewports[].layers[].frames[].frameId`

Method:
1. resolve child layers through:
   - `Layers.ViewPortButtonId = viewportButtonId`
2. resolve child-layer button rows through:
   - `RTIDeviceButtonData.SharedLayerId = Layers.SharedLayerId`
3. group rows by `RTIDeviceButtonData.FrameNumber`
4. group frame rows inside the owning viewport child layer
5. use `FrameNumber` as `viewports[].layers[].frames[].frameId`

#### `viewports[].layers[].frames[].buttonCategories`

Method:
- apply the same locked `screenLabels` / `screenButtons` / `hardButtons` categorization rules used for page-level buttons to each frame's grouped button set

Rule boundary:
- viewport frames are reconstructed from child-layer button rows only
- viewport frame button categories belong to the owning viewport child layer
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

Resolved runtime note from Verrier room-selection review:

- the room-selector viewport button is not the final navigation carrier
- for `Room: Master Bedroom` on iPhone `Room Select` (`PageId = 513`):
  - button-tag macro resolves to `Type 24` -> `Select Room: Master Bedroom`
  - no direct button page-link step is required on that room-selector item
  - room-level follow-up navigation is carried by `RoomEvents` macros for `RoomId = 6`
  - those room-event macros include `Type 8` page-link steps targeting `Lights/Home (Master)` on the iPhone (`PageId = 518`)
- use this distinction when resolving navigation:
  - room selector button -> room context change
  - room-selected event -> landing page
- do not collapse room-selection navigation and activity-selection navigation into one rule:
  - room selection can land through `RoomEvents`
  - activity selection can land through `Activities.PagelinkMacroId`

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
- do not mark a macro `empty` just because its step types are not yet resolved into page-link or command summaries
- `MacroFlag`-only macros are `not empty` because they have real `MacroSteps`
5. Presentation rule:
- after text-label review, hide `Label Type = Text` rows from main non-text action table

Validated example:
- `Verrier Home FEENY EDIT v49.apex`
  - `ButtonTagName = AV - Select Apple TV 1`
  - iPad `AV Overview` uses `MacroId = 6951`
  - `MacroSteps` contains four rows (`11808`, `11809`, `11810`, `11807`)
  - all four are `Type = 15` and resolve through `MacroFlag`
  - therefore `isEmpty = true` is incorrect for this button

### Button macro diagnostics: `MacroFlag` summaries

Status: `locked for raw file-backed flag summaries`

Method:
- when a button's direct button-step wrapper macro contains `MacroStepsView.Type = 15`
- read:
  - `MacroStepsView.FlagIndex`
  - `MacroStepsView.FlagType`
- build one raw summary per step in step order:
  - `FlagIndex=<n>, FlagType=<m>`
- if multiple `MacroFlag` steps exist on the same wrapper macro:
  - join them in order with ` | `
- store that joined summary in:
  - `diagnostics.buttons[].testTargets.macro.resolvedCommand`

Rule boundary:
- this is a raw schema-backed resolution path
- do not guess semantic names for `FlagType` values that are not already proven
- for current button diagnostics, raw `FlagIndex` / `FlagType` output is preferred over invented action wording

Validated example:
- `Verrier Home FEENY EDIT v49.apex`
  - `ButtonTagName = AV - Select Apple TV 1`
  - wrapper `MacroId = 6951`
  - ordered `MacroFlag` steps:
    - `FlagIndex=253, FlagType=0`
    - `FlagIndex=254, FlagType=0`
    - `FlagIndex=255, FlagType=0`
    - `FlagIndex=252, FlagType=1`

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
- `resolvedPageLink`

`Test Targets` is a set populated only from what exists on that button:
- `Label` (only for pure label rows: text shown, no non-empty macro, no variable, no page link)
- `Macros`
- `Macro Steps`
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
