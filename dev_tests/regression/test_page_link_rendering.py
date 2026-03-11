import unittest

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.generation.render_core import render_html


class PageLinkRenderingRegressionTest(unittest.TestCase):
    def test_page_link_overlay_renders_only_for_enabled_links(self):
        project_data = {
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
                                            "buttonIdentity": {"buttonTagName": "GO - Lights", "text": "Lights", "buttonType": None},
                                            "buttonUI": {"fontSize": 10, "coordinates": {"top": 20, "left": 20, "height": 40, "width": 120}},
                                            "testTargets": {
                                                "text": True,
                                                "macro": False,
                                                "variables": {"Text": False, "Reversed": False, "Inactive": False, "Visible": False, "Value": False, "State": False, "Command": False},
                                                "pageLink": {"enabled": True, "targetPageId": 200},
                                            },
                                        },
                                        {
                                            "buttonIdentity": {"buttonTagName": "PLAIN - Button", "text": "Plain", "buttonType": None},
                                            "buttonUI": {"fontSize": 10, "coordinates": {"top": 80, "left": 20, "height": 40, "width": 120}},
                                            "testTargets": {
                                                "text": True,
                                                "macro": False,
                                                "variables": {"Text": False, "Reversed": False, "Inactive": False, "Visible": False, "Value": False, "State": False, "Command": False},
                                                "pageLink": {"enabled": False, "targetPageId": None},
                                            },
                                        },
                                    ],
                                    "hardButtons": [],
                                },
                                "viewports": [],
                            },
                            {
                                "pageName": "Lights",
                                "buttonCategories": {"screenLabels": [], "screenButtons": [], "hardButtons": []},
                                "viewports": [],
                            },
                        ],
                    },
                    "diagnostics": {"deviceId": 1, "pages": [{"pageId": 100, "pageName": "Home"}, {"pageId": 200, "pageName": "Lights"}]},
                }
            ]
        }
        app_ui = {
            "layout": {"appCanvas": {"mode": "fit-to-content", "centerOnPage": True}, "rtiDeviceCanvas": {"fitMode": "contain", "maxScale": 1, "minScale": 0.25, "centerWithinAppCanvas": True}},
            "uiHierarchy": {"appCanvas": ["rtiDeviceCanvas", "appUI"], "rtiDeviceCanvas": ["rtiDeviceUI"], "rtiDeviceUI": ["projectButtons", "projectViewports"], "appUI": ["header", "appNavigation", "viewportNavigation"]},
            "header": {"enabled": True, "titleTemplate": "{deviceName} - {pageName}", "placement": "top"},
            "appNavigation": {"enabled": True, "placement": "canvas-adjacent", "showPageControls": True, "pageLinks": {"enabled": True, "showLinkAffordanceOnHover": True, "iconPlacement": "right-center-inside-button", "iconStyle": "inline-svg", "iconSize": 16, "iconPaddingRight": 8, "hoverActivationArea": {"width": 28, "fullButtonHeight": True}}},
            "viewportNavigation": {"enabled": False, "placement": {"previous": "canvas-left-center", "next": "canvas-right-center", "frameIndicator": "canvas-bottom-center"}, "indicatorStyle": "dots", "labels": {"previous": "Prev", "next": "Next"}, "behavior": {"wrapFrames": False}},
            "testingPopup": {"enabled": True, "titleTemplate": "{category} Test - {identity}", "includeButtonTypeInTitle": True, "showIdentity": True, "variableLabelTemplate": "Variable - {variableType}", "targetGroupStyle": "single-group-per-target", "showOnlyTrueTargets": True, "failNoteRequiredOnFail": True},
            "buttonPresentation": {"useProjectFontSize": True, "fallbackFontSize": 10, "preserveRtiCoordinates": True},
            "viewportPresentation": {"showViewportContainer": True, "renderViewportButtonsByDefault": False, "initialFrameStrategy": "defaultFrameId"},
            "state": {"persistTestResults": True, "persistViewportFrameSelection": True},
        }

        html = render_html(project_data, app_ui, project_stem="sample_project_data", device_index=0, page_index=0)
        self.assertEqual(html.count("<a class='page-link-hit'"), 1)
        self.assertIn("material-symbols-outlined", html)
        self.assertIn("link_2", html)
        self.assertIn("sample_project_data__page-1-lights.html", html)


if __name__ == "__main__":
    unittest.main()
