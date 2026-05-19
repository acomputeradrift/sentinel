import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.generation import render_core


class HardKeysLayoutDisplayHeightTest(unittest.TestCase):
    def test_isr2_strip_at_touch_width_exceeds_touch_height(self) -> None:
        touch_w, touch_h = 480, 854
        design_w, design_h = 468, 862
        expected_strip = int(round(touch_w * design_h / design_w))
        self.assertGreater(expected_strip, touch_h)
        self.assertEqual(
            render_core._hard_key_layout_display_height(touch_w, touch_h, design_w, design_h),
            expected_strip,
        )

    def test_t4x_keeps_touch_height(self) -> None:
        touch_w, touch_h = 480, 854
        design_w, design_h = 608, 732
        self.assertEqual(
            render_core._hard_key_layout_display_height(touch_w, touch_h, design_w, design_h),
            touch_h,
        )

    def test_isr4_keeps_touch_height(self) -> None:
        touch_w, touch_h = 480, 854
        design_w, design_h = 602, 734
        self.assertEqual(
            render_core._hard_key_layout_display_height(touch_w, touch_h, design_w, design_h),
            touch_h,
        )

    def test_invalid_dimensions_fall_back_to_touch_height(self) -> None:
        self.assertEqual(render_core._hard_key_layout_display_height(0, 854, 468, 862), 854)
        self.assertEqual(render_core._hard_key_layout_display_height(480, 0, 468, 862), 1)


if __name__ == "__main__":
    unittest.main()
