"""ISR-2 traced hard-key geometry."""
from __future__ import annotations

import math
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

_TOKEN = re.compile(
    r"[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d+\.\d+|\d+|\.\d+)(?:[eE][-+]?\d+)?"
)


def _path_points(d: str) -> list[tuple[float, float]]:
    tokens = _TOKEN.findall(d)
    i = 0
    points: list[tuple[float, float]] = []
    while i < len(tokens):
        cmd = tokens[i]
        if not cmd.isalpha():
            raise AssertionError(f"expected command, got {cmd!r}")
        i += 1
        if cmd in "Zz":
            continue
        if cmd in "MmLl":
            points.append((float(tokens[i]), float(tokens[i + 1])))
            i += 2
            continue
        if cmd in "Aa":
            points.append((float(tokens[i + 5]), float(tokens[i + 6])))
            i += 7
            continue
        raise AssertionError(f"unsupported command {cmd!r}")
    return points


class Isr2TraceGeometryTest(unittest.TestCase):
    def test_shapes_cover_slots_128_through_161_once(self) -> None:
        from sentinel.generation.hard_keys import isr2_trace

        slots = [shape.slot for shape in isr2_trace.SHAPES]
        self.assertEqual(sorted(slots), list(range(128, 162)))
        self.assertEqual(len(slots), len(set(slots)))
        self.assertEqual(isr2_trace.RECTS, ())

    def test_design_size_is_pad_4_crop(self) -> None:
        from sentinel.generation.hard_keys import isr2_trace

        width, height = isr2_trace.DESIGN_SIZE
        self.assertEqual(type(width), int)
        self.assertEqual(type(height), int)
        self.assertGreater(width, 0)
        self.assertGreater(height, 0)

        ox, oy = isr2_trace.CROP_ORIGIN
        xs: list[float] = []
        ys: list[float] = []
        for shape in isr2_trace.SHAPES:
            for x, y in _path_points(shape.d):
                xs.append(round(x + ox, 1))
                ys.append(round(y + oy, 1))
        pad = isr2_trace.HK_TIGHT_PAD
        min_x = math.floor(min(xs)) - pad
        min_y = math.floor(min(ys)) - pad
        max_x = math.ceil(max(xs)) + pad
        max_y = math.ceil(max(ys)) + pad
        self.assertEqual(isr2_trace.CROP_ORIGIN, (min_x, min_y))
        self.assertEqual(isr2_trace.DESIGN_SIZE, (max_x - min_x, max_y - min_y))

    def test_home_label_box_is_top_left_of_crop(self) -> None:
        from sentinel.generation.hard_keys import isr2_trace

        home = next(shape for shape in isr2_trace.SHAPES if shape.slot == 128)
        more = next(shape for shape in isr2_trace.SHAPES if shape.slot == 129)
        self.assertIsNotNone(home.label_box)
        self.assertIsNotNone(more.label_box)
        assert home.label_box is not None
        assert more.label_box is not None
        pad = float(isr2_trace.HK_TIGHT_PAD)
        self.assertLess(abs(home.label_box[0] - pad), 1.0)
        self.assertLess(abs(home.label_box[1] - pad), 1.0)
        self.assertLess(home.label_box[0], more.label_box[0])

    def test_every_shape_has_a_label_box(self) -> None:
        from sentinel.generation.hard_keys import isr2_trace

        ok = next(shape for shape in isr2_trace.SHAPES if shape.slot == 135)
        self.assertIsNotNone(ok.label_box)
        self.assertTrue(all(shape.label_box is not None for shape in isr2_trace.SHAPES))
