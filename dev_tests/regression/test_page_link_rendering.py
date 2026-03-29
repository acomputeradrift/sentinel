import unittest

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.generation.render_core import render_project_home_html, render_single_device_html


def orientation_ui(font_size: int, top: int, left: int, height: int, width: int) -> dict:
    return {
        "fontSize": font_size,
        "orientations": {
            "portrait": {
                "visible": True,
                "coordinates": {"top": top, "left": left, "height": height, "width": width},
            },
            "landscape": {
                "visible": False,
                "coordinates": {"top": top, "left": left, "height": height, "width": width},
            },
        },
    }


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
                                            "buttonUI": orientation_ui(10, 20, 20, 40, 120),
                                            "testTargets": {
                                                "text": True,
                                                "macro": False,
                                                "variables": {"Text": False, "Reversed": False, "Inactive": False, "Visible": False, "Value": False, "State": False, "Command": False},
                                                "pageLink": {"enabled": True, "targetPageId": 200},
                                            },
                                            "resolvedPageLink": {"targetPageId": 200},
                                        },
                                        {
                                            "buttonIdentity": {"buttonTagName": "PLAIN - Button", "text": "Plain", "buttonType": None},
                                            "buttonUI": orientation_ui(10, 80, 20, 40, 120),
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

        html = render_single_device_html(project_data, app_ui, project_stem="sample_project_data", device_index=0)
        self.assertEqual(html.count("<a class='page-link-hit'"), 1)
        self.assertIn("material-symbols-outlined", html)
        self.assertIn("link_2", html)
        self.assertIn("opacity:1;pointer-events:auto;", html)
        self.assertIn("class='test-btn fill-screen-control state-untested'", html)
        self.assertIn("<span class='test-btn-count' aria-hidden='true'>0/0</span>", html)
        self.assertIn("sample_project_data__device-0-ist-5-global.html", html)
        self.assertIn("data-target-page-index='1'", html)
        self.assertIn("class='project-home-link' href='sample_project_data__project-home.html'", html)

    def test_project_home_event_rows_use_standard_popup_button_contract(self):
        project_data = {
            "source": {"file": r"C:\\Projects\\sample.apex", "extractedAtUtc": "2026-03-13T00:00:00Z", "scriptVersion": "0.1.0"},
            "events": {
                "system": [
                    {
                        "userFacing": {
                            "eventType": "Sense",
                            "description": "Hall Motion",
                            "resolvedTrigger": "Hall Sensor",
                            "macroName": "Hall Lights",
                            "testTargets": {"Trigger": True, "Macro": True},
                        }
                    }
                ],
                "driver": [],
            },
            "devices": [],
        }
        app_ui = {
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

        html = render_project_home_html(project_data, app_ui, project_stem="sample_project_data")
        self.assertIn('"Hall Motion" | Hall Sensor, run macro: Hall Lights', html)
        self.assertIn("class='home-row event-row test-btn fill-screen-control state-untested'", html)
        self.assertIn("<span class='test-btn-count' aria-hidden='true'>0/0</span>", html)
        self.assertIn('"targets": ["Trigger", "Macro"]', html)
        self.assertIn("function esc(s)", html)

    def test_single_device_page_links_include_client_side_target_indexes(self):
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
                                            "buttonUI": orientation_ui(10, 20, 20, 40, 120),
                                            "testTargets": {
                                                "text": True,
                                                "macro": False,
                                                "variables": {"Text": False, "Reversed": False, "Inactive": False, "Visible": False, "Value": False, "State": False, "Command": False},
                                                "pageLink": {"enabled": True, "targetPageId": 200},
                                            },
                                            "resolvedPageLink": {"targetPageId": 200},
                                        }
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

        html = render_single_device_html(project_data, app_ui, project_stem="sample_project_data", device_index=0)
        self.assertIn("data-target-page-index='1'", html)
        self.assertIn("setActivePage(targetPageIndex)", html)
        self.assertIn("class='device-page active' data-page-index='0'", html)
        self.assertIn("class='device-page' data-page-index='1'", html)


if __name__ == "__main__":
    unittest.main()
