import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.generation import render_core
from sentinel.server.services import progress


def _ui_item_button() -> dict:
    return {
        "buttonIdentity": {"buttonTagName": "", "text": "", "buttonType": None},
        "buttonUI": {
            "orientations": {
                "portrait": {"visible": True, "coordinates": {"left": 1, "top": 2, "width": 30, "height": 40}},
                "landscape": {"visible": True, "coordinates": {"left": 3, "top": 4, "width": 30, "height": 40}},
            }
        },
        "testTargets": {
            "text": False,
            "macros": False,
            "macroSteps": False,
            "variables": {
                "Text": False,
                "Reversed": False,
                "Inactive": False,
                "Visible": False,
                "Value": False,
                "State": False,
                "Command": False,
                "Image": False,
                "List": False,
            },
            "pageLink": False,
        },
    }


def _empty_tag_button() -> dict:
    return {
        "buttonIdentity": {"buttonTagName": "Channel Up", "text": "", "buttonType": None},
        "buttonUI": {
            "orientations": {
                "portrait": {"visible": True, "coordinates": {"left": 1, "top": 2, "width": 30, "height": 40}},
                "landscape": {"visible": True, "coordinates": {"left": 3, "top": 4, "width": 30, "height": 40}},
            }
        },
        "testTargets": {
            "text": False,
            "macros": False,
            "macroSteps": False,
            "variables": {
                "Text": False,
                "Reversed": False,
                "Inactive": False,
                "Visible": False,
                "Value": False,
                "State": False,
                "Command": False,
                "Image": False,
                "List": False,
            },
            "graphics": {"bitmap": False, "icon": False},
            "pageLink": False,
        },
    }


class UiItemsCategoryFlowTest(unittest.TestCase):
    def test_render_runtime_uses_category_fallback_token_for_button_keys(self):
        source = (ROOT / "src" / "sentinel" / "generation" / "render_core.py").read_text(encoding="utf-8")
        self.assertEqual(source.count('const keyToken = String(label || "").trim() || categoryName || buttonName || "Button";'), 2)

    def test_render_iter_page_buttons_includes_ui_items(self):
        page = {
            "layers": [
                {
                    "layerName": "L1",
                    "layerOrder": 0,
                    "buttonCategories": {
                        "screenLabels": [],
                        "screenButtons": [],
                        "hardButtons": [],
                        "emptyTag": [],
                        "uiItems": [_ui_item_button()],
                    },
                    "viewports": [],
                }
            ]
        }
        items = render_core._iter_page_buttons(page)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0][1], "UI Item")

    def test_render_iter_viewport_buttons_includes_ui_items(self):
        page = {
            "layers": [
                {
                    "layerName": "L1",
                    "layerOrder": 0,
                    "buttonCategories": {"screenLabels": [], "screenButtons": [], "hardButtons": [], "emptyTag": [], "uiItems": []},
                    "viewports": [
                        {
                            "viewportUI": {
                                "orientations": {
                                    "portrait": {"visible": True, "coordinates": {"left": 10, "top": 10, "width": 100, "height": 100}},
                                    "landscape": {"visible": True, "coordinates": {"left": 10, "top": 10, "width": 100, "height": 100}},
                                }
                            },
                            "layers": [
                                {
                                    "layerName": "VP",
                                    "layerOrder": 0,
                                    "frames": [
                                        {
                                            "frameId": 0,
                                            "buttonCategories": {
                                                "screenLabels": [],
                                                "screenButtons": [],
                                                "hardButtons": [],
                                                "emptyTag": [],
                                                "uiItems": [_ui_item_button()],
                                            },
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        items = render_core._iter_viewport_buttons(page, "portrait")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["label"], "UI Item")

    def test_render_iter_page_buttons_includes_empty_tag(self):
        page = {
            "layers": [
                {
                    "layerName": "L1",
                    "layerOrder": 0,
                    "buttonCategories": {
                        "screenLabels": [],
                        "screenButtons": [],
                        "hardButtons": [],
                        "emptyTag": [_empty_tag_button()],
                        "uiItems": [],
                    },
                    "viewports": [],
                }
            ]
        }
        items = render_core._iter_page_buttons(page)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0][1], "Empty Tag")

    def test_render_iter_viewport_buttons_includes_empty_tag(self):
        page = {
            "layers": [
                {
                    "layerName": "L1",
                    "layerOrder": 0,
                    "buttonCategories": {"screenLabels": [], "screenButtons": [], "hardButtons": [], "emptyTag": [], "uiItems": []},
                    "viewports": [
                        {
                            "viewportUI": {
                                "orientations": {
                                    "portrait": {"visible": True, "coordinates": {"left": 10, "top": 10, "width": 100, "height": 100}},
                                    "landscape": {"visible": True, "coordinates": {"left": 10, "top": 10, "width": 100, "height": 100}},
                                }
                            },
                            "layers": [
                                {
                                    "layerName": "VP",
                                    "layerOrder": 0,
                                    "frames": [
                                        {
                                            "frameId": 0,
                                            "buttonCategories": {
                                                "screenLabels": [],
                                                "screenButtons": [],
                                                "hardButtons": [],
                                                "emptyTag": [_empty_tag_button()],
                                                "uiItems": [],
                                            },
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        items = render_core._iter_viewport_buttons(page, "portrait")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["label"], "Empty Tag")

    def test_progress_iter_page_buttons_includes_ui_items(self):
        page = {
            "layers": [
                {
                    "buttonCategories": {
                        "screenLabels": [],
                        "screenButtons": [],
                        "hardButtons": [],
                        "emptyTag": [],
                        "uiItems": [_ui_item_button()],
                    },
                    "viewports": [],
                }
            ]
        }
        items = progress._iter_page_buttons(page)
        self.assertEqual(len(items), 1)

    def test_progress_iter_page_buttons_includes_empty_tag(self):
        page = {
            "layers": [
                {
                    "buttonCategories": {
                        "screenLabels": [],
                        "screenButtons": [],
                        "hardButtons": [],
                        "emptyTag": [_empty_tag_button()],
                        "uiItems": [],
                    },
                    "viewports": [],
                }
            ]
        }
        items = progress._iter_page_buttons(page)
        self.assertEqual(len(items), 1)


if __name__ == "__main__":
    unittest.main()
