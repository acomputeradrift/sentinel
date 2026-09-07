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

    def test_rtsp_style_stores_empty_identity_text(self):
        display_text, identifier_text = extractor_core._identity_texts_for_style(style=4, text="RTSP Video")
        self.assertEqual(display_text, "")
        self.assertEqual(identifier_text, "")

    def test_rtsp_empty_text_classifies_as_ui_item(self):
        button = {
            "buttonIdentity": {"buttonType": None, "buttonTagName": ""},
            "buttonUI": {
                "orientations": {
                    "portrait": {"coordinates": {"height": 12, "width": 20}},
                    "landscape": {"coordinates": {"height": 12, "width": 20}},
                }
            },
            "testTargets": {
                "text": False,
                "macros": False,
                "macroSteps": False,
                "variables": {"Text": False},
                "pageLink": False,
            },
        }
        category = extractor_core._classify_user_button_category(
            button=button,
            has_tag_field=False,
            raw_text="",
            has_macros_target=False,
            has_any_variable_target=False,
        )
        self.assertEqual(category, "uiItems")

    def test_rtsp_dialogue_title_is_ui_item_graphics(self):
        btn = {
            "buttonIdentity": {"buttonTagName": "", "text": "", "buttonType": None},
            "testTargets": {
                "text": False,
                "macros": False,
                "macroSteps": False,
                "variables": {},
                "graphics": {"bitmap": False, "icon": False, "rtspVideo": True},
                "pageLink": False,
            },
        }
        self.assertEqual(render_core._button_identity_label(btn), "Graphics")
        self.assertEqual(render_core._targets(btn, "Variable - {variableType}"), ["RTSP Video"])
        leftover = dict(btn)
        leftover["buttonIdentity"] = {"buttonTagName": "", "text": "RTSP Video", "buttonType": None}
        self.assertEqual(render_core._button_identity_label(leftover), "Graphics")

    def test_canonicalize_rtsp_video_row_to_catalog_id(self):
        self.assertEqual(testing_types.canonicalize_label("RTSP Video"), "RTSP Video")
        self.assertEqual(testing_types.type_id_for_label(family="button", label="RTSP Video"), "button:RTSP Video")


if __name__ == "__main__":
    unittest.main()
