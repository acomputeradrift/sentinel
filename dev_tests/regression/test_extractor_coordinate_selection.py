import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.extraction import extractor_core


def _minimal_row(
    *,
    portrait: tuple[int, int, int, int],
    landscape: tuple[int, int, int, int],
    visible_orientations: int = 3,
) -> dict[str, object]:
    top, left, h, w = portrait
    at, al, ah, aw = landscape
    return {
        "VisibleOrientations": visible_orientations,
        "TextSize": 10,
        "ButtonTop": top,
        "ButtonLeft": left,
        "ButtonHeight": h,
        "ButtonWidth": w,
        "ButtonTopAlt": at,
        "ButtonLeftAlt": al,
        "ButtonHeightAlt": ah,
        "ButtonWidthAlt": aw,
    }


class ExtractorCoordinateSelectionTest(unittest.TestCase):
    def test_portrait_uses_only_portrait_columns(self):
        ui = extractor_core._button_ui(
            _minimal_row(
                portrait=(60, 240, 40, 60),
                landscape=(95, 500, 134, 200),
            ),
        )
        c = ui["orientations"]["portrait"]["coordinates"]
        self.assertEqual(c["top"], 60)
        self.assertEqual(c["left"], 240)
        self.assertEqual(c["height"], 40)
        self.assertEqual(c["width"], 60)

    def test_landscape_uses_only_landscape_columns(self):
        ui = extractor_core._button_ui(
            _minimal_row(
                portrait=(60, 240, 40, 60),
                landscape=(95, 500, 134, 200),
            ),
        )
        c = ui["orientations"]["landscape"]["coordinates"]
        self.assertEqual(c["top"], 95)
        self.assertEqual(c["left"], 500)
        self.assertEqual(c["height"], 134)
        self.assertEqual(c["width"], 200)

    def test_no_cross_orientation_when_landscape_is_off_panel(self):
        """If landscape coordinates are off-panel, portrait must not be substituted."""
        ui = extractor_core._button_ui(
            _minimal_row(
                portrait=(120, 120, 80, 80),
                landscape=(820, 503, 82, 92),
            ),
        )
        land = ui["orientations"]["landscape"]["coordinates"]
        self.assertEqual(land["top"], 820)
        self.assertEqual(land["left"], 503)
        port = ui["orientations"]["portrait"]["coordinates"]
        self.assertEqual(port["top"], 120)

    def test_landscape_only_device_still_separates_columns(self):
        ui = extractor_core._button_ui(
            _minimal_row(
                portrait=(15, 20, 180, 200),
                landscape=(260, 300, 140, 190),
                visible_orientations=2,
            ),
        )
        self.assertFalse(ui["orientations"]["portrait"]["visible"])
        self.assertTrue(ui["orientations"]["landscape"]["visible"])
        l = ui["orientations"]["landscape"]["coordinates"]
        self.assertEqual(l["top"], 260)
        p = ui["orientations"]["portrait"]["coordinates"]
        self.assertEqual(p["top"], 15)


if __name__ == "__main__":
    unittest.main()
