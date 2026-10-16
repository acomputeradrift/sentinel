import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.extraction import extractor_core
from sentinel.extraction.extractor_core import (
    _classify_user_button_category,
    _has_any_variable_target,
    _resolve_button,
)


class _NoSqlCursor:
    def execute(self, _sql, _params=()):
        raise AssertionError("No SQL queries are expected in _resolve_button for tag-macro priority")


def _macro_row(*, macro_id: int, room_id: int, device_id: int) -> dict:
    return {"MacroId": macro_id, "RoomId": room_id, "DeviceId": device_id}


def _button_row(*, text: str, height: int, width: int, global_macro_id: int | None = None) -> dict:
    return {
        "ButtonId": 501,
        "ButtonTagId": 8801,
        "Text": text,
        "ButtonStyle": 0,
        "VisibleOrientations": 3,
        "TextSize": 12,
        "ButtonTop": 0,
        "ButtonLeft": 0,
        "ButtonHeight": height,
        "ButtonWidth": width,
        "ButtonTopAlt": 0,
        "ButtonLeftAlt": 0,
        "ButtonHeightAlt": height,
        "ButtonWidthAlt": width,
        "GlobalMacroId": global_macro_id,
        "DeviceMacroId": None,
        "PageLinkId": None,
        "LinkPageId": None,
        "ButtonOrder": 0,
        "FrameNumber": 254,
    }


def _resolve_tag_macros(
    *,
    macro_rows: list[dict],
    macro_non_empty_by_id: dict[int, bool],
    step_device_ids_by_macro: dict[int, set[int]],
    layer_room_id: int | None,
    layer_source_id: int | None,
    page_room_id: int,
    page_source_device_id: int | None,
    text: str = "",
    height: int = 0,
    width: int = 0,
    global_macro_id: int | None = None,
):
    return _resolve_button(
        _NoSqlCursor(),
        _button_row(text=text, height=height, width=width, global_macro_id=global_macro_id),
        current_device_id=112,
        tag_name_by_id={8801: "Watch"},
        variables_by_tag={},
        button_text_tag_ids=set(),
        macros_by_tag={8801: macro_rows},
        macro_non_empty_by_id=macro_non_empty_by_id,
        macro_device_ids_by_macro=step_device_ids_by_macro,
        page_links_by_device_and_tag={},
        page_links_by_tag={},
        first_page_target_by_device_id={},
        page_name_by_page_id={},
        room_name_by_id={0: "Global", 3: "Den"},
        source_name_by_device_id={7: "Apple TV", 8: "Denon", 9: "Sonos"},
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
        page_room_id=page_room_id,
        current_rti_address=1,
        global_room_fallback_id=None,
        layer_id=1,
        shared_layer_id=1,
        layer_name_resolved="Layer",
        layer_room_id=layer_room_id,
        layer_source_id=layer_source_id,
        page_layer_room_id=None,
        page_layer_source_id=None,
        layer_order=0,
        button_order=0,
        frame_number=254,
        host_viewport_button_id=None,
        next_in_group_sequences={},
    )


def _winning_id(diag_button: dict) -> int | None:
    macro = diag_button["testTargets"]["macro"]
    raw = macro.get("globalMacroId")
    return None if raw is None else int(raw)


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
            or bool((user_button["testTargets"].get("graphics") or {}).get("bitmapNormal"))
            or bool((user_button["testTargets"].get("graphics") or {}).get("bitmapActive"))
            or bool((user_button["testTargets"].get("graphics") or {}).get("icon"))
            or bool((user_button["testTargets"].get("graphics") or {}).get("rtspVideo"))
            or isinstance((user_button.get("apexScopeSource") or {}).get("audioScope"), dict)
        ),
    )


