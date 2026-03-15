# APEX Data Extraction Scope for Codex

## Purpose

This document defines the known scope of data that can be extracted from an RTI `.apex` file for use in another application.

It is written for AI-assisted analysis and implementation planning.

The goal is to give Codex a reliable map of:

- what is confirmed extractable now
- what is partially understood
- what schema areas exist but are not fully explored
- which exact identifiers and relationships must be preserved

## Evidence Base

This document is derived from:

- all docs in `ApexDiscovery`
- root repository docs that define `.apex` constraints and data contracts
- current extraction code in the codebase
- current tests in the codebase
- direct schema inspection of sample `.apex` files in `ApexDiscovery/Assets`
- direct schema inspection of the current working samples in `Initial Testing`:
  - `Sung Residence v207.2.apex`
  - `Verrier Home FEENY EDIT v49.apex`

Primary doc evidence:

- `ApexDiscovery/apex_discovery_all_info.md`
- `ApexDiscovery/Achives/apex_extraction_schemas.md`
- `ApexDiscovery/Achives/proven_apex_data.md`
- `ApexDiscovery/Achives/apex_general_scope_info.md`
- `ApexDiscovery/Achives/apex_discovery_diagnostics_info.md`
- `data_contracts.md`

## Non-Negotiable Facts

- A `.apex` file is a SQLite database.
- The code treats `.apex` as read-only input.
- The main extraction path opens the file with `Mode=ReadOnly`.
- The broader extractor first copies the `.apex` file to a temp `.apex` path, then reads the temp copy in read-only mode.
- Missing or unresolved data is expected to remain explicit; names must not be fabricated.
- Current extraction logic is deterministic and based on direct joins, string parsing, XML parsing, and stable lookup maps.

## Current Extraction Entry Points

### 1. Confirmed primary extractor: `ApexDiscoveryPreloadExtractor.Extract`

This is the repository's current authoritative extraction path for reusable `.apex` preload data.

It returns an `ApexDiscoveryPreloadResult` with these top-level data sets:

- `PageIndexMap`
- `SysVarRefMap`
- `DriverConfigMap`
- `PageMappings`
- `RelayPorts`
- `MpioIrPorts`
- `SensePorts`
- `TriggerPorts`
- `Rs232Ports`
- `RoomMappings`
- `SourceCatalog`
- `SystemManagerSourceCatalog`
- `DriverTemplateVariables`
- `ExpansionDeviceTypes`

### 2. Confirmed broader extractor: `ProjectDataExtractor.Extract`

This is a second, broader extraction path that still reads directly from the `.apex` database.

It produces:

- `DiagnosticsMapping`
- `ProjectReport`
- `ProjectTest`
- `ApexDiscoveryPreload` (by calling the primary extractor)

This path is useful because it proves additional extraction methods beyond the preload contract, especially for:

- page identity beyond page names
- source labels
- layers
- button instances
- flat report-style entity export

### 3. Confirmed projection wrappers

These do not read the database themselves. They re-project already extracted `.apex` data:

- `ApexSystemExtractor.Extract`
- `ApexDriverExtractor.Extract`

They confirm that the repository expects `.apex` data to be reusable as structured system-level and driver-level data.

## Confirmed Extractable Now

The following are confirmed by current code and backed by passing tests where noted.

### A. Page index to page name mapping

Status: `confirmed extractable now`

Output:

- key: `deviceId|pageIndex`
- value: `pageName`

Source chain:

- `RTIDeviceData.DeviceId`
- `RTIDeviceData.RTIAddress`
- `RTIDevicePageData.PageOrder`
- `RTIDevicePageData.PageNameId`
- `PageNames.PageName`

Important rules:

- `PageOrder` is the true per-device page index.
- `PageNumber` in user-facing lists is `PageOrder + 1`.
- `PageId` must not be used as the page index.
- Clone-aware logic exists:
  - if `RTIDeviceData.CloneRTIAddress` exists and is greater than zero, page lookup uses that address instead of the device's own `RTIAddress`.

This clone behavior is explicitly tested.

### B. Page mappings with device, room, and source context

Status: `confirmed extractable now`

Output fields:

- `device_id`
- `device_name`
- `room_id`
- `room_name`
- `source_id`
- `source_name`
- `page_number`
- `page_name`

Source chain:

- controller device: `RTIDeviceData -> Devices`
- page rows: `RTIDevicePageData`
- source device: `RTIDevicePageData.SourceDeviceId -> Devices`
- room: source `Devices.RoomId -> Rooms`
- page name: `PageNames`

This is the repository's strongest current page-context extraction model.

### C. Room to source to page to controller mapping

Status: `confirmed extractable now`

Output fields:

- `room_id`
- `room_name`
- `source_id`
- `source_name`
- `controller_device_id`
- `controller_device_name`
- `page_id`
- `page_name`

Source chain:

- `Rooms`
- source device via `Devices.RoomId`
- page via `RTIDevicePageData.SourceDeviceId`
- controller via `RTIDevicePageData.RTIAddress -> RTIDeviceData -> Devices`

This is useful when the target app needs room-centric navigation instead of device-centric navigation.

### D. Driver config extraction

Status: `confirmed extractable now`

Output shape:

- key: `driverDeviceId`
- value:
  - `deviceName`
  - `deviceDisplayName`
  - `config` key/value map

Source chain:

- `DriverConfig`
- `DriverData`
- `Devices`

Confirmed behaviors:

- `Debug*` config keys are excluded.
- `DisplayName` falls back to `Name` when blank.
- Config groups are bounded by discovered limits when applicable:
  - `MaxZones`
  - `MaxSources`
  - `Inputs`
  - `Outputs`
- Prefix/count filtering also exists for matched driver profiles.
- Special-case filtering exists for `System Variable Events` devices.

This is tested.

### E. `System Variable Events` filtered config extraction

Status: `confirmed extractable now`

This is a special case inside driver config extraction.

Confirmed filtering rules:

- drop `Config_PersistEnabledStates`
- drop values equal to `(not set)`
- drop boolean config groups when the paired `Macro` value is blank
- drop integer config groups when the paired `Macro` value is blank or `0`

This prevents exporting dead config groups that exist structurally but are not actually configured.

### F. SYSVARREF registry and human-readable variable resolution

Status: `confirmed extractable now`

Output shape:

- key: normalized full SYSVARREF
- value:
  - `driverDeviceId`
  - `driverName`
  - `variableName`
  - `deviceId`

Confirmed parsing behavior:

- stored keys are normalized to `SYSVARREF:{GUID}#...@Token`
- GUID is parsed from the SYSVARREF string
- token is parsed as the substring after `@`
- driver lookup is done through `DriverData.DriverId`
- human-readable variable names come from `DriverData.SystemVariables` XML
- device identity comes from `SystemVariableIds.DeviceId`

Supported forms:

- standard form: `{GUID}#NN@Token`
- device-scoped form: `{GUID}#<DeviceId>@Token`

This is tested.

### G. Driver template variable extraction

Status: `confirmed extractable now`

Output fields:

- `driver_device_id`
- `driver_device_name`
- `driver_display_name`
- `sysvar_ref`
- `sysvar_token`
- `source_driver_id`
- `source_driver_name`
- `variable_category`
- `variable_name`
- `variable_type`
- `format`

Source chain:

- driver instance: `Devices + DriverData`
- SYSVARREF population: `SystemVariableIds`
- variable metadata: parsed from `DriverData.SystemVariables` XML

Confirmed XML parsing rules:

- looks for `<variable ...>`
- takes `name`
- takes `type` or `datatype`
- takes `format`
- takes nearest ancestor `<category name="...">`

This is tested.

### H. Source catalog extraction

Status: `confirmed extractable now`

Output fields:

- `device_id`
- `room_id`
- `control_type`
- `source_name`
- `source_display_name`

Current source definition:

- `Devices` rows where `ControlType IN (5, 6)`

Ordering rule:

- ordered by `DeviceId`

This is the base source list used by current System Manager source resolution.

### I. System Manager source catalog

Status: `confirmed extractable now`

Output fields:

- `source_index`
- `source_name`

Current logic:

- count System Manager tokens from `SystemVariableIds` matching:
  - `SourceInUse<N>`
  - `SourceName<N>`
- build the visible catalog by:
  - optional prefix sources discovered from `SourceName*` values in driver config
  - then append the device-derived `SourceCatalog`
- fill missing slots with explicit blanks
- store as zero-based indices

Important implication:

- the current code does not use the older simple `Devices ordered by DeviceId` assumption by itself; it builds a token-space-aware catalog.

### J. Expansion device type detection

Status: `confirmed extractable now`

Output:

- set of distinct `ExpansionDevices.DeviceType` values for `RTIAddress = 0`

Current extractor does not only infer expansion model names from labels; it explicitly captures raw device type integers.

This is tested.

### K. Port extraction: relay

Status: `confirmed extractable now`

Output fields:

- `controller_device_name`
- `expander_device_type`
- `expander_name`
- `relay_name`
- `relay_type`
- `relay_mode`

Source chain:

- controller: `RTIDeviceData(RTIAddress=0) -> Devices`
- labels: `PortLabels`
- expansion context: `ExpansionDevices`

Confirmed label rules:

- internal relay labels use `LabelKey` range `-64768..-64761`
- expansion relay rows also include labels where `LabelName LIKE 'Relay %'`

Confirmed inference:

- `expander_id = LabelKey >> 16`

Current model names hard-coded in code:

- `3 -> ESC-2`
- `5 -> RCM-4`
- `6 -> XP-6`

Current limitations:

- relay type/mode are hard-coded per current known cases, not generically decoded for all expansion hardware

This is tested for internal relay state.

### L. Port extraction: MPIO/IR

Status: `confirmed extractable now`

Output fields:

- `controller_device_name`
- `expander_device_type`
- `expander_name`
- `port_number`
- `port_name`

Confirmed label rules:

- internal range: `-65536..-65529`
- XP-6 range: `65536..65543`

Confirmed inference:

- `expander_id = LabelKey >> 16`
- `port_number = (LabelKey & 65535) % 256 + 1`

This is tested.

### M. Port extraction: sense

Status: `confirmed extractable now`

Output fields:

- `controller_device_name`
- `expander_device_type`
- `expander_name`
- `port_number`
- `port_name`
- `sense_mode_state`

Confirmed label rules:

- internal range: `-65024..-65017`
- XP-6 range: `66048..66055`

Confirmed inference:

- `expander_id = LabelKey >> 16`
- `port_number = (LabelKey & 65535) - 512 + 1`

Confirmed sense mode decoding:

- `SenseModeMap` at `RTIAddress = 0`, `ExpanderId = -1`
- each internal port reads one bit from the mask
- bit `1` -> `Sense Closure`
- bit `0` -> `Sense Voltage`

This is tested.

### N. Port extraction: trigger

Status: `confirmed extractable now`

Output fields:

- `controller_device_name`
- `expander_device_type`
- `expander_name`
- `trigger_number`
- `trigger_name`

Confirmed label rules:

- current trigger range: `66307..66309`

Confirmed inference:

- `expander_id = LabelKey >> 16`
- `trigger_number = (LabelKey & 65535) - 770`

Current code assumes the observed trigger rows are XP-6-context trigger labels.

This is tested.

### O. Port extraction: RS-232

Status: `confirmed extractable now`

Output fields:

- `controller_device_name`
- `expander_device_type`
- `expander_name`
- `port_number`
- `port_name`

Confirmed label rules:

- internal range: `-65280..-65273`
- XP-6 range: `65792..65799`

Confirmed inference:

- `expander_id = LabelKey >> 16`
- `port_number = (LabelKey & 65535) - 256 + 1`

This is tested.

### P. Broader diagnostics mapping extraction

Status: `confirmed extractable now`

This comes from `ProjectDataExtractor`, not the preload contract.

Output fields:

- `DeviceId`
- `DeviceName`
- `DeviceDisplayName`
- `RtiAddress`
- `PageIndex`
- `PageId`
- `PageNameId`
- `PageName`

Important behavior:

- diagnostics mapping is built against each device's effective RTI address
- clone-aware address selection exists here too

This path is important if the new app needs both page names and raw page identifiers.

### Q. Flat report extraction

Status: `confirmed extractable now`

This comes from `ProjectDataExtractor.ProjectReport`.

Current exported entity types:

- `Room`
- `Device`
- `Port`
- `Page`
- `Source`

This is not a full schema export, but it proves a simple flat report model can be built directly from `.apex`.

### R. Button/source test index extraction

Status: `confirmed extractable now`

This comes from `ProjectDataExtractor.ProjectTest`.

Current output fields:

- `DeviceId`
- `DeviceName`
- `RtiAddress`
- `SourceLabelId`
- `SourceLabelIndex`
- `SourceLabelName`
- `PageId`
- `PageNameId`
- `PageName`
- `ButtonId`
- `ButtonTagId`
- `ButtonText`

Confirmed source chain:

- device -> `RTIDeviceData`
- pages -> `RTIDevicePageData`
- page layers -> `Layers`
- source label lookup -> `SourceLabels`
- button rows -> `RTIDeviceButtonData`

