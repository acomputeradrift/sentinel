# Hard Keys Working Notes

Status: draft working document for investigation/discovery.  
Scope: define layout behavior for RTI remotes with touchscreen + hard keys before implementation.

## Current Agreed Layout Model -> C:\Development\Sentinel\Assets\Hard Keys\Hard Key Remote Spacing Layout.png

This captures the current understanding from the reference screenshot and discussion.

- `rtiUsableCanvas` is the full blue-bounded area.
- A standard `20px` inset creates the red "usable content" box.
- The red box is split with 4 equal vertical guides (yellow) to establish alignment.
- For hard-key remotes, content is treated as two centered zones inside that red box:
  - **Touchscreen zone** centered in the left-side portion (targeted around the 25% region).
  - **Hard-keys zone** centered in the right-side portion (targeted around the 75% region).
- Green dotted rectangles are estimated placement guides for those two centered zones.
- Devices that are screen-only (for example iPhone, iPad, KA11) stay as single-screen behavior and do not use this split model.

## Hard-Key Data Source (Apex Extraction Summary)

Hard keys are already available from Apex project files and should be treated as source-of-truth data.

### 1) Open Apex Project

- Open `.apex` as a SQLite database (`SQLite format 3`).

### 2) Identify the Target Device/Remote

- Use `Devices` + `RTIDeviceData` to determine target remote identity:
  - `DeviceId`
  - `ProductId`
  - `RTIAddress`

### 3) Locate Hard-Key Layers

- Query `SharedLayers` with:
  - `ProductId = <target ProductId>`
  - `IsKeypadLayer = 1`
  - layer name like `Hard Keys`
- These are layer copies that hold hard-key rows.

### 4) Pull Hard-Key Rows

- Query `RTIDeviceButtonData` joined to `ButtonTagNames` on `ButtonTagId`.
- Filter by selected `SharedLayerId`.
- Return at least:
  - `ButtonLeft`
  - `ButtonId`
  - `ButtonTagId`
  - `ButtonTagName`
- Optionally include:
  - `FrameNumber`
  - `ButtonTop`
  - `ButtonOrder`

### 5) Keep Physical Hard-Key Style Rows

- Keep only rows where:
  - `ButtonWidth = 0`
  - `ButtonHeight = 0`
- Sort by:
  1. `FrameNumber`
  2. `ButtonTop`
  3. `ButtonLeft`
  4. `ButtonOrder`

### 6) Map Physical Slots

- Use `ButtonLeft` as physical slot index.
- For T4x-style strips, values are typically a stable increasing run (for example `128..147`).
- Each distinct `ButtonLeft` maps to one physical button position.

### 7) Multi-Copy Layer Caveat

- A single file can contain multiple `Hard Keys` layer copies.
- Run extraction per `SharedLayerId`.
- Treat the active template's chosen hard-key layer as canonical for slot assignments.
- Do not assume slot assignments are identical across copies.

## Open Questions to Resolve Before Coding

1. Canonical layer selection: exact rule for "active template layer" selection when multiple hard-key copies exist.
2. Layout contract: exact percent split and centering math to use at runtime (guide intent is clear; final formula still to be locked).
3. Slot-to-UI mapping: expected normalization for different remote families where `ButtonLeft` ranges differ.
4. Frame behavior: how to handle frame-specific hard-key rows when multiple frames are present.
5. Fallback behavior: what to render when hard-key data is missing, partial, or inconsistent.

## Approved Remote Inputs (Initial 3 Models)

Initial implementation scope for hard-key remotes:

- `T4x`
- `ISR-2`
- `ISR-4`

Each remote has two input artifacts:

1. A remote-specific hard-key **layout template** (`.html`)
2. A remote-specific hard-key **slot ID map** (`Hard Key IDs.png`) that maps physical positions to `ButtonLeft` values

Together with Apex extraction:

- Apex rows provide key identity and action data (`ButtonId`, `ButtonTagId`, `ButtonTagName`, etc.).
- `ButtonLeft` acts as the physical slot key.
- The ID map defines which `ButtonLeft` value belongs to each visual slot.
- The HTML defines the rendered geometry for those slots.

