# Handheld Remotes with Hard Keys — Photo Overlay Standard

Status: approved method (2026-10-13). Traced strips in `src/`: **T2x**, **ISR-2**, **ISR-4**, **T4x**. **T2i** (ProductId 75) uses the T2x strip.

Standard way to turn a photo of an RTI handheld remote into a clickable hard-key overlay, and how that overlay sits beside the touchscreen in the testing screen. Use this for every new remote photo.

A code deploy does not redraw a remote already generated. The strip on screen is the last upload of that project. Upload that project again to rebuild it.

Related: `hard_keys.md` (Apex hard-key extraction, `ButtonLeft` slots, T4x / ISR-2 / ISR-4 HTML templates).

---

## 1. Trace the buttons on the photo

Input: one photo/screenshot of the remote's hard keys.

1. Keep the photo as the background at its native pixel size. All button coordinates are in **source-image pixels**.
2. Outline every physical button in **red** (`2px solid red`) as a real `<button>` (or SVG shape) so each one is clickable.
3. Number every button in reading order (top-to-bottom, left-to-right) and give it a name. Clicking shows `#N Name`.
4. Shapes:
   - Ordinary keys: rectangle (`left, top, width, height`), rounded corners.
   - Round keys: same rectangle with `border-radius: 50%`.
   - **Wrap-around keys** (keys that curve around a d-pad, e.g. T2x CH+/CH-/VOL+/VOL-): SVG path = rectangle quadrant minus a circular cut-out (radius = outer edge of the d-pad ring).
   - **D-pad**: SVG ring split on the diagonals into Up / Right / Down / Left wedges (outer radius = inside of the ring, inner radius = OK button), plus a circular **OK** in the center.
5. Serve locally and review with Jamie. Iterate one fix at a time until Jamie confirms every outline.

Reference implementation (T2x): `remote_trace/index.html` (scratch folder next to the repo).

### Button fill vs casing (Jamie, 2026-10-14)

Do this before drawing any outline. One remote at a time. Worked example is **ISR-2** (outlines locked 2026-10-14).

On the photo, separate three things:

| What you see | What it is |
|---|---|
| Darker grey | The button. Trace this shape, including its curves. |
| Lighter grey | The casing. Not a button. |
| White or blue, other than icons | The surround of the d-pad, and of Back and Mute on ISR-2 and ISR-4. Not the button. Leave it clear. |

**OK is the exception.** The d-pad OK disc is not the darker button fill. Trace it as its own circle.

Measure the darker face first, then replace the jagged pixel edge with the real geometry: straight lines and circular arcs. Do not leave the raw trace as the outline, and do not substitute a flat rectangle when the face is sloped or curved.

ISR-2 photo `remote_trace/isr2.png` (534×998). Darker fill on this file is luminance under 40. Casing sits around 52–64. White surround is about 200 and up. Locked scratch trace: `remote_trace/isr2.html` v7.

- **Keypad and transport.** Left column mirrors the right across x=264.5. Each side key is a rounded trapezoid: vertical sides, top and bottom parallel, sloping down toward the center by 1/12, corner radius 12, height 57. The middle column is a straight rounded rectangle, not a mirror of the sides. Row tops at the left edge: 408, 486, 564, then a gap, 666, 743, 821, 899.
- **Home, More, channel, and volume have no corner radius.** Same rule as the T2x wrap keys: a corner where two edges meet is square. Curves are only the measured edges (the bezel arc and the outside of this ring).
- **Home and More.** The black panel above the grey bezel, split at x=264.5. Top and side edges are straight. Bottom edge is the bezel arc (circle center (264.5, 1743.7), radius 1643.6).
- **Cluster.** D-pad, channel, volume, Back, and Mute are mirrored both ways, then placed together. Center (264.2, 257.5). White ring outer radius 131.2. D-pad wedges stop at the inner edge, radius 116. OK radius 39. Pill half-height 40.5, so channel + stops at y=217 and channel −, its flip, stops at y=298.
- **Plus, Minus, Vol +, Vol −.** Plus traces the black face: bezel arc to the center line, straight drop onto the ring, ring down to the pill, straight edge to the side. Minus is Plus flipped through the cluster center. Vol + is the left-right mirror of Plus. Vol − is the mirror of Minus. No corner radius.
- **Back and Mute.** Rounded rectangle on the dark interior of the white pill, not the white stroke. Back is (54, 236.5, 74×42), corner radius 11. Mute is the mirror across the cluster center.
- **D-pad.** Wedges use the inside of the white ring at the cluster center (outer radius 116, OK radius 39). Jamie locked this treatment on ISR-2. ISR-4 uses the same cluster. T4x in `src/` uses the v2 scratch trace (`t4x.html`), not this darker-fill outline.

