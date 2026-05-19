import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.generation.render_core import _page_link_markup, build_device_payload, render_single_device_html


def _coords(*, top: int, left: int, height: int, width: int, font_size: int = 14) -> dict:
    return {
        "fontSize": font_size,
        "orientations": {
            "portrait": {"visible": True, "coordinates": {"top": top, "left": left, "height": height, "width": width}},
            "landscape": {"visible": True, "coordinates": {"top": top, "left": left, "height": height, "width": width}},
        },
    }


def _identity(name: str) -> dict:
    return {"buttonIdentity": {"buttonTagName": name, "text": name, "buttonType": None}}


def _hard_button(name: str, slot_key: int, button_id: int) -> dict:
    return {
        **_identity(name),
        "apexScopeSource": {"button": {"buttonId": button_id}},
        "testTargets": {"text": False, "macros": False, "macroSteps": False, "variables": {}},
    }


def _project_data_with_hard_keys(model: str, slot_lefts: list[int]) -> dict:
    hard_buttons = [_hard_button(f"HK_{i}", left, button_id=i + 1) for i, left in enumerate(slot_lefts)]
    return {
        "devices": [
            {
                "userFacing": {
                    "displayName": f"{model.upper()} Device",
                    "productModel": model,
                    "deviceUI": {
                        "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                        "landscape": {"supported": True, "resolution": {"width": 854, "height": 480}},
                    },
                    "pages": [
                        {
                            "pageName": "Page 1",
                            "layers": [
                                {
                                    "layerName": "Hard Keys",
                                    "sharedLayerId": 1,
                                    "layerOrder": 0,
                                    "isKeypadLayer": True,
                                    "buttonCategories": {
                                        "screenLabels": [],
                                        "screenButtons": [],
                                        "hardButtons": hard_buttons,
                                        "emptyTag": [],
                                        "uiItems": [],
                                    },
                                    "viewports": [],
                                    "hardKeyLayer": {
                                        "slots": [
                                            {
                                                "slotKey": left,
                                                "buttonId": idx + 1,
                                                "buttonTagId": 0,
                                                "frameNumber": 254,
                                                "buttonOrder": idx,
                                            }
                                            for idx, left in enumerate(slot_lefts)
                                        ],
                                        "gestures": [],
                                        "unmappedSlots": [],
                                    },
                                }
                            ],
                        }
                    ],
                },
                "diagnostics": {
                    "deviceId": 1,
                    "deviceName": f"{model.upper()} Device",
                    "displayName": f"{model.upper()} Device",
                    "rtiAddress": 1,
                    "isClonedController": False,
                    "rooms": [],
                    "sourceListRows": [],
                    "pages": [{"pageId": 1, "pageName": "Page 1", "pageOrder": 0, "pageNumber": 1, "uiItems": [], "buttons": [], "viewports": []}],
                },
            }
        ],
        "events": {"system": [], "macro": [], "macroStep": []},
        "source": {},
    }


def _project_data_single_screen() -> dict:
    return {
        "devices": [
            {
                "userFacing": {
                    "displayName": "iPhone Device",
                    "productModel": None,
                    "deviceUI": {
                        "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                        "landscape": {"supported": True, "resolution": {"width": 854, "height": 480}},
                    },
                    "pages": [
                        {
                            "pageName": "Page 1",
                            "layers": [
                                {
                                    "layerName": "Layer 1",
                                    "sharedLayerId": 1,
                                    "layerOrder": 0,
                                    "buttonCategories": {
                                        "screenLabels": [],
                                        "screenButtons": [
                                            {
                                                **_identity("Screen Btn"),
                                                "buttonUI": _coords(top=10, left=10, height=40, width=120),
                                                "testTargets": {"text": True, "macros": False, "macroSteps": False, "variables": {}},
                                            }
                                        ],
                                        "hardButtons": [],
                                        "emptyTag": [],
                                        "uiItems": [],
                                    },
                                    "viewports": [],
                                }
                            ],
                        }
                    ],
                },
                "diagnostics": {
                    "deviceId": 1,
                    "deviceName": "iPhone Device",
                    "displayName": "iPhone Device",
                    "rtiAddress": 1,
                    "isClonedController": False,
                    "rooms": [],
                    "sourceListRows": [],
                    "pages": [{"pageId": 1, "pageName": "Page 1", "pageOrder": 0, "pageNumber": 1, "uiItems": [], "buttons": [], "viewports": []}],
                },
            }
        ],
        "events": {"system": [], "macro": [], "macroStep": []},
        "source": {},
    }


