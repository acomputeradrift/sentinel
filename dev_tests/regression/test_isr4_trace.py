"""ISR-4 traced hard-key geometry."""
import math
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

_NUM = re.compile(r"-?\d+(?:\.\d+)?")
_KEYPAD_NAME = r"(?:[0-9]|ENTER|Enter|-/|Keypad)"


def _path_points(d: str) -> list[tuple[float, float]]:
    nums = [float(tok) for tok in _NUM.findall(d)]
    if len(nums) % 2 != 0:
        raise AssertionError(f"odd coordinate count: {len(nums)}")
    return list(zip(nums[0::2], nums[1::2]))


class Isr4TraceGeometryTest(unittest.TestCase):
    def test_slots_are_128_through_149_once(self) -> None:
        from sentinel.generation.hard_keys import isr4_trace

        slots = [rect.slot for rect in isr4_trace.RECTS] + [
            shape.slot for shape in isr4_trace.SHAPES
        ]
        self.assertEqual(sorted(slots), list(range(128, 150)))
        self.assertEqual(len(slots), len(set(slots)))

    def test_rects_empty_and_twenty_two_shapes(self) -> None:
        from sentinel.generation.hard_keys import isr4_trace

        self.assertEqual(isr4_trace.RECTS, ())
        self.assertEqual(len(isr4_trace.SHAPES), 22)
        self.assertEqual(len({shape.slot for shape in isr4_trace.SHAPES}), 22)
        for shape in isr4_trace.SHAPES:
            letters = set(re.findall(r"[A-Za-z]", shape.d))
            self.assertTrue(letters <= {"M", "L", "Z"}, letters)
            self.assertIsNotNone(shape.label_box)
            assert shape.label_box is not None
            self.assertEqual(len(shape.label_box), 4)
            pts = _path_points(shape.d)
            xs = [pt[0] for pt in pts]
            ys = [pt[1] for pt in pts]
            x, y, w, h = shape.label_box
            self.assertAlmostEqual(x, min(xs), places=5)
            self.assertAlmostEqual(y, min(ys), places=5)
            self.assertAlmostEqual(w, max(xs) - min(xs), places=5)
            self.assertAlmostEqual(h, max(ys) - min(ys), places=5)

    def test_design_size_is_pad_4_crop(self) -> None:
        from sentinel.generation.hard_keys import isr4_trace

        self.assertEqual(isr4_trace.HK_TIGHT_PAD, 4)
        width, height = isr4_trace.DESIGN_SIZE
        origin_x, origin_y = isr4_trace.CROP_ORIGIN
        self.assertEqual(type(width), int)
        self.assertEqual(type(height), int)
        self.assertEqual(type(origin_x), int)
        self.assertEqual(type(origin_y), int)
        self.assertGreater(width, 0)
        self.assertGreater(height, 0)
        xs: list[float] = []
        ys: list[float] = []
        for shape in isr4_trace.SHAPES:
            for x, y in _path_points(shape.d):
                xs.append(x + origin_x)
                ys.append(y + origin_y)
        min_x = math.floor(min(xs)) - 4
        min_y = math.floor(min(ys)) - 4
        max_x = math.ceil(max(xs)) + 4
        max_y = math.ceil(max(ys)) + 4
        self.assertEqual(isr4_trace.CROP_ORIGIN, (min_x, min_y))
        self.assertEqual(isr4_trace.DESIGN_SIZE, (max_x - min_x, max_y - min_y))

    def test_home_is_left_of_more(self) -> None:
        from sentinel.generation.hard_keys import isr4_trace

        home = next(shape for shape in isr4_trace.SHAPES if shape.slot == 128)
        more = next(shape for shape in isr4_trace.SHAPES if shape.slot == 129)
        self.assertIsNotNone(home.label_box)
        self.assertIsNotNone(more.label_box)
        assert home.label_box is not None
        assert more.label_box is not None
        self.assertLess(home.label_box[0], more.label_box[0])

    def test_no_keypad_names_or_out_of_range_slots(self) -> None:
        from sentinel.generation.hard_keys import isr4_trace

        text = Path(isr4_trace.__file__).read_text(encoding="utf-8")
        self.assertIsNone(re.search(rf'["\']{_KEYPAD_NAME}["\']\s*:', text))
        self.assertIsNone(re.search(rf'\(\s*["\']{_KEYPAD_NAME}["\']', text))
        slots = [rect.slot for rect in isr4_trace.RECTS] + [
            shape.slot for shape in isr4_trace.SHAPES
        ]
        for slot in slots:
            self.assertGreaterEqual(slot, 128)
            self.assertLessEqual(slot, 149)
