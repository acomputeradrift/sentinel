import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.generation.render_core import render_single_device_html


def _identity(name: str) -> dict:
    return {"buttonIdentity": {"buttonTagName": name, "text": "", "buttonType": None}}


def _hard_button(name: str, slot_key: int, button_id: int) -> dict:
    return {
        **_identity(name),
        "apexScopeSource": {"button": {"buttonId": button_id}},
        "testTargets": {"text": False, "macros": False, "macroSteps": False, "variables": {}},
    }


def _t2x_project(
    *,
    slot_lefts: list[int],
    empty_tag_lefts: list[int] | None = None,
    blank_lefts: list[int] | None = None,
) -> dict:
    empty_tag_lefts = list(empty_tag_lefts or [])
    blank = set(blank_lefts or [])
    hard_buttons = [_hard_button(f"HK_{left}", left, button_id=left) for left in slot_lefts]
    empty_buttons = [
        _hard_button("" if left in blank else f"HK_{left}", left, button_id=left)
        for left in empty_tag_lefts
    ]
    slot_lefts = list(slot_lefts) + empty_tag_lefts
    return {
        "devices": [
            {
                "userFacing": {
                    "displayName": "T2x",
                    "productModel": "t2x",
                    "deviceUI": {
                        "portrait": {"supported": True, "resolution": {"width": 360, "height": 480}},
                        "landscape": {"supported": False, "resolution": {"width": 480, "height": 360}},
                    },
                    "pages": [
                        {
                            "pageName": "Apple TV",
                            "layers": [
                                {
                                    "layerName": "Touch",
                                    "sharedLayerId": 1,
                                    "layerOrder": 1,
                                    "isKeypadLayer": False,
                                    "buttonCategories": {
                                        "screenLabels": [],
                                        "screenButtons": [
                                            {
                                                **_identity("Power On"),
                                                "buttonIdentity": {"buttonTagName": "Power On", "text": "Power On", "buttonType": None},
                                                "buttonUI": {
                                                    "fontSize": 14,
                                                    "orientations": {
                                                        "portrait": {"visible": True, "coordinates": {"top": 88, "left": 10, "height": 58, "width": 168}},
                                                        "landscape": {"visible": True, "coordinates": {"top": 88, "left": 10, "height": 58, "width": 168}},
                                                    },
                                                },
                                                "testTargets": {"text": True, "macros": False, "macroSteps": False, "variables": {}},
                                            }
                                        ],
                                        "hardButtons": [],
                                        "emptyTag": [],
                                        "uiItems": [],
                                    },
                                    "viewports": [],
                                },
                                {
                                    "layerName": "Hard Keys",
                                    "sharedLayerId": 2,
                                    "layerOrder": 0,
                                    "isKeypadLayer": True,
                                    "buttonCategories": {
                                        "screenLabels": [],
                                        "screenButtons": [],
                                        "hardButtons": hard_buttons,
                                        "emptyTag": empty_buttons,
                                        "uiItems": [],
                                    },
                                    "viewports": [],
                                    "hardKeyLayer": {
                                        "slots": [
                                            {
                                                "slotKey": left,
                                                "buttonId": left,
                                                "buttonTagId": 0,
                                                "frameNumber": 254,
                                                "buttonOrder": idx,
                                            }
                                            for idx, left in enumerate(slot_lefts)
                                        ],
                                        "gestures": [],
                                        "unmappedSlots": [],
                                    },
                                },
                            ],
                        }
                    ],
                },
                "diagnostics": {
                    "deviceId": 1,
                    "deviceName": "T2x",
                    "displayName": "T2x",
                    "rtiAddress": 1,
                    "isClonedController": False,
                    "rooms": [],
                    "sourceListRows": [],
                    "pages": [{"pageId": 1, "pageName": "Apple TV", "pageOrder": 0, "pageNumber": 1, "uiItems": [], "buttons": [], "viewports": []}],
                },
            }
        ],
        "events": {"system": [], "macro": [], "macroStep": []},
        "source": {},
    }


