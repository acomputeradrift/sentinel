import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.extraction.extractor_core import _resolve_button
from sentinel.generation.render_core import _page_link_markup, _page_link_target_id


class _NoSqlCursor:
    def execute(self, _sql, _params=()):
        raise AssertionError("No SQL queries are expected in _resolve_button for page-link resolution")


def _button_row() -> dict:
    return {
        "ButtonId": 201,
        "ButtonTagId": 88,
        "Text": "Prev",
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


def _resolve_group_link(link_type: int) -> dict:
    page_link_row = {
        "PageLinkId": 501,
        "LinkType": link_type,
        "PageId": -1,
    }
    user_button, _diag_button = _resolve_button(
        _NoSqlCursor(),
        _button_row(),
        current_device_id=1,
        tag_name_by_id={88: "PREV"},
        variables_by_tag={},
        button_text_tag_ids=set(),
        macros_by_tag={},
        macro_non_empty_by_id={},
        macro_device_ids_by_macro={},
        page_links_by_device_and_tag={},
        page_links_by_tag={88: page_link_row},
        first_page_target_by_device_id={},
        page_name_by_page_id={1: "Home", 21: "Power Off"},
        room_name_by_id={1: "Room"},
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
        page_id=21,
        page_source_device_id=5,
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
        next_in_group_sequences={(1, 5, 1): [1, 21]},
    )
    resolved = user_button["resolvedPageLink"]
    if not isinstance(resolved, dict):
        raise AssertionError(f"expected resolvedPageLink dict, got {resolved!r}")
    return resolved


class PreviousInGroupPageLinkTest(unittest.TestCase):
    def test_link_types_3_and_254_resolve_previous_in_group(self) -> None:
        for link_type in (254, 3):
            resolved = _resolve_group_link(link_type)
            self.assertEqual(resolved.get("resolutionPath"), "previousInGroup", link_type)
            self.assertEqual(resolved.get("groupPageIds"), [1, 21], link_type)
            self.assertEqual(resolved.get("anchorPageId"), 21, link_type)
            self.assertNotEqual(resolved.get("targetPageId"), -1, link_type)

    def test_link_type_2_still_resolves_next_in_group(self) -> None:
        resolved = _resolve_group_link(2)
        self.assertEqual(resolved.get("resolutionPath"), "nextInGroup")
        self.assertEqual(resolved.get("groupPageIds"), [1, 21])
        self.assertEqual(resolved.get("anchorPageId"), 21)
        self.assertNotEqual(resolved.get("targetPageId"), -1)

    def test_previous_in_group_markup_steps_backward_and_wraps(self) -> None:
        btn = {
            "testTargets": {"pageLink": True},
            "resolvedPageLink": {
                "resolutionPath": "previousInGroup",
                "groupPageIds": [1, 2, 3],
                "anchorPageId": 1,
            },
        }
        app_ui = {
            "appNavigation": {
                "pageLinks": {
                    "enabled": True,
                    "hoverActivationArea": {"width": 28},
                    "iconPaddingRight": 8,
                    "iconSize": 16,
                }
            }
        }
        targets = {1: "./p1.html", 2: "./p2.html", 3: "./p3.html"}
        indexes = {1: 0, 2: 1, 3: 2}
        html_on_p1 = _page_link_markup(btn, app_ui, targets, indexes, rendering_page_id=1)
        self.assertIn("./p3.html", html_on_p1)
        self.assertIn("data-target-page-index='2'", html_on_p1)
        html_on_p2 = _page_link_markup(btn, app_ui, targets, indexes, rendering_page_id=2)
        self.assertIn("./p1.html", html_on_p2)
        self.assertIn("data-target-page-index='0'", html_on_p2)
        html_on_p3 = _page_link_markup(btn, app_ui, targets, indexes, rendering_page_id=3)
        self.assertIn("./p2.html", html_on_p3)
        self.assertIn("data-target-page-index='1'", html_on_p3)

        power_off = {
            "resolvedPageLink": {
                "resolutionPath": "previousInGroup",
                "groupPageIds": [1, 21],
                "anchorPageId": 21,
            }
        }
        self.assertEqual(_page_link_target_id(power_off, rendering_page_id=21), 1)
        self.assertEqual(_page_link_target_id(power_off, rendering_page_id=1), 21)


if __name__ == "__main__":
    unittest.main()