class ButtonCategoryRulesTest(unittest.TestCase):
    def test_macro_ids_resolve_when_any_macro_targets_effective_source(self):
        resolved = extractor_core._macro_ids_resolve_for_effective_source(
            macro_ids=[50, 75],
            macro_non_empty_by_id={50: True, 75: True},
            macro_device_ids_by_macro={50: {9}, 75: {12}},
            effective_source_id=12,
        )
        self.assertTrue(resolved)

    def test_macro_ids_do_not_resolve_when_only_other_sources_exist(self):
        resolved = extractor_core._macro_ids_resolve_for_effective_source(
            macro_ids=[49, 74],
            macro_non_empty_by_id={49: True, 74: True},
            macro_device_ids_by_macro={49: {9}, 74: {10}},
            effective_source_id=12,
        )
        self.assertFalse(resolved)

    def test_macro_ids_resolve_when_non_empty_macro_is_source_agnostic(self):
        resolved = extractor_core._macro_ids_resolve_for_effective_source(
            macro_ids=[201],
            macro_non_empty_by_id={201: True},
            macro_device_ids_by_macro={},
            effective_source_id=12,
        )
        self.assertTrue(resolved)

    def test_hard_button_wins_over_ui_item(self):
        button = {
            "buttonIdentity": {"buttonType": None, "buttonTagName": None},
            "buttonUI": {
                "orientations": {
                    "portrait": {"coordinates": {"height": 0, "width": 0}},
                    "landscape": {"coordinates": {"height": 0, "width": 0}},
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
        self.assertEqual("hardButtons", category)

    def test_ui_item_when_empty_and_not_hard(self):
        button = {
            "buttonIdentity": {"buttonType": None, "buttonTagName": None},
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
        self.assertEqual("uiItems", category)

    def test_empty_tag_category_requires_tag_field_present(self):
        button = {
            "buttonIdentity": {"buttonType": None, "buttonTagName": ""},
            "buttonUI": {
                "orientations": {
                    "portrait": {"coordinates": {"height": 10, "width": 10}},
                    "landscape": {"coordinates": {"height": 10, "width": 10}},
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
        with_tag = extractor_core._classify_user_button_category(
            button=button,
            has_tag_field=True,
            raw_text="label",
            has_macros_target=False,
            has_any_variable_target=False,
        )
        without_tag = extractor_core._classify_user_button_category(
            button=button,
            has_tag_field=False,
            raw_text="label",
            has_macros_target=False,
            has_any_variable_target=False,
        )
        self.assertEqual("emptyTag", with_tag)
        self.assertEqual("screenButtons", without_tag)

    def test_effective_empty_tag_overrides_hard_button_when_content_missing(self):
        button = {
            "buttonIdentity": {"buttonType": None, "buttonTagName": "Channel Up"},
            "buttonUI": {
                "orientations": {
                    "portrait": {"coordinates": {"height": 0, "width": 0}},
                    "landscape": {"coordinates": {"height": 0, "width": 0}},
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
            has_tag_field=True,
            raw_text="",
            has_macros_target=False,
            has_any_variable_target=False,
            has_meaningful_tag_content=False,
        )
        self.assertEqual("emptyTag", category)

    def test_hard_button_remains_hard_button_when_meaningful_content_exists(self):
        button = {
            "buttonIdentity": {"buttonType": None, "buttonTagName": "Volume Up"},
            "buttonUI": {
                "orientations": {
                    "portrait": {"coordinates": {"height": 0, "width": 0}},
                    "landscape": {"coordinates": {"height": 0, "width": 0}},
                }
            },
            "testTargets": {
                "text": False,
                "macros": False,
                "macroSteps": True,
                "variables": {"Text": False},
                "pageLink": False,
            },
        }
        category = extractor_core._classify_user_button_category(
            button=button,
            has_tag_field=True,
            raw_text="",
            has_macros_target=False,
            has_any_variable_target=False,
            has_meaningful_tag_content=True,
        )
        self.assertEqual("hardButtons", category)

    def test_room_macro_counts_when_step_device_is_not_the_source(self):
        room_macro = _macro_row(macro_id=410, room_id=3, device_id=-1)
        step_devices = {410: {8}}
        for source_id in (7, 9):
            won = extractor_core._winning_tag_macro_id(
                [room_macro],
                effective_room_id=3,
                effective_source_id=source_id,
            )
            self.assertEqual(410, won)
        user_button, diag_button = _resolve_tag_macros(
            macro_rows=[room_macro],
            macro_non_empty_by_id={410: True},
            step_device_ids_by_macro=step_devices,
            layer_room_id=3,
            layer_source_id=7,
            page_room_id=9,
            page_source_device_id=99,
        )
        self.assertTrue(user_button["testTargets"]["macroSteps"])
        self.assertEqual(410, _winning_id(diag_button))

    def test_source_macro_counts_only_when_device_id_is_effective_source(self):
        room_source = _macro_row(macro_id=420, room_id=3, device_id=7)
        global_source = _macro_row(macro_id=421, room_id=0, device_id=7)
        self.assertEqual(
            420,
            extractor_core._winning_tag_macro_id(
                [room_source],
                effective_room_id=3,
                effective_source_id=7,
            ),
        )
        self.assertEqual(
            421,
            extractor_core._winning_tag_macro_id(
                [global_source],
                effective_room_id=3,
                effective_source_id=7,
            ),
        )
        self.assertIsNone(
            extractor_core._winning_tag_macro_id(
                [room_source],
                effective_room_id=3,
                effective_source_id=9,
            )
        )
        user_button, diag_button = _resolve_tag_macros(
            macro_rows=[room_source],
            macro_non_empty_by_id={420: True},
            step_device_ids_by_macro={420: {8}},
            layer_room_id=3,
            layer_source_id=7,
            page_room_id=3,
            page_source_device_id=7,
        )
        self.assertTrue(user_button["testTargets"]["macroSteps"])
        self.assertEqual(420, _winning_id(diag_button))

    def test_source_macro_for_another_source_does_not_count(self):
        other_source = _macro_row(macro_id=430, room_id=3, device_id=9)
        self.assertIsNone(
            extractor_core._winning_tag_macro_id(
                [other_source],
                effective_room_id=3,
                effective_source_id=7,
            )
        )
        user_button, diag_button = _resolve_tag_macros(
            macro_rows=[other_source],
            macro_non_empty_by_id={430: True},
            step_device_ids_by_macro={430: {7}},
            layer_room_id=3,
            layer_source_id=7,
            page_room_id=3,
            page_source_device_id=7,
        )
        self.assertFalse(user_button["testTargets"]["macroSteps"])
        self.assertIsNone(_winning_id(diag_button))

    def test_room_macro_wins_over_matching_source_macro(self):
        room_macro = _macro_row(macro_id=410, room_id=3, device_id=-1)
        source_macro = _macro_row(macro_id=420, room_id=3, device_id=7)
        rows = [source_macro, room_macro]
        self.assertEqual(
            410,
            extractor_core._winning_tag_macro_id(
                rows,
                effective_room_id=3,
                effective_source_id=7,
            ),
        )
        user_button, diag_button = _resolve_tag_macros(
            macro_rows=rows,
            macro_non_empty_by_id={410: True, 420: True},
            step_device_ids_by_macro={410: {8}, 420: {8}},
            layer_room_id=3,
            layer_source_id=7,
            page_room_id=3,
            page_source_device_id=7,
        )
        self.assertTrue(user_button["testTargets"]["macroSteps"])
        self.assertEqual(410, _winning_id(diag_button))

    def test_global_macro_counts_only_when_no_room_or_source_row_applies(self):
        room_macro = _macro_row(macro_id=410, room_id=3, device_id=-1)
        other_room = _macro_row(macro_id=411, room_id=4, device_id=-1)
        source_macro = _macro_row(macro_id=420, room_id=0, device_id=7)
        other_source = _macro_row(macro_id=430, room_id=0, device_id=9)
        global_macro = _macro_row(macro_id=440, room_id=0, device_id=-1)
        self.assertEqual(
            440,
            extractor_core._winning_tag_macro_id(
                [global_macro],
                effective_room_id=3,
                effective_source_id=7,
            ),
        )
        self.assertEqual(
            410,
            extractor_core._winning_tag_macro_id(
                [global_macro, room_macro],
                effective_room_id=3,
                effective_source_id=7,
            ),
        )
        self.assertEqual(
            420,
            extractor_core._winning_tag_macro_id(
                [global_macro, source_macro],
                effective_room_id=3,
                effective_source_id=7,
            ),
        )
        self.assertEqual(
            440,
            extractor_core._winning_tag_macro_id(
                [global_macro, other_source, other_room],
                effective_room_id=3,
                effective_source_id=7,
            ),
        )
        user_button, diag_button = _resolve_tag_macros(
            macro_rows=[global_macro],
            macro_non_empty_by_id={440: True},
            step_device_ids_by_macro={440: {8}},
            layer_room_id=3,
            layer_source_id=7,
            page_room_id=3,
            page_source_device_id=7,
        )
        self.assertTrue(user_button["testTargets"]["macroSteps"])
        self.assertEqual(440, _winning_id(diag_button))
        blocked, blocked_diag = _resolve_tag_macros(
            macro_rows=[global_macro, source_macro],
            macro_non_empty_by_id={440: True, 420: True},
            step_device_ids_by_macro={440: {8}, 420: {8}},
            layer_room_id=3,
            layer_source_id=7,
            page_room_id=3,
            page_source_device_id=7,
        )
        self.assertTrue(blocked["testTargets"]["macroSteps"])
        self.assertEqual(420, _winning_id(blocked_diag))

    def test_empty_winning_room_macro_does_not_set_macro_steps(self):
        room_macro = _macro_row(macro_id=410, room_id=3, device_id=-1)
        source_macro = _macro_row(macro_id=420, room_id=3, device_id=7)
        self.assertEqual(
            410,
            extractor_core._winning_tag_macro_id(
                [source_macro, room_macro],
                effective_room_id=3,
                effective_source_id=7,
            ),
        )
        user_button, diag_button = _resolve_tag_macros(
            macro_rows=[source_macro, room_macro],
            macro_non_empty_by_id={410: False, 420: True},
            step_device_ids_by_macro={410: {8}, 420: {8}},
            layer_room_id=3,
            layer_source_id=7,
            page_room_id=3,
            page_source_device_id=7,
        )
        self.assertFalse(user_button["testTargets"]["macroSteps"])
        self.assertEqual(410, _winning_id(diag_button))

    def test_explicit_system_macro_stays_when_tag_macro_adds_macro_steps(self):
        room_macro = _macro_row(macro_id=410, room_id=3, device_id=-1)
        user_button, diag_button = _resolve_tag_macros(
            macro_rows=[room_macro],
            macro_non_empty_by_id={410: True, 50: True},
            step_device_ids_by_macro={410: {8}},
            layer_room_id=3,
            layer_source_id=7,
            page_room_id=3,
            page_source_device_id=7,
            global_macro_id=50,
        )
        self.assertTrue(user_button["testTargets"]["macros"])
        self.assertTrue(user_button["testTargets"]["macroSteps"])
        self.assertEqual(410, _winning_id(diag_button))

    def test_touch_button_with_room_macro_is_screen_button_and_hard_key_stays_hard(self):
        room_macro = _macro_row(macro_id=410, room_id=3, device_id=-1)
        common = dict(
            macro_rows=[room_macro],
            macro_non_empty_by_id={410: True},
            step_device_ids_by_macro={410: {8}},
            layer_room_id=3,
            layer_source_id=7,
            page_room_id=9,
            page_source_device_id=99,
            text="Watch",
        )
        touch_button, touch_diag = _resolve_tag_macros(**common, height=40, width=80)
        hard_button, hard_diag = _resolve_tag_macros(**common, height=0, width=0)
        self.assertTrue(touch_button["testTargets"]["macroSteps"])
        self.assertEqual(410, _winning_id(touch_diag))
        self.assertEqual("screenButtons", _category(touch_button, touch_diag))
        self.assertNotEqual("screenLabels", _category(touch_button, touch_diag))
        self.assertTrue(hard_button["testTargets"]["macroSteps"])
        self.assertEqual(410, _winning_id(hard_diag))
        self.assertEqual("hardButtons", _category(hard_button, hard_diag))


if __name__ == "__main__":
    unittest.main()
