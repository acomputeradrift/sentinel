import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.generation.render_core import render_single_device_html


def _button(tag: str, *, button_order: int, top: int) -> dict:
    return {
        "buttonIdentity": {"buttonTagName": tag, "text": tag, "buttonType": None},
        "buttonUI": {
            "fontSize": 10,
            "stack": {"layerOrder": 0, "buttonOrder": button_order, "frameNumber": 0},
            "orientations": {
                "portrait": {"visible": True, "coordinates": {"top": top, "left": 10, "height": 40, "width": 120}},
                "landscape": {"visible": False, "coordinates": {"top": top, "left": 10, "height": 40, "width": 120}},
            },
        },
        "testTargets": {
            "text": True,
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


def _app_ui() -> dict:
    return {
        "layout": {
            "appCanvas": {"mode": "browser-viewport"},
            "appUIControls": {"top": 52, "bottom": 32, "left": 240, "right": 240},
            "rtiCanvas": {"deriveFromAppCanvas": True},
            "rtiDeviceCanvas": {"fitMode": "contain", "allowScaleAboveOne": True, "maxScale": 10, "minScale": 0.25},
        },
        "header": {"enabled": True, "titleTemplate": "{deviceName} - {pageName}", "placement": "top"},
        "appNavigation": {"enabled": True, "pageLinks": {"enabled": False}},
        "zoomControls": {"enabled": False},
        "viewportNavigation": {"enabled": False},
        "testingPopup": {"enabled": True},
        "buttonPresentation": {"fallbackFontSize": 10, "scaleRtiDerivedFontSizes": True},
        "state": {},
        "layerPanel": {"enabled": False},
    }


class ButtonStackOrderRenderingRegressionTest(unittest.TestCase):
    def test_page_layer_respects_button_order_across_categories(self):
        project_data = {
            "devices": [
                {
                    "userFacing": {
                        "displayName": "RTI (Test Device)",
                        "deviceUI": {
                            "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                            "landscape": {"supported": False, "resolution": {"width": 854, "height": 480}},
                        },
                        "pages": [
                            {
                                "pageName": "Home",
                                "layers": [
                                    {
                                        "layerName": "Layer 1",
                                        "layerOrder": 0,
                                        "buttonCategories": {
                                            "screenLabels": [],
                                            "screenButtons": [_button("ACT", button_order=20, top=120)],
                                            "hardButtons": [],
                                            "uiItems": [_button("BG", button_order=0, top=100)],
                                        },
                                        "viewports": [],
                                    }
                                ],
                                "buttonCategories": {"screenLabels": [], "screenButtons": [], "hardButtons": []},
                                "viewports": [],
                            }
                        ],
                    },
                    "diagnostics": {"deviceId": 1, "pages": [{"pageId": 1, "pageName": "Home"}]},
                }
            ]
        }

        html = render_single_device_html(project_data, _app_ui(), project_stem="sample_project_data", device_index=0)
        idx_bg = html.index("data-button-tag='BG'")
        idx_act = html.index("data-button-tag='ACT'")
        self.assertLess(idx_bg, idx_act, "Expected lower buttonOrder BG to render before higher buttonOrder ACT")

    def test_viewport_layer_respects_button_order_across_categories(self):
        project_data = {
            "devices": [
                {
                    "userFacing": {
                        "displayName": "RTI (Test Device)",
                        "deviceUI": {
                            "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                            "landscape": {"supported": False, "resolution": {"width": 854, "height": 480}},
                        },
                        "pages": [
                            {
                                "pageName": "Home",
                                "layers": [
                                    {
                                        "layerName": "Layer 1",
                                        "layerOrder": 0,
                                        "buttonCategories": {"screenLabels": [], "screenButtons": [], "hardButtons": []},
                                        "viewports": [
                                            {
                                                "viewportIdentity": {"viewportButtonId": 123},
                                                "viewportUI": {
                                                    "navigationMode": "page",
                                                    "orientations": {
                                                        "portrait": {"visible": True, "coordinates": {"top": 10, "left": 20, "height": 200, "width": 300}},
                                                        "landscape": {"visible": False, "coordinates": {"top": 10, "left": 20, "height": 200, "width": 300}},
                                                    },
                                                },
                                                "layers": [
                                                    {
                                                        "layerName": "Viewport Layer",
                                                        "layerOrder": 0,
                                                        "frames": [
                                                            {
                                                                "frameId": 0,
                                                                "buttonCategories": {
                                                                    "screenLabels": [],
                                                                    "screenButtons": [_button("VP-ACT", button_order=10, top=40)],
                                                                    "hardButtons": [],
                                                                    "uiItems": [_button("VP-BG", button_order=0, top=20)],
                                                                },
                                                            }
                                                        ],
                                                    }
                                                ],
                                            }
                                        ],
                                    }
                                ],
                                "buttonCategories": {"screenLabels": [], "screenButtons": [], "hardButtons": []},
                                "viewports": [],
                            }
                        ],
                    },
                    "diagnostics": {"deviceId": 1, "pages": [{"pageId": 1, "pageName": "Home"}]},
                }
            ]
        }

        html = render_single_device_html(project_data, _app_ui(), project_stem="sample_project_data", device_index=0)
        idx_bg = html.index("data-button-tag='VP-BG'")
        idx_act = html.index("data-button-tag='VP-ACT'")
        self.assertLess(idx_bg, idx_act, "Expected lower buttonOrder VP-BG to render before higher buttonOrder VP-ACT")


if __name__ == "__main__":
    unittest.main()

