"""T2x traced hard-key geometry.

Source of truth for positions: the locked trace in ``docs/handheld_hard_key_remotes.md``
and the scratch mockup ``remote_trace/mockup.html``. Coordinates are source-image
pixels. The strip design size is the bounding box of every key plus a 4px pad.
The photo is not rendered.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

HK_TIGHT_PAD = 4
MARGIN = 20

# D-pad block and ring, source-image pixels (locked trace).
_CX0 = 827
_CY0 = 350
_RING = 95
_DPAD_R = 82
_OK_R = 33
_L0, _R0, _T0, _B0 = 664, 992, 240, 462

# name, x, y, w, h, slot. Slot None is the joystick disc (bbox only; five wedges).
_SOURCE_RECTS: tuple[tuple[str, int, int, int, int, int | None], ...] = (
    ("Top 1", 662, 32, 74, 38, 136),
    ("Top 2", 750, 32, 72, 38, 130),
    ("Top 3", 838, 32, 70, 38, 177),
    ("Top 4", 922, 32, 70, 38, 137),
    ("Green power", 678, 100, 86, 48, 171),
    ("Center knob", 790, 84, 76, 76, None),
    ("Red power", 892, 100, 86, 48, 145),
    ("PREV", 664, 183, 72, 35, 178),
    ("LIST", 750, 183, 70, 35, 172),
    ("BACK", 834, 183, 72, 35, 179),
    ("MUTE", 920, 183, 72, 35, 129),
    ("GUIDE", 664, 484, 70, 35, 142),
    ("MENU", 748, 484, 72, 35, 143),
    ("INFO", 834, 484, 72, 35, 144),
    ("EXIT", 920, 484, 72, 35, 128),
    ("Red", 664, 540, 70, 26, 173),
    ("Green", 748, 540, 72, 26, 174),
    ("Yellow", 834, 540, 72, 26, 175),
    ("Blue", 920, 540, 72, 26, 176),
    ("Play", 678, 602, 72, 44, 146),
    ("Pause", 754, 602, 72, 44, 147),
    ("Stop", 830, 602, 72, 44, 148),
    ("Record", 904, 602, 72, 44, 149),
    ("Skip back", 678, 662, 72, 44, 152),
    ("Skip fwd", 754, 662, 72, 44, 153),
    ("Rewind", 830, 662, 72, 44, 150),
    ("Fast fwd", 904, 662, 72, 44, 151),
    ("1", 664, 742, 98, 48, 154),
    ("2", 778, 742, 98, 48, 155),
    ("3", 890, 742, 100, 48, 156),
    ("4", 664, 806, 98, 48, 157),
    ("5", 778, 806, 98, 48, 158),
    ("6", 890, 806, 100, 48, 159),
    ("7", 664, 870, 98, 48, 160),
    ("8", 778, 870, 98, 48, 161),
    ("9", 890, 870, 100, 48, 162),
    ("-/", 664, 934, 98, 48, 164),
    ("0", 778, 934, 98, 48, 163),
    ("ENTER", 890, 934, 100, 48, 165),
)

# D-pad / wrap-around photo name → ButtonLeft. Joystick wedges are separate.
_DPAD_SLOTS: dict[str, int] = {
    "+CH": 140,
    "VOL +": 138,
    "-CH": 141,
    "VOL -": 139,
    "Up": 131,
    "Right": 133,
    "Down": 134,
    "Left": 132,
    "OK": 135,
}

_JOYSTICK_SLOTS: tuple[tuple[str, int, float, float], ...] = (
    ("Joystick Up", 166, -135, -45),
    ("Joystick Right", 170, -45, 45),
    ("Joystick Down", 168, 45, 135),
    ("Joystick Left", 169, 135, 225),
)


def _crop_origin_and_size() -> tuple[int, int, int, int]:
    xs = [row[1] for row in _SOURCE_RECTS]
    ys = [row[2] for row in _SOURCE_RECTS]
    xe = [row[1] + row[3] for row in _SOURCE_RECTS]
    ye = [row[2] + row[4] for row in _SOURCE_RECTS]
    min_x = min(xs + [_L0]) - HK_TIGHT_PAD
    min_y = min(ys + [_T0]) - HK_TIGHT_PAD
    max_x = max(xe + [_R0]) + HK_TIGHT_PAD
    max_y = max(ye + [_B0]) + HK_TIGHT_PAD
    return min_x, min_y, max_x - min_x, max_y - min_y


CROP_X, CROP_Y, CROP_W, CROP_H = _crop_origin_and_size()
CROP_ORIGIN = (CROP_X, CROP_Y)
DESIGN_SIZE = (CROP_W, CROP_H)

_CX = _CX0 - CROP_X
_CY = _CY0 - CROP_Y
_L = _L0 - CROP_X
_R = _R0 - CROP_X
_T = _T0 - CROP_Y
_B = _B0 - CROP_Y


def _n(value: float) -> str:
    rounded = round(float(value), 1)
    if abs(rounded - round(rounded)) < 1e-9:
        return str(int(round(rounded)))
    return f"{rounded:.1f}"


def _pt(cx: float, cy: float, radius: float, deg: float) -> str:
    angle = math.radians(deg)
    return f"{_n(cx + radius * math.cos(angle))},{_n(cy + radius * math.sin(angle))}"


def _wedge(cx: float, cy: float, outer: float, inner: float, start: float, end: float) -> str:
    return (
        f"M{_pt(cx, cy, outer, start)} A{_n(outer)},{_n(outer)} 0 0 1 {_pt(cx, cy, outer, end)} "
        f"L{_pt(cx, cy, inner, end)} A{_n(inner)},{_n(inner)} 0 0 0 {_pt(cx, cy, inner, start)} Z"
    )


def _circle(cx: float, cy: float, radius: float) -> str:
    return (
        f"M{_n(cx - radius)},{_n(cy)} A{_n(radius)},{_n(radius)} 0 1 0 {_n(cx + radius)},{_n(cy)} "
        f"A{_n(radius)},{_n(radius)} 0 1 0 {_n(cx - radius)},{_n(cy)} Z"
    )


@dataclass(frozen=True)
class T2xRect:
    slot: int
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class T2xShape:
    slot: int
    d: str
    label_box: tuple[float, float, float, float] | None


def _rects() -> tuple[T2xRect, ...]:
    out: list[T2xRect] = []
    for _name, x, y, w, h, slot in _SOURCE_RECTS:
        if slot is None:
            continue
        out.append(T2xRect(slot=slot, x=x - CROP_X, y=y - CROP_Y, w=w, h=h))
    return tuple(out)


def _wedge_box(start: float, end: float, cx: float, cy: float) -> tuple[float, float, float, float]:
    mid = math.radians((start + end) / 2)
    radius = (_DPAD_R + _OK_R) / 2
    x = cx + radius * math.cos(mid)
    y = cy + radius * math.sin(mid)
    return (x - 26, y - 14, 52, 28)


def _shapes() -> tuple[T2xShape, ...]:
    dpad: list[tuple[str, str, tuple[float, float, float, float] | None]] = [
        ("+CH", f"M{_n(_L)},{_n(_T)} H{_n(_CX)} V{_n(_CY - _RING)} A{_n(_RING)},{_n(_RING)} 0 0 0 {_n(_CX - _RING)},{_n(_CY)} H{_n(_L)} Z", (_L, _T, (_CX - _RING) - _L, _CY - _T)),
        ("VOL +", f"M{_n(_CX)},{_n(_T)} H{_n(_R)} V{_n(_CY)} H{_n(_CX + _RING)} A{_n(_RING)},{_n(_RING)} 0 0 0 {_n(_CX)},{_n(_CY - _RING)} Z", (_CX + _RING, _T, _R - (_CX + _RING), _CY - _T)),
        ("-CH", f"M{_n(_L)},{_n(_CY)} H{_n(_CX - _RING)} A{_n(_RING)},{_n(_RING)} 0 0 0 {_n(_CX)},{_n(_CY + _RING)} V{_n(_B)} H{_n(_L)} Z", (_L, _CY, (_CX - _RING) - _L, _B - _CY)),
        ("VOL -", f"M{_n(_CX)},{_n(_CY + _RING)} A{_n(_RING)},{_n(_RING)} 0 0 0 {_n(_CX + _RING)},{_n(_CY)} H{_n(_R)} V{_n(_B)} H{_n(_CX)} Z", (_CX + _RING, _CY, _R - (_CX + _RING), _B - _CY)),
        ("Up", _wedge(_CX, _CY, _DPAD_R, _OK_R, -135, -45), _wedge_box(-135, -45, _CX, _CY)),
        ("Right", _wedge(_CX, _CY, _DPAD_R, _OK_R, -45, 45), _wedge_box(-45, 45, _CX, _CY)),
        ("Down", _wedge(_CX, _CY, _DPAD_R, _OK_R, 45, 135), _wedge_box(45, 135, _CX, _CY)),
        ("Left", _wedge(_CX, _CY, _DPAD_R, _OK_R, 135, 225), _wedge_box(135, 225, _CX, _CY)),
        ("OK", _circle(_CX, _CY, _OK_R), (_CX - _OK_R, _CY - _OK_R, _OK_R * 2, _OK_R * 2)),
    ]
    out = [
        T2xShape(slot=_DPAD_SLOTS[name], d=path, label_box=box)
        for name, path, box in dpad
    ]
    knob = next(row for row in _SOURCE_RECTS if row[0] == "Center knob")
    _name, kx, ky, kw, kh, _slot = knob
    jx = kx + kw / 2 - CROP_X
    jy = ky + kh / 2 - CROP_Y
    jr = kw / 2
    jc = round((_OK_R / _DPAD_R) * jr)
    for label, slot, start, end in _JOYSTICK_SLOTS:
        del label
        out.append(T2xShape(slot=slot, d=_wedge(jx, jy, jr, jc, start, end), label_box=None))
    out.append(T2xShape(slot=167, d=_circle(jx, jy, jc), label_box=None))
    return tuple(out)


RECTS: tuple[T2xRect, ...] = _rects()
SHAPES: tuple[T2xShape, ...] = _shapes()


def layout_like_mockup(
    usable_w: float,
    usable_h: float,
    touch_w: float,
    touch_h: float,
    crop_w: float | None = None,
    crop_h: float | None = None,
) -> dict[str, dict[str, float]]:
    """Same placement as ``remote_trace/mockup.html`` ``hardKeySplit``.

    Touchscreen contained in half the padded usable box, centered on the 25% line.
    Strip contained the same way, width capped at the touchscreen width, centered
    on the 75% line. Strip aspect is the traced crop.
    """
    cw = float(CROP_W if crop_w is None else crop_w)
    ch = float(CROP_H if crop_h is None else crop_h)
    uw = float(usable_w)
    uh = float(usable_h)
    tw0 = float(touch_w)
    th0 = float(touch_h)
    half_w = max(1.0, (uw - 2.0 * MARGIN) / 2.0)
    fit_h = max(1.0, uh - 2.0 * MARGIN)

    def _contain(iw: float, ih: float, fw: float, fh: float) -> float:
        if iw <= 0 or ih <= 0 or fw <= 0 or fh <= 0:
            return 0.0
        return max(0.0, min(fw / iw, fh / ih))

    ts = _contain(tw0, th0, half_w, fit_h)
    touch_w_px = tw0 * ts
    touch_h_px = th0 * ts
    strip_w0 = th0 * cw / ch if ch else 0.0
    ss = _contain(strip_w0, th0, half_w, fit_h)
    if strip_w0 > 0:
        ss = min(ss, touch_w_px / strip_w0)
    strip_h = th0 * ss
    strip_w = strip_h * cw / ch if ch else 0.0
    return {
        "touch": {
            "left": 0.25 * uw - touch_w_px / 2.0,
            "top": max(0.0, (uh - touch_h_px) / 2.0),
            "width": touch_w_px,
            "height": touch_h_px,
        },
        "strip": {
            "left": 0.75 * uw - strip_w / 2.0,
            "top": max(0.0, (uh - strip_h) / 2.0),
            "width": strip_w,
            "height": strip_h,
        },
    }
