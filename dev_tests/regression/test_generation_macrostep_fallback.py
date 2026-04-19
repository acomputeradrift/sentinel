import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.generation.render_core import render_single_device_html


def _app_ui() -> dict:
    return {
        "layout": {
            "appCanvas": {"mode": "browser-viewport"},
            "appUIControls": {"top": 52, "bottom": 32, "left": 300, "right": 300},
            "rtiCanvas": {"deriveFromAppCanvas": True},
            "rtiDeviceCanvas": {
                "fitMode": "contain",
                "allowScaleAboveOne": True,
                "maxScale": 10,
                "minScale": 0.25,
                "centerWithinRtiCanvas": True,
            },
        },
        "uiHierarchy": {
            "appCanvas": ["appUIControls", "rtiCanvas"],
            "rtiCanvas": ["rtiDeviceCanvas"],
            "rtiDeviceUI": ["projectButtons", "projectViewports"],
            "appUIControls": ["header", "appNavigation", "viewportNavigation"],
            "rtiDeviceCanvas": ["rtiDeviceUI"],
        },
        "header": {"enabled": True, "titleTemplate": "{deviceName} - {pageName}", "placement": "top"},
        "appNavigation": {
            "enabled": True,
            "placement": "canvas-adjacent",
            "showPageControls": True,
            "pageLinks": {
                "enabled": True,
                "showLinkAffordanceOnHover": True,
                "iconPlacement": "right-center-inside-button",
                "iconStyle": "inline-svg",
                "iconSize": 16,
                "iconPaddingRight": 8,
                "hoverActivationArea": {"width": 28, "fullButtonHeight": True},
            },
        },
        "zoomControls": {
            "enabled": True,
            "placement": {
                "anchor": "left-control-space",
                "alignTopToRtiCanvas": True,
                "centerHorizontallyInControlSpace": True,
            },
            "buttons": {"decrease": "-", "reset": "100%", "increase": "+"},
            "zoom": {"defaultPercent": 100, "maxPercent": 200, "stepPercent": 10},
            "scrollbars": {"showOnHover": True, "thickness": 10},
        },
        "viewportNavigation": {
            "enabled": False,
            "placement": {
                "previous": "canvas-left-center",
                "next": "canvas-right-center",
                "frameIndicator": "canvas-bottom-center",
                "edgeOffset": 36,
            },
            "indicatorStyle": "dots",
            "labels": {"previous": "Prev", "next": "Next"},
            "behavior": {"wrapFrames": False},
        },
        "testingPopup": {
            "enabled": True,
            "titleTemplate": "{category} Test - {identity}",
            "includeButtonTypeInTitle": True,
            "showIdentity": True,
            "variableLabelTemplate": "Variable - {variableType}",
            "targetGroupStyle": "single-group-per-target",
            "showOnlyTrueTargets": True,
            "failNoteRequiredOnFail": True,
        },
        "buttonPresentation": {
            "useProjectFontSize": True,
            "fallbackFontSize": 10,
            "preserveRtiCoordinates": True,
            "scaleRtiDerivedFontSizes": True,
        },
        "viewportPresentation": {
            "showViewportContainer": True,
            "renderViewportButtonsByDefault": False,
            "initialFrameStrategy": "defaultFrameId",
        },
        "state": {"persistTestResults": True, "persistViewportFrameSelection": True},
    }


class GenerationMacroStepFallbackTest(unittest.TestCase):
    def test_render_includes_macrostep_fallback_key_logic_and_target_label(self):
        project_data = {
            "devices": [
                {
                    "userFacing": {
                        "displayName": "Device A",
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
                                            "buttonIdentity": {"buttonTagName": "TAG-1", "text": "Btn", "buttonType": None},
                                            "buttonUI": {
                                                "fontSize": 10,
                                                "orientations": {
                                                    "portrait": {"visible": True, "coordinates": {"top": 1, "left": 1, "height": 10, "width": 10}},
                                                    "landscape": {"visible": False, "coordinates": {"top": 1, "left": 1, "height": 10, "width": 10}},
                                                },
                                                "stack": {"layerOrder": 0, "buttonOrder": 0, "frameNumber": 0},
                                            },
                                            "testTargets": {
                                                "text": False,
                                                "macros": False,
                                                "macroSteps": True,
                                                "variables": {},
                                                "graphics": {"bitmap": False, "icon": False},
                                                "pageLink": False,
                                            },
                                            "apexScopeSource": {
                                                "page": {"pageId": 513, "roomId": 23, "sourceDeviceId": 74, "rtiAddress": 2},
                                                "viewportLayer": {"layerId": 300, "sharedLayerId": 700, "roomId": 23, "sourceId": 74},
                                                "pageLayer": {"roomId": None, "sourceId": None},
                                                "button": {"buttonId": 48551, "buttonTagId": 20},
                                                "bindings": {"macroIds": [3122], "variableIds": [], "macroStepIds": [], "pageLinkId": None},
                                            },
                                        }
                                    ],
                                    "hardButtons": [],
                                    "uiItems": [],
                                },
                                "viewports": [],
                            }
                        ],
                    },
                    "diagnostics": {
                        "deviceId": 81,
                        "pages": [
                            {
                                "pageId": 513,
                                "buttons": [{"buttonId": 48551, "buttonTagName": "TAG-1", "identifiers": {"text": "Btn"}}],
                                "viewports": [],
                            }
                        ],
                    },
                }
            ]
        }

        html = render_single_device_html(project_data, _app_ui(), project_stem="sample_project_data", device_index=0)
        self.assertIn('"targets": ["Macro Step"]', html)
        self.assertIn("mstepmacro:${firstMacroId}", html)


if __name__ == "__main__":
    unittest.main()