This is the strongest current evidence that button-level extraction is feasible, even though button text/tag resolution is not fully generalized in production code.

## Partially Supported or Incomplete

These areas are known and partially documented, but are not fully generalized in current implementation.

### A. Macro extraction

Status: `partially supported / incomplete`

Known now:

- `Macros` provides structural IDs and scope-like fields:
  - `MacroId`
  - `SystemMacroId`
  - `RoomId`
  - `DeviceId`
  - `ButtonTagId`
  - `OutputType`
- `MacroSteps` and `MacroStepsView` hold step sequences.
- `ButtonTagId` can sometimes be mapped through `ButtonTagNames`.

Not yet proven:

- a canonical macro name field
- a universal rule for global vs room vs source macro scoping
- a complete typed action model for every macro subtype table

### B. Generic variables beyond driver template variables

Status: `partially supported / incomplete`

Known now:

- `Variables`
- `VariableNames`
- `SystemVariableIds`
- `VariableRedirect`
- `VariableRedirectView`

Current code fully exploits only:

- `SystemVariableIds` for SYSVARREF resolution
- driver XML metadata for named variables

Not yet fully productized:

- a complete extract of user variables from `Variables + VariableNames`
- safe semantic interpretation of variable values
- redirect-aware variable tracing

### C. System Manager variables beyond source-name resolution

Status: `partially supported / incomplete`

Known now:

- System Manager uses GUID `{20186C86-446C-4FC6-89E1-1931718A169B}`.
- Current code handles only source catalog reconstruction.

Not yet proven:

- room source categories
- selected room state naming
- layer visibility variables
- popup-related variables
- time-related variables
- a complete naming taxonomy for all System Manager token families

### D. Source labels vs true source routing

Status: `partially supported / incomplete`

Known now:

- `SourceLabels` is read by `ProjectDataExtractor`.
- `SourceCatalog` is currently derived from `Devices.ControlType IN (5,6)`.

Not yet proven:

- whether `SourceLabels` can be treated as authoritative source naming across projects
- how `SourceMapping` should modify, override, or contextualize source relationships
- whether source labels are complete when blank or partially populated

### E. Buttons and UI label resolution

Status: `partially supported / incomplete`

Known now:

- relevant schema is present:
  - `Layers`
  - `LayerButtons` view
  - `RTIDeviceButtonData`
  - `ButtonTagNames`
  - `ButtonTextTags`
  - `AllButtons`
  - `AllButtonsWithTextTags`
  - `ButtonsAndListItems`
- docs show practical extraction methods for page -> layer -> button traversal

Current code only partially uses this:

- `ProjectDataExtractor` uses `Layers` and `RTIDeviceButtonData`
- it does not yet perform a complete button text/tag resolution pipeline

Not yet generalized:

- reliable final button label precedence rules across all layouts
- denormalized view selection strategy (`LayerButtons` view vs raw tables)

### F. Project metadata extraction

Status: `partially supported / incomplete`

Known now from docs:

- `JobInfo` contains company/client style fields
- `UnstructuredData` can contain:
  - cloud IDs
  - database upgrade markers
  - save history
  - timestamps
  - usernames
  - machine names
  - file paths
  - DB version traces

Current code does not extract this.

This is a strong candidate for future cross-project metadata extraction.

### G. IO maps beyond current hard-coded port logic

Status: `partially supported / incomplete`

Known now:

- `RelayModeMap`
- `RelayTypeMap`
- `SenseModeMap`
- `RS232Data`
- `RS232DataStrings`
- `IrData`
- `IrFunction`
- `ExpansionDevices`

Current code uses:

- `SenseModeMap` directly
- `ExpansionDevices` directly
- `PortLabels` directly
- hard-coded rules for several device types and ranges

Not yet generalized:

- broad support for additional expansion hardware
- authoritative decoding of all relay mask variants
- richer IR and RS-232 capability extraction beyond names

## Known Schema Paths That Exist But Are Not Fully Explored

These schema areas are present in sample `.apex` files and are relevant to a future extraction app, but are not currently exploited in a robust way.

### A. High-value unexplored or underused tables

- `Activities`
- `AutoprogrammedButtons`
- `ControllerRoomList`
- `DriverDataReference`
- `DriverScripts`
- `Events`
- `GraphProperties`
- `LicenseKeys`
- `MacroBacklight`
- `MacroBeep`
- `MacroButtonHold`
- `MacroComment`
- `MacroDelay`
- `MacroDeviceCommand`
- `MacroEventControl`
- `MacroEventTest`
- `MacroFindRemote`
- `MacroFlag`
- `MacroFunctionCall`
- `MacroLedControl`
- `MacroOSDCommand`
- `MacroPageLink`
- `MacroPopup`
- `MacroPowerSense`
- `MacroRedirect`
- `MacroRelay`
- `MacroRepeat`
- `MacroRoomOff`
- `MacroSelectRoom`
- `MacroSelectSource`
- `MacroShowMenu`
- `MacroTimeRange`
- `MacroVariableTest`
- `PageLinks`
- `RTiQAction`
- `RTiQConfig`
- `RTiQMonitoredDevices`
- `SharedLayers`
- `SourceMapping`
- `VariableRedirect`

These likely contain meaningful relationship or behavior data but are not yet converted into a stable extraction contract here.

### B. High-value unexplored or underused views

- `AllButtons`
- `AllButtonsWithTextTags`
- `AllListItems`
- `AutoprogramInfo`
- `ButtonsAndListItems`
- `ClonePageData`
- `DevicesView`
- `LayerButtons`
- `MacroPageLinkView`
- `MacroRedirectView`
- `MacroRoomView`
- `MacroStepsView`
- `PageLinkView`
- `PagesView`
- `RoomMacrosWithRedirect`
- `RoomVariablesWithRedirect`
- `VariableRedirectView`
- `VariableRoomView`

These may provide faster or cleaner extraction paths than raw table joins, but the current code mostly avoids relying on them.

### C. Empty-or-conditional schema paths

Some schema objects may be empty in one project and populated in another. They should not be dismissed as irrelevant only because a sample file leaves them empty.

Examples already called out in docs:

- `NetworkConfig`
- `NetworkDefaults`
- `RS232Data`
- `RS232DataStrings`
- `IrData`
- `IrFunction`
- `Sounds`
- `WlanConfig`
- `WlanConfigDefaults`

Interpretation:

- these are known paths
- they are not proven universally useful yet
- they may become critical in a different `.apex` corpus

Correction from current direct inspection:

- `Events` is populated in both current working samples and should not be treated as an example of an empty path in this corpus.

## Naming and Relationship Rules Codex Must Preserve

These are the most important exact naming and relationship rules for future extraction work.

### A. Identity keys

- `DeviceId` is not the same thing as `RTIAddress`.
- `RTIAddress` is the device-scoped address used by pages, ports, source labels, and other address-bound structures.
- `DriverDeviceId` is not the same thing as `DeviceId`.
- `PageId` is not the same thing as `PageOrder`.
- `PageNameId` is a lookup key, not the page index.

### B. Stable high-value joins

- controller page context: `RTIDeviceData.RTIAddress -> RTIDevicePageData.RTIAddress`
- controller room scope (primary path): `effective RTI address -> ControllerRoomList.RTIAddress -> Rooms.RoomId`
- page name: `RTIDevicePageData.PageNameId -> PageNames.PageNameId`
- source device on page: `RTIDevicePageData.SourceDeviceId -> Devices.DeviceId`
- room from source device: `Devices.RoomId -> Rooms.RoomId`
- driver instance: `DriverConfig.DriverDeviceId -> DriverData.DriverDeviceId`
- driver device: `DriverData.DeviceId -> Devices.DeviceId`
- SYSVARREF registry: `SystemVariableIds.SysVarRef`
- driver variable names: `DriverData.SystemVariables` XML

### C. Important extraction conventions

- Normalize SYSVARREF keys with `SYSVARREF:` prefix when storing lookup keys.
- Prefer `DisplayName`, but fall back to `Name` when display name is blank.
- When joins fail, preserve blanks or null-like states explicitly.
- Do not invent names for unmapped pages, variables, sources, or macro entities.
- For controller-scoped room lists, use the effective RTI address:
  - if `RTIDeviceData.CloneRTIAddress > 0`, use `CloneRTIAddress`
  - otherwise use `RTIAddress`
- Do not treat `CloneRTIAddress = -1` as a valid inherited address.

## Second Pass: Macros, Buttons, and UI Structure

This section narrows the scope to UI composition and action wiring only.

All findings below use the same classification model:

- `confirmed extractable now`
- `partially supported / incomplete`
- `known schema paths that exist but are not fully explored`

### Confirmed Extractable Now

#### A. Button instance geometry and raw visual properties

Status: `confirmed extractable now`

`RTIDeviceButtonData` is a rich button-instance table, not just a button ID list.

Confirmed extractable fields include:

- identity:
  - `ButtonId`
  - `SharedLayerId`
  - `ButtonOrder`
  - `ButtonTagId`
- text:
  - `Text`
- positioning:
  - `ButtonTop`
  - `ButtonLeft`
  - `ButtonHeight`
  - `ButtonWidth`
  - alternate geometry fields (`ButtonTopAlt`, `ButtonLeftAlt`, `ButtonHeightAlt`, `ButtonWidthAlt`)
- styling/state:
  - `FrameNumber`
  - `ButtonStyle`
  - color fields
  - font/alignment fields
- command payload storage:
  - `Command` (BLOB)
  - `TWParams` (BLOB)

Practical implication:

- a new app can reconstruct a button layout grid and preserve raw visual/button metadata without decoding command blobs yet.

#### B. Page-to-layer-to-button traversal

Status: `confirmed extractable now`

The relationship chain is explicit and populated:

- `RTIDevicePageData.PageId`
- `Layers.PageId`
- `Layers.SharedLayerId`
- `RTIDeviceButtonData.SharedLayerId`

This means a page's button set can be reconstructed by joining:

- page
- layer
- shared layer
- button rows

Current repository evidence:

- `ProjectDataExtractor` already uses this path in a reduced form
- `AllButtons` and `LayerButtons` views encode the same chain more directly

#### C. Shared layer metadata

Status: `confirmed extractable now`

`SharedLayers` provides reusable UI-layer metadata.

Confirmed extractable fields:

- `SharedLayerId`
- `Name`
- `ProductId`
- portrait and landscape dimensions
- `IsKeypadLayer`
- `IsShared`

Observed in current sample:

- `SharedLayers` is populated
- some rows are explicitly marked shared
- some rows are explicitly marked keypad layers

Practical implication:

- the UI can be modeled as reusable layer templates, not just flattened per-page controls.

#### D. Layer-level visibility and viewport structure

Status: `confirmed extractable now`

`Layers` provides more than page grouping.

Confirmed extractable fields:

- `LayerId`
- `PageId`
- `SourceId`
- `SharedLayerId`
- `LayerOrder`
- `IsVisible`
- `VisibilityVariable`
- `IsLocked`
- `ViewPortButtonId`
- `RoomId`

Observed in current sample:

- many layers have non-empty `VisibilityVariable`
- many layers use `ViewPortButtonId`

Practical implication:

- dynamic layer visibility is explicitly modeled
- viewport-driven nested UI composition exists and is not hypothetical

#### E. Button tag naming

Status: `confirmed extractable now`

`ButtonTagNames` is a direct tag-name registry.

Confirmed extractable fields:

- `ButtonTagId`
- `ButtonTagName`

This is the primary stable path for human-readable tag names when a button has a non-negative tag ID.

#### F. Button text-tag indirection

Status: `confirmed extractable now`

`ButtonTextTags` is a second explicit button-label path.

Confirmed extractable fields:

- `ButtonTextTagId`
- `ButtonId`
- `ButtonTagId`

Confirmed meaning from docs and view definitions:

- a button can acquire text through `ButtonTextTags` even when the displayed text is not stored directly as `RTIDeviceButtonData.Text`

Practical implication:

- there are at least two parallel label mechanisms:
  - direct literal text
  - tag-based text indirection

#### G. Denormalized button views already encode useful UI relationships

Status: `confirmed extractable now`

The sample `.apex` contains populated views that already flatten button/UI relationships:

- `LayerButtons`
- `AllButtons`
- `AllButtonsWithTextTags`
- `ButtonsAndListItems`

These are not theoretical. They are populated in the sample corpus and carry relationship logic.

What they confirm:

- button rows can be lifted into page context
- button tag names can be prejoined
- source context can be carried with buttons
- redirect context can be carried with buttons
- list items are treated as button-like UI entities in some views

#### H. `LayerButtons` exposes action-oriented button metadata

Status: `confirmed extractable now`

The `LayerButtons` view is especially important because it already joins raw button rows to action relationships.

Confirmed exposed columns include:

- all `RTIDeviceButtonData` fields
- `DeviceMacroId`
- `OutputType`
- `GlobalMacroId`
- `GlobalMacroRouting`
- `GlobalMacroExpanderId`
- `LinkType`
- `PageLinkId`
- `LinkPageId`
- `DeviceVariableId`
- `GlobalVariableId`
- `LayerId`
- `SourceId`
- `VisibilityVariable`
- `RoomId`
- `ButtonTagName`
- `DeviceId`