class HardKeysSplitRenderTest(unittest.TestCase):
    def test_split_layout_emitted_for_t4x(self) -> None:
        slot_lefts = list(range(128, 148))
        html = render_single_device_html(
            project_data=_project_data_with_hard_keys("t4x", slot_lefts),
            app_ui={"header": {"titleTemplate": "{deviceName} - {pageName}"}},
            project_stem="render_test",
        )
        self.assertIn("hk-split-left", html)
        self.assertIn("hk-split-right", html)
        self.assertIn("data-hk-model=\"t4x\"", html)
        self.assertIn("hk-touch-stack", html)
        self.assertRegex(html, r"class='hk-split-left'>")
        self.assertNotRegex(html, r"class='hk-split-left' style=")
        self.assertIn("layoutHardKeyTouchColumn", html)
        self.assertIn("layoutHardKeyStripColumn", html)
        self.assertIn("layoutHardKeySplit", html)
        self.assertIn("applyHardKeySplitLayout", html)

    def test_payload_orientation_sizes_include_hard_key_layout(self) -> None:
        slot_lefts = list(range(128, 148))
        payload = build_device_payload(
            project_data=_project_data_with_hard_keys("t4x", slot_lefts),
            app_ui={"header": {"titleTemplate": "{deviceName} - {pageName}"}},
            project_stem="render_test",
        )
        portrait = (payload.get("orientationState") or {}).get("sizes", {}).get("portrait") or {}
        hkl = portrait.get("hardKeyLayout")
        self.assertIsInstance(hkl, dict)
        self.assertEqual(hkl.get("touchSourceWidth"), 480)
        self.assertEqual(hkl.get("touchSourceHeight"), 854)
        self.assertEqual(hkl.get("stripDesignWidth"), 608)
        self.assertEqual(hkl.get("stripDesignHeight"), 732)
        self.assertEqual(int(portrait.get("width") or 0), 480)

    def test_split_layout_emitted_for_isr2(self) -> None:
        slot_lefts = list(range(128, 162))
        html = render_single_device_html(
            project_data=_project_data_with_hard_keys("isr2", slot_lefts),
            app_ui={"header": {"titleTemplate": "{deviceName} - {pageName}"}},
            project_stem="render_test",
        )
        self.assertIn("hk-split-left", html)
        self.assertIn("hk-split-right", html)
        self.assertIn("data-hk-model=\"isr2\"", html)

    def test_hk_usable_split_layout_wired_in_runtime_script(self) -> None:
        """Hard-key device HTML positions columns from rtiUsableCanvas 25% / 75% anchors."""
        slot_lefts = list(range(128, 140))
        html = render_single_device_html(
            project_data=_project_data_with_hard_keys("isr4", slot_lefts),
            app_ui={"header": {"titleTemplate": "{deviceName} - {pageName}"}},
            project_stem="render_test",
        )
        self.assertIn("layoutHardKeyTouchColumn", html)
        self.assertIn("layoutHardKeyStripColumn", html)
        self.assertIn("layoutHardKeySplit", html)
        self.assertIn("applyHardKeySplitLayout", html)
        self.assertIn("layoutHardKeySplitAtScale", html)
        self.assertIn("var(--sentinel-device-frame-ring-width)", html)

    def test_hard_key_page_link_anchor_when_resolved_and_navigation_enabled(self) -> None:
        """Hard-key strip should emit page-link-hit like touchscreen buttons when link resolves."""
        hb = {
            **_identity("LinkHK"),
            "apexScopeSource": {"button": {"buttonId": 1}},
            "testTargets": {
                "text": False,
                "macros": False,
                "macroSteps": False,
                "variables": {},
                "pageLink": True,
            },
            "resolvedPageLink": {"targetPageId": 2, "resolvedRoomId": None},
        }
        project_data = {
            "devices": [
                {
                    "userFacing": {
                        "displayName": "T4X Device",
                        "productModel": "t4x",
                        "deviceUI": {
                            "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                            "landscape": {"supported": True, "resolution": {"width": 854, "height": 480}},
                        },
                        "pages": [
                            {"pageName": "Page 1", "layers": []},
                            {"pageName": "Page 2", "layers": []},
                        ],
                    },
                    "diagnostics": {
                        "deviceId": 1,
                        "deviceName": "T4X Device",
                        "displayName": "T4X Device",
                        "rtiAddress": 1,
                        "isClonedController": False,
                        "rooms": [],
                        "sourceListRows": [],
                        "pages": [
                            {"pageId": 1, "pageName": "Page 1", "pageOrder": 0, "pageNumber": 1, "uiItems": [], "buttons": [], "viewports": []},
                            {"pageId": 2, "pageName": "Page 2", "pageOrder": 1, "pageNumber": 2, "uiItems": [], "buttons": [], "viewports": []},
                        ],
                    },
                }
            ],
            "events": {"system": [], "macro": [], "macroStep": []},
            "source": {},
        }
        page = project_data["devices"][0]["userFacing"]["pages"][0]
        page["layers"] = [
            {
                "layerName": "Hard Keys",
                "sharedLayerId": 1,
                "layerOrder": 0,
                "isKeypadLayer": True,
                "buttonCategories": {
                    "screenLabels": [],
                    "screenButtons": [],
                    "hardButtons": [hb],
                    "emptyTag": [],
                    "uiItems": [],
                },
                "viewports": [],
                "hardKeyLayer": {
                    "slots": [{"slotKey": 128, "buttonId": 1, "buttonTagId": 0, "frameNumber": 254, "buttonOrder": 0}],
                    "gestures": [],
                    "unmappedSlots": [],
                },
            }
        ]
        app_ui = {
            "header": {"titleTemplate": "{deviceName} - {pageName}"},
            "appNavigation": {
                "pageLinks": {
                    "enabled": True,
                    "hoverActivationArea": {"width": 28},
                    "iconPaddingRight": 8,
                    "iconSize": 16,
                }
            },
        }
        html = render_single_device_html(
            project_data=project_data,
            app_ui=app_ui,
            project_stem="render_test",
        )
        self.assertIn("class='page-link-hit'", html)
        self.assertIn("data-target-page-index='1'", html)

    def test_next_in_group_page_link_markup_uses_rendering_page_for_successor(self) -> None:
        btn = {
            "testTargets": {"pageLink": True},
            "resolvedPageLink": {
                "resolutionPath": "nextInGroup",
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
        self.assertIn("./p2.html", html_on_p1)
        self.assertIn("data-target-page-index='1'", html_on_p1)
        html_on_p3 = _page_link_markup(btn, app_ui, targets, indexes, rendering_page_id=3)
        self.assertIn("./p1.html", html_on_p3)
        self.assertIn("data-target-page-index='0'", html_on_p3)

    def test_isr2_injects_buttons_in_data_label_slot_order_not_sequential_order(self) -> None:
        """ISR-2 DOM order is not 128..161 consecutive; strip uses registry label → ButtonLeft map."""
        from sentinel.generation.hard_keys.registry import ISR2_SLOT_BY_DATA_LABEL

        slot_lefts = list(range(128, 162))
        html = render_single_device_html(
            project_data=_project_data_with_hard_keys("isr2", slot_lefts),
            app_ui={"header": {"titleTemplate": "{deviceName} - {pageName}"}},
            project_stem="render_test",
        )
        all_slots = [int(x) for x in re.findall(r"data-hard-key-slot='(\d+)'", html)]
        self.assertGreaterEqual(len(all_slots), 34)
        # Document may emit the active page strip twice (e.g. orientation shells); first strip order is canonical.
        slots_found = all_slots[:34]
        expected = tuple(ISR2_SLOT_BY_DATA_LABEL.values())
        self.assertEqual(tuple(slots_found), expected)

    def test_split_layout_emitted_for_isr4(self) -> None:
        slot_lefts = list(range(128, 150))
        html = render_single_device_html(
            project_data=_project_data_with_hard_keys("isr4", slot_lefts),
            app_ui={"header": {"titleTemplate": "{deviceName} - {pageName}"}},
            project_stem="render_test",
        )
        self.assertIn("hk-split-left", html)
        self.assertIn("hk-split-right", html)
        self.assertIn("data-hk-model=\"isr4\"", html)

    def test_isr4_injects_buttons_in_data_label_slot_order_not_sequential_order(self) -> None:
        """ISR-4 DOM order is not 128..149 consecutive; strip uses registry label → ButtonLeft map."""
        from sentinel.generation.hard_keys.registry import ISR4_SLOT_BY_DATA_LABEL

        slot_lefts = list(range(128, 150))
        html = render_single_device_html(
            project_data=_project_data_with_hard_keys("isr4", slot_lefts),
            app_ui={"header": {"titleTemplate": "{deviceName} - {pageName}"}},
            project_stem="render_test",
        )
        all_slots = [int(x) for x in re.findall(r"data-hard-key-slot='(\d+)'", html)]
        self.assertGreaterEqual(len(all_slots), 22)
        # Document may emit the active page strip twice (e.g. orientation shells); first strip order is canonical.
        slots_found = all_slots[:22]
        expected = tuple(ISR4_SLOT_BY_DATA_LABEL.values())
        self.assertEqual(tuple(slots_found), expected)

    def test_single_screen_layout_unchanged_when_product_model_missing(self) -> None:
        html = render_single_device_html(
            project_data=_project_data_single_screen(),
            app_ui={"header": {"titleTemplate": "{deviceName} - {pageName}"}},
            project_stem="render_test",
        )
        self.assertNotIn("class='hk-split-left'", html)
        self.assertNotIn("class='hk-split-right'", html)
        self.assertNotIn("data-hk-model=", html)
        self.assertNotIn("data-sentinel-hard-key-template", html)

    def test_hard_key_template_css_in_separate_style_for_shell_copy(self) -> None:
        """Commissioning shell copies this block whole; see project_device_static_layout copyFilteredStyles."""
        slot_lefts = list(range(128, 148))
        html = render_single_device_html(
            project_data=_project_data_with_hard_keys("t4x", slot_lefts),
            app_ui={"header": {"titleTemplate": "{deviceName} - {pageName}"}},
            project_stem="render_test",
        )
        self.assertIn('data-sentinel-hard-key-template="1"', html)
        marker = html.find('data-sentinel-hard-key-template="1"')
        self.assertGreaterEqual(marker, 0)
        tail = html[marker : marker + 12000]
        self.assertIn(".frame", tail)

    def test_hard_key_buttons_carry_data_meta_for_target_wiring(self) -> None:
        slot_lefts = list(range(128, 148))
        html = render_single_device_html(
            project_data=_project_data_with_hard_keys("t4x", slot_lefts),
            app_ui={"header": {"titleTemplate": "{deviceName} - {pageName}"}},
            project_stem="render_test",
        )
        self.assertIn("data-meta=", html)
        self.assertRegex(html, r"data-hard-key-slot=['\"]128['\"]")
        self.assertRegex(html, r"data-hard-key-slot=['\"]147['\"]")


if __name__ == "__main__":
    unittest.main()