ISR-4 photo `remote_trace/isr4.png` (514×638). Locked scratch trace: `remote_trace/isr4.html` v5 (2026-10-14). These buttons are the ISR-2 outlines with the numeric keypad left off (1–9, Dash, 0, Backspace). Scale the locked ISR-2 paths by 125.7/131.2 about the ISR-2 cluster center (264.2, 257.5) onto (255, 248). That puts the white ring at outer radius 125.7. D-pad wedges and OK use the ISR-2 radii through that same scale. Order: Home, More, Plus, Vol +, Back, Mute, Minus, Vol −, Up, Right, Down, Left, OK, Skip back, Play, Skip fwd, Replay, Pause, Info, Power, Menu, Exit.

Serve the scratch folder with `python3 -m http.server 8765` (port 8765 may already be in use). ISR-2 and ISR-4 outlines are locked. Their strips, and the T4x v2 trace, are in `src/` (`isr2_trace.py`, `isr4_trace.py`, `t4x_trace.py`).

---

## 2. Place the remote beside the touchscreen (usable-space contract)

The photo overlay follows the same layout rules as the existing hard-key remotes. Do not invent new spacing.

| Rule | Source |
|---|---|
| Usable canvas = window minus header (50px), footer (40px), and **58px** each side (collapsed panel width). Expanded 300px panels overlay it. | `project_device_static_layout.css` (`.rtiUsableCanvas`), shell `alignRuntimeControlsToShell` |
| 20px margin inside the usable canvas; nothing renders outside that box. | `DEVICE_CANVAS_MARGIN`, `test_isr2_hard_key_layout_fits_inside_rti_canvas` |
| Touchscreen: contain in half of the padded width × padded height, centered on the **25%** line. | `_layout_hard_key_touch_column` |
| Remote strip: contain in half of the padded width × padded height, **width capped at the touchscreen width**, centered on the **75%** line. | `_layout_hard_key_strip_column`, `_layout_hard_key_split` |
| Strip design size = bounding box of all traced buttons + **4px** pad (tight cluster). | `applyHkTightClusterLayout` (`HK_TIGHT_PAD`) |
| Strip rim: **3px** black. Approved interior fill is **`#363739`**, painted on the frame itself. The near-white surround (`--sentinel-hk-remote-surround-bg`) leaves a white seam beside a scaled child. Touchscreen keeps its ring. | `sentinel_device_theme.css`; T2x mockup locked 2026-10-13 |

Tall remotes (like the T2x) are height-limited: the strip fills the usable height and ends up narrower than the touchscreen.

Reference mockup: `remote_trace/mockup.html` (toggles for usable-space guides and collapsed panels).

---

## 3. Remote register

| Remote | Photo | Buttons traced | Status |
|---|---|---|---|
| T2x | `remote_trace/remote.png` (trace only) | 48 (incl. 4 wrap-around keys, 4-way d-pad + OK; joystick = 5 targets → 52 slots) | Locked 2026-10-13: slot map, Apple TV (RV) labels, black frame, `#363739` fill, no photo in the strip. In `src/` as `t2x_trace.py`. ProductId 70. |
| T2i | same trace as T2x | same 52 slots, ButtonLeft 128..179 | ProductId 75. Same model as T2x (`product_model_for_product_id` returns `t2x`). No separate trace file. The T2x `HardKeyModel.product_id` stays 70. |
| ISR-2 | `remote_trace/isr2.png` | 34 | Locked outlines `remote_trace/isr2.html` v7. Strip in `src/` as `isr2_trace.py` (crop 521×971). Slots are the approved `ISR2_SLOT_BY_DATA_LABEL` map. |
| ISR-4 | `remote_trace/isr4.png` | 22 | Locked outlines `remote_trace/isr4.html` v5. Strip in `src/` as `isr4_trace.py` (crop 500×610). Slots are the approved `ISR4_SLOT_BY_DATA_LABEL` map. |
| T4x | `remote_trace/t4x.png` | 20 | Scratch trace `remote_trace/t4x.html` v2. Strip in `src/` as `t4x_trace.py` (crop 551×679). Slots follow `_T4X_SLOT_DOM_ORDER`. |

