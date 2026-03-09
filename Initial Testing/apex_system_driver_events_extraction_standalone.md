# RTI `.apex` System + Driver Events Extraction (Standalone)

This document is a standalone extraction/resolution guide for AI agents.

Scope:
- System Events extraction from `Events`
- Driver Events extraction from `Events`
- Macro resolution and macro-scope rendering for event output

Out of scope for this workflow:
- `SourceEvents` power hooks (`SourceId`, `OnMacroId`, `OffMacroId`) are tracked separately and are not part of the initial event-testing tables.

---

## Locked Output Table Format

Use this exact heading format:

| Event Name | Event Type | Resolved Trigger | Macro Room/Source -> Macros/Commands |
|---|---|---|---|

---

## Locked Event Class Rules

### System Events
- Source table: `Events`
- Filter: `Events.DriverId IS NULL`
- Type names:
  - `EventType = 1` -> `Sense`
  - `EventType = 3` -> `Scheduled`
  - `EventType = 4` -> `Startup`

### Driver Events
- Source table: `Events`
- Filter: `Events.EventType = 5 AND Events.DriverId IS NOT NULL`
- Display class name in workflow: `Driver Events`

### Enabled-only rule
- Include only `Events.Enabled = 1` rows.

---

## Macro Scope Model (Locked)

Macro scope groups:
1. `Room (includes Global)`:
   - `Macros.DeviceId = -1`
   - Room label from `Macros.RoomId` (`0 = Global`, `>0 = room name`)
2. `Room + Source/Driver`:
   - `Macros.DeviceId >= 0 AND Macros.RoomId > 0`
3. `Source/Driver`:
   - `Macros.DeviceId >= 0 AND Macros.RoomId = 0`

Display rule for `Macro Room/Source -> Macros/Commands`:
- Always display the scope of the macro/command being reported.
- If wrapper macro uses `MacroSteps.Type = 14` (`MacroFunctionCall`):
  - display the target command macro scope (from target `CommandTagId` macro rows), not wrapper scope.
- If wrapper macro is direct command (`Type = 1`, no `Type = 14`):
  - display that macro row scope.

---

## Resolution Pipeline

## 1) Build base event rows

System Events query:

```sql
SELECT *
FROM Events
WHERE DriverId IS NULL
  AND Enabled = 1
ORDER BY EventId;
```

Driver Events query:

```sql
SELECT *
FROM Events
WHERE EventType = 5
  AND DriverId IS NOT NULL
  AND Enabled = 1
ORDER BY DriverId, DriverExtraString, EventId;
```

## 2) Resolve event type name

Mapping:
- `1 -> Sense`
- `3 -> Scheduled`
- `4 -> Startup`
- `5 -> Driver`

## 3) Resolve trigger text

### System Events trigger resolution

Sense (`EventType=1`):
- Use `SensePort`, `SenseAction`, `SenseExpanderId`.
- Resolve port label from `PortLabels` where available.
- In current workflow, use approved sense-action wording logic from project rules.

Scheduled (`EventType=3`):
- If fixed schedule: decode day mask/time payload with project-proven decoder.
- If astronomical schedule (`DailyAstronomical=1`):
  - keep astronomical classification.
  - if project rule is available and approved:
    - `DailyStartTimeHex ...0000` -> sunrise
    - `DailyStartTimeHex ...0001` -> sunset

Startup (`EventType=4`):
- Trigger = startup.

### Driver Events trigger resolution

Resolve token `Events.DriverExtraString` using driver metadata:
- `Events.DriverId -> DriverData.DeviceId`
- Parse `DriverData.SystemEvents` XML:
  - match `<event tag="...">` to `DriverExtraString`
  - use `event name` as trigger text
  - resolve category tokens (`%%token%%`) via `DriverConfig` for that `DriverDeviceId`

---

## 4) Resolve assigned event macro

### System Events macro identity

Use:
- `Events.MacroId -> Macros.SystemMacroId`

Then resolve macro row:
- `Macros.RoomId`, `Macros.DeviceId`, `Macros.ButtonTagId`

### Driver Events macro identity (strict driver/source-first)

Use:
- `Events.MacroId -> Macros.SystemMacroId`
- and enforce wrapper scope:
  - `Macros.DeviceId = Events.DriverId`

SQL shape:

```sql
SELECT *
FROM Macros
WHERE SystemMacroId = :event_macro_id
  AND DeviceId = :event_driver_id
ORDER BY MacroId;
```

If no row exists, mark unresolved; do not silently switch to unrelated scope.

---

## 5) Resolve `Macros/Commands` text + scope

For each resolved event macro:

1. Load steps:

```sql
SELECT MacroStepId, StepIndex, Type
FROM MacroSteps
WHERE MacroId = :macro_id
ORDER BY StepIndex, MacroStepId;
```

2. If any `Type = 14`:
   - join `MacroFunctionCall` by `MacroStepId`
   - get `CommandTagId`
   - resolve command name from `ButtonTagNames.ButtonTagName`
   - resolve target macro scope from `Macros` rows where `ButtonTagId = CommandTagId`
   - display target scope + command name

3. Else if macro has `ButtonTagId`:
   - resolve label from `ButtonTagNames`
   - display macro row scope + label

4. Else fallback:
   - summarize direct command steps (`Type=1`) via `MacroDeviceCommand`
   - display macro row scope + command summary

---

## 6) Render scope label

Room label:
- `Macros.RoomId -> Rooms.Name` (`0` should resolve to `Global`)

Source/device label:
- if `DeviceId = -1`, show room only
- if `DeviceId >= 0`, append device display:
  - `Devices.DisplayName` and `Devices.Name` (if both exist and differ, show `DisplayName (Name)`)

Final scope string examples:
- `Global`
- `Theater`
- `Global/Lutron Lower (Lutron Caseta / RA2 Select)`

---

## Determinism + Quality Gates

Before final output:
1. Confirm all rows are `Enabled=1`.
2. Confirm event class filters were applied exactly.
3. Confirm driver events used strict driver-scoped wrapper mapping.
4. Confirm `Type=14` rows display target command macro scope, not wrapper scope.
5. Keep unresolved rows explicit; do not infer.

---

## Minimal Implementation Checklist

1. Read `Events` enabled rows, split into System and Driver classes.
2. Resolve triggers (System payload or Driver XML tags + config token expansion).
3. Resolve macro identity (`SystemMacroId` path; strict driver device match for Driver events).
4. Resolve command and scope (`Type=14` target scope rule).
5. Emit locked table heading and rows.

