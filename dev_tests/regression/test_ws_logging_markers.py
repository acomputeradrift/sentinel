import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.generation.render_core import render_single_device_html


def _orientation_ui(font_size: int, top: int, left: int, height: int, width: int) -> dict:
    return {
        "fontSize": font_size,
        "orientations": {
            "portrait": {"visible": True, "coordinates": {"top": top, "left": left, "height": height, "width": width}},
            "landscape": {"visible": False, "coordinates": {"top": top, "left": left, "height": height, "width": width}},
        },
    }


def _minimal_project_data() -> dict:
    return {
        "devices": [
            {
                "userFacing": {
                    "displayName": "IST-5 (Global)",
                    "deviceUI": {
                        "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                        "landscape": {"supported": False, "resolution": {"width": 854, "height": 480}},
                    },
                    "pages": [
                        {
                            "pageName": "Home",
                            "buttonCategories": {
                                "screenLabels": [],
                                "screenButtons": [
                                    {
                                        "buttonIdentity": {"buttonTagName": "CONTROL - Presets", "text": "Presets", "buttonType": None},
                                        "buttonUI": _orientation_ui(10, 20, 20, 40, 120),
                                        "testTargets": {
                                            "text": True,
                                            "macro": False,
                                            "variables": {"Text": False, "Reversed": False, "Inactive": False, "Visible": False, "Value": False, "State": False, "Command": False},
                                            "pageLink": {"enabled": False, "targetPageId": None},
                                        },
                                    }
                                ],
                                "hardButtons": [],
                            },
                            "viewports": [],
                        }
                    ],
                },
                "diagnostics": {"deviceId": 1, "pages": [{"pageId": 100, "pageName": "Home"}]},
            }
        ]
    }


def _minimal_app_ui() -> dict:
    return {
        "layout": {
            "appCanvas": {"mode": "browser-viewport"},
            "appUIControls": {"top": 52, "bottom": 32, "left": 300, "right": 300},
            "rtiCanvas": {"deriveFromAppCanvas": True},
            "rtiDeviceCanvas": {"fitMode": "contain", "allowScaleAboveOne": True, "maxScale": 10, "minScale": 0.25, "centerWithinRtiCanvas": True},
        },
        "uiHierarchy": {"appCanvas": ["appUIControls", "rtiCanvas"], "rtiCanvas": ["rtiDeviceCanvas"], "rtiDeviceUI": ["projectButtons", "projectViewports"], "appUIControls": ["header", "appNavigation", "viewportNavigation"], "rtiDeviceCanvas": ["rtiDeviceUI"]},
        "header": {"enabled": True, "titleTemplate": "{deviceName} - {pageName}", "placement": "top"},
        "appNavigation": {"enabled": True, "placement": "canvas-adjacent", "showPageControls": True, "pageLinks": {"enabled": True, "showLinkAffordanceOnHover": True, "iconPlacement": "right-center-inside-button", "iconStyle": "inline-svg", "iconSize": 16, "iconPaddingRight": 8, "hoverActivationArea": {"width": 28, "fullButtonHeight": True}}},
        "zoomControls": {"enabled": True, "placement": {"anchor": "left-control-space", "alignTopToRtiCanvas": True, "centerHorizontallyInControlSpace": True}, "buttons": {"decrease": "-", "reset": "100%", "increase": "+"}, "zoom": {"defaultPercent": 100, "maxPercent": 200, "stepPercent": 10}, "scrollbars": {"showOnHover": True, "thickness": 10}},
        "viewportNavigation": {"enabled": False, "placement": {"previous": "canvas-left-center", "next": "canvas-right-center", "frameIndicator": "canvas-bottom-center", "edgeOffset": 36}, "indicatorStyle": "dots", "labels": {"previous": "Prev", "next": "Next"}, "behavior": {"wrapFrames": False}},
        "testingPopup": {"enabled": True, "titleTemplate": "{category} Test - {identity}", "includeButtonTypeInTitle": True, "showIdentity": True, "variableLabelTemplate": "Variable - {variableType}", "targetGroupStyle": "single-group-per-target", "showOnlyTrueTargets": True, "failNoteRequiredOnFail": True},
        "buttonPresentation": {"useProjectFontSize": True, "fallbackFontSize": 10, "preserveRtiCoordinates": True, "scaleRtiDerivedFontSizes": True},
        "viewportPresentation": {"showViewportContainer": True, "renderViewportButtonsByDefault": False, "initialFrameStrategy": "defaultFrameId"},
        "state": {"persistTestResults": True, "persistViewportFrameSelection": True},
    }


class WsLoggingMarkerTest(unittest.TestCase):
    def test_device_html_contains_tech_ws_marker(self):
        html = render_single_device_html(_minimal_project_data(), _minimal_app_ui(), project_stem="sample_project_data", device_index=0)
        self.assertIn("[tech-ws]", html)

    def test_commissioning_js_contains_ws_marker(self):
        target = ROOT / "src" / "sentinel" / "ui" / "commissioning" / "commission_tab.js"
        self.assertTrue(target.exists(), f"Missing file: {target}")
        text = target.read_text(encoding="utf-8")
        self.assertIn("[commission-ws]", text)
        self.assertIn("reconnect-sync", text)

    def test_diagnostics_js_contains_ws_marker(self):
        target = ROOT / "src" / "sentinel" / "ui" / "commissioning" / "diagnostics_tab.js"
        self.assertTrue(target.exists(), f"Missing file: {target}")
        text = target.read_text(encoding="utf-8")
        self.assertIn("[diagnostics-ws]", text)
        self.assertIn("fallback", text)

    def test_server_ws_contains_log_markers(self):
        testing = ROOT / "src" / "sentinel" / "server" / "api" / "testing.py"
        commissioning = ROOT / "src" / "sentinel" / "server" / "api" / "commissioning.py"
        self.assertTrue(testing.exists(), f"Missing file: {testing}")
        self.assertTrue(commissioning.exists(), f"Missing file: {commissioning}")
        self.assertIn("[testing-ws]", testing.read_text(encoding="utf-8"))
        self.assertIn("publish", testing.read_text(encoding="utf-8"))
        self.assertIn("broker_id", testing.read_text(encoding="utf-8"))
        self.assertIn("[commissioning-ws]", commissioning.read_text(encoding="utf-8"))
        self.assertIn("broker_id", commissioning.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
