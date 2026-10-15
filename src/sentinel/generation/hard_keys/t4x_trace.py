"""T4x traced hard-key geometry.

Source of truth for positions: scratch mockup ``remote_trace/t4x.html`` (v2).
Stage is 608×734. Coordinates are source-image pixels. The strip design size
is the bounding box of every rectangle, the wrap block, and the d-pad extents,
plus a 4px pad. The photo is not rendered. There is no joystick.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

HK_TIGHT_PAD = 4

# Wrap block and d-pad, source-image pixels (t4x.html v2).
_CX0 = 303
_CY0 = 450
_RING = 159
_PAD = 140
_OK_R = 54
_L0, _R0, _T0, _B0 = 33, 576, 264, 634

# name, x, y, w, h, slot.
_SOURCE_RECTS: tuple[tuple[str, int, int, int, int, int], ...] = (
    ("Green power", 35, 49, 140, 81, 128),
    ("Home", 234, 49, 140, 81, 129),
    ("Red power", 433, 49, 140, 81, 130),
    ("PREV", 36, 184, 116, 61, 131),
    ("LIST", 177, 184, 112, 61, 132),
    ("BACK", 318, 184, 114, 61, 133),
    ("MUTE", 458, 184, 115, 61, 134),
    ("GUIDE", 35, 652, 119, 68, 144),
    ("MENU", 175, 652, 118, 68, 145),
    ("INFO", 317, 652, 115, 68, 146),
    ("EXIT", 456, 652, 115, 68, 147),
)

# Wrap / d-pad photo name → slot. Approved T4x DOM order, no joystick.
_DPAD_SLOTS: dict[str, int] = {
    "+CH": 140,
    "VOL +": 142,
    "-CH": 141,
    "VOL -": 143,
    "Up": 135,
    "Right": 137,
    "Down": 138,
    "Left": 136,
    "OK": 139,
}


def _crop_origin_and_size() -> tuple[int, int, int, int]:
    xs = [row[1] for row in _SOURCE_RECTS]
    ys = [row[2] for row in _SOURCE_RECTS]
    xe = [row[1] + row[3] for row in _SOURCE_RECTS]
    ye = [row[2] + row[4] for row in _SOURCE_RECTS]
    dpad_l = _CX0 - _PAD
    dpad_r = _CX0 + _PAD
    dpad_t = _CY0 - _PAD
    dpad_b = _CY0 + _PAD
    min_x = min(xs + [_L0, dpad_l]) - HK_TIGHT_PAD
    min_y = min(ys + [_T0, dpad_t]) - HK_TIGHT_PAD
    max_x = max(xe + [_R0, dpad_r]) + HK_TIGHT_PAD
    max_y = max(ye + [_B0, dpad_b]) + HK_TIGHT_PAD
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
class Rect:
    slot: int
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class Shape:
    slot: int
    d: str
    label_box: tuple[float, float, float, float] | None


def _rects() -> tuple[Rect, ...]:
    return tuple(
        Rect(slot=slot, x=x - CROP_X, y=y - CROP_Y, w=w, h=h)
        for _name, x, y, w, h, slot in _SOURCE_RECTS
    )


def _wedge_box(start: float, end: float, cx: float, cy: float) -> tuple[float, float, float, float]:
    mid = math.radians((start + end) / 2)
    radius = (_PAD + _OK_R) / 2
    x = cx + radius * math.cos(mid)
    y = cy + radius * math.sin(mid)
    return (x - 26, y - 14, 52, 28)


def _shapes() -> tuple[Shape, ...]:
    dpad: list[tuple[str, str, tuple[float, float, float, float]]] = [
        ("+CH", f"M{_n(_L)},{_n(_T)} H{_n(_CX)} V{_n(_CY - _RING)} A{_n(_RING)},{_n(_RING)} 0 0 0 {_n(_CX - _RING)},{_n(_CY)} H{_n(_L)} Z", (_L, _T, (_CX - _RING) - _L, _CY - _T)),
        ("VOL +", f"M{_n(_CX)},{_n(_T)} H{_n(_R)} V{_n(_CY)} H{_n(_CX + _RING)} A{_n(_RING)},{_n(_RING)} 0 0 0 {_n(_CX)},{_n(_CY - _RING)} Z", (_CX + _RING, _T, _R - (_CX + _RING), _CY - _T)),
        ("-CH", f"M{_n(_L)},{_n(_CY)} H{_n(_CX - _RING)} A{_n(_RING)},{_n(_RING)} 0 0 0 {_n(_CX)},{_n(_CY + _RING)} V{_n(_B)} H{_n(_L)} Z", (_L, _CY, (_CX - _RING) - _L, _B - _CY)),
        ("VOL -", f"M{_n(_CX)},{_n(_CY + _RING)} A{_n(_RING)},{_n(_RING)} 0 0 0 {_n(_CX + _RING)},{_n(_CY)} H{_n(_R)} V{_n(_B)} H{_n(_CX)} Z", (_CX + _RING, _CY, _R - (_CX + _RING), _B - _CY)),
        ("Up", _wedge(_CX, _CY, _PAD, _OK_R, -135, -45), _wedge_box(-135, -45, _CX, _CY)),
        ("Right", _wedge(_CX, _CY, _PAD, _OK_R, -45, 45), _wedge_box(-45, 45, _CX, _CY)),
        ("Down", _wedge(_CX, _CY, _PAD, _OK_R, 45, 135), _wedge_box(45, 135, _CX, _CY)),
        ("Left", _wedge(_CX, _CY, _PAD, _OK_R, 135, 225), _wedge_box(135, 225, _CX, _CY)),
        ("OK", _circle(_CX, _CY, _OK_R), (_CX - _OK_R, _CY - _OK_R, _OK_R * 2, _OK_R * 2)),
    ]
    return tuple(Shape(slot=_DPAD_SLOTS[name], d=path, label_box=box) for name, path, box in dpad)


RECTS: tuple[Rect, ...] = _rects()
SHAPES: tuple[Shape, ...] = _shapes()
