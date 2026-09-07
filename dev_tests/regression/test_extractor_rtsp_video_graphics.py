import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.extraction import extractor_core
from sentinel.generation import render_core
from sentinel.server.services import testing_types


class ExtractorRtspVideoGraphicsTest(unittest.TestCase):
    def test_style_4_is_rtsp_video_and_not_text(self):
        is_rtsp, has_text = extractor_core._rtsp_video_and_text_targets(style=4, text="RTSP Video")
        self.assertTrue(is_rtsp)
        self.assertFalse(has_text)

    def test_normal_literal_text_stays_text_target(self):
        is_rtsp, has_text = extractor_core._rtsp_video_and_text_targets(style=0, text="Power")
        self.assertFalse(is_rtsp)
        self.assertTrue(has_text)

    def test_catalog_marks_rtsp_video_as_graphics(self):
        row = testing_types.CATALOG_BY_ID["button:RTSP Video"]
        self.assertEqual(row.label, "RTSP Video")
        self.assertTrue(row.graphics)
        self.assertIn("button:RTSP Video", testing_types.GRAPHICS_TYPE_IDS)

    def test_render_targets_emit_rtsp_video_not_text(self):
        labels = render_core._targets(
            {
                "testTargets": {
                    "text": False,
                    "macros": False,
                    "macroSteps": False,
                    "variables": {},
                    "graphics": {"bitmap": False, "icon": False, "rtspVideo": True},
                    "pageLink": False,
                }
            },
            "Variable - {variableType}",
        )
        self.assertEqual(labels, ["RTSP Video"])


if __name__ == "__main__":
    unittest.main()
