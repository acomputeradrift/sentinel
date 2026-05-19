import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.generation import render_core


class ContainScaleTest(unittest.TestCase):
    def test_width_limited(self) -> None:
        self.assertAlmostEqual(
            render_core._contain_scale(1000, 500, 400, 400),
            0.4,
        )

    def test_height_limited(self) -> None:
        self.assertAlmostEqual(
            render_core._contain_scale(400, 1000, 400, 400),
            0.4,
        )

    def test_invalid_returns_zero(self) -> None:
        self.assertEqual(render_core._contain_scale(0, 100, 100, 100), 0.0)


class LayoutTouchscreenDeviceTest(unittest.TestCase):
    def test_matches_min_width_height_scale(self) -> None:
        lay = render_core._layout_touchscreen_device(1280, 900, 480, 854, margin=20)
        self.assertIsNotNone(lay)
        assert lay is not None
        fit_w, fit_h = 1280 - 40, 900 - 40
        expected = min(fit_w / 480, fit_h / 854)
        self.assertAlmostEqual(lay["scale"], expected, places=5)
        self.assertAlmostEqual(lay["width"], 480 * expected, places=3)
        self.assertAlmostEqual(lay["height"], 854 * expected, places=3)
        self.assertAlmostEqual(lay["left"], (1280 - lay["width"]) / 2, places=3)
        self.assertAlmostEqual(lay["top"], (900 - lay["height"]) / 2, places=3)


class LayoutHardKeyTouchColumnTest(unittest.TestCase):
    def test_matches_half_width_height_contain(self) -> None:
        lay = render_core._layout_hard_key_touch_column(1280, 900, 480, 854, margin=20)
        self.assertIsNotNone(lay)
        assert lay is not None
        half_w, fit_h = (1280 - 40) / 2, 900 - 40
        expected = min(half_w / 480, fit_h / 854)
        self.assertAlmostEqual(lay["scale"], expected, places=5)

    def test_jazz_room_touch_margins_near_twenty_px(self) -> None:
        """ISR-2 Jazz Room apex portrait 240x320; height-limited touch column -> A=C~20."""
        lay = render_core._layout_hard_key_touch_column(1804, 990, 240, 320, margin=20)
        self.assertIsNotNone(lay)
        assert lay is not None
        top = float(lay["top"])
        height = float(lay["height"])
        self.assertAlmostEqual(top, 20.0, delta=0.6)
        self.assertAlmostEqual(990 - top - height, 20.0, delta=0.6)
        self.assertAlmostEqual(float(lay["centerX"]), 0.25 * 1804, places=3)

    def test_touch_scale_not_reduced_by_assembly_span(self) -> None:
        split = render_core._layout_hard_key_split(1804, 990, 240, 320, 468, 862, margin=20)
        touch_only = render_core._layout_hard_key_touch_column(1804, 990, 240, 320, margin=20)
        self.assertIsNotNone(split)
        self.assertIsNotNone(touch_only)
        assert split is not None and touch_only is not None
        self.assertAlmostEqual(float(split["touchScale"]), float(touch_only["scale"]), places=5)


class LayoutHardKeySplitTest(unittest.TestCase):
    def test_centers_at_quarter_lines(self) -> None:
        lay = render_core._layout_hard_key_split(
            1200, 900, 480, 854, 468, 862, margin=20
        )
        self.assertIsNotNone(lay)
        assert lay is not None
        touch = lay["touch"]
        strip = lay["strip"]
        self.assertAlmostEqual(touch["centerX"], 300, places=3)
        self.assertAlmostEqual(strip["centerX"], 900, places=3)
        self.assertAlmostEqual(
            touch["left"] + touch["width"] / 2, touch["centerX"], places=3
        )
        self.assertAlmostEqual(
            strip["left"] + strip["width"] / 2, strip["centerX"], places=3
        )

    def test_each_zone_width_capped_at_half_padded_usable(self) -> None:
        usable_w, margin = 1280, 20
        half_w = (usable_w - 2 * margin) / 2
        lay = render_core._layout_hard_key_split(
            usable_w, 900, 480, 854, 608, 732, margin=margin
        )
        self.assertIsNotNone(lay)
        assert lay is not None
        self.assertLessEqual(lay["touch"]["width"], half_w + 0.5)
        self.assertLessEqual(lay["strip"]["width"], half_w + 0.5)

    def test_assembly_fits_margin_box(self) -> None:
        usable_w, usable_h, margin = 1280, 900, 20
        lay = render_core._layout_hard_key_split(
            usable_w, usable_h, 480, 854, 468, 862, margin=margin
        )
        self.assertIsNotNone(lay)
        assert lay is not None
        asm = lay["assembly"]
        self.assertGreaterEqual(asm["left"], margin - 0.5)
        self.assertLessEqual(asm["left"] + asm["width"], usable_w - margin + 0.5)
        self.assertLessEqual(asm["height"], usable_h - 2 * margin + 0.5)

    def test_at_scale_doubles_dimensions(self) -> None:
        base = render_core._layout_hard_key_split(1200, 900, 480, 854, 608, 732)
        assert base is not None
        base_touch_scale = float(base["touchScale"])
        base_strip_scale = float(base["stripScale"])
        at2 = render_core._layout_hard_key_split_at_scale(
            base, base_touch_scale * 2.0, base_strip_scale * 2.0
        )
        self.assertAlmostEqual(at2["touch"]["width"], base["touch"]["width"] * 2, places=3)
        self.assertAlmostEqual(at2["touch"]["centerX"], base["touch"]["centerX"], places=3)


if __name__ == "__main__":
    unittest.main()