Observed in current sample:

- many rows have `GlobalMacroId`
- hundreds have `PageLinkId` and `LinkPageId`

Practical implication:

- the DB already contains a prejoined button-to-action graph
- a new app can likely use `LayerButtons` as the fastest path for UI/action discovery

#### I. Page link extraction

Status: `confirmed extractable now`

`PageLinks` and `PageLinkView` provide explicit page-navigation mappings.

Confirmed extractable fields:

- `PageLinkId`
- `DeviceId`
- `ButtonTagId`
- `LinkType`
- `PageId`

`PageLinkView` adds:

- `PageName`
- `PageGroupName`

Practical implication:

- page navigation is not only implicit in button command blobs
- part of it is explicitly modeled through tag-linked page-link tables

#### J. Page views with display-ready page metadata

Status: `confirmed extractable now`

`PagesView` is a populated denormalized page view.

Confirmed additions beyond `RTIDevicePageData`:

- default background fields from `RTIDevicePageDefaults`
- resolved `PageName`
- `RoomId` from the source device

Practical implication:

- page rendering metadata can be extracted from the view without reproducing all joins by hand

#### K. Macro identity and step sequencing

Status: `confirmed extractable now`

The core macro structure is explicit and populated.

`Macros` confirms:

- `MacroId`
- `SystemMacroId`
- `RoomId`
- `DeviceId`
- `ButtonTagId`
- `OutputType`

`MacroSteps` confirms:

- `MacroStepId`
- `MacroId`
- `StepIndex`
- `Type`
- `Level`
- `InElseSection`

Practical implication:

- macro sequencing is formally represented
- branches/conditional structure are at least partially represented through `Level` and `InElseSection`

#### L. Macro action detail is already flattened in `MacroStepsView`

Status: `confirmed extractable now`

`MacroStepsView` is a major evidence source because it joins `MacroSteps` to many specialized action tables.

Confirmed exposed action families include fields from:

- comments
- delays
- device commands
- IR data and IR function metadata
- RS-232 strings and serial settings
- flags
- button hold conditions
- page-link actions
- repeat actions
- power-sense actions
- beep actions
- relay actions
- function-call / macro-call actions
- time ranges
- event control
- event tests
- find-remote
- variable tests
- LED control
- backlight control
- room selection
- source selection
- room off
- OSD commands
- popup actions

Practical implication:

- the schema already supports a typed macro action model
- a future parser can classify steps by `Type` and then read the populated column family for that step

### Partially Supported / Incomplete

#### A. Final button label resolution rules

Status: `partially supported / incomplete`

The schema proves multiple label channels, but current evidence supports preserving multiple parallel label fields rather than collapsing them into one universal final string too early.

Known channels:

- direct button literal text in `RTIDeviceButtonData.Text`
- tag name via `ButtonTagNames`
- text-tag indirection via `ButtonTextTags`
- denormalized tag text through `AllButtonsWithTextTags`

Best current extraction model:

1. Always preserve `RTIDeviceButtonData.Text` when non-empty as the literal text payload.
2. Always preserve `ButtonTagId` as the stable identity hook.
3. If `ButtonTagId >= 0`, preserve `ButtonTagNames.ButtonTagName` as the tag-backed semantic name.
4. If `ButtonTextTags` rows exist for the same `ButtonId`, preserve them as a separate text-tag set and treat direct `Text` as potentially tokenized/template content rather than assuming it is the final rendered label.
5. Do not automatically discard direct `Text` just because a tag name exists; the current samples contain many buttons where both are populated.
6. Do not automatically treat `ButtonTagName` as the rendered label; in current samples it is a reliable semantic identifier, but not yet proven to override literal text in every UI style.

Evidence from the current sample:

- all buttons with `ButtonTagId >= 0` resolve through `ButtonTagNames` in both current samples
- many buttons with `ButtonTagId >= 0` also have non-empty direct `Text`
- some buttons with `ButtonTagId < 0` also have `ButtonTextTags`, proving that direct text can be a tag-template string rather than final literal text
- `AllButtonsWithTextTags` is a union-expansion view, not a single canonical label field

Not yet proven:

- the exact final precedence rule across all button styles, text-tag cases, and list items

#### B. Button action classification

Status: `partially supported / incomplete`

`LayerButtons` shows that buttons may connect to:

- device macros
- global macros
- page links
- variables

Not yet generalized:

- a single stable classification rule for "this button does X"
- how to rank competing action signals if multiple are populated
- whether raw `Command` blobs contain actions not represented by the joined views

#### C. Macro naming

Status: `partially supported / incomplete`

The macro graph is rich, but a canonical human-readable macro name is still not proven.

Current best-known candidates:

- `Macros.ButtonTagId -> ButtonTagNames.ButtonTagName`
- action semantics inferred from the first or dominant step in `MacroStepsView`

Neither is yet proven to be a universal macro name.

#### D. Macro step type decoding

Status: `partially supported / incomplete`

`MacroSteps.Type` is clearly meaningful and heavily used. Direct schema inspection now allows a stronger type map because the subtype tables can be validated by joining each `Macro*` table to `MacroSteps` on `MacroStepId`.

What is known:

- step types are enumerable and frequent
- `MacroStepsView` exposes different column families depending on the step subtype
- direct subtype-table joins are stronger evidence than nullable `MacroStepsView` columns by themselves

Stronger current type map from direct subtype-table joins plus representative `MacroStepsView` rows:

- `Type 1` -> device command
  Evidence:
  - `MacroDeviceCommand.MacroStepId -> MacroSteps.MacroStepId`
  - `DeviceId` and `Function` are populated in `MacroStepsView`
  - important caveat: `MacroDeviceCommand` also contains extra rows with `MacroStepId NULL`, so raw table row count is not a macro-step count by itself
- `Type 3` -> delay
  Evidence:
  - `MacroDelay.MacroStepId -> MacroSteps.MacroStepId`
  - `Delay` is populated
- `Type 8` -> macro page-link navigation step
  Evidence:
  - `MacroPageLink.MacroStepId -> MacroSteps.MacroStepId`
  - `TargetPageId`, `TargetPageIndex`, and `TargetPageNameId` are populated through `MacroPageLinkView`
- `Type 9` -> repeat action
  Evidence:
  - `MacroRepeat.MacroStepId -> MacroSteps.MacroStepId`
- `Type 10` -> power-sense action
  Evidence:
  - `MacroPowerSense.MacroStepId -> MacroSteps.MacroStepId`
- `Type 13` -> relay action
  Evidence:
  - `MacroRelay.MacroStepId -> MacroSteps.MacroStepId`
  - `RelayPort` and `RelayCommand` are populated
- `Type 14` -> macro call / function call
  Evidence:
  - `MacroFunctionCall.MacroStepId -> MacroSteps.MacroStepId`
  - `CommandMacroId` is populated
- `Type 15` -> flag action
  Evidence:
  - `MacroFlag.MacroStepId -> MacroSteps.MacroStepId`
  - `FlagIndex` and `FlagType` are populated
- `Type 16` -> flag-related action
  Evidence:
  - `MacroFlag.MacroStepId -> MacroSteps.MacroStepId`
  - `FlagIndex` is populated, but `FlagType` is not consistently populated
- `Type 17` -> comment
  Evidence:
  - `MacroComment.MacroStepId -> MacroSteps.MacroStepId`
  - `CommentText` is populated
- `Type 20` -> event-control action
  Evidence:
  - `MacroEventControl.MacroStepId -> MacroSteps.MacroStepId`
- `Type 22` -> variable test
  Evidence:
  - `MacroVariableTest.MacroStepId -> MacroSteps.MacroStepId`
  - `VariableDeviceId` and `Variable` are populated
- `Type 24` -> select room
  Evidence:
  - `MacroSelectRoom.MacroStepId -> MacroSteps.MacroStepId`
  - `SelectRoomId` is populated
- `Type 26` -> select source
  Evidence:
  - `MacroSelectSource.MacroStepId -> MacroSteps.MacroStepId`
  - `SelectSourceId` and `SelectSourceRoomId` are populated
- `Type 27` -> room off
  Evidence:
  - `MacroRoomOff.MacroStepId -> MacroSteps.MacroStepId`
  - `RoomOffId` is populated
- `Type 29` -> show-menu action
  Evidence:
  - `MacroShowMenu.MacroStepId -> MacroSteps.MacroStepId`
  - `MenuType` is populated in `MacroStepsView`
  - current sample rows align with button tags such as `System: Show Menu`, `System: Show Power Options`, and `System: Show Room List`

Types observed but not decoded in the current sample:

- `Type 7`
- `Type 28`

Additional evidence for unresolved types:

- `Type 7`
  - appears in both current samples
  - has no matching row in any populated `Macro*` subtype table
  - exposes no populated subtype-specific fields in `MacroStepsView`
  - currently remains unproven; it behaves like a zero-payload control step or built-in action marker, but that semantic label is not yet schema-proven
- `Type 28`
  - appears once in both current samples
  - has no matching row in any populated `Macro*` subtype table
  - exposes no populated subtype-specific fields in `MacroStepsView`
  - in both current samples it is the only step in a global macro whose `Macros.ButtonTagId -> ButtonTagNames.ButtonTagName` resolves to `System: Source Return`
  - this is strong evidence that `Type 28` is a built-in source-return style action, but the exact schema-level action name is still unproven

What is not yet proven:

- a complete mapping such as `Type N -> semantic step class`
- whether the inferred type meanings above are stable across all `.apex` versions and project types

#### E. Page-link semantics

Status: `partially supported / incomplete`

`PageLinks.LinkType` is clearly meaningful.

What is proven:

- it exists
- it is used in `PageLinkView`
- buttons can bind to page links by tag and device
- `LayerButtons.PageLinkId` is the strongest explicit button-to-page-link bridge
- `MacroSteps.Type = 8` plus `MacroPageLinkView` is the strongest macro-driven navigation path
- `MacroPageLinkView` is intentionally multi-target and uses `GROUP_CONCAT`, so one macro step can expand to many target pages
- `MacroPageLinkView` explicitly unions `RTIDevicePageData` and `ClonePageData`, which means clone-derived page targets are part of the intended navigation model

What is not proven:

- the complete semantic meaning of each `LinkType` value
- whether `PageLinks.PageId` always means target page versus group/device semantics

Best current navigation interpretation:

- rows where `LayerButtons.PageLinkId` is populated represent explicit tag-based page navigation wiring
- rows where `MacroStepsView.Type = 8` represent macro-driven navigation wiring
- `PageLinkView` is the easiest direct source for button-tag-to-page targets
- `MacroPageLinkView` is the easiest direct source for macro-step-to-page targets
- explicit page-link targets and macro-driven page targets should be stored as separate edge types, not merged into one ambiguous navigation field

Observed constraints:

- `LinkType 0` commonly resolves to `RTIDevicePageData.PageId` and usually returns `PageName`
- `LinkType 1` can resolve `Devices.Name` as `PageGroupName` without resolving `PageName`, which is strong evidence that some links target a device/group context instead of a single page row
- `LinkType 2`, `LinkType 3`, and `LinkType 254` are present in both current samples and commonly use `PageId = -1`, so they remain explicit-but-ambiguous navigation/control cases
- many `MacroPageLinkView` rows contain comma-separated target lists, so multi-target navigation is confirmed rather than hypothetical

#### F. Redirect-aware UI resolution

Status: `partially supported / incomplete`

The denormalized views prove redirect concepts exist:

- `ButtonsAndListItems` carries `MacroRedirect.SourceId` as `RedirectDeviceId`
- `AllButtonsWithTextTags` carries `VariableRedirect.SourceId` as `RedirectDeviceId`

Not yet generalized:

- when redirect context should override base `SourceDeviceId`
- whether redirect semantics should be modeled as source remapping, UI scoping, or variable scoping

#### G. View-first versus raw-table-first extraction strategy

Status: `partially supported / incomplete`

There are two viable approaches:

- build from raw tables (`RTIDeviceButtonData`, `Layers`, `PageLinks`, `Macros`, etc.)
- consume denormalized views (`LayerButtons`, `AllButtons`, `MacroStepsView`, `PagesView`, etc.)

The repository currently mixes both ideas but does not define when each is safer.

This matters because:

- views are richer and faster for discovery
- raw tables may be safer if view logic differs across `.apex` versions

#### H. Page navigation tree construction

Status: `partially supported / incomplete`

A practical navigation graph can already be built, but it is not yet fully lossless or fully semantic.

Best current graph model:

1. Node type: page
   Fields:
   - `PageId`
   - `PageName`
   - `RTIAddress`
   - `PageOrder`
2. Edge type: explicit button page link
   Source:
   - `LayerButtons.PageLinkId`
   - `LayerButtons.ButtonId`
   - `LayerButtons.ButtonTagId`
   - `LayerButtons.ButtonTagName`
   - `LayerButtons.LinkPageId`
   - `PageLinkView`
