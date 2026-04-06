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


class MacroStepsDisabledInButtonResolutionTest(unittest.TestCase):
    def test_macrostep_targets_and_ids_are_disabled_without_sql_lookup(self):
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
        )

        self.assertFalse(user_button["testTargets"]["macroSteps"])
        self.assertEqual(user_button["apexScopeSource"]["bindings"]["macroStepIds"], [])


if __name__ == "__main__":
    unittest.main()