### File Paths (Source Inputs)

Layout templates:

- `Assets/Hard Keys/T4x Hard Keys.html`
- `Assets/Hard Keys/ISR-2 Hard Keys.html`
- `Assets/Hard Keys/ISR-4 Hard Keys.html`

Slot ID maps:

- `Assets/Hard Keys/T4x Hard Key IDs.png`
- `Assets/Hard Keys/ISR-2 Hard Key IDs.png`
- `Assets/Hard Keys/ISR-4 Hard Key IDs.png`

Additional visual reference:

- `Assets/Hard Keys/Hard Key Remote Spacing Layout.png`

### Known `ButtonLeft` Slot Ranges from Provided Maps

- `T4x`: `128..147`
- `ISR-4`: `128..149`
- `ISR-2`: `128..161`

### Working Mapping Contract (Approved So Far)

For each supported remote model:

1. Determine canonical hard-key layer (`SharedLayerId`) from Apex for that remote.
2. Extract hard-key-style rows (`ButtonWidth=0`, `ButtonHeight=0`) from that layer.
3. Sort rows by the agreed stable order (`FrameNumber`, `ButtonTop`, `ButtonLeft`, `ButtonOrder`).
4. Match each row to a visual slot using `ButtonLeft`.
5. Render slot geometry from that remote's hard-key HTML layout template.
6. Place this hard-key region in the right-side split area of the red usable box, while touchscreen renders in the left-side split area.

## Proposed First Implementation Goal (User-Directed, Not Yet Executed)

Target: implement `T4x` first.

Goal statement:

1. Generate a split layout for T4x with:
   - touchscreen rendered in the left area
   - hard keys rendered in the right area
2. For both regions, maximize rendered height to the red usable area (`rtiUsableCanvas` minus standard `20px` buffer), while preserving aspect ratio.
3. Draw a black outline around the hard-key region like the touchscreen container.
4. Use the T4x hard-key HTML as the source of hard-key geometry (do not use Apex button dimensions/coordinates for drawing hard keys).
5. Use `ButtonLeft` from Apex hard-key rows to map each extracted hard-key button to the correct template slot from the T4x ID map.
6. Assign testing targets and behavior so hard-key buttons function like touchscreen buttons with normal scope handling.

## Locked Implementation Rules (Phase 0 lock-in, evidence-backed)

Evidence sources (all under `devtools/`):
- `probe_hk_test_apex.out.json` (from `Assets/test with t4x isr-2 isr-4.apex`).
- `probe_hk_layer_detail.run.txt` (T4x SharedLayerId=1574 in Dash OS, ISR-4 SharedLayerId=388 in Rockett).
- `probe_hk_*.out.json` for all other accessible apex files in `Assets/`.

### 1. Device identification rule (locked)

`productModel` is resolved exclusively from `RTIDeviceData.ProductId`:

| ProductId | productModel | Devices.Name observed |
| --- | --- | --- |
| 102 | `t4x`  | `T4x`   |
| 110 | `isr2` | `ISR-2` |
| 111 | `isr4` | `ISR-4` |

Any other `ProductId` (or missing/null) yields `productModel = None` and the device renders single-screen via the existing pipeline (KA11, T2x/T2i, RK3-V, KX2, RTiPanel, XP/CX, etc.). No name-substring fallback.

### 2. Canonical hard-key layer rule (locked)

A `SharedLayer` is a hard-key layer when `SharedLayers.IsKeypadLayer = 1 AND SharedLayers.Name = 'Hard Keys'`.

Hard-key data is emitted **per page**:

- During the existing per-page `Layers` iteration in `extractor_core.py`, when a layer's `SharedLayerId` references a hard-key SharedLayer for the device's `productModel`, that page's `hardKeyLayer` block is populated from that layer's rows.
- If a single page has multiple hard-key layers attached, all are recorded under `hardKeyLayer.layerCopies[]` ordered by `Layers.LayerOrder, Layers.LayerId`. The first entry is the page's canonical slot mapping for rendering.
- No global "pick one SharedLayer for the whole device" rule is needed.