3. Edge type: macro-driven page link
   Source:
   - button -> `DeviceMacroId` or `GlobalMacroId` from `LayerButtons`
   - macro step -> `MacroStepsView` rows where `Type = 8`
   - target pages -> `TargetPageId`, `TargetPageIndex`, `TargetPageNameId`

What this supports now:

- page-to-page navigation edges from explicit page links
- button-to-page navigation edges
- button-to-macro-to-page navigation edges

What still blocks a complete final tree:

- unresolved `LinkType` semantics
- unresolved global versus device macro precedence
- multi-target macro page steps, where one macro step expands to many target pages

### Known Schema Paths That Exist But Are Not Fully Explored

#### A. Macro subtype tables

Status: `known schema paths that exist but are not fully explored`

The schema has many specialized macro tables that likely map to distinct step types:

- `MacroBacklight`
- `MacroBeep`
- `MacroButtonHold`
- `MacroComment`
- `MacroDelay`
- `MacroDeviceCommand`
- `MacroEventControl`
- `MacroEventTest`
- `MacroFindRemote`
- `MacroFlag`
- `MacroFunctionCall`
- `MacroLedControl`
- `MacroOSDCommand`
- `MacroPageLink`
- `MacroPopup`
- `MacroPowerSense`
- `MacroRedirect`
- `MacroRelay`
- `MacroRepeat`
- `MacroRoomOff`
- `MacroSelectRoom`
- `MacroSelectSource`
- `MacroShowMenu`
- `MacroTimeRange`
- `MacroVariableTest`

These are the highest-value path for turning macros into a typed action language.

#### B. UI/list and button aggregation views

Status: `known schema paths that exist but are not fully explored`

These populated views deserve dedicated analysis:

- `AllButtons`
- `AllButtonsWithTextTags`
- `AllListItems`
- `ButtonsAndListItems`
- `LayerButtons`

They likely encode the intended RTI-side interpretation of:

- button scope
- list-item scope
- text-tag expansion
- source redirects
- macro redirects

#### C. Page and navigation structure views

Status: `known schema paths that exist but are not fully explored`

Relevant paths:

- `PagesView`
- `PageLinks`
- `PageLinkView`
- `ClonePageData`
- `SharedLayers`

These allow a stronger UI navigation model than the current code uses.

Current direct evidence adds:

- `ClonePageData` is not just a passive helper view; it is explicitly consumed by `MacroPageLinkView` to expand clone-aware page targets
- `SharedLayers` is the key path for identifying keypad-style `Hard Keys` layers through `IsKeypadLayer = 1`

## Third Pass: Conceptual Hierarchy Translation

This section treats the user-supplied hierarchy as a conceptual lens, not a literal schema.

The goal here is to restate each concept using the strongest exact schema-backed equivalent currently supported by direct inspection of the two working sample `.apex` files.

### Conceptual-to-schema translation

| User conceptual wording | Strongest schema-backed term(s) now | Relationship status | Evidence |
| --- | --- | --- | --- |
| `Project` | the `.apex` SQLite file as the root container; optionally `JobInfo` for project metadata | `partially supported / incomplete` | there is no `Project` table; the database file itself is the true container |
| `Events` | `Events` | `confirmed extractable now` | both current samples have populated `Events` tables |
| `Global Events` | `Events` joined to `Macros` where the linked macro is global-scope (`Macros.DeviceId = -1`); room scope still depends on `Macros.RoomId` | `partially supported / incomplete` | event rows do not carry a dedicated global-event type column; scope is inferred from the linked macro |
| `Driver Events` | `Events` rows where `Events.DriverId` is populated (current samples: `EventType = 5`); macro linkage is driver-scoped in practice through `Events.MacroId -> Macros.SystemMacroId` with `Macros.DeviceId = Events.DriverId` | `partially supported / incomplete` | this pass treats `Driver Events` as the primary source/device event class for event testing output; `SourceEvents` is tracked separately as source power on/off hooks |
| `Devices` | `Devices`; plus `RTIDeviceData` when RTI-addressed controller/page context is needed | `confirmed extractable now` | `Devices` and `RTIDeviceData` are both populated and are used in page, button, and navigation joins |
| `Rooms` | `Rooms` | `confirmed extractable now` | `Devices.RoomId` and other room-aware tables join back to `Rooms` |
| `Activities` | `Activities` | `confirmed extractable now` | `Activities` is populated in both samples |
| `Pages` under `Activities` | `Activities.PagelinkMacroId -> Macros -> MacroSteps(Type 8) -> MacroPageLinkView` | `partially supported / incomplete` | activities do not point directly to pages; page targets are reached through a page-link macro chain |
| `Pages` | `RTIDevicePageData` plus `PageNames`; `PagesView` is the strongest denormalized page view | `confirmed extractable now` | explicit page rows, page order, names, and page views are all populated |
| `Layers` | `Layers` plus `SharedLayers` | `confirmed extractable now` | page-to-layer and shared-layer joins are explicit and populated |
| `Screen Titles` | page-title text is most strongly represented by `RTIDevicePageData.PageNameId -> PageNames.PageName`; title styling lives in `RTIDevicePageData.TitleFont` and `TitleHorzAlign` | `partially supported / incomplete` | there is no dedicated `ScreenTitles` table; current evidence supports page-title metadata, not a fully separate title entity |
| `Screen Text Variables` | composite of `Variables` (`ButtonText`, `ObjectData`, `ReversedData`, `InactiveData`, `VisibleData`), `ButtonTextTags`, and literal text tokens embedded in `RTIDeviceButtonData.Text` | `partially supported / incomplete` | variable-driven text exists, but there is no single canonical screen-text-variable table |
| `Screen Buttons` | `RTIDeviceButtonData`; `LayerButtons` is the strongest action-aware button view | `confirmed extractable now` | raw button rows and denormalized button/action rows are both populated |
| `Macros` under `Screen Buttons` | `LayerButtons.DeviceMacroId` and `LayerButtons.GlobalMacroId` -> `Macros` -> `MacroSteps` / `MacroStepsView` | `confirmed extractable now` | button-to-macro bindings are explicitly exposed in `LayerButtons` |
| `Variables` under `Screen Buttons` | `LayerButtons.DeviceVariableId` and `LayerButtons.GlobalVariableId` -> `Variables` / `RoomVariablesWithRedirect` | `confirmed extractable now` | button-to-variable bindings are explicitly exposed in `LayerButtons` |
| `Status` under `Variables` | likely a composite of `Variables.ObjectData`, `Variables.ReversedData`, and `Variables.InactiveData` | `partially supported / incomplete` | state payload fields exist, but a single exact `Status` semantic has not been proven |
| `Visibility` under `Variables` | `Variables.VisibleData` for button/object visibility payloads; `Layers.VisibilityVariable` for layer-level visibility conditions | `partially supported / incomplete` | visibility is clearly variable-aware, but it spans at least two schema paths |
| `Page Links` under `Screen Buttons` | explicit links: `LayerButtons.PageLinkId` -> `PageLinks` / `PageLinkView`; macro links: `Macros` -> `MacroSteps(Type 8)` -> `MacroPageLinkView` | `confirmed extractable now` | both explicit and macro-driven navigation paths are populated |
| `Hard Buttons` | no dedicated `HardButtons` table; strongest current equivalent is `RTIDeviceButtonData` rows on `SharedLayers.IsKeypadLayer = 1` (often named `Hard Keys`) | `partially supported / incomplete` | keypad layers are explicit, but `hard button` is a UI/hardware concept assembled from layer metadata rather than a first-class table |
| `Macros` under `Hard Buttons` | same macro path as screen buttons, but filtered to keypad layers via `SharedLayers.IsKeypadLayer = 1` | `confirmed extractable now` | current samples contain keypad-layer buttons with populated `GlobalMacroId` or `PageLinkId` |
| `Page Links` under `Hard Buttons` | same explicit page-link path as screen buttons, but filtered to keypad layers via `SharedLayers.IsKeypadLayer = 1` | `confirmed extractable now` | current samples contain keypad-layer buttons with populated `PageLinkId` |

### Relationship corrections to the user hierarchy

Status: `partially supported / incomplete`

The user hierarchy is directionally useful, but direct schema inspection supports these corrections:

- `Rooms` is not a child of `Devices`; `Devices` usually points to `Rooms` through `Devices.RoomId`, so this is a many-devices-to-one-room relationship instead of a containment tree.
- `Activities` is not a direct parent of page rows; activities primarily carry macro pointers (`SelectedMacroId`, `DeselectedMacroId`, `PagelinkMacroId`), and page targets are reached through `PagelinkMacroId`.
- `Layers` is not only a page child; `Layers` references `SharedLayerId`, so the effective UI model is page instance layer -> shared layer template -> button instances.
- `Screen Titles`, `Screen Text Variables`, and `Hard Buttons` are not first-class tables in the current schema; each is a composite concept that must be assembled from multiple objects.

### Corrected schema-backed hierarchy

Status: `partially supported / incomplete`

This is the strongest current restatement that preserves the user intent while using exact schema-backed terms:

- project container:
  - `.apex` SQLite file
  - optional project metadata in `JobInfo`
- project-level relationship groups:
  - `Rooms`
  - `Devices`
  - `Events`
  - `Activities`
- controller UI pages:
  - `RTIDevicePageData`
  - `PageNames`
  - `PagesView`
- page composition:
  - `Layers`
  - `SharedLayers`
  - `RTIDeviceButtonData`
  - `LayerButtons`
- button action wiring:
  - explicit page links: `PageLinks` / `PageLinkView`
  - macro bindings: `Macros` / `MacroSteps` / `MacroStepsView`
  - variable bindings: `Variables` / redirect-aware variable views
- hard-key subset:
  - same button/action wiring, filtered to `SharedLayers.IsKeypadLayer = 1`
- activity-driven navigation:
  - `Activities.PagelinkMacroId`
  - `MacroSteps.Type = 8`
  - `MacroPageLinkView`

### Adjacent schema paths required to explain the hierarchy

Status: `known schema paths that exist but are not fully explored`

These paths sit slightly outside the user wording but are required to explain the real relationship model:

- `ClonePageData`
  - required for clone-aware macro page targets because `MacroPageLinkView` unions it directly
- `AllListItems`
  - present as a view but empty in both current samples, so list-item behavior remains unproven in this corpus
- `ButtonsAndListItems`
  - proves that list items and buttons are intended to be normalized into one UI-action stream when data exists
- `MacroRedirect` and `VariableRedirect`
  - not just metadata; they actively multiply rows in `ButtonsAndListItems` and `AllButtonsWithTextTags` by redirect target source
- `RoomMacrosWithRedirect` and `RoomVariablesWithRedirect`
  - these are the exact view paths used by `LayerButtons` to expose redirect-aware global macros and global variables

## Fourth Pass: Device Room Control Scope

This section answers a narrower question: how to determine which rooms a controller device can control, especially for global/mobile clients such as RTI panels on iPhone or iPad.

### Confirmed extractable now

#### A. Primary room-scope path for a controller device

Status: `confirmed extractable now`

The strongest schema-backed room control scope path is:

- start from `RTIDeviceData`
- compute the controller's effective address:
  - if `RTIDeviceData.CloneRTIAddress > 0`, use `CloneRTIAddress`
  - otherwise use `RTIAddress`
- join effective address to `ControllerRoomList.RTIAddress`
- join `ControllerRoomList.RoomId -> Rooms.RoomId`
- preserve `ControllerRoomOrder` as the UI ordering field

Practical meaning:

- `ControllerRoomList` is the best current source for the selectable room set exposed by a controller
- this is the closest schema-backed equivalent to "which rooms can this device control?"

Observed evidence from current samples:

- non-clone global/mobile controllers have populated `ControllerRoomList` rows directly on their own `RTIAddress`
- clone controllers often have no `ControllerRoomList` rows on their own address but do inherit a populated room list from `CloneRTIAddress`
- room-scoped handheld controllers can also have a limited `ControllerRoomList` (for example, 1 room or a small subset) when configured that way

#### B. Clone-aware room-scope inheritance

Status: `confirmed extractable now`

`CloneRTIAddress` is not only a page lookup concern. It also matters for room scope.

Current direct evidence:

- in both current sample files, several mobile clients have `CloneRTIAddress > 0`
- those clone devices have no direct `ControllerRoomList` rows on their own address
- the inherited address has the populated `ControllerRoomList` that matches the clone device's usable room-selection UI

Extraction rule:

- the same effective-address rule used for clone-aware pages should be applied before reading `ControllerRoomList`

#### C. `ControllerRoomList` is a selectable control-scope list, not a generic page-room list

Status: `confirmed extractable now`

`ControllerRoomList` and page-derived room references are related but not interchangeable.

Important distinction:

- `ControllerRoomList` is the best current source for the selectable room scope
- page-derived room context comes from `RTIDevicePageData.SourceDeviceId -> Devices.RoomId`
- page-derived room context can include utility/global pages and extra contextual pages that do not imply a selectable room in the room-picker UI

Observed evidence from current samples:

- `ControllerRoomList` commonly excludes room `0` (`Global`)
- the same controller's page set often includes pages whose source device is in room `0`
- some controllers have page source rows that reference rooms outside their `ControllerRoomList` subset because shared utility pages are present

