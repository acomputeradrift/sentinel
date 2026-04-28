import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.generation.render_core import render_single_device_html


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


def _hard_button(name: str, slot_key: int) -> dict:
    return {
        **_identity(name),
        "buttonUI": _coords(top=0, left=slot_key, height=0, width=0, font_size=12),
        "testTargets": {"text": False, "macros": False, "macroSteps": False, "variables": {}},
    }


def _project_data_with_hard_keys(model: str, slot_lefts: list[int]) -> dict:
    hard_buttons = [_hard_button(f"HK_{i}", left) for i, left in enumerate(slot_lefts)]
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

    def test_single_screen_layout_unchanged_when_product_model_missing(self) -> None:
        html = render_single_device_html(
            project_data=_project_data_single_screen(),
            app_ui={"header": {"titleTemplate": "{deviceName} - {pageName}"}},
            project_stem="render_test",
        )
        self.assertNotIn("class='hk-split-left'", html)
        self.assertNotIn("class='hk-split-right'", html)
        self.assertNotIn("data-hk-model=", html)

    def test_hard_key_buttons_carry_data_meta_for_target_wiring(self) -> None:
        slot_lefts = list(range(128, 148))
        html = render_single_device_html(
            project_data=_project_data_with_hard_keys("t4x", slot_lefts),
            app_ui={"header": {"titleTemplate": "{deviceName} - {pageName}"}},
            project_stem="render_test",
        )
        self.assertIn("data-meta=", html)
        self.assertIn("data-hard-key-slot=\"128\"", html)
        self.assertIn("data-hard-key-slot=\"147\"", html)


if __name__ == "__main__":
    unittest.main()
