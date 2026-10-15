"""T4x traced hard-key geometry."""
from __future__ import annotations

import unittest

# Trace v2 coordinates from remote_trace/t4x.html (stage 608×734).
_TRACE_RECTS = (
    (35, 49, 140, 81),
    (234, 49, 140, 81),
    (433, 49, 140, 81),
    (36, 184, 116, 61),
    (177, 184, 112, 61),
    (318, 184, 114, 61),
    (458, 184, 115, 61),
    (35, 652, 119, 68),
    (175, 652, 118, 68),
    (317, 652, 115, 68),
    (456, 652, 115, 68),
)
_L, _R, _T, _B = 33, 576, 264, 634
_CX, _CY, _PAD = 303, 450, 140
_TIGHT_PAD = 4


def _expected_crop() -> tuple[tuple[int, int], tuple[int, int]]:
    xs = [row[0] for row in _TRACE_RECTS]
    ys = [row[1] for row in _TRACE_RECTS]
    xe = [row[0] + row[2] for row in _TRACE_RECTS]
    ye = [row[1] + row[3] for row in _TRACE_RECTS]
    min_x = min(xs + [_L, _CX - _PAD]) - _TIGHT_PAD
    min_y = min(ys + [_T, _CY - _PAD]) - _TIGHT_PAD
    max_x = max(xe + [_R, _CX + _PAD]) + _TIGHT_PAD
    max_y = max(ye + [_B, _CY + _PAD]) + _TIGHT_PAD
    return (min_x, min_y), (max_x - min_x, max_y - min_y)


class T4xTraceGeometryTest(unittest.TestCase):
    def test_slots_cover_128_through_147_once(self) -> None:
        from sentinel.generation.hard_keys import t4x_trace

        slots = [rect.slot for rect in t4x_trace.RECTS] + [shape.slot for shape in t4x_trace.SHAPES]
        self.assertEqual(sorted(slots), list(range(128, 148)))
        self.assertEqual(len(slots), len(set(slots)))

    def test_eleven_rects_and_nine_shapes(self) -> None:
        from sentinel.generation.hard_keys import t4x_trace

        self.assertEqual(len(t4x_trace.RECTS), 11)
        self.assertEqual(len(t4x_trace.SHAPES), 9)

    def test_green_power_sits_on_the_crop_pad(self) -> None:
        from sentinel.generation.hard_keys import t4x_trace

        green = next(rect for rect in t4x_trace.RECTS if rect.slot == 128)
        self.assertLessEqual(abs(green.x - 4), 2)
        self.assertLessEqual(abs(green.y - 4), 2)
        self.assertEqual((green.x, green.y), (35 - t4x_trace.CROP_ORIGIN[0], 49 - t4x_trace.CROP_ORIGIN[1]))
        self.assertEqual((green.w, green.h), (140, 81))

    def test_ok_is_slot_139_with_label_box(self) -> None:
        from sentinel.generation.hard_keys import t4x_trace

        ok = next(shape for shape in t4x_trace.SHAPES if shape.slot == 139)
        self.assertIsNotNone(ok.label_box)
        self.assertEqual(len(ok.label_box), 4)

    def test_design_size_matches_crop(self) -> None:
        from sentinel.generation.hard_keys import t4x_trace

        origin, size = _expected_crop()
        self.assertEqual(t4x_trace.HK_TIGHT_PAD, 4)
        self.assertEqual(t4x_trace.CROP_ORIGIN, origin)
        self.assertEqual(t4x_trace.DESIGN_SIZE, size)
        self.assertGreater(t4x_trace.DESIGN_SIZE[0], 0)
        self.assertGreater(t4x_trace.DESIGN_SIZE[1], 0)


if __name__ == "__main__":
    unittest.main()