Practical implication:

- when `ControllerRoomList` exists, do not derive room control scope from page source rooms instead
- page source rooms are useful as supporting context, but not as the authoritative room-selection scope

### Partially supported / incomplete

#### A. Fallback when `ControllerRoomList` is empty

Status: `partially supported / incomplete`

Some controller devices have no `ControllerRoomList` rows.

Current best fallback model:

1. If `ControllerRoomList` is empty after clone-aware effective-address resolution, inspect `Devices.RoomId`.
2. If `Devices.RoomId > 0`, treat that device as likely single-room scoped.
3. Use page-derived room context (`RTIDevicePageData.SourceDeviceId -> Devices.RoomId`) only as a consistency check, not the primary source.

Current evidence:

- in the current samples, room-local controllers such as room-bound touch panels can have no `ControllerRoomList` rows while all of their direct pages point to one non-global room

What is not yet proven:

- that every controller with an empty `ControllerRoomList` should always be interpreted as single-room scoped
- whether some projects omit `ControllerRoomList` even for multi-room controllers

#### B. First-page room-selection detection

Status: `partially supported / incomplete`

The user-facing room-selection experience is visible in current samples, but it should be treated as supporting evidence, not the primary scope definition.

What is observed:

- global/mobile clients often begin with page names such as `Room Select`, `Feeny Room Select`, or `Room Menu - List`
- these first pages are usually sourced from a global device (`Devices.RoomId = 0`)

What is safer:

- use `ControllerRoomList` to determine room scope
- use first-page identity only to label or explain the UI flow

Reason:

- first pages describe UI entry behavior
- `ControllerRoomList` describes the actual configured room-selection set

### Known schema paths that exist but are not fully explored

#### A. Related paths that may refine room-scope semantics

Status: `known schema paths that exist but are not fully explored`

Relevant supporting paths:

- `ControllerRoomList`
  - currently the strongest scope list and ordering source
- `RTIDevicePageData`
  - useful for detecting room-selection entry pages and page-derived room context
- `PageLinks` / `PageLinkView`
  - may help explain how room-selection pages transition into room-specific pages
- `Activities`
  - may help explain room-driven source/page navigation after a room has been selected
- `SourceLabels`
  - may help explain room-specific labels shown after selection, but not the scope list itself

#### D. Variable-aware UI state paths

Status: `known schema paths that exist but are not fully explored`

Relevant paths:

- `Variables`
- `VariableRedirect`
- `VariableRedirectView`
- `RoomVariablesWithRedirect`
- `VariableRoomView`

These likely matter for:

- layer visibility
- dynamic labels
- source redirection
- page state that changes by room/source context

## Fifth Pass: Activity-to-Room Linkage and Selection Flow

This section captures direct findings from `Sung Residence v207.2.apex` for room activities, source scope, enabled state, and selected activity flow.

### Confirmed extractable now

#### A. Activity rows are directly room-bound

Status: `confirmed extractable now`

`Activities` has a direct room foreign key:

- `Activities.RoomId -> Rooms.RoomId`

This is the authoritative room association for an activity row. It is not inferred through pages or macros.

#### B. Activity source scope can be classified from `Activities.DeviceId`

Status: `confirmed extractable now`

Strong schema-backed classification:

- `Activities.DeviceId -> Devices.DeviceId`
- if `Devices.RoomId = 0`, classify source scope as global/shared
- if `Devices.RoomId = Activities.RoomId`, classify source scope as local
- if `Devices.RoomId` is neither `0` nor `Activities.RoomId`, classify as cross-room

Observed evidence in `Sung Residence v207.2.apex`:

- total activity rows: `1749`
- global/shared-source rows: `1675`
- local-source rows: `74`
- cross-room rows: `0`

This is currently the strongest extractable model for local vs global activity source scope.

#### C. Activity enabled state is directly extractable

Status: `confirmed extractable now`

`Activities.Checked` is the activity enabled/disabled field:

- `Checked = 1` -> enabled
- `Checked = 0` -> disabled

Observed evidence in Office (`RoomId = 2`) from the same sample:

- total activities: `71`
- enabled: `32`
- disabled: `39`

#### D. Activity macro pointers are direct and complete

Status: `confirmed extractable now`

`Activities` directly carries:

- `SelectedMacroId`
- `DeselectedMacroId`
- `PagelinkMacroId`

In the current sample, these IDs resolve to real `Macros` rows when populated.

Office example (`ActivitiesId = 93`, `Rogers #1`):

- `SelectedMacroId = 1658`
- `DeselectedMacroId = NULL`
- `PagelinkMacroId = 194`

Both macro IDs resolve, and both are global macro rows with room context:

- `Macros.DeviceId = -1`
- `Macros.RoomId = 2` (Office)
- `Macros.OutputType = 1`

#### E. Room-level selection/deselection event hooks are extractable separately from `Activities`

Status: `confirmed extractable now`

The room-level event scaffold shown in the designer is represented by `RoomEvents` rows, not only by `Activities`.

Strong extractable path:

- `RoomEvents.RoomId -> Rooms.RoomId`
- `RoomEvents.SelectedMacroId -> Macros.MacroId` (when populated)
- `RoomEvents.DeselectedMacroId -> Macros.MacroId` (when populated)

Office (`RoomId = 2`) has one row for each `EventType` `0..6`:

- `EventType 0`: `DeselectedMacroId = 1659`
- `EventType 1`: no macros
- `EventType 2`: `SelectedMacroId = 1656`, `DeselectedMacroId = 1657`
- `EventType 3`: `SelectedMacroId = 5`
- `EventType 4`: `SelectedMacroId = 2938`
- `EventType 5`: no macros
- `EventType 6`: `SelectedMacroId = 6`

Resolved command/page details for those Office room-event macros:

- `MacroId 1656`: `Type 1` command `LG TV -> POWER ON`
- `MacroId 1657`: `Type 1` command `LG TV -> POWER OFF`
- `MacroId 1659`: `Type 1` command `Vaux Lattis Matrix -> SingleSource:ZoneOff`
- `MacroId 5`: `Type 26` select source `Home (DeviceId 6) in Office (RoomId 2)` plus `Type 1` layer-switch commands `setSelLyr:5` and `setSelLyr:6`
- `MacroId 2938`: `Type 8` page-link to `Please Wait` (multi-target by controller address)
- `MacroId 6`: flag-gated flow (`Type 16/17/15`) plus `Type 26` select source `Home (DeviceId 6) in Office (RoomId 2)`

Verrier runtime clarification from direct room-select tracing:

- viewport room-selector buttons do not need to carry page-link steps themselves
- in `Verrier Home FEENY EDIT v49.apex`, iPhone `Room Select` page (`PageId = 513`, `RTIAddress = 3`) uses viewport/list items such as `Room: Master Bedroom`
- those room items resolve to button-tag macros whose only proven step is `Type 24` via `MacroSelectRoom.SelectRoomId`
- the landing-page jump occurs in room-level follow-up macros from `RoomEvents`, not on the room-selector button macro itself
- confirmed `Master Bedroom` chain:
  - viewport item `Room: Master Bedroom`
  - button macro `Type 24` -> `SelectRoomId = 6`
  - room-level `RoomEvents` selected-hook macros for `RoomId = 6` include page-link-bearing macros (`MacroId 5877`, `MacroId 5894`)
  - those room-event macros contain `Type 8` page-link steps targeting iPhone page `PageId = 518` -> `Lights/Home (Master)`
- practical implication:
  - room selection is a two-stage navigation model:
    - stage 1: select room context
    - stage 2: room event applies landing-page navigation and any setup commands

Relationship to `Activities`:

- once already inside a room, activity selection is a separate navigation path from room selection
- `Activities` rows can carry:
  - `SelectedMacroId` for activity-specific follow-up actions
  - `PagelinkMacroId` for activity-specific page navigation
- therefore page navigation in runtime can come from at least two distinct non-button-direct paths:
  - room selection -> `RoomEvents`
  - activity selection -> `Activities.PagelinkMacroId`

#### F. Source-level on/off event hooks are separately extractable

Status: `confirmed extractable now`

Source-level hooks are represented by `SourceEvents`:

- `SourceEvents.SourceId -> Devices.DeviceId`
- `SourceEvents.OnMacroId`
- `SourceEvents.OffMacroId`

For Office `Rogers #1` source (`SourceId = 59`):

- `OnMacroId = 4186`
- `OffMacroId = NULL`

### Partially supported / incomplete

### Partially supported / incomplete

#### A. Runtime execution order between selected/deselected/page-link macros

Status: `partially supported / incomplete`

What is proven:

- activity rows expose three macro pointers (`SelectedMacroId`, `DeselectedMacroId`, `PagelinkMacroId`)
- each pointed macro can be fully inspected through `MacroStepsView`

What is not fully proven from schema alone:

- exact runtime orchestration order across all controller contexts (for example, whether page-link logic always executes after selected macro logic, and under what toggled conditions)

Practical extraction position:

- treat all three macro pointers as configured behavior hooks
- do not hardcode execution ordering unless confirmed by direct runtime evidence

#### B. Example activity deep dive: Office `Rogers #1` (`ActivitiesId = 93`)

Status: `partially supported / incomplete`

Strong extractable configuration:

- activity room: `Office` (`RoomId = 2`)
- source device: `Rogers #1` (`DeviceId = 59`, `Devices.RoomId = 0` -> global/shared source)
- enabled: `Checked = 1`

Selected behavior macro (`MacroId = 1658`) currently resolves to three `Type = 1` device command steps:

- `DeviceId = 35` (`Vaux Lattis Matrix`), `Function = SingleSource:SrcSelect`
- `DeviceId = 64` (`VHDx`), `Function = PortSet`
- `DeviceId = 74` (`LG TV`), `Function = INPUT HDMI 1`

Page-link macro (`MacroId = 194`) includes:

- conditional/comment structure (`Type 17`)
- flag-related steps using `FlagIndex = 179` (`Type 16` and `Type 15`, with `FlagType = 0` on `Type 15`)
- a `Type 8` page-link step (`MacroStepId = 296`) for `Device = 59`, `Page = 0`

The `Type 8` step resolves to multiple target controller/page combinations (not a single page target), including:

- `KA11` (`RTIAddress = 2`) -> `DCT 1 - Room` and `DCT 1 - House`
- multiple iPhone clients (`RTIAddress = 1,7,8,9,11`) -> `DCT 1 - Room` and `DCT 1 - House`
- plus additional panel targets (for example `T2i`, `T4x`) with device-specific page variants

This confirms activity page navigation can be multi-target and controller-specific.

#### C. Room event type labels versus `RoomEvents.EventType` numeric values

Status: `partially supported / incomplete`

What is proven:

- each room has exactly one `RoomEvents` row for each `EventType` value `0..6`
- each row can independently carry `SelectedMacroId` and/or `DeselectedMacroId`

What is not yet proven from schema alone:

- the exact canonical string label for each `EventType` integer (for example the exact mapping to UI labels such as `Activity Start`, `Room ON`, `Video ON`, `Power On Source`, `Activity Selected`, `Activity Ready`, and the deselection labels shown in the designer tree)

Current extraction stance:

- keep `EventType` as explicit numeric identity
- expose linked macro IDs and resolved step payloads directly
- allow label mapping as an inferred/overlay layer until enum names are directly proven

#### D. `SourceEvents.OnMacroId` appears to use mixed macro identifier semantics

Status: `partially supported / incomplete`

Direct evidence from `Sung Residence v207.2.apex`:

- some `SourceEvents.OnMacroId` values resolve as `Macros.MacroId`
- some resolve only as `Macros.SystemMacroId`
- some values match both namespaces

Observed aggregate for non-null `OnMacroId` rows in the sample:

- total rows: `7`
- direct `MacroId` hits: `4`
- `SystemMacroId` hits: `4`

Office `Rogers #1` example:

- `OnMacroId = 4186`
- no direct `Macros.MacroId = 4186`
- one `Macros.SystemMacroId = 4186` row exists (`MacroId = 4558`, `RoomId = 3`)

This indicates `SourceEvents.OnMacroId` cannot yet be treated as strictly `MacroId` or strictly `SystemMacroId` without additional normalization rules.

#### E. Office `Rogers #1` slot-by-slot breakdown for the 6 selection + 6 deselection UI labels

Status: `partially supported / incomplete`

The user-visible tree labels are clear, but schema does not yet provide a proven direct enum-name map from each label to a single `RoomEvents.EventType` integer.

For `Office` / `Rogers #1`, the strongest extractable slot breakdown is:

- Selection `Activity Start`
  - strongest direct activity hook: `Activities.SelectedMacroId = 1658` (not empty)
  - resolved commands: `SingleSource:SrcSelect`, `PortSet`, `INPUT HDMI 1`
- Selection `Room ON`
  - no label-to-`EventType` proof yet
  - candidate room-event selection macros exist and are non-empty (`1656`, `5`, `2938`, `6`)
- Selection `Video ON`
  - no label-to-`EventType` proof yet
  - candidate likely includes `RoomEvents` row with `SelectedMacroId = 1656` (`LG TV -> POWER ON`)
