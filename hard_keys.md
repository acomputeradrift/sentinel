# Hard Keys Working Notes

Status: draft working document for investigation/discovery.  
Scope: define layout behavior for RTI remotes with touchscreen + hard keys before implementation.

## Current Agreed Layout Model -> \\mac\Home\Desktop\Development\Sentinel\Assets\Hard Keys\Hard Key Remote Spacing Layout.png

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

## Open Clarifications Required Before Implementation

These items are currently needed to avoid inference/guessing during implementation.

1. Device identification contract:
   - Exact runtime rule for "this device is T4x" (for example explicit `ProductId` mapping).

2. Canonical hard-key layer selection:
   - Exact rule when multiple `Hard Keys` layer copies exist for a device (`SharedLayerId` choice logic).

3. Slot mismatch policy:
   - Required behavior if Apex returns a `ButtonLeft` that has no slot in the T4x map.
   - Required behavior if a template slot has no matching Apex row.

4. Scope resolution confirmation:
   - Confirm hard-key scope/target resolution must use the exact same logic/path as touchscreen targets.

5. Final split-layout math lock:
   - Exact formulas for left/right region sizing and centering inside the red usable area.

## Change Log

- Initial draft created from user-approved layout interpretation and Apex extraction summary.
- Added approved initial remote set, six source input file paths, and the current mapping contract for HTML + `ButtonLeft` ID maps.
- Added user-directed first implementation goal for T4x and explicit unresolved questions required before coding.