### T2x trace (source-image px, photo 1024×1005)

1. Top row 1–4 · 5 Green power · 6 Center knob (round) · 7 Red power
2. 8 PREV · 9 LIST · 10 BACK · 11 MUTE
3. 12 +CH · 13 VOL+ · 14 −CH · 15 VOL− (wrap-around) · 16 Up · 17 Right · 18 Down · 19 Left · 20 OK
   - D-pad center `(827, 350)`, wrap cut-out radius 95, d-pad outer radius 82, OK radius 33, block `664..992 × 240..462`
4. 21 GUIDE · 22 MENU · 23 INFO · 24 EXIT
5. 25 Red · 26 Green · 27 Yellow · 28 Blue
6. 29 Play · 30 Pause · 31 Stop · 32 Record · 33 Skip back · 34 Skip fwd · 35 Rewind · 36 Fast fwd
7. 37–48 keypad `1 2 3 / 4 5 6 / 7 8 9 / -/. 0 ENTER`

Exact rectangles live in the `BUTTONS` array in `remote_trace/index.html`.

### T2x slot map (approved 2026-10-13)

Source: `1790 High Rd (Simple v30).apex`. T2x `ProductId = 70`. Hard-key layer: `SharedLayers` `ProductId = 70`, `IsKeypadLayer = 1`, `Name = 'Hard Keys'` (4 copies in this file). Physical slots: `FrameNumber = 254`, `ButtonLeft 128..179` (52 slots). `FrameNumber = 252` rows (`ButtonLeft 0..2`: Rotate Clockwise / Counterclockwise / Shake) are gestures, not keys.

Method: photo key labels matched to Apex `ButtonTagName` across all layer copies; Jamie confirmed names and the joystick split.

| Photo # | Key on photo | `ButtonLeft` | Key name |
|---|---|---|---|
| 1 | Top 1 | 136 | Softkey 1 |
| 2 | Top 2 | 130 | Softkey 2 |
| 3 | Top 3 | 177 | Softkey 3 |
| 4 | Top 4 | 137 | Softkey 4 |
| 5 | Green power | 171 | Power On |
| 6 | Center knob (joystick, 5 targets) | 166 / 167 / 168 / 169 / 170 | Joystick Up / Click / Down / Left / Right |
| 7 | Red power | 145 | Power Off |
| 8 | PREV | 178 | Prev |
| 9 | LIST | 172 | List |
| 10 | BACK | 179 | Back |
| 11 | MUTE | 129 | Mute |
| 12 | +CH | 140 | Channel Up |
| 13 | VOL+ | 138 | Volume Up |
| 14 | −CH | 141 | Channel Down |
| 15 | VOL− | 139 | Volume Down |
| 16 | Up | 131 | Up |
| 17 | Right | 133 | Right |
| 18 | Down | 134 | Down |
| 19 | Left | 132 | Left |
| 20 | OK | 135 | OK |
| 21 | GUIDE | 142 | Guide |
| 22 | MENU | 143 | Menu |
| 23 | INFO | 144 | Info |
| 24 | EXIT | 128 | Exit |
| 25 | Red | 173 | Red |
| 26 | Green | 174 | Green |
| 27 | Yellow | 175 | Yellow |
| 28 | Blue | 176 | Blue |
| 29 | Play | 146 | Play |
| 30 | Pause | 147 | Pause |
| 31 | Stop | 148 | Stop |
| 32 | Record | 149 | Record |
| 33 | Skip back | 152 | Skip Back |
| 34 | Skip fwd | 153 | Skip Forward |
| 35 | Rewind | 150 | Scan Back |
| 36 | Fast fwd | 151 | Scan Forward |
| 37–45 | 1–9 | 154–162 | 1–9 |
| 46 | -/. | 164 | Dash |
| 47 | 0 | 163 | 0 |
| 48 | ENTER | 165 | Enter |

All 52 slots `128..179` are used exactly once. Key names above are physical-key names; per-page `ButtonTagName` text in Apex is the programmer's label and can differ by layer copy (e.g. slot 128 is "Back" on some copies, "Exit" on others).