- Selection `Power On Source`
  - `SourceEvents.SourceId=59 -> OnMacroId=4186` (not empty)
  - ID resolution is mixed (`OnMacroId` namespace ambiguity); for this row it resolves via `SystemMacroId` (`MacroId=4558`, room-context differs)
- Selection `Activity Selected`
  - strongest direct activity navigation hook: `Activities.PagelinkMacroId = 194` (not empty)
  - resolves to multi-target page navigation (`DCT #1`, `DCT 1`, `DCT 1 - Room`, `DCT 1 - House`)
- Selection `Activity Ready`
  - no label-to-`EventType` proof yet
  - candidate room-event page-link macro is non-empty (`RoomEvents.SelectedMacroId = 2938` -> `Please Wait` targets)

- Deselection `Room Off Start`
  - no direct label-to-`EventType` proof yet
  - candidate non-empty room-event deselection macro: `RoomEvents.DeselectedMacroId = 1659` (`SingleSource:ZoneOff`)
- Deselection `Activity Deselected`
  - strongest direct activity hook: `Activities.DeselectedMacroId = NULL` (empty)
- Deselection `Power Off Source`
  - `SourceEvents.SourceId=59 -> OffMacroId = NULL` (empty)
- Deselection `Video OFF`
  - no label-to-`EventType` proof yet
  - candidate likely includes `RoomEvents.DeselectedMacroId = 1657` (`LG TV -> POWER OFF`)
- Deselection `Room OFF`
  - no proven direct slot mapping yet
  - no separate activity-level deselection macro beyond `Activities.DeselectedMacroId` (empty)
- Deselection `Room Off Complete`
  - no direct label-to-`EventType` proof yet
  - one `RoomEvents` event slot is fully empty in Office (`EventType=5`, both macro columns null)

Exact `RoomEvents` rows for Office (`RoomId=2`) are:

- `EventType=0`: `SelectedMacroId=NULL`, `DeselectedMacroId=1659`
- `EventType=1`: `SelectedMacroId=NULL`, `DeselectedMacroId=NULL`
- `EventType=2`: `SelectedMacroId=1656`, `DeselectedMacroId=1657`
- `EventType=3`: `SelectedMacroId=5`, `DeselectedMacroId=NULL`
- `EventType=4`: `SelectedMacroId=2938`, `DeselectedMacroId=NULL`
- `EventType=5`: `SelectedMacroId=NULL`, `DeselectedMacroId=NULL`
- `EventType=6`: `SelectedMacroId=6`, `DeselectedMacroId=NULL`

### Known schema paths that exist but are not fully explored

#### A. Additional paths needed to fully normalize activity runtime behavior

Status: `known schema paths that exist but are not fully explored`

High-value paths for next activity pass:

- `MacroSteps` and `MacroStepsView`
  - especially control-flow step families (`Type 16`, `Type 17`) used around page-link steps
- `MacroPageLink` and `MacroPageLinkView`
  - for precise, expanded target list normalization
- `Activities` with `SelectedMacroId`, `DeselectedMacroId`, `PagelinkMacroId`
  - to formalize a deterministic extraction representation of activity behavior hooks
- flag-related paths (`MacroFlag` and variable mappings)
  - to resolve how activity-level conditionals tie to system flag state

#### B. Extra paths required to normalize room/source event layers under activity UX

Status: `known schema paths that exist but are not fully explored`

High-value adjacent paths:

- `RoomEvents`
  - likely the direct backbone of room selection/deselection event slots shown in UI
- `SourceEvents`
  - likely the direct source-level on/off event hooks shown in UI
- `Events`
  - contains separate event automation records (`EventType`, `Enabled`, `MacroId`) and may intersect with room/source event behavior
- `Macros.SystemMacroId`
  - needed to resolve mixed-ID references from `SourceEvents.OnMacroId`

## Sixth Pass: Global Events and Driver Events (Sung Sample)

This section resolves concrete event examples from `Sung Residence v207.2.apex` with focus on:

- event name
- trigger
- macro run
- enabled/disabled

### Confirmed extractable now

#### A. `Events` records are directly extractable with enabled state and linked macro

Status: `confirmed extractable now`

Direct fields:

- `Events.EventId`
- `Events.EventType`
- `Events.Description`
- `Events.Enabled`
- `Events.MacroId`
- trigger payload columns (`Sense*`, `Periodic*`, `Daily*`, `StartupType`, `DriverId`, `DriverExtraString`)

Current sample evidence:

- `Events` row count: `91`
- all rows have `Enabled = 1` in Sung
- `Events.MacroId` resolves to an existing `Macros.MacroId` for most rows (`81/91`)

#### B. `SourceEvents` records are directly extractable with on/off macro references (tracked separately)

Status: `confirmed extractable now`

Direct fields:

- `SourceEvents.SourceEventsId`
- `SourceEvents.SourceId`
- `SourceEvents.OnMacroId`
- `SourceEvents.OffMacroId`

Current sample evidence:

- `SourceEvents` row count: `141`
- `OnMacroId` non-null rows: `7`
- `OffMacroId` non-null rows: `1`
- there is no explicit enabled/disabled column on `SourceEvents`

Scope boundary for this pass:

- `SourceEvents` is treated as source power on/off hook data (`OnMacroId` / `OffMacroId`) and is not part of the initial `System Events` vs `Driver Events` event-testing output tables.

### Partially supported / incomplete

#### A. Trigger label mapping from `Events.EventType` to user-facing names

Status: `partially supported / incomplete`

`EventType` numbers and trigger payload columns are extractable, but exact canonical UI label mapping for every `EventType` is not yet fully proven from schema alone.

Practical extraction rule:

- emit `EventType` integer and trigger payload columns as ground truth
- expose inferred trigger family only when payload columns clearly indicate it (for example sense, driver, daily, startup)

Additional clarification from Sung direct inspection:

- there is no dedicated `DriverEvents` table
- driver-triggered events are represented in `Events`
- strongest current driver-event signature is:
  - `Events.EventType = 5`
  - `Events.DriverId IS NOT NULL`
  - `Events.DriverExtraString` populated with trigger token strings

Observed evidence in Sung:

- `Events` rows with `DriverId` populated: `63`
- all `63` are `EventType = 5`
- all current `Events` rows in Sung are enabled (`Enabled = 1`)

#### A1. Trigger extraction model (`Events`) for Sung

Status: `confirmed extractable now`

For `Sung Residence v207.2.apex`, trigger payload extraction can be done deterministically from `Events.EventType` plus payload columns:

- `EventType = 1` (sense payload)
  - trigger fields: `SensePort`, `SenseAction`, `SenseExpanderId`
- `EventType = 3` (scheduled payload)
  - trigger fields: `DailyAstronomical`, `DailyStartTime`, `DailyDayMask`
  - preserve `DailyStartTime` as raw blob (or hex) unless a project-proven decoder is applied
- `EventType = 4` (startup payload)
  - trigger field: `StartupType`
- `EventType = 5` (driver payload)
  - trigger fields: `DriverId`, `DriverExtraString`

Observed type-to-payload profile in Sung (`Events`):

- `EventType 1`: `2` rows, all with sense payload populated, no driver payload
- `EventType 3`: `25` rows, all with daily payload populated, no driver payload
- `EventType 4`: `1` row, startup payload populated, no driver payload
- `EventType 5`: `63` rows, all with driver payload populated

Recommended extraction output for trigger normalization:

- `EventId`
- `EventType` (numeric identity)
- `TriggerFamily` (project-level label for convenience; for Sung: `Sense`, `Scheduled`, `Startup`, `Driver`)
- `TriggerPayload` (type-specific fields above, preserved exactly)

Sense-trigger port-name resolution for internal controller ports is repeatable and schema-backed:

- join basis:
  - `Events.SensePort` (zero-based port index)
  - `Events.SenseExpanderId`
  - `PortLabels` internal sense label key range `-65024..-65017`
- mapping rule:
  - `port_number = (LabelKey & 65535) - 512 + 1`
  - `sense_port_index = port_number - 1`
  - match `sense_port_index = Events.SensePort` when `SenseExpanderId = -1`

Validated in Sung:

- `EventId=7` and `EventId=8` (`SensePort=0`, `SenseExpanderId=-1`) resolve to internal sense port name `Gate`.

Resolved sense-trigger rows (Sung, clarified wording):

| Event Name | Event Type | Resolved Trigger | Macro Scope | Macro Name |
|---|---|---|---|---|
| Sets/clears flags using a macro when gate opens | Sense | Sense Port 1 (Gate) Opens | Global | GATE - is OPEN |
| Sets/clears flags using a macro when gate closes | Sense | Sense Port 1 (Gate) Closes | Global | GATE - is CLOSED |

#### B. System event list (`Events`) resolved with System/Global macro mapping (Sung)

Status: `partially supported / incomplete`

User-validated working rule for this project pass:

- treat non-driver `Events` rows (`EventType` `1`, `3`, `4`) as system event triggers
- resolve macro identity through:
  - `Events.MacroId -> Macros.SystemMacroId`
- then resolve:
  - macro scope room via `Macros.RoomId -> Rooms.Name`
  - macro name via `Macros.ButtonTagId -> ButtonTagNames.ButtonTagName`

Why this remains `partially supported / incomplete`:

- `Events.MacroId` is overloaded in this file and can match both `Macros.MacroId` and `Macros.SystemMacroId`
- RTI runtime namespace precedence is not exposed as an explicit schema flag
- this rule is currently validated for Sung system-event review, but not yet generalized to all projects

Resolved system-event output fields requested:

- event name
- event type name
- macro scope room name
- macro name

Resolved rows (`Sung Residence v207.2.apex`):

| Event Name | Event Type Name | Macro Scope Room Name | Macro Name |
|---|---|---|---|
| Sets/clears flags using a macro when gate opens | Sense | Global | GATE - is OPEN |
| Sets/clears flags using a macro when gate closes | Sense | Global | GATE - is CLOSED |
| Turns ON master recessed to 50% and the ensuite tub to 50% WEEKDAY MORNINGS | Scheduled | Global | VACATION MODE - Master Bed/Bath ON |
| Turns ON master recessed to 50% and the ensuite tub to 50% WEEKEND MORNINGS | Scheduled | Global | VACATION MODE - Master Bed/Bath ON |
| Turns ON master recessed to 50% and the ensuite tub to 50% WEEKDAY EVENINGS | Scheduled | Global | VACATION MODE - Master Bed/Bath ON |
| Turns ON master recessed to 50% and the ensuite tub to 50% WEEKEND EVENINGS | Scheduled | Global | VACATION MODE - Master Bed/Bath ON |
| Turns ON hallway/stairs recessed to 50% WEEKDAY MORNINGS | Scheduled | Global | VACATION MODE - Hallway/Stairs ON |
| Turns ON hallway/stairs recessed to 50% WEEKEND MORNINGS | Scheduled | Global | VACATION MODE - Hallway/Stairs ON |
| Turns ON hallway/stairs recessed to 50% WEEKDAY EVENINGS | Scheduled | Global | VACATION MODE - Hallway/Stairs ON |
| Turns ON hallway/stairs recessed to 50% WEEKEND EVENINGS | Scheduled | Global | VACATION MODE - Hallway/Stairs ON |
| Turns ON sink recessed to 50% WEEKDAY MORNINGS | Scheduled | Global | VACATION MODE - Kitchen ON |
| Turns ON sink recessed to 50% WEEKEND MORNINGS | Scheduled | Global | VACATION MODE - Kitchen ON |
| Turns ON sink recessed to 50% WEEKDAY EVENINGS | Scheduled | Global | VACATION MODE - Kitchen ON |
| Turns ON sink recessed to 50% WEEKEND EVENINGS | Scheduled | Global | VACATION MODE - Kitchen ON |
| Turns ON living fireplace recessed to 50% WEEKDAY EVENINGS | Scheduled | Global | VACATION MODE - Living ON |
| Turns ON living fireplace recessed to 50% WEEKEND EVENINGS | Scheduled | Global | VACATION MODE - Living ON |
| Turns OFF all included loads except for hallway WEEKDAY MORNINGS | Scheduled | Global | VACATION MODE - All Rooms Except Hallway Morning OFF |
| Turns OFF all included loads except for hallway WEEKEND MORNINGS | Scheduled | Global | VACATION MODE - All Rooms Except Hallway Morning OFF |
| Turns OFF all included loads WEEKDAY EVENINGS | Scheduled | Global | VACATION MODE - All Included Rooms Evening OFF |
| Turns OFF all included loads WEEKEND EVENINGS | Scheduled | Global | VACATION MODE - All Included Rooms Evening OFF |
| Master Bath Fan On | Scheduled | Global | HRV - Master Bath Fan ON |
| Master Bath Fan Off | Scheduled | Global | HRV - Master Bath Fan OFF |
| Theater Off (All Systems) | Scheduled | Theater | POWER OFF - Room (All Systems) |
| Rec Room Off (All Systems) | Scheduled | Rec Room | POWER OFF - Room (All Systems) |
| Spa Mode OFF at 1am | Scheduled | Global | POOL - Spa Mode OFF |
| TEST - 3am shutoff of Gym with 3 second delay, Off, delay and then another off | Scheduled | Global | POWER - Gym OFF - TEST |
| TEST - 3:30am shutoff of Gym TV with 3 second delay, Off, delay and then another off of the 2 TVs | Scheduled | Global | POWER - Gym TVs Off - TEST |
| Set the Vacation Mode to OFF & Set the Garage Boiler to OFF | Startup | Global | STARTUP - Vacation OFF & Flags Reset & Garage Boiler OFF |