class T2xTraceGeometryTest(unittest.TestCase):
    def test_crop_is_trace_bbox_plus_four_px(self) -> None:
        from sentinel.generation.hard_keys import t2x_trace

        self.assertEqual(t2x_trace.CROP_ORIGIN, (658, 28))
        self.assertEqual(t2x_trace.DESIGN_SIZE, (338, 958))

    def test_every_slot_128_through_179_once(self) -> None:
        from sentinel.generation.hard_keys import t2x_trace

        slots = [rect.slot for rect in t2x_trace.RECTS] + [shape.slot for shape in t2x_trace.SHAPES]
        self.assertEqual(sorted(slots), list(range(128, 180)))

    def test_top_row_slot_sits_on_the_pad(self) -> None:
        from sentinel.generation.hard_keys import t2x_trace

        top = next(rect for rect in t2x_trace.RECTS if rect.slot == 136)
        self.assertEqual((top.x, top.y, top.w, top.h), (4, 4, 74, 38))

    def test_joystick_wedges_have_no_label_box(self) -> None:
        from sentinel.generation.hard_keys import t2x_trace

        joystick = [shape for shape in t2x_trace.SHAPES if shape.slot in {166, 167, 168, 169, 170}]
        self.assertEqual(len(joystick), 5)
        self.assertTrue(all(shape.label_box is None for shape in joystick))

    def test_layout_matches_mockup_anchors(self) -> None:
        from sentinel.generation.hard_keys.t2x_trace import layout_like_mockup

        lay = layout_like_mockup(1400, 900, 360, 480)
        touch = lay["touch"]
        strip = lay["strip"]
        self.assertAlmostEqual(touch["left"] + touch["width"] / 2.0, 0.25 * 1400, places=3)
        self.assertAlmostEqual(strip["left"] + strip["width"] / 2.0, 0.75 * 1400, places=3)
        self.assertLess(strip["width"], touch["width"])
        self.assertAlmostEqual(strip["width"] / strip["height"], 338 / 958, places=4)
        self.assertLessEqual(strip["height"], 900 - 40 + 0.01)
        self.assertLessEqual(touch["height"], 900 - 40 + 0.01)


class T2xRenderTest(unittest.TestCase):
    def test_split_renders_touchscreen_and_traced_strip(self) -> None:
        html = render_single_device_html(
            project_data=_t2x_project(slot_lefts=list(range(128, 180))),
            app_ui={"header": {"titleTemplate": "{deviceName} - {pageName}"}},
            project_stem="t2x_render",
        )
        left = html.find("class='hk-split-left'")
        right = html.find("class='hk-split-right hk-model-t2x'")
        self.assertGreaterEqual(left, 0)
        self.assertGreater(right, left)
        self.assertIn("Power On", html[left:right])
        self.assertIn('data-hk-model="t2x"', html)
        self.assertIn("data-hk-design-w='338'", html)
        self.assertIn("data-hk-design-h='958'", html)
        self.assertIn("#363739", html)
        self.assertIn("hk-traced-frame", html)
        self.assertIn("layoutT2xLikeMockup", html)
        self.assertNotIn("remote.png", html)
        self.assertIn("left:4px;top:4px;width:74px;height:38px", html)
        self.assertIn(">HK_136<", html)
        slots = [int(n) for n in re.findall(r"data-hard-key-slot='(\d+)'", html)]
        self.assertEqual(sorted(set(slots)), list(range(128, 180)))
        joystick = re.search(
            r"data-hard-key-slot='167'[\s\S]*?<button class='test-btn'[^>]*>(.*?)</button>",
            html,
        )
        self.assertIsNotNone(joystick)
        assert joystick is not None
        self.assertEqual(joystick.group(1), "")
        self.assertNotIn(">HK_167<", html)

    def test_empty_tag_slots_are_drawn_in_empty_tag_red(self) -> None:
        hard = [136, 140, 171]
        empty = [n for n in range(128, 180) if n not in hard]
        html = render_single_device_html(
            project_data=_t2x_project(slot_lefts=hard, empty_tag_lefts=empty, blank_lefts=[130]),
            app_ui={"header": {"titleTemplate": "{deviceName} - {pageName}"}},
            project_stem="t2x_empty_tag",
        )
        slots = [int(n) for n in re.findall(r"data-hard-key-slot='(\d+)'", html)]
        self.assertEqual(sorted(set(slots)), list(range(128, 180)))
        self.assertIn(">HK_146<", html)
        self.assertNotIn(">HK_130<", html)
        self.assertIn(">HK_138<", html)
        self.assertRegex(
            html,
            r"data-hard-key-slot='146'[^>]*data-button-category='emptyTag'[^>]*--btn-fill-color:var\(--sentinel-fill-empty-tag\)",
        )
        self.assertRegex(
            html,
            r"data-hard-key-slot='136'[^>]*data-button-category='hardButtons'[^>]*--btn-fill-color:var\(--sentinel-fill-hard-button\)",
        )
        self.assertIn("data-hard-key-slot='138' style='fill:var(--sentinel-fill-empty-tag)'", html)
        self.assertIn("data-hard-key-slot='140' style='fill:var(--sentinel-fill-hard-button)'", html)
        self.assertIn('"categoryKey": "emptyTag"', html)
        blank = re.search(
            r"data-hard-key-slot='130'[\s\S]*?<button class='test-btn'[^>]*>(.*?)</button>",
            html,
        )
        self.assertIsNotNone(blank)
        assert blank is not None
        self.assertEqual(blank.group(1), "")
