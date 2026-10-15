import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.extraction.extractor_core import (
    _classify_user_button_category,
    _has_any_variable_target,
    _resolve_button,
)


class _NoSqlCursor:
    def execute(self, _sql, _params=()):
        raise AssertionError("No SQL queries are expected in _resolve_button for variable scope")


def _hard_key_button_row() -> dict:
    return {
        "ButtonId": 501,
        "ButtonTagId": 8801,
        "Text": "",
        "ButtonStyle": 0,
        "VisibleOrientations": 3,
        "TextSize": 12,
        "ButtonTop": 0,
        "ButtonLeft": 0,
        "ButtonHeight": 0,
        "ButtonWidth": 0,
        "ButtonTopAlt": 0,
        "ButtonLeftAlt": 0,
        "ButtonHeightAlt": 0,
        "ButtonWidthAlt": 0,
        "GlobalMacroId": None,
        "DeviceMacroId": None,
        "PageLinkId": None,
        "LinkPageId": None,
        "ButtonOrder": 0,
        "FrameNumber": 254,
    }


def _variable_row(*, variable_id: int, room_id: int, device_id: int) -> dict:
    return {
        "VariableId": variable_id,
        "RoomId": room_id,
        "DeviceId": device_id,
        "ButtonText": "Scan Back",
        "ObjectData": "",
        "VisibleData": "1",
        "ReversedData": "",
        "InactiveData": "",
    }


def _resolve(*, layer_source_id: int, page_source_device_id: int, variable_row: dict):
    return _resolve_button(
        _NoSqlCursor(),
        _hard_key_button_row(),
        current_device_id=112,
        tag_name_by_id={8801: "Scan Back"},
        variables_by_tag={8801: [variable_row]},
        button_text_tag_ids=set(),
        macros_by_tag={},
        macro_non_empty_by_id={},
        macro_device_ids_by_macro={},
        page_links_by_device_and_tag={},
        page_links_by_tag={},
        first_page_target_by_device_id={},
        page_name_by_page_id={},
        room_name_by_id={0: "Global", 1: "Room 1"},
        source_name_by_device_id={13: "Nintendo Switch", 24: "Sonos"},
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
        page_source_device_id=page_source_device_id,
        page_room_id=1,
        current_rti_address=1,
        global_room_fallback_id=None,
        layer_id=1,
        shared_layer_id=1,
        layer_name_resolved="Layer",
        layer_room_id=None,
        layer_source_id=layer_source_id,
        page_layer_room_id=None,
        page_layer_source_id=None,
        layer_order=0,
        button_order=0,
        frame_number=254,
        host_viewport_button_id=None,
        next_in_group_sequences={},
    )


def _category(user_button: dict, diag_button: dict) -> str:
    return _classify_user_button_category(
        button=user_button,
        has_tag_field=diag_button["identifiers"].get("buttonTagId") is not None,
        raw_text=str(diag_button["identifiers"].get("text") or ""),
        has_macros_target=bool(user_button["testTargets"].get("macros")),
        has_any_variable_target=_has_any_variable_target(user_button),
        has_meaningful_tag_content=bool(
            user_button["testTargets"].get("pageLink")
            or user_button["testTargets"].get("text")
            or user_button["testTargets"].get("macros")
            or user_button["testTargets"].get("macroSteps")
            or _has_any_variable_target(user_button)
            or bool((user_button["testTargets"].get("graphics") or {}).get("bitmap"))
            or bool((user_button["testTargets"].get("graphics") or {}).get("icon"))
            or bool((user_button["testTargets"].get("graphics") or {}).get("rtspVideo"))
            or isinstance((user_button.get("apexScopeSource") or {}).get("audioScope"), dict)
        ),
    )


class VariableScopeForPageSourceTest(unittest.TestCase):
    def test_controller_variable_does_not_paint_other_source(self):
        user_button, diag_button = _resolve(
            layer_source_id=13,
            page_source_device_id=13,
            variable_row=_variable_row(variable_id=2401, room_id=1, device_id=24),
        )
        self.assertFalse(user_button["testTargets"]["variables"]["Visible"])
        self.assertFalse(user_button["testTargets"]["variables"]["Text"])
        self.assertEqual(user_button["apexScopeSource"]["bindings"]["variableIds"], [])
        self.assertEqual(_category(user_button, diag_button), "emptyTag")

    def test_controller_variable_counts_on_matching_source(self):
        user_button, diag_button = _resolve(
            layer_source_id=24,
            page_source_device_id=24,
            variable_row=_variable_row(variable_id=2401, room_id=1, device_id=24),
        )
        self.assertTrue(user_button["testTargets"]["variables"]["Visible"])
        self.assertEqual(user_button["apexScopeSource"]["bindings"]["variableIds"], [2401])
        self.assertEqual(_category(user_button, diag_button), "hardButtons")

    def test_global_variable_counts_on_every_page(self):
        user_button, _diag_button = _resolve(
            layer_source_id=13,
            page_source_device_id=13,
            variable_row=_variable_row(variable_id=2402, room_id=0, device_id=-1),
        )
        self.assertTrue(user_button["testTargets"]["variables"]["Visible"])
        self.assertEqual(user_button["apexScopeSource"]["bindings"]["variableIds"], [2402])


if __name__ == "__main__":
    unittest.main()