Resolved rows with human-readable trigger strings (AM/PM style):

| Event Name | Event Type | Resolved Trigger | Macro Room->Source | Macro Name |
|---|---|---|---|---|
| Sets/clears flags using a macro when gate opens | Sense | Sense Port 1 (Gate) Opens | Global | GATE - is OPEN |
| Sets/clears flags using a macro when gate closes | Sense | Sense Port 1 (Gate) Closes | Global | GATE - is CLOSED |
| Turns ON master recessed to 50% and the ensuite tub to 50% WEEKDAY MORNINGS | Scheduled | Weekdays at 7:00 AM | Global | VACATION MODE - Master Bed/Bath ON |
| Turns ON master recessed to 50% and the ensuite tub to 50% WEEKEND MORNINGS | Scheduled | Weekends at 8:00 AM | Global | VACATION MODE - Master Bed/Bath ON |
| Turns ON master recessed to 50% and the ensuite tub to 50% WEEKDAY EVENINGS | Scheduled | Weekdays at 9:05 PM | Global | VACATION MODE - Master Bed/Bath ON |
| Turns ON master recessed to 50% and the ensuite tub to 50% WEEKEND EVENINGS | Scheduled | Weekends at 10:05 PM | Global | VACATION MODE - Master Bed/Bath ON |
| Turns ON hallway/stairs recessed to 50% WEEKDAY MORNINGS | Scheduled | Weekdays at 7:35 AM | Global | VACATION MODE - Hallway/Stairs ON |
| Turns ON hallway/stairs recessed to 50% WEEKEND MORNINGS | Scheduled | Weekends at 8:35 AM | Global | VACATION MODE - Hallway/Stairs ON |
| Turns ON hallway/stairs recessed to 50% WEEKDAY EVENINGS | Scheduled | Weekdays at 8:45 PM | Global | VACATION MODE - Hallway/Stairs ON |
| Turns ON hallway/stairs recessed to 50% WEEKEND EVENINGS | Scheduled | Weekends at 9:45 PM | Global | VACATION MODE - Hallway/Stairs ON |
| Turns ON sink recessed to 50% WEEKDAY MORNINGS | Scheduled | Weekdays at 7:37 AM | Global | VACATION MODE - Kitchen ON |
| Turns ON sink recessed to 50% WEEKEND MORNINGS | Scheduled | Weekends at 8:37 AM | Global | VACATION MODE - Kitchen ON |
| Turns ON sink recessed to 50% WEEKDAY EVENINGS | Scheduled | Weekdays at 6:17 PM | Global | VACATION MODE - Kitchen ON |
| Turns ON sink recessed to 50% WEEKEND EVENINGS | Scheduled | Weekends at 7:17 PM | Global | VACATION MODE - Kitchen ON |
| Turns ON living fireplace recessed to 50% WEEKDAY EVENINGS | Scheduled | Weekdays at 7:20 PM | Global | VACATION MODE - Living ON |
| Turns ON living fireplace recessed to 50% WEEKEND EVENINGS | Scheduled | Weekends at 8:20 PM | Global | VACATION MODE - Living ON |
| Turns OFF all included loads except for hallway WEEKDAY MORNINGS | Scheduled | Weekdays at 8:25 AM | Global | VACATION MODE - All Rooms Except Hallway Morning OFF |
| Turns OFF all included loads except for hallway WEEKEND MORNINGS | Scheduled | Weekends at 9:25 AM | Global | VACATION MODE - All Rooms Except Hallway Morning OFF |
| Turns OFF all included loads WEEKDAY EVENINGS | Scheduled | Weekdays at 10:17 PM | Global | VACATION MODE - All Included Rooms Evening OFF |
| Turns OFF all included loads WEEKEND EVENINGS | Scheduled | Weekends at 11:17 PM | Global | VACATION MODE - All Included Rooms Evening OFF |
| Master Bath Fan On | Scheduled | Daily at 9:00 AM | Global->Fans (HRV Fans (RTI RCM12)) | HRV - Master Bath Fan ON |
| Master Bath Fan Off | Scheduled | Daily at 12:00 PM | Global->Fans (HRV Fans (RTI RCM12)) | HRV - Master Bath Fan OFF |
| Theater Off (All Systems) | Scheduled | Daily at 3:00 AM | Theater | POWER OFF - Room (All Systems) |
| Rec Room Off (All Systems) | Scheduled | Daily at 3:00 AM | Rec Room | POWER OFF - Room (All Systems) |
| Spa Mode OFF at 1am | Scheduled | Daily at 1:00 AM | Global | POOL - Spa Mode OFF |
| TEST - 3am shutoff of Gym with 3 second delay, Off, delay and then another off | Scheduled | Daily at 3:00 AM | Global | POWER - Gym OFF - TEST |
| TEST - 3:30am shutoff of Gym TV with 3 second delay, Off, delay and then another off of the 2 TVs | Scheduled | Daily at 3:30 AM | Global | POWER - Gym TVs Off - TEST |
| Set the Vacation Mode to OFF & Set the Garage Boiler to OFF | Startup | At Startup | Global | STARTUP - Vacation OFF & Flags Reset & Garage Boiler OFF |

#### C. Five resolved Source Event examples (`SourceEvents`)

Status: `partially supported / incomplete`

There is no explicit enabled field in `SourceEvents`, so enabled/disabled status is currently unproven at row level.

1. Source Event example `SourceEventsId=32` (`Rogers #1`, `SourceId=59`)
- event name (derived): `Rogers #1 On`
- trigger (inferred): source-on hook (`OnMacroId=4186`)
- macro resolution:
  - direct `MacroId` hit: none
  - `SystemMacroId` hit: `MacroId=4558` (`RoomId=3`, `DeviceId=-1`)
  - steps: one `Type 8` page-link step (`PageLinkDevice=193`, `Page=0`)

2. Source Event example `SourceEventsId=33` (`Rogers #2`, `SourceId=60`)
- event name (derived): `Rogers #2 On`
- trigger (inferred): source-on hook (`OnMacroId=4187`)
- macro resolution:
  - via `SystemMacroId`: `MacroId=4559`
  - steps: one `Type 8` page-link step (`PageLinkDevice=193`, `Page=0`)

3. Source Event example `SourceEventsId=37` (`Apple TV #1 (Gen 4)`, `SourceId=84`)
- event name (derived): `Apple TV #1 (Gen 4) On`
- trigger (inferred): source-on hook (`OnMacroId=5724`)
- macro resolution:
  - direct `MacroId` hit: `MacroId=5724` (`SystemMacroId=5277`, `RoomId=0`, `DeviceId=-1`)
  - steps: one `Type 1` command `Apple TV #1 (Gen 4) -> MENU MAIN`

4. Source Event example `SourceEventsId=38` (`Apple TV #2 (Gen 4)`, `SourceId=85`)
- event name (derived): `Apple TV #2 (Gen 4) On`
- trigger (inferred): source-on hook (`OnMacroId=5725`)
- macro resolution:
  - direct `MacroId` hit: `MacroId=5725`
  - steps: one `Type 1` command `Apple TV #2 (Gen 4) -> MENU MAIN`

5. Source Event example `SourceEventsId=62` (`Theater LG BluRay`, `SourceId=82`)
- event name (derived): `Theater LG BluRay On/Off`
- trigger (inferred): source-on and source-off hooks (`OnMacroId=4238`, `OffMacroId=4239`)
- macro resolution:
  - `On` steps: one `Type 1` command `Theater LG BluRay -> POWER ON`
  - `Off` steps: one `Type 1` command `Theater LG BluRay -> POWER OFF`

#### D. Clipsal C-Bus driver event token pattern in Sung

Status: `confirmed extractable now`

For `Sung Residence v207.2.apex`, Clipsal C-Bus driver events are present in `Events` as driver-triggered rows:

- `Events.EventType = 5`
- `Events.DriverId = 96` (`Devices.DeviceId=96`, `Name='Clipsal C-Bus'`)
- `Events.DriverExtraString` carries the trigger token

Observed token family in Sung:

- `APP38GROUP...` (for example `APP38GROUP20ON`, `APP38GROUP21OFF`, `APP38GROUP3COFF`)

Observed count:

- `58` Clipsal C-Bus event rows (`DriverId=96`)

Important file-specific note:

- no `APP56GROUP...` rows were found in Sung
- if the UI shows `App 56 Group ...`, that may come from a different project file or a different driver configuration/version than this sample

Token-decoding clarification (confirmed from event payload semantics):

- `APP38GROUP01ON` decodes to:
  - App hex `38` -> decimal `56`
  - Group hex `01` -> decimal `1`
  - state `ON`

Resolved example for `App 56, Group 1 On` in Sung:

- event row: `EventId=30`, `DriverId=96` (`Clipsal C-Bus`), `Enabled=1`, `EventType=5`
- `DriverExtraString=APP38GROUP01ON`
- macro run: `MacroId=1030` (`SystemMacroId=1016`, `RoomId=0`, `DeviceId=95`)
- macro step payload:
  - `Type 1`
  - command device: `DeviceId=94` (`Lutron Caseta / RA2 Select`, display `Lutron Upper`)
  - function: `SwitchCmd:Switch`
  - parameters: `Parameter1='11'`, `Parameter2='1'`, `Parameter3='2'`

Sibling `OFF` row for same app/group:

- `APP38GROUP01OFF` -> `EventId=32` -> `MacroId=1032`

Parameter decoding for `SwitchCmd:Switch` (from `DriverData.SystemFunctions` for Device `94`):

- `Parameter1` = `Integration ID` (driver source/device index)
  - choice format: `%%__IDNameNNN%% (ID N)`
  - resolve display name via `DriverConfig` key `__IDNameNNN`
- `Parameter2` = hidden driver field (`name='hidden'`, default `1`)
- `Parameter3` = `Switch Command`
  - `1` = `Toggle`
  - `2` = `On`
  - `3` = `Off`

Applied to this event:

- schema-level candidate: `Parameter1='11'` -> choice slot `Device11` / `__IDName011`
- `Parameter2='1'` -> hidden/default control flag
- `Parameter3='2'` -> `On`

User-validated correction for this exact event:

- RTI UI resolves this command as:
  - controlled device: `Lutron Upper`
  - function: `Switches \ Switch Commands`
  - integration ID display: `West Bedroom Accent Lights (ID 6)`
  - command: `On`

Current extraction stance for this command family:

- preserve raw macro payload (`Function`, `Parameter1..Parameter4`) as authoritative extractable data
- preserve schema-level function metadata (parameter names and choice labels) as a candidate decoding layer
- treat final human label for Integration ID as `partially supported / incomplete` unless validated against RTI runtime/UI behavior
- for human-readable target intent, also resolve `Macros.ButtonTagId -> ButtonTagNames.ButtonTagName` when available

Observed examples from Sung:

- `MacroId=1030` (`APP38GROUP01ON`) has `ButtonTagId=306` -> `ButtonTagName='LIGHTS - Patio Accent ON'`
- `MacroId=1031` (`APP38GROUP08ON`) has `ButtonTagId=307` -> `ButtonTagName='LIGHTS - Patio Accent OFF'`

Additional validation samples provided by user (same Sung file):

- `App 56 Group 8 On` (token `APP38GROUP08ON`) resolves to:
  - `EventId=31`, `MacroId=1031`
  - macro step: `SwitchCmd:Switch` with params `11,1,3`
  - RTI UI shown value: Integration ID `East Bedroom Accent Light (ID 4)`, command `On`
  - this reinforces that direct parameter-to-label decoding is not yet deterministic from schema alone

Validated expanded command resolution example:

- `App 56 Group 60 On` (`Events.DriverExtraString='APP38GROUP3CON'`, `EventId=74`)
  - resolved trigger: `App 56 Group 60 On`
  - resolved path format:
    - `Macro Room/Source -> Macros/Commands`
  - resolved row:
    - `Global/Lutron Lower (Lutron Caseta / RA2 Select) -> Set Dimmer Level -> Guest Bed Shelf (ID 13), Level 100, Fade 00:00:02, Delay 00:00:00`
  - schema evidence:
    - wrapper macro via `Events.MacroId -> Macros.SystemMacroId` (`MacroId=4323`, `DeviceId=96`)
    - command step is direct `Type=1` on wrapper macro (no `Type=14` indirection):
      - `DeviceId=161`
      - `Function='SetDimmerLevel:QSDimmer'`
      - `Parameter1='13'`, `Parameter2='100'`, `Parameter3='00:00:02'`, `Parameter4='00:00:00'`
    - integration target name:
    - `DriverData(DeviceId=161).DriverDeviceId=21`
    - `DriverConfig(DriverDeviceId=21, Name='__IDName013')='Guest Bed Shelf'`