---

## 4. Paint the test targets on the trace

After the trace, usable-space mockup, and slot map are approved, replace the red outlines with Sentinel hard-key test buttons. Do this in the scratch mockup first. Do not edit `src/` until a separate scope is approved.

Chrome comes from `src/sentinel/ui/testing/sentinel_device_theme.css` (`.btn-wrap`, `.hk-btn-wrap`, `.test-btn`) and `render_core._render_hard_key_button`. Keep the traced geometry. Do not restyle the shapes as the 32px device-button radius.

| Piece | Rule |
|---|---|
| Fill | `--sentinel-fill-hard-button` (`#2c6fb7`) |
| Border | 1px inset `--sentinel-device-button-border-color` (`#154665`) |
| Label | 12px white (`--sentinel-hard-button-font-size`), overflow hidden. Shape names sit above the shape fill |
| State trim | Untested: width `0`, color transparent |
| Shape | Traced rect (6px corners), wrap-around path, d-pad wedge, or round split |

**Which layer.** Use the Hard Keys copy for the page on screen (`SharedLayers` where `ProductId` matches, `IsKeypadLayer = 1`, `Name = 'Hard Keys'`). The T2x mockup is Apple TV (RV): `SharedLayerId` 2058. Other copies in the same file differ. Source Select (2060) uses Exit, Play, Pause, Skip Back, Power On, and Prev where 2058 uses Back, Play/Pause, Replay, a blank tag, and Back.

**Tag scope.** The hard-key layer `SourceId` matches the page source. That source is the effective source for the tag.

Variable rows count only when their `RoomId` and `DeviceId` fit that source. Global counts on every page. A source row counts only on its own source. A Sonos variable on Play does not paint the Switch or Xbox page.

Tag macros use one winner, `_winning_tag_macro_id`: Room, then Source, then Global. A Room row is `RoomId` of that room and `DeviceId` -1, and it runs on every source in the room. A Source row is `DeviceId` equal to the effective source, with `RoomId` of that room or 0. Global is `RoomId` 0 and `DeviceId` -1, and it runs only when no Room or Source row applies. The command step’s device is the driver the macro addresses, not the scope. Controller level is not selected. `(RoomId > 0, DeviceId >= 0)` is Source, not Controller. Redirected volume and mute still add System Macro from `audio_scope`; a winning tag macro can also add Macro Step.

**Label.** Same rule as `_button_identity_label`: Apex `Text` if it is set, otherwise `ButtonTagName`. On these T2x hard keys `Text` is empty, so the label is `ButtonTagName`. Slot 171 has no tag on layer 2058, so that button is blank. Volume, channel, d-pad, and OK names are a separate `.hk-traced-label` with `z-index: 3`, above the shape layer (`z-index: 2`), so the fill does not cover the words.

**Too small to label.** The joystick wedges (Up / Right / Down / Left plus center Click) have no label box. A click still puts the tag in the dialog title.

**Click.** Log `Label · ButtonLeft` (example: `Back · 128`). The tooltip carries the same string.

**Layout.** Do not change the usable-space contract in section 2.

**Frame (locked 2026-10-13).** The testing strip does not show the photo. The photo is only the trace source (`remote.png`, `index.html`). The strip is a **3px black** frame filled with **`#363739`**. Put that grey on the frame element. A scaled inner layer on a different background leaves a white line inside the border.

Reference: `remote_trace/mockup.html`.

---

## Open items (not yet decided)

1. Done in `src/`: `ProductId` 70 is `t2x` in `registry.py`. `ProductId` 75 (T2i) resolves to that same `t2x` model. The strip is drawn from `t2x_trace.py` (crop 338×958, 3px black frame, `#363739` fill, traced shapes). Labels come from the hard-key layer on screen. The photo stays the trace source, outside the repo.
2. Where the photo + trace data live in the repo (`Assets/Hard Keys/` vs `src/sentinel/ui/testing/hard_keys/`) once this moves out of the scratch folder.
3. Done in `src/`: ISR-2, ISR-4, and T4x use the same traced strip as T2x. Crops: ISR-2 521×971, ISR-4 500×610, T4x 551×679. Slot numbers are the approved registry maps. T4x geometry is `t4x.html` v2, not a darker-fill outline.
