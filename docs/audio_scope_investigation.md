# Audio Scope for Hard-Key Volume Buttons — Investigation Lock-Down

Status: locked.

## Purpose

Define how Sentinel identifies hard-key volume / mute buttons that share an
audio target, so a pass or fail on one can later be propagated to the others
in the same scope without comparing macros.

Scope: **hard keys only** — three buttons per controller (vol+, vol-, mute).
Soft-button volume bars, mute-state indicators, and any other on-screen
volume display are out of scope and are not affected by this work.

This document covers **Phase A only**: what gets extracted into the
project-data JSON. Test-result application (Phase B) and UI surfacing
(Phase C) are tracked separately.

## Source of truth in the apex file

RTI Apex stores per-room hard-key action redirection in:

| Table           | Columns                                          | Role                              |
|-----------------|--------------------------------------------------|-----------------------------------|
| `MacroRedirect` | `MacroRedirectId, RoomId, ButtonTagId, SourceId` | Redirect a hard-key's action macro to a room-specific audio wrapper |

`SourceId` points at a `Devices` row with `ControlType=6` — a "wrapper" device
representing the audio output for that room. The underlying driver (e.g.
Denon AVR) is reachable via:

`DriverDataReference.DeviceId = wrapper.DeviceId, ParentDeviceId = driver.DeviceId`

In every project examined, a redirected room has **exactly 3 rows** in
`MacroRedirect` — one each for vol+, vol-, mute. Rooms with no audio
override have zero rows.

## There is no project-default audio device

If `MacroRedirect` has no rows for `(RoomId, ButtonTagId)`, that hard-key
button is **not part of any audio scope**. It continues to be handled
exactly as it is today (existing tag-based handling), with no new metadata
emitted.

## Verified evidence

### Haven and Wire Sunrise (Jazz Room) v15.1 — single-room project

```
MacroRedirect:
  1 | RoomId=1 (Jazz Room) | ButtonTagId=14 | SourceId=9 (Marantz wrapper)
  2 | RoomId=1 (Jazz Room) | ButtonTagId=22 | SourceId=9
  3 | RoomId=1 (Jazz Room) | ButtonTagId=19 | SourceId=9

DriverDataReference:
  2 | DeviceId=9 (Marantz wrapper) | ParentDeviceId=8 (Denon Receiver driver)
```

### Sung Residence v207.2 — 26-room project, all global controllers

```
MacroRedirect:
  14 | Theater (RoomId=12)  | ButtonTagId=10 | SourceId=166 (Denon-Theater)
  15 | Theater              | ButtonTagId=14 | SourceId=166
  16 | Theater              | ButtonTagId=8  | SourceId=166
  17 | Rec Room (RoomId=7)  | ButtonTagId=10 | SourceId=168 (Denon-Rec)
  18 | Rec Room             | ButtonTagId=14 | SourceId=168
  19 | Rec Room             | ButtonTagId=8  | SourceId=168
```

The remaining 24 of 26 rooms have no `MacroRedirect` rows; their hard-key
volume/mute buttons remain unscoped.

### `ButtonTagId` is not a stable name

`ButtonTagId` values differ between projects/templates because they are
defined by the specific wrapper template. Vol+ is `ButtonTagId=14` in Haven,
but Sung uses different IDs for the same logical keys. The scope rule does
**not** depend on identifying which `ButtonTagId` is which hard key — the
existence of a `MacroRedirect` row is itself the marker.

## Scope identity emitted into project-data JSON

For every hard-key button whose `(RoomId, ButtonTagId)` appears in
`MacroRedirect`, the extractor emits:

```json
"testTargets": {
  "macro": { ... existing fields ... },
  "audioScope": {
    "roomId": <int>,
    "wrapperDeviceId": <int>
  }
}
```

For every hard-key button whose `(RoomId, ButtonTagId)` does not appear in
`MacroRedirect`, the `audioScope` field is **absent**.

## Equivalence rule (for Phase B consumers)

Two `testTargets` entries share audio scope iff:

1. Both have a non-null `audioScope.wrapperDeviceId`, **and**
2. `audioScope.wrapperDeviceId` values are equal.

`audioScope.roomId` is informational only.

## What Phase A does NOT do

- No macro comparison.
- No change to non-redirected hard-key buttons.
- No effect on volume-bar or mute-state displays.
- No UI changes.

## Files touched in Phase A

