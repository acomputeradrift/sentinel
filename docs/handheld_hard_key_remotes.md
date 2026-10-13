# Handheld Remotes with Hard Keys — Photo Overlay Standard

Status: approved method (2026-10-13). First remote: **T2x**.

Standard way to turn a photo of an RTI handheld remote into a clickable hard-key overlay, and how that overlay sits beside the touchscreen in the testing screen. Use this for every new remote photo.

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
| T2x | `remote_trace/remote.png` (trace only) | 48 (incl. 4 wrap-around keys, 4-way d-pad + OK; joystick = 5 targets → 52 slots) | Locked 2026-10-13: slot map, Apple TV (RV) labels, black frame, `#363739` fill, no photo in the strip. |

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
| Label | 12px white (`--sentinel-hard-button-font-size`), overflow hidden |
| State trim | Untested: width `0`, color transparent |
| Shape | Traced rect (6px corners), wrap-around path, d-pad wedge, or round split |

**Which layer.** Use the Hard Keys copy for the page on screen (`SharedLayers` where `ProductId` matches, `IsKeypadLayer = 1`, `Name = 'Hard Keys'`). The T2x mockup is Apple TV (RV): `SharedLayerId` 2058. Other copies in the same file differ. Source Select (2060) uses Exit, Play, Pause, Skip Back, Power On, and Prev where 2058 uses Back, Play/Pause, Replay, a blank tag, and Back.

**Label.** Same rule as `_button_identity_label`: Apex `Text` if it is set, otherwise `ButtonTagName`. On these T2x hard keys `Text` is empty, so the label is `ButtonTagName`. Slot 171 has no tag on layer 2058, so that button is blank.

**Too small to label.** Split a multi-target key inside its traced shape (T2x center knob: one circle, five slots, same wedge split as the d-pad — Up / Right / Down / Left plus a center Click). If the 12px label does not fit, leave the target unlabeled. A click still reports the identity.

**Click.** Log `Label · ButtonLeft` (example: `Back · 128`). The tooltip carries the same string.

**Layout.** Do not change the usable-space contract in section 2.

**Frame (locked 2026-10-13).** The testing strip does not show the photo. The photo is only the trace source (`remote.png`, `index.html`). The strip is a **3px black** frame filled with **`#363739`**. Put that grey on the frame element. A scaled inner layer on a different background leaves a white line inside the border.

Reference: `remote_trace/mockup.html`.

---

## Open items (not yet decided)

1. T2x is not in `src/sentinel/generation/hard_keys/registry.py` (only T4x / ISR-2 / ISR-4). `ProductId` (70) and slot map are known. Still needed: a renderer that draws the black frame, `#363739` fill, and traced shapes. The photo stays the trace source.
2. Where the photo + trace data live in the repo (`Assets/Hard Keys/` vs `src/sentinel/ui/testing/hard_keys/`) once this moves out of the scratch folder.
