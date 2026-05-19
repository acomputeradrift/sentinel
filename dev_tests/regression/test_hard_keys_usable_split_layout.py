import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.generation import render_core


class HardKeysUsableSplitLayoutTest(unittest.TestCase):
    def test_centers_at_quarter_lines_of_usable_width(self) -> None:
        lay = render_core._layout_hard_key_split(
            1200,
            900,
            480,
            854,
            468,
            862,
        )
        self.assertIsNotNone(lay)
        assert lay is not None
        touch = lay["touch"]
        strip = lay["strip"]
        self.assertAlmostEqual(touch["left"] + touch["width"] / 2.0, touch["centerX"], places=3)
        self.assertAlmostEqual(touch["centerX"], 0.25 * 1200, places=3)
        self.assertAlmostEqual(strip["left"] + strip["width"] / 2.0, strip["centerX"], places=3)
        self.assertAlmostEqual(strip["centerX"], 0.75 * 1200, places=3)

    def test_fits_scaled_span_and_zone_caps(self) -> None:
        usable_w, usable_h = 1280, 900
        lay = render_core._layout_hard_key_split(
            usable_w,
            usable_h,
            480,
            854,
            608,
            732,
        )
        self.assertIsNotNone(lay)
        assert lay is not None
        margin = 20
        half_w = (usable_w - 2 * margin) / 2.0
        fit_w = usable_w - 2 * margin
        fit_h = usable_h - 2 * margin
        asm = lay["assembly"]
        self.assertLessEqual(asm["width"], fit_w + 0.5)
        self.assertLessEqual(lay["touch"]["width"], half_w + 0.5)
        self.assertLessEqual(lay["strip"]["width"], half_w + 0.5)
        self.assertLessEqual(lay["touch"]["height"], fit_h + 0.5)

    def test_isr2_t4x_isr4_all_produce_layout(self) -> None:
        for design_w, design_h in ((468, 862), (608, 732), (602, 734)):
            lay = render_core._layout_hard_key_split(
                1280,
                900,
                480,
                854,
                design_w,
                design_h,
            )
            self.assertIsNotNone(lay, msg=f"design {design_w}x{design_h}")


if __name__ == "__main__":
    unittest.main()
