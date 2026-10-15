import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.generation import render_core
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
        self.assertRegex(html, r"class='hk-split-left' style=")
        self.assertIn("applyHkTightClusterLayout", html)
        self.assertIn("hkTouchSourceSize", html)
        self.assertIn("scheduleRtiLayout", html)

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
        from sentinel.generation.hard_keys.registry import MODELS

        design_w, design_h = MODELS["t4x"].design_size
        self.assertEqual(
            hkl.get("stripWidth"),
            render_core._hard_key_strip_width_for_height(854, design_w, design_h),
        )
        self.assertEqual(int(portrait.get("width") or 0), int(hkl.get("virtualWidth") or 0))
        self.assertGreater(int(hkl.get("virtualWidth") or 0), 480)
        self.assertIn("usableU", hkl)
        self.assertIn("padPx", hkl)

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
        self.assertIn("applyHkTightClusterLayout", html)
        self.assertIn("hkTouchSourceSize", html)
        self.assertIn("scheduleRtiLayout", html)
        self.assertIn("var(--sentinel-device-frame-ring-width)", html)
        self.assertRegex(html, r"class='hk-split-left' style=")

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

    def test_isr2_traced_strip_covers_every_slot_once(self) -> None:
        """ISR-2 strip is the traced crop, one target per ButtonLeft 128..161."""
        slot_lefts = list(range(128, 162))
        html = render_single_device_html(
            project_data=_project_data_with_hard_keys("isr2", slot_lefts),
            app_ui={"header": {"titleTemplate": "{deviceName} - {pageName}"}},
            project_stem="render_test",
        )
        self.assertIn("hk-traced-frame", html)
        self.assertIn("hk-model-isr2 hk-traced-remote", html)
        self.assertIn("data-hk-design-w='521'", html)
        self.assertIn("data-hk-design-h='971'", html)
        all_slots = [int(x) for x in re.findall(r"data-hard-key-slot='(\d+)'", html)]
        self.assertEqual(sorted(set(all_slots)), list(range(128, 162)))

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

    def test_isr4_traced_strip_covers_every_slot_once(self) -> None:
        """ISR-4 strip is the traced crop, one target per ButtonLeft 128..149."""
        slot_lefts = list(range(128, 150))
        html = render_single_device_html(
            project_data=_project_data_with_hard_keys("isr4", slot_lefts),
            app_ui={"header": {"titleTemplate": "{deviceName} - {pageName}"}},
            project_stem="render_test",
        )
        self.assertIn("hk-traced-frame", html)
        self.assertIn("hk-model-isr4 hk-traced-remote", html)
        self.assertIn("data-hk-design-w='500'", html)
        self.assertIn("data-hk-design-h='610'", html)
        all_slots = [int(x) for x in re.findall(r"data-hard-key-slot='(\d+)'", html)]
        self.assertEqual(sorted(set(all_slots)), list(range(128, 150)))

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

    def test_t4x_traced_strip_uses_shared_frame_not_flexbox_template(self) -> None:
        slot_lefts = list(range(128, 148))
        html = render_single_device_html(
            project_data=_project_data_with_hard_keys("t4x", slot_lefts),
            app_ui={"header": {"titleTemplate": "{deviceName} - {pageName}"}},
            project_stem="render_test",
        )
        self.assertIn("hk-traced-frame", html)
        self.assertIn("hk-model-t4x hk-traced-remote", html)
        self.assertIn("#363739", html)
        self.assertIn("data-hk-design-w='551'", html)
        self.assertIn("data-hk-design-h='679'", html)
        self.assertNotIn('data-sentinel-hard-key-template="1"', html)
        all_slots = [int(x) for x in re.findall(r"data-hard-key-slot='(\d+)'", html)]
        self.assertEqual(sorted(set(all_slots)), list(range(128, 148)))

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

    def test_isr2_shape_page_links_sit_on_each_label_box(self) -> None:
        """Traced shape page links use the key label box, not the full-stage hit."""
        linked_slots = (128, 129, 147)
        project_data = _project_data_with_hard_keys("isr2", list(linked_slots))
        device = project_data["devices"][0]
        device["userFacing"]["pages"].append({"pageName": "Page 2", "layers": []})
        device["diagnostics"]["pages"].append(
            {
                "pageId": 2,
                "pageName": "Page 2",
                "pageOrder": 1,
                "pageNumber": 2,
                "uiItems": [],
                "buttons": [],
                "viewports": [],
            }
        )
        hard_buttons = device["userFacing"]["pages"][0]["layers"][0]["buttonCategories"]["hardButtons"]
        for btn in hard_buttons:
            btn["testTargets"] = {
                "text": False,
                "macros": False,
                "macroSteps": False,
                "variables": {},
                "pageLink": True,
            }
            btn["resolvedPageLink"] = {"targetPageId": 2, "resolvedRoomId": None}
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
        body = html.split("<body", 1)[1].split("</body>", 1)[0]
        # PAGE_HTML_BY_INDEX repeats page 0 inside the script. Count the rendered anchors.
        markup = body.split("<script>", 1)[0]
        self.assertEqual(markup.count("class='page-link-hit'"), 3)
        link_boxes = re.findall(
            r"<div class='hk-traced-link' style='([^']*)'>(.*?)</div>",
            markup,
            flags=re.DOTALL,
        )
        self.assertEqual(len(link_boxes), 3)
        from sentinel.generation.hard_keys.isr2_trace import SHAPES

        shapes = {shape.slot: shape for shape in SHAPES}
        expected_styles: set[str] = set()
        for slot in linked_slots:
            box = shapes[slot].label_box
            self.assertIsNotNone(box)
            assert box is not None
            x, y, w, h = box
            expected_styles.add(
                "position:absolute;"
                f"left:{render_core._t2x_fmt(x)}px;"
                f"top:{render_core._t2x_fmt(y)}px;"
                f"width:{render_core._t2x_fmt(w)}px;"
                f"height:{render_core._t2x_fmt(h)}px;"
                "z-index:4;pointer-events:none"
            )
        self.assertEqual({style for style, _inner in link_boxes}, expected_styles)
        for _style, inner in link_boxes:
            self.assertEqual(inner.count("class='page-link-hit'"), 1)
        hits = re.findall(
            r"<div class='btn-wrap hk-btn-wrap hk-traced hk-traced-hit'"
            r"[^>]*style='[^']*width:521px;height:971px[^']*'[^>]*>"
            r".*?<div class='btn-pass-total' aria-hidden='true'></div></div>",
            markup,
            flags=re.DOTALL,
        )
        self.assertEqual(len(hits), 3)
        for hit in hits:
            self.assertNotIn("class='page-link-hit'", hit)


if __name__ == "__main__":
    unittest.main()
