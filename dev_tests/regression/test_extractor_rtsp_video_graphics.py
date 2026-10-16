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


class _NoSqlCursor:
    def execute(self, _sql, _params=()):
        raise AssertionError("graphics bitmap resolution must use the button row, not SQL")


def _graphics_button_row(*, style: int = 0, up: object = "missing", down: object = "missing", icon: object = "missing") -> dict:
    row = {
        "ButtonId": 501,
        "ButtonTagId": 0,
        "Text": "RTSP Video" if style == 4 else "",
        "ButtonStyle": style,
        "VisibleOrientations": 3,
        "TextSize": 12,
        "ButtonTop": 0,
        "ButtonLeft": 0,
        "ButtonHeight": 40,
        "ButtonWidth": 80,
        "ButtonTopAlt": 0,
        "ButtonLeftAlt": 0,
        "ButtonHeightAlt": 40,
        "ButtonWidthAlt": 80,
        "GlobalMacroId": None,
        "DeviceMacroId": None,
        "PageLinkId": None,
        "LinkPageId": None,
        "ButtonOrder": 0,
        "FrameNumber": 0,
    }
    if up != "missing":
        row["UpBitmapId"] = up
    if down != "missing":
        row["DownBitmapId"] = down
    if icon != "missing":
        row["IconBitmapId"] = icon
    return row


def _resolved_graphics(*, style: int = 0, up: object = "missing", down: object = "missing", icon: object = "missing") -> dict:
    user_button, _diag = extractor_core._resolve_button(
        _NoSqlCursor(),
        _graphics_button_row(style=style, up=up, down=down, icon=icon),
        current_device_id=112,
        tag_name_by_id={},
        variables_by_tag={},
        button_text_tag_ids=set(),
        macros_by_tag={},
        macro_non_empty_by_id={},
        macro_device_ids_by_macro={},
        page_links_by_device_and_tag={},
        page_links_by_tag={},
        first_page_target_by_device_id={},
        page_name_by_page_id={},
        room_name_by_id={},
        source_name_by_device_id={},
        macro_step_exact_page_by_macro={},
        macro_step_targets_by_macro={},
        room_event_targets_by_room={},
        select_rooms_by_macro={},
        room_offs_by_macro={},
        select_sources_by_macro={},
        activity_target_pages_by_room_and_device={},
        room_home_target_pages_by_room={},
        variable_command_rows_by_variable_id={},
        macro_flag_summaries_by_macro_id={},
        button_graphics_targets_by_button_id={},
        use_explicit_button_bitmaps=False,
        page_id=1,
        page_source_device_id=None,
        page_room_id=1,
        current_rti_address=1,
        global_room_fallback_id=None,
        layer_id=1,
        shared_layer_id=1,
        layer_name_resolved="Layer",
        layer_room_id=None,
        layer_source_id=None,
        page_layer_room_id=None,
        page_layer_source_id=None,
        layer_order=0,
        button_order=0,
        frame_number=0,
        host_viewport_button_id=None,
        next_in_group_sequences={},
    )
    return user_button["testTargets"]["graphics"]


def _labels_for_graphics(graphics: dict) -> list[str]:
    button = {
        "testTargets": {
            "text": False,
            "macros": False,
            "macroSteps": False,
            "variables": {},
            "graphics": graphics,
            "pageLink": False,
        }
    }
    return render_core._targets(button, "Variable - {variableType}")


class ExtractorSplitBitmapGraphicsTest(unittest.TestCase):
    def test_up_bitmap_id_emits_bitmap_normal_only(self):
        graphics = _resolved_graphics(up=12)
        self.assertEqual(
            graphics,
            {"bitmapNormal": True, "bitmapActive": False, "icon": False, "rtspVideo": False},
        )
        self.assertNotIn("bitmap", graphics)
        self.assertEqual(_labels_for_graphics(graphics), ["Bitmap - Normal"])

    def test_down_bitmap_id_emits_bitmap_active_only(self):
        graphics = _resolved_graphics(down=8)
        self.assertEqual(
            graphics,
            {"bitmapNormal": False, "bitmapActive": True, "icon": False, "rtspVideo": False},
        )
        self.assertEqual(_labels_for_graphics(graphics), ["Bitmap - Active"])

    def test_up_and_down_bitmap_ids_emit_two_targets(self):
        graphics = _resolved_graphics(up=12, down=8, icon=3)
        self.assertEqual(
            graphics,
            {"bitmapNormal": True, "bitmapActive": True, "icon": True, "rtspVideo": False},
        )
        self.assertEqual(_labels_for_graphics(graphics), ["Bitmap - Normal", "Bitmap - Active", "Icon"])

    def test_missing_null_and_negative_bitmap_ids_emit_no_bitmap_target(self):
        for kwargs in ({}, {"up": None, "down": None}, {"up": -1, "down": -1}):
            graphics = _resolved_graphics(**kwargs)
            self.assertFalse(graphics.get("bitmapNormal"))
            self.assertFalse(graphics.get("bitmapActive"))
            self.assertNotIn("bitmap", graphics)
            self.assertEqual(_labels_for_graphics(graphics), [])

    def test_slider_toggle_and_level_indicator_emit_no_graphic_targets(self):
        for style in (5, 7, 11):
            graphics = _resolved_graphics(style=style, up=12, down=8, icon=3)
            self.assertEqual(
                graphics,
                {"bitmapNormal": False, "bitmapActive": False, "icon": False, "rtspVideo": False},
            )
            self.assertEqual(_labels_for_graphics(graphics), [])

    def test_rtsp_style_still_emits_rtsp_video_without_bitmap_flags(self):
        graphics = _resolved_graphics(style=4)
        self.assertEqual(
            graphics,
            {"bitmapNormal": False, "bitmapActive": False, "icon": False, "rtspVideo": True},
        )
        self.assertEqual(_labels_for_graphics(graphics), ["RTSP Video"])

    def test_diagnostics_still_groups_split_bitmap_labels_via_bitmap_substring(self):
        source = (ROOT / "src" / "sentinel" / "ui" / "commissioning" / "diagnostics_tab.js").read_text(encoding="utf-8")
        self.assertIn('label.includes("bitmap")', source)


if __name__ == "__main__":
    unittest.main()