- `App 56 Group 60 Off` (`Events.DriverExtraString='APP38GROUP3COFF'`, `EventId=75`)
  - resolved trigger: `App 56 Group 60 Off`
  - resolved row:
    - `Global/Lutron Lower (Lutron Caseta / RA2 Select) -> Switch Command: Guest Bed Shelf Off`
  - schema evidence:
    - wrapper macro via `Events.MacroId -> Macros.SystemMacroId` (`MacroId=4324`, `DeviceId=96`)
    - wrapper has one direct command step (`Type=1`, no `Type=14` indirection):
      - `DeviceId=161`
      - `Function='SwitchCmd:Switch'`
      - `Parameter1='13'`, `Parameter2='1'`, `Parameter3='3'`
    - command decoding:
      - `DriverData(DeviceId=161).DriverDeviceId=21`
    - `DriverConfig(DriverDeviceId=21, Name='__IDName013')='Guest Bed Shelf'`
    - `SwitchCmd:Switch Parameter3='3' -> Off`

#### D2. Locked output format and macro-scope display rule

Status: `confirmed extractable now`

Locked table headings for event output:

| Event Name | Event Type | Resolved Trigger | Macro Room/Source -> Macros/Commands |
|---|---|---|---|

Locked `Macro Room/Source` rule:

- display the scope of the macro/command being reported in `Macros/Commands`
- when event resolution uses a wrapper macro with `MacroSteps.Type = 14` (`MacroFunctionCall`):
  - use the target command macro scope (resolved from `CommandTagId` -> target `Macros` rows), not the wrapper macro scope
- when wrapper is direct command (`Type = 1`, no `Type = 14`), use that macro row scope (`Macros.RoomId`, `Macros.DeviceId`)

#### D3. Locked event-class scope and filtering for event testing output

Status: `confirmed extractable now`

Locked event classes for this event-testing workflow:

- `System Events`:
  - rows from `Events` where `DriverId IS NULL`
  - current type mapping used in output:
    - `EventType=1` -> `Sense`
    - `EventType=3` -> `Scheduled`
    - `EventType=4` -> `Startup`
- `Driver Events`:
  - rows from `Events` where `EventType=5` and `DriverId IS NOT NULL`
  - display name is locked to `Driver Events` (not `Source Events`) for this reporting flow

Enabled-state lock:

- event output tables for this flow must include only enabled events:
  - `Events.Enabled = 1`

Out-of-scope note for this flow:

- `SourceEvents` (`SourceId`, `OnMacroId`, `OffMacroId`) are source power-hook rows and are tracked separately; they are not part of the initial `System Events`/`Driver Events` event-testing tables.

- `OPSTATECHANGE002` (`Events.DriverExtraString='OPSTATECHANGE002'`, `EventId=126`)
  - resolved trigger:
    - `Garage (Stat 2) Operating State Change`
  - resolved row:
    - `Global -> If Garage (Stat 2) Operating State = Heating, close Internal Relay Port 8 (Garage Boiler Trigger); else open Internal Relay Port 8 (Garage Boiler Trigger)`
  - schema evidence:
    - trigger name decoding:
      - `DriverData(DeviceId=248).SystemEvents` includes token template:
        - `OPSTATECHANGE002 -> %%StatName002%% (Stat 2) - Operating State Change`
      - `DriverConfig(DriverDeviceId=55, Name='StatName002')='Garage'`
    - condition decoding:
      - `MacroVariableTest(MacroStepId=15953)` -> `Variable='state002001'`, `VariableDeviceId=248`
      - `DriverData(DeviceId=248).SystemVariables` maps `state002001` to:
        - `%%StatName002%% (Stat 2) - Operating State Heating`
    - action decoding:
      - `MacroRelay` rows:
        - `MacroStepId=15962`, `RelayPort=-65529`, `RelayCommand=0`
        - `MacroStepId=15963`, `RelayPort=-65529`, `RelayCommand=1`
      - `MacroComment` rows:
        - `MacroStepId=15954`: `Close the XP-8 relay`
        - `MacroStepId=15957`: `Open the XP-8 relay`
      - internal relay name mapping uses relay-label key range (`-64768..-64761`):
        - internal relay port `8` label is `Garage Boiler Trigger` (`PortLabels.LabelKey=-64761`)
  - display rule confirmed:
    - when variable token is fully resolved to a human-readable meaning, output should use the resolved name and not show raw variable tokens

#### E. ButtonTag-selected command metadata resolution path (Sung)

Status: `confirmed extractable now`

For this sample, selecting a macro by `ButtonTagNames.ButtonTagName` can be resolved to a concrete device command payload and driver metadata using only `.apex` data.

Confirmed chain:

- `ButtonTagNames.ButtonTagName -> ButtonTagId`
- `Macros.ButtonTagId -> Macros.MacroId/SystemMacroId/DeviceId/OutputType`
- `MacroStepsView` (or `MacroDeviceCommand`) by `MacroId`
- command target driver metadata:
  - `MacroStepsView.DeviceId -> DriverData.DeviceId -> DriverData.SystemFunctions`
  - parameter-choice display names via `DriverConfig` for that `DriverData.DriverDeviceId`

Confirmed example (`Sung Residence v207.2.apex`):

- `ButtonTagName='LIGHTS - West Bed Accent ON'` -> `ButtonTagId=301`
- `Macros` row:
  - `MacroId=1025`
  - `SystemMacroId=1011`
  - `DeviceId=95`
  - `OutputType=1`
- single step payload:
  - `MacroStepId=1350`
  - `Type=1`
  - `DeviceId=94`
  - `Function='SwitchCmd:Switch'`
  - `Parameter1='6'`
  - `Parameter2='1'`
  - `Parameter3='2'`
- driver-backed parameter metadata (from `DriverData.SystemFunctions` + `DriverConfig` for `DriverDeviceId=9`):
  - `Parameter1` (`Integration ID`) value `6` -> `__IDName006`
  - `DriverConfig.__IDName006='West Bedroom Accent Lights'`
  - `Parameter3` (`Switch Command`) value `2` -> `On`

#### F. Event-linking gap and macro-family framing (Sung)

Status: `partially supported / incomplete`

User conceptual framing for this area:

- `System Macros` (central/global behavior)
- `Source Macros` (behavior under a source/device context)

Schema-backed translation currently supported:

- there is one macro table (`Macros`); no separate `SystemMacros`/`SourceMacros` tables
- `Macros.SystemMacroId` is a stable identity/grouping field inside `Macros`
- macro scoping/context signals currently available are `Macros.DeviceId` and `Macros.RoomId`

Confirmed gap from current sample row (`ButtonTagId=301`, `MacroId=1025`):

- no rows found linking this macro through:
  - `Events.MacroId`
  - `Activities.SelectedMacroId` / `Activities.DeselectedMacroId` / `Activities.PagelinkMacroId`
  - `RoomEvents.SelectedMacroId` / `RoomEvents.DeselectedMacroId`
  - `SourceEvents.OnMacroId` / `SourceEvents.OffMacroId`

Confirmed context for this macro:

- `Macros.DeviceId=95`
- `Devices.DeviceId=95`, `Name='Lutron Upper Floor (Macros Here)'`, `DisplayName='Lutron Upper Floor'`

Working implication for extraction logic:

- keep a separate unresolved linkage state for macros that are fully command-resolved but not yet connected to `Events`/activity/source hook tables
- preserve the user conceptual labels (`System Macros` vs `Source Macros`) as a translation layer, but map them to schema fields (`Macros.SystemMacroId`, `Macros.DeviceId`, `Macros.RoomId`) until a stricter rule is proven

## Inferred by Jamie

This section stores user-provided semantic mappings that are useful for investigation, but are not yet fully proven from schema alone.

Status: `partially supported / incomplete`

### A. Flag action naming

- user-provided mapping:
  - `FlagType = 1` -> `Flag Set`
- schema-backed fields:
  - `MacroFlag.FlagType`
  - `MacroStepsView.FlagType`

### B. Sense action naming

- user-provided mapping is mode-aware and depends on sense input type:
  - for `Sense Closure` mode:
    - `SenseAction = 0` -> `Opens`
    - `SenseAction = 1` -> `Closes`
  - for `Sense Voltage` mode:
    - `SenseAction = 0` -> `Goes High`
    - `SenseAction = 1` -> `Goes Low`
- schema-backed fields:
  - `Events.SenseAction`
  - `Events.SensePort`
  - `Events.SenseExpanderId`

### C. Sense input electrical mode distinction

- schema-backed distinction exists:
  - `SenseModeMap` provides per-port mode mask by `RTIAddress` and `ExpanderId`
  - bit decoding (already validated in extraction logic):
    - bit `1` -> `Sense Closure`
    - bit `0` -> `Sense Voltage`
- important constraint:
  - this is port-mode configuration, not the same field as `Events.SenseAction`
  - event trigger behavior should preserve both dimensions:
    - action (`SenseAction`)
    - port mode (`SenseModeMap`-derived state)

### D. Astronomical schedule subtype mapping

- user-provided mapping:
  - `Events.DailyAstronomical = 1` and `DailyStartTimeHex` suffix `...0000` -> `Sunrise`
  - `Events.DailyAstronomical = 1` and `DailyStartTimeHex` suffix `...0001` -> `Sunset`
- validated example in `Verrier Home FEENY EDIT v49.apex`:
  - `EventId=126`, `DailyStartTimeHex=6E004100700065007800000000000000` -> sunrise trigger
  - `EventId=127`, `DailyStartTimeHex=6E004100700065007800000000000100` -> sunset trigger
- schema-backed fields:
  - `Events.DailyAstronomical`
  - `Events.DailyStartTime`
  - `LocationDefaults.LocationLatitude`
  - `LocationDefaults.LocationLongitude`
  - `ClockDefaults.TimeZone`
  - `ClockDefaults.EnableDst`

### E. `MacroRoomOff.RoomOffId` semantic naming

- user-provided mapping to use for current interpretation:
  - `RoomOffId = -2` -> `Room Off: All Rooms Off`
  - `RoomOffId = -1` -> `Room Off: Current Room`
  - third pattern (still to be proven): `Room Off: <Room Name>`
- current status:
  - first two mappings are treated as inferred/user-validated naming
  - third pattern remains intentionally unresolved until proven by additional extraction evidence
- schema-backed fields:
  - `MacroSteps.Type = 27`
  - `MacroRoomOff.RoomOffId`

### Known schema paths that exist but are not fully explored

#### A. Event-trigger normalization and naming completeness

Status: `known schema paths that exist but are not fully explored`

High-value next paths:

- `Events` + full `EventType` enum mapping
  - to produce canonical trigger names instead of inferred families
- `SourceEvents` + macro ID namespace normalization (`MacroId` vs `SystemMacroId`)
  - to make source event macro resolution deterministic across projects
- `MacroEventControl` / `MacroEventTest`
  - to capture event-control steps embedded inside macros

### Immediate Codex Guidance For This Area

If Codex is asked to extract UI structure from an `.apex` file, the best current sequence is:

1. Start with `PagesView` for page metadata.
2. Join `Layers` and `SharedLayers` to understand page composition and reusable layers.
3. Use `LayerButtons` as the first-choice button/action view.
4. Fall back to `RTIDeviceButtonData` when raw geometry, text, blob fields, or view discrepancies matter.
5. Use `PageLinkView` for explicit navigation links.
6. Use `MacroStepsView` for typed macro step discovery.
7. Treat button labels as unresolved until all applicable sources have been checked (`Text`, `ButtonTagNames`, `ButtonTextTags`, denormalized views).

## Practical Scope for a New App

If the new application needs a stable first-version `.apex` extractor, the safest currently-proven scope is:

- devices
- rooms
- RTI address mappings
- page identities and page names
- page-to-source-to-room relationships
- driver config values
- SYSVARREF registry and variable names
- driver template variable catalog
- source catalogs
- expansion device types
- relay/MPIO/sense/trigger/RS-232 port names and basic derived metadata
- button/source test indexing if raw button traversal is needed

## Best Next Expansion Areas

If the goal is to teach Codex to find more specific naming and relationships, the highest-value next schema investigations are:

1. Macro naming and macro step typing across all `Macro*` tables and views.
2. Full button label resolution using `LayerButtons`, `ButtonTagNames`, and `ButtonTextTags`.
3. True source routing semantics using `SourceLabels` plus `SourceMapping`.
4. System Manager variable families beyond source-name tokens.
5. Project metadata extraction from `UnstructuredData` and `JobInfo`.
6. Denormalized view audit to decide when views are safer than raw table joins.
7. IR and RS-232 functional extraction, not just port naming.

## Current Confidence Summary

- `confirmed extractable now`: strong
- `partially supported / incomplete`: significant and useful
- `suspected but not yet implemented`: extensive, especially in macro/UI/view metadata

The repository already proves that `.apex` can support far more than simple page-name mapping. The current codebase reliably extracts page, room, source, driver, sysvar, and port data now, while the schema and archive docs show several larger unexplored paths for macros, UI/button structures, variables, routing, and project metadata.
