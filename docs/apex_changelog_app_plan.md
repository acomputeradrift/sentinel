# Standalone RTI Apex changelog app

Working plan. Approved 2026-09-08. Lives in Sentinel until the new repo/folder exists; then move this file there.

**Product:** local two-file Apex compare. Not commissioning, not a Sentinel route.

**Sentinel File tab stays as-is.** This app reuses extract + changelog ideas; it does not replace the console.

---

## Constraints

- New repo/folder. Do not add `/changelog/` to Sentinel.
- `.apex` files stay on the client machine. Never POST them to a remote server.
- Default compute: **localhost Python sidecar** so we reuse Sentinel extract (`extractor_core` + `build_resolved_targets`) and `build_changelog`. Do not rewrite extract in the browser for MVP.
- Do not permanently fork extract or `upload_changelog.py`. One brain; share or import from Sentinel until a shared package is justified.

---

## UI

One page. No tabs, no tree nav, no save, no history.

1. File A — local `.apex` picker (previous)
2. File B — local `.apex` picker (current)
3. Compare
4. Changelog box
5. Export CSV — enabled after a successful Compare

Changelog box matches the File tab shape (`#fileChangelogBox`):

- Heading: `Change Log (A -> B)`
- **Testable**
- **Non-testable but changed**
- Later tags in the same lists: Identity / Graphics if added

Empty / error copy in that box:

- Missing a file: `Choose two .apex files.`
- Extract or diff fail: `Changelog could not be computed.`
- No diffs: `No changes since last file.`

One progress line under Compare (extract A, extract B, diff). Not a second page.

---

## CSV export

Generated locally from the last Compare result. Nothing stored on a server.

One row per changelog line. Columns:

| column | example |
|---|---|
| previousFile | `v29.apex` |
| currentFile | `v30.apex` |
| category | `testable` or `layout` (later `identity` / `graphics`) |
| line | `RTiPanel / Cameras / Page / Screen Button / NAV - Go to CAMERA 1: test targets changed` |

Export the **full** lists. Do not apply the on-screen line cap (`and N more` is UI only).

If Compare is empty or failed, Export stays disabled.

---

## Diff coverage (not UI)

The tree is what the engine may report. The page does not browse it.

```
System
  Settings
  Rooms
  Events
  Macros          (+ steps, not just the macro)
  Drivers
    Settings
    Events
    Commands
  Sources
    Macros
    Variables
  Activities
    Membership    (Checked + ActivityOrder)
    Events
    Macros

Devices
  (device add/remove/rename)
  Settings        (resolution / orientation)
  Graphics
  Pages
    Layers / Shared Layers
    Viewports / Frames
    Programming
      Screen Labels
      Screen Buttons
      Hard Buttons
      Empty Tag / UI Items
      Page Links
      Slot / Gesture map
```

Line tags (not tree nodes):

- **Programming** (testable)
- **Layout** (moved / stacked / visibility)
- **Graphics**
- **Identity** (rename / text)

### Overlap with Sentinel File-tab changelog today

Already isolated: matching-button test targets, macro/page-link binds, coords/visibility/stack, viewport layer order, added/removed *resolved test-target keys*. Path: `device / page / layer / [viewport] / type / identity`.

Not isolated today (desk tool should treat as first-class over time): add/remove of objects, identity/renames, system/driver/source/activity *bodies*, macro steps, rooms, activity membership, graphics *assets*, driver command set, hard-key slot map, cloned controllers.

---

## Build slices

1. **MVP:** two local files → sidecar extract → current Sentinel changelog lines (programming + layout + viewport stack) → box + CSV.
2. **Next:** add/remove of buttons and identity (tag/text/rename).
3. **Then:** System Events / Macros / Drivers (bodies, not just target keys).
4. **Then:** Rooms, Activities membership, Sources, Graphics assets, viewports as first-class add/remove.

---

## Out of scope

- Remote upload, accounts, project DB, technician tokens
- Generating technician HTML or commissioning PASS/FAIL
- Replacing Sentinel File-tab history
- In-browser extract rewrite (unless sidecar is later rejected)
- Clean-slate Apex parser