### 3. Slot-mismatch and frame policy (locked)

Frame semantics (verified across T4x, ISR-2, ISR-4 in the test apex):

- `FrameNumber = 254` -> physical hard-key release frame (canonical slots, `ButtonLeft >= 128`).
- `FrameNumber = 252` -> gesture inputs (`Rotate Clockwise`, `Rotate Counterclockwise`, `Shake`) at `ButtonLeft 0..2`. Not physical buttons.

Physical hard-key filter: `ButtonWidth = 0 AND ButtonHeight = 0 AND FrameNumber = 254 AND ButtonLeft >= 128`. Sort by `FrameNumber, ButtonTop, ButtonLeft, ButtonOrder`.

Authoritative slot ranges (per registry, derived from the user-provided `*Hard Key IDs.png`):

- `t4x` : 128..147 (20 slots)
- `isr4`: 128..149 (22 slots)
- `isr2`: 128..161 (34 slots)

Apex rows present in the data but outside the registry slot range (e.g., ISR-4 dock 150..152, ISR-2 162..164 in the test apex) are recorded under `hardKeyLayer.unmappedSlots[]` with `reason = "outsideTemplateRange"`. They are not rendered and produce no test target on this branch.

Frame 252 gesture rows are recorded under `hardKeyLayer.gestures[]` (full button identity preserved) but are not rendered on the hard-key strip.

Empty-template-slot policy: any registry slot with no matching Apex row renders the template's geometry as an empty placeholder slot with no `.btn-wrap` and no test target.

### 4. Scope/target reuse (locked)

Hard-key buttons reuse the existing `_resolve_button` pipeline (`buttonIdentity`, `buttonUI`, `testTargets`, `apexScopeSource`, `stack`). They render with the standard `.btn-wrap` element and `data-meta` attribute, so `buildTargetPayload` and `postResultWs` in `render_core.py` produce the same `targetKey` shape as touchscreen buttons. `buttonUI.coordinates.{left,top,width,height}` is ignored for hard keys; template positions are used instead.

### 5. Split-layout math (locked)

The static-layout shell exposes `#rtiUsableCanvas`. The runtime applies `DEVICE_CANVAS_MARGIN = 20` on each side, producing the red usable box.

For hard-key models, the device canvas content swaps from a single `rti-device-canvas` to a flex row holding two children inside the red usable box:

```text
redW = canvasW - 2 * 20
redH = canvasH - 2 * 20
splitGap = 16
zoneW = (redW - splitGap) / 2
zoneH = redH

For each zone (left = touchscreen, right = hard keys):
  fittedScale = min(zoneW / designW, zoneH / designH)
  fittedW = designW * fittedScale
  fittedH = designH * fittedScale
  offsetX = (zoneW - fittedW) / 2  (centered horizontally in zone)
  offsetY = (zoneH - fittedH) / 2  (centered vertically in zone; usually 0 since maximizing height)
```

`designW`, `designH` per template (from each remote's `--frame-w / --frame-h`):

- `t4x` : 608 x 732
- `isr2`: 468 x 862
- `isr4`: 602 x 734

Touchscreen uses the device's existing portrait/landscape size for `designW/H`. The right zone has the same black ring (`box-shadow 0 0 0 ring-w ring-color`) as the touchscreen container. Devices with `productModel = None` (KA11, iPhone, iPad, etc.) keep the current single-screen layout unchanged.

## Change Log

- Initial draft created from user-approved layout interpretation and Apex extraction summary.
- Added approved initial remote set, six source input file paths, and the current mapping contract for HTML + `ButtonLeft` ID maps.
- Added user-directed first implementation goal for T4x and explicit unresolved questions required before coding.
- Phase 0 lock-in (this commit): evidence-backed answers to all five Open Clarifications appended above; ProductId mapping confirmed (t4x=102, isr2=110, isr4=111); frame 254 / 252 semantics locked; registry slot ranges locked; split-layout math locked.
