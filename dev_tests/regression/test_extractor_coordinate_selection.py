import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.extraction import extractor_core


class ExtractorCoordinateSelectionTest(unittest.TestCase):
    def test_landscape_only_prefers_alt_when_alt_fits(self):
        primary = {"top": 60, "left": 240, "height": 40, "width": 60}
        alt = {"top": 95, "left": 500, "height": 134, "width": 200}
        out = extractor_core._select_orientation_coordinates(
            orientation="landscape",
            primary=primary,
            alt=alt,
            portrait_supported=False,
            landscape_supported=True,
            portrait_resolution={"width": 0, "height": 0},
            landscape_resolution={"width": 800, "height": 480},
        )
        self.assertEqual(alt, out)

    def test_both_orientations_keep_alt_for_landscape_when_alt_fits(self):
        primary = {"top": 60, "left": 240, "height": 40, "width": 60}
        alt = {"top": 95, "left": 500, "height": 134, "width": 200}
        out = extractor_core._select_orientation_coordinates(
            orientation="landscape",
            primary=primary,
            alt=alt,
            portrait_supported=True,
            landscape_supported=True,
            portrait_resolution={"width": 480, "height": 854},
            landscape_resolution={"width": 800, "height": 480},
        )
        self.assertEqual(alt, out)

    def test_both_orientations_fallback_to_primary_when_alt_invalid(self):
        primary = {"top": 120, "left": 120, "height": 80, "width": 80}
        alt = {"top": 820, "left": 503, "height": 82, "width": 92}
        out = extractor_core._select_orientation_coordinates(
            orientation="landscape",
            primary=primary,
            alt=alt,
            portrait_supported=True,
            landscape_supported=True,
            portrait_resolution={"width": 1080, "height": 2201},
            landscape_resolution={"width": 2264, "height": 881},
        )
        self.assertEqual(primary, out)

    def test_portrait_only_uses_primary_coordinates(self):
        primary = {"top": 15, "left": 20, "height": 180, "width": 200}
        alt = {"top": 260, "left": 300, "height": 140, "width": 190}
        out = extractor_core._select_orientation_coordinates(
            orientation="portrait",
            primary=primary,
            alt=alt,
            portrait_supported=True,
            landscape_supported=False,
            portrait_resolution={"width": 480, "height": 854},
            landscape_resolution={"width": 0, "height": 0},
        )
        self.assertEqual(primary, out)


if __name__ == "__main__":
    unittest.main()