| File | Reason |
|---|---|
| `src/sentinel/extraction/extractor_core.py` | Read `MacroRedirect`, `Devices`, `DriverDataReference`; emit `audioScope` on matching hard-key targets |
| `src/sentinel/contracts/apex_project_structure_v4.json` | Declare the new optional `audioScope` field additively |
| `dev_tests/regression/test_extractor_audio_scope.py` (new) | Cover redirect-present and redirect-absent cases |
| `docs/data_contracts.md` | Document the new field |

---

# Phase B — Pass-on-scope-sibling via targetKey collapse

Status: locked.

## Purpose

Reuse the codebase's existing target-equivalence mechanism (same `targetKey`
string = same result) so a single pass on any redirected hard-key button
automatically passes every redirected hard-key button in the same room, on
every page in that room — without introducing a separate "propagation"
service.

## Pattern reused

`_scoped_target_key_from_button` in `src/sentinel/server/services/progress.py`
and `buildTargetPayload` in `src/sentinel/generation/render_core.py` already
encode equivalence into the `targetKey` itself; the latest-record-per-key
read model then provides propagation for free. Phase B collapses the key for
redirected hard keys and changes nothing else.

## Where `audioScope` lives on the user side

In addition to its Phase A diag-side home, `audioScope` is also mirrored
into the user-facing button at:

`devices[].userFacing.pages[].layers[].buttonCategories.hardButtons[].apexScopeSource.audioScope`

(and the equivalent path under viewport frames). This is the same dict that
`_scoped_target_key_from_button` and `buildTargetPayload` already read for
every other scope component (`page`, `viewportLayer`, `pageLayer`, `button`,
`bindings`), so no new plumbing is needed.

Value: `null` when no `MacroRedirect` row exists, otherwise
`{ "roomId": <int>, "wrapperDeviceId": <int> }`.

## Collapsed `targetKey` format

When `apexScopeSource.audioScope.wrapperDeviceId` is non-null, the key
becomes:

```
tt2_audio:{rtiAddress}:{scopeType}:{roomId}:{wrapperDeviceId}:{buttonTagId}:{label}
```

- `tt2_audio:` prefix is distinct from the existing `tt2:` / `tt_ui:`
  prefixes; collision with a non-redirected key is impossible.
- `effectiveSourceId` and `programRef` are deliberately omitted — those are
  the components that differ between pages (per-source) and per-button
  (per-macro-instance) on the same hard key, so dropping them lets a pass on
  any one page propagate to every page in the same redirected room.
- `buttonTagId` is **kept** — vol+, vol-, and mute have distinct
  `ButtonTagId`s and must remain three distinct test results.
- `label` (e.g. `System Macro`) is preserved so different test targets on
  the same button still produce different keys.

## Behavioral guarantees

| Scenario | Result |
|---|---|
| vol+, vol-, mute in the same redirected room | **Three distinct** `targetKey`s (one per hard key) |
| vol+ on Theater Home and vol+ on Theater AppleTV | Same shared `targetKey` (cross-page propagation) |
| Theater (wrapper 166) vs. Rec Room (wrapper 168) hard keys | Different keys |
| Non-redirected hard key (no `MacroRedirect` row) | Existing `tt2:` key — byte-identical to pre-Phase-B |
| Older fixture without `audioScope` field | Existing `tt2:` key — falls back |
| Malformed `audioScope` (missing `wrapperDeviceId`, non-dict) | Existing `tt2:` key — falls back |

## What Phase B does NOT do

- No change to non-redirected hard keys, soft buttons, or any non-hard
  target.
- No effect on volume-bar or mute-state displays.
- No new service, repository, or UI component. Existing
  latest-record-per-`targetKey` read model handles propagation.
- No change to `commissioning.py`, `repositories.py`, `testing.py`,
  `queries.py`, or any UI JS file outside `render_core.py`'s template.

## Files touched in Phase B

| File | Reason |
|---|---|
| `src/sentinel/extraction/extractor_core.py` | Mirror `audioScope` into the user-side `apexScopeSource` dict |
| `src/sentinel/contracts/apex_project_structure_v4.json` | Declare `apexScopeSource.audioScope` on both user-side button templates |
| `src/sentinel/server/services/progress.py` | Branch `_scoped_target_key_from_button` on `audioScope` |
| `src/sentinel/generation/render_core.py` | Same branch in both `buildTargetPayload` template copies |
| `dev_tests/regression/test_progress_audio_scope_target_key.py` (new) | Cover collapse + non-regression for normal keys |

Out of scope: any "propagation" service, UI changes, or non-hard-key behavior.
