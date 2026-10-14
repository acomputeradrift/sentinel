import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.extraction.extractor_core import _resolve_button


class _NoSqlCursor:
    def execute(self, _sql, _params=()):
        raise AssertionError("No SQL queries are expected in _resolve_button for macro-step extraction")


class MacroStepsInButtonResolutionTest(unittest.TestCase):
    def test_macrostep_target_remains_enabled_without_sql_lookup(self):
        button_row = {
            "ButtonId": 101,
            "ButtonTagId": 77,
            "Text": "Power",
            "ButtonStyle": 0,
            "VisibleOrientations": 3,
            "TextSize": 12,
            "ButtonTop": 0,
            "ButtonLeft": 0,
            "ButtonHeight": 10,
            "ButtonWidth": 10,
            "ButtonTopAlt": 0,
            "ButtonLeftAlt": 0,
            "ButtonHeightAlt": 10,
            "ButtonWidthAlt": 10,
            "GlobalMacroId": None,
            "DeviceMacroId": None,
            "PageLinkId": None,
            "LinkPageId": None,
            "ButtonOrder": 0,
            "FrameNumber": 0,
        }

        user_button, _diag_button = _resolve_button(
            _NoSqlCursor(),
            button_row,
            current_device_id=1,
            tag_name_by_id={77: "POWER"},
            variables_by_tag={},
            button_text_tag_ids=set(),
            macros_by_tag={77: [{"MacroId": 999, "RoomId": 0}]},
            macro_non_empty_by_id={999: True},
            macro_device_ids_by_macro={},
            page_links_by_device_and_tag={},
            page_links_by_tag={},
            first_page_target_by_device_id={},
            page_name_by_page_id={},
            room_name_by_id={0: "Global"},
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
            page_room_id=0,
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

        self.assertTrue(user_button["testTargets"]["macroSteps"])
        self.assertEqual(user_button["apexScopeSource"]["bindings"]["macroStepIds"], [])

    def test_page_link_still_resolves_from_macro_step_maps_without_sql_lookup(self):
        button_row = {
            "ButtonId": 102,
            "ButtonTagId": 78,
            "Text": "Go",
            "ButtonStyle": 0,
            "VisibleOrientations": 3,
            "TextSize": 12,
            "ButtonTop": 0,
            "ButtonLeft": 0,
            "ButtonHeight": 10,
            "ButtonWidth": 10,
            "ButtonTopAlt": 0,
            "ButtonLeftAlt": 0,
            "ButtonHeightAlt": 10,
            "ButtonWidthAlt": 10,
            "GlobalMacroId": None,
            "DeviceMacroId": None,
            "PageLinkId": None,
            "LinkPageId": None,
            "ButtonOrder": 0,
            "FrameNumber": 0,
        }

        user_button, _diag_button = _resolve_button(
            _NoSqlCursor(),
            button_row,
            current_device_id=1,
            tag_name_by_id={78: "NAV"},
            variables_by_tag={},
            button_text_tag_ids=set(),
            macros_by_tag={78: [{"MacroId": 1001, "RoomId": 0}]},
            macro_non_empty_by_id={1001: True},
            macro_device_ids_by_macro={},
            page_links_by_device_and_tag={},
            page_links_by_tag={},
            first_page_target_by_device_id={},
            page_name_by_page_id={55: "Target Page"},
            room_name_by_id={0: "Global"},
            source_name_by_device_id={},
            macro_step_exact_page_by_macro={1001: 55},
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
            page_room_id=0,
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

        self.assertTrue(user_button["testTargets"]["pageLink"])
        self.assertEqual(user_button["resolvedPageLink"]["targetPageId"], 55)
        self.assertEqual(user_button["resolvedPageLink"]["resolutionPath"], "macroStep")

    def test_room_off_uses_page_source_activity_not_first_checked(self):
        button_row = {
            "ButtonId": 103,
            "ButtonTagId": 1252,
            "Text": "",
            "ButtonStyle": 0,
            "VisibleOrientations": 3,
            "TextSize": 12,
            "ButtonTop": 0,
            "ButtonLeft": 171,
            "ButtonHeight": 0,
            "ButtonWidth": 0,
            "ButtonTopAlt": 0,
            "ButtonLeftAlt": 171,
            "ButtonHeightAlt": 0,
            "ButtonWidthAlt": 0,
            "GlobalMacroId": None,
            "DeviceMacroId": None,
            "PageLinkId": None,
            "LinkPageId": None,
            "ButtonOrder": 0,
            "FrameNumber": 254,
        }

        user_button, _diag_button = _resolve_button(
            _NoSqlCursor(),
            button_row,
            current_device_id=112,
            tag_name_by_id={1252: "POWER OFF - Current ROOM"},
            variables_by_tag={},
            button_text_tag_ids=set(),
            macros_by_tag={1252: [{"MacroId": 993, "RoomId": 0}]},
            macro_non_empty_by_id={993: True},
            macro_device_ids_by_macro={},
            page_links_by_device_and_tag={},
            page_links_by_tag={},
            first_page_target_by_device_id={},
            page_name_by_page_id={138: "Apple TV (RV)", 104: "Room Select (Global)"},
            room_name_by_id={9: "RV"},
            source_name_by_device_id={63: "Apple TV (RV)"},
            macro_step_exact_page_by_macro={},
            macro_step_targets_by_macro={},
            room_event_targets_by_room={},
            select_rooms_by_macro={},
            room_offs_by_macro={993: [-1]},
            select_sources_by_macro={},
            activity_target_pages_by_room_and_device={(9, 63): [(138, 1), (108, 2)]},
            room_home_target_pages_by_room={9: [(104, 2)]},
            variable_command_rows_by_variable_id={},
            macro_flag_summaries_by_macro_id={},
            button_graphics_targets_by_button_id={},
            use_explicit_button_bitmaps=False,
            page_id=138,
            page_source_device_id=63,
            page_room_id=9,
            current_rti_address=1,
            global_room_fallback_id=None,
            layer_id=3881,
            shared_layer_id=2058,
            layer_name_resolved="Hard Keys",
            layer_room_id=None,
            layer_source_id=63,
            page_layer_room_id=None,
            page_layer_source_id=None,
            layer_order=0,
            button_order=0,
            frame_number=254,
            host_viewport_button_id=None,
            next_in_group_sequences={},
        )

        resolved = user_button["resolvedPageLink"]
        self.assertEqual(resolved["resolutionPath"], "roomOffEvent")
        self.assertEqual(resolved["targetPageId"], 138)
        self.assertEqual(resolved["targetPageName"], "Apple TV (RV)")
        self.assertNotEqual(resolved["targetPageId"], 104)


if __name__ == "__main__":
    unittest.main()
