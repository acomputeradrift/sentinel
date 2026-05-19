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
        lay = render_core._hard_key_usable_split_layout(
            1200,
            900,
            480,
            854,
            468,
            862,
        )
        self.assertIsNotNone(lay)
        assert lay is not None
        self.assertAlmostEqual(
            lay["touchLeft"] + lay["touchWidth"] / 2.0,
            lay["touchCenterX"],
            places=3,
        )
        self.assertAlmostEqual(lay["touchCenterX"], 0.25 * 1200, places=3)
        self.assertAlmostEqual(
            lay["hkLeft"] + lay["hkWidth"] / 2.0,
            lay["hkCenterX"],
            places=3,
        )
        self.assertAlmostEqual(lay["hkCenterX"], 0.75 * 1200, places=3)

    def test_fits_inside_margin_inset_box(self) -> None:
        usable_w, usable_h = 1280, 900
        lay = render_core._hard_key_usable_split_layout(
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
        left_edge = min(lay["touchLeft"], lay["hkLeft"])
        right_edge = max(
            lay["touchLeft"] + lay["touchWidth"],
            lay["hkLeft"] + lay["hkWidth"],
        )
        self.assertGreaterEqual(left_edge, margin - 0.5)
        self.assertLessEqual(right_edge, usable_w - margin + 0.5)
        self.assertLessEqual(lay["touchHeight"], usable_h - 2 * margin + 0.5)

    def test_isr2_t4x_isr4_all_produce_layout(self) -> None:
        for design_w, design_h in ((468, 862), (608, 732), (602, 734)):
            lay = render_core._hard_key_usable_split_layout(
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
