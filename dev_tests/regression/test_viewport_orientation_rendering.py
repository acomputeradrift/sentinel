import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.generation.render_core import render_single_device_html


def oriented_ui(*, font_size: int = 10, portrait: dict, landscape: dict) -> dict:
    return {
        "fontSize": font_size,
        "orientations": {
            "portrait": {"visible": bool(portrait.get("visible", True)), "coordinates": dict(portrait.get("coordinates", {}))},
            "landscape": {"visible": bool(landscape.get("visible", True)), "coordinates": dict(landscape.get("coordinates", {}))},
        },
    }


class ViewportOrientationRenderingRegressionTest(unittest.TestCase):
    def test_viewport_boxes_respect_orientation_visibility_on_toggle(self):
        project_data = {
            "devices": [
                {
                    "userFacing": {
                        "displayName": "RTI (Test Device)",
                        "deviceUI": {
                            "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                            "landscape": {"supported": True, "resolution": {"width": 854, "height": 480}},
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
                                                        "landscape": {"visible": False, "coordinates": {"top": 5, "left": 8, "height": 210, "width": 310}},
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
                                                                    "hardButtons": [],
                                                                    "screenButtons": [
                                                                        {
                                                                            "buttonIdentity": {"buttonTagName": "VP Child", "text": "VP Child", "buttonType": None},
                                                                            # Child claims landscape-visible, but must be gated by the viewport’s own visibility.
                                                                            "buttonUI": oriented_ui(
                                                                                font_size=10,
                                                                                portrait={"visible": True, "coordinates": {"top": 7, "left": 11, "height": 40, "width": 60}},
                                                                                landscape={"visible": True, "coordinates": {"top": 9, "left": 13, "height": 41, "width": 61}},
                                                                            ),
                                                                            "testTargets": {
                                                                                "text": True,
                                                                                "macros": False,
                                                                                "macroSteps": True,
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
                                                                    ],
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

        # Minimal app UI config sufficient for render_single_device_html.
        app_ui = {
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

        html = render_single_device_html(project_data, app_ui, project_stem="sample_project_data", device_index=0)

        # Viewport boxes already carry per-orientation visibility flags.
        self.assertIn("class='vp-box'", html)
        self.assertIn("data-p-visible='1'", html)
        self.assertIn("data-l-visible='0'", html)

        # Regression: viewport boxes must participate in orientation-based visibility.
        self.assertIn("const visKey=`${short}Visible`", html)
        self.assertIn("const baseVisible=String(el.dataset.visible||'1')==='1';", html)

        # Regression: applyLayerVisibility must not overwrite shouldShow for vp-btns in a way that drops
        # viewport visibility gating (vpVisible/baseVisible). This exact bug reproduces the UI symptom.
        self.assertIn("shouldShow=shouldShow && Number(el.dataset.frame)===activeFrame;", html)

        # Viewport child buttons must not be shown in an orientation where the viewport container is hidden.
        # This is enforced by carrying viewport-visibility info into the vp-btn itself.
        m = re.search(r"<div class='btn-wrap vp-btn'[^>]*data-button-tag='VP Child'[^>]*>", html)
        self.assertIsNotNone(m, "Expected VP child button wrapper to be rendered")
        btn_tag = m.group(0)
        self.assertIn("data-vp-pv='1'", btn_tag)
        self.assertIn("data-vp-lv='0'", btn_tag)

        # Coordinate fidelity: orientation coordinates should be viewport-offset + child coords.
        # Portrait viewport left/top = 20/10, child left/top = 11/7 -> 31/17
        self.assertIn("data-p-left='31'", btn_tag)
        self.assertIn("data-p-top='17'", btn_tag)
        # Landscape viewport left/top = 8/5, child left/top = 13/9 -> 21/14
        self.assertIn("data-l-left='21'", btn_tag)
        self.assertIn("data-l-top='14'", btn_tag)

    def test_landscape_only_viewport_is_still_emitted_into_html(self):
        project_data = {
            "devices": [
                {
                    "userFacing": {
                        "displayName": "RTI (Test Device)",
                        "deviceUI": {
                            "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                            "landscape": {"supported": True, "resolution": {"width": 854, "height": 480}},
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
                                                "viewportIdentity": {"viewportButtonId": 456},
                                                "viewportUI": {
                                                    "navigationMode": "verticalScroll",
                                                    "orientations": {
                                                        "portrait": {"visible": False, "coordinates": {"top": 10, "left": 20, "height": 200, "width": 300}},
                                                        "landscape": {"visible": True, "coordinates": {"top": 5, "left": 8, "height": 210, "width": 310}},
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
                                                                    "hardButtons": [],
                                                                    "screenButtons": [
                                                                        {
                                                                            "buttonIdentity": {"buttonTagName": "Land VP Child", "text": "Land VP Child", "buttonType": None},
                                                                            "buttonUI": oriented_ui(
                                                                                font_size=10,
                                                                                portrait={"visible": False, "coordinates": {"top": 7, "left": 11, "height": 40, "width": 60}},
                                                                                landscape={"visible": True, "coordinates": {"top": 9, "left": 13, "height": 41, "width": 61}},
                                                                            ),
                                                                            "testTargets": {
                                                                                "text": True,
                                                                                "macros": False,
                                                                                "macroSteps": True,
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
                                                                    ],
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

        app_ui = {
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

        html = render_single_device_html(project_data, app_ui, project_stem="sample_project_data", device_index=0)

        # Regression: landscape-only viewports must still be emitted so an orientation toggle can reveal them.
        self.assertIn("class='vp-box'", html)
        self.assertIn("data-p-visible='0'", html)
        self.assertIn("data-l-visible='1'", html)

        m = re.search(r"<div class='btn-wrap vp-btn'[^>]*data-button-tag='Land VP Child'[^>]*>", html)
        self.assertIsNotNone(m, "Expected landscape-only VP child button wrapper to be rendered")
        btn_tag = m.group(0)
        self.assertIn("data-vp-pv='0'", btn_tag)
        self.assertIn("data-vp-lv='1'", btn_tag)

    def test_viewport_navigation_targets_active_visible_viewport(self):
        project_data = {
            "devices": [
                {
                    "userFacing": {
                        "displayName": "RTI (Test Device)",
                        "deviceUI": {
                            "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                            "landscape": {"supported": True, "resolution": {"width": 854, "height": 480}},
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
                                                "viewportIdentity": {"viewportButtonId": 1},
                                                "viewportUI": {
                                                    "navigationMode": "page",
                                                    "orientations": {
                                                        "portrait": {"visible": True, "coordinates": {"top": 10, "left": 20, "height": 200, "width": 300}},
                                                        "landscape": {"visible": False, "coordinates": {"top": 5, "left": 8, "height": 210, "width": 310}},
                                                    },
                                                },
                                                "layers": [{"layerName": "VP0", "layerOrder": 0, "frames": [{"frameId": 0, "buttonCategories": {"screenLabels": [], "hardButtons": [], "screenButtons": []}}]}],
                                            },
                                            {
                                                "viewportIdentity": {"viewportButtonId": 2},
                                                "viewportUI": {
                                                    "navigationMode": "verticalScroll",
                                                    "orientations": {
                                                        "portrait": {"visible": False, "coordinates": {"top": 300, "left": 20, "height": 200, "width": 300}},
                                                        "landscape": {"visible": True, "coordinates": {"top": 30, "left": 40, "height": 210, "width": 310}},
                                                    },
                                                },
                                                "layers": [{"layerName": "VP1", "layerOrder": 0, "frames": [{"frameId": 7, "buttonCategories": {"screenLabels": [], "hardButtons": [], "screenButtons": []}}]}],
                                            },
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

        app_ui = {
            "layout": {
                "appCanvas": {"mode": "browser-viewport"},
                "appUIControls": {"top": 52, "bottom": 32, "left": 240, "right": 240},
                "rtiCanvas": {"deriveFromAppCanvas": True},
                "rtiDeviceCanvas": {"fitMode": "contain", "allowScaleAboveOne": True, "maxScale": 10, "minScale": 0.25},
            },
            "header": {"enabled": True, "titleTemplate": "{deviceName} - {pageName}", "placement": "top"},
            "appNavigation": {"enabled": True, "pageLinks": {"enabled": False}},
            "zoomControls": {"enabled": False},
            "viewportNavigation": {"enabled": True},
            "testingPopup": {"enabled": True},
            "buttonPresentation": {"fallbackFontSize": 10, "scaleRtiDerivedFontSizes": True},
            "state": {},
            "layerPanel": {"enabled": False},
        }

        html = render_single_device_html(project_data, app_ui, project_stem="sample_project_data", device_index=0)

        # Viewport boxes must be tagged with their viewport index so JS can target the active one.
        self.assertIn("class='vp-box'", html)
        self.assertIn("data-vp='0'", html)
        self.assertIn("data-vp='1'", html)

        # Regression: viewport nav logic must not hard-code viewport index 0.
        self.assertIn("function activeViewportIndex()", html)
        self.assertIn("const vpIndex=activeViewportIndex();", html)
        self.assertNotIn("currentViewportIndexes[0]--", html)
        self.assertNotIn("currentViewportIndexes[0]++", html)

    def test_viewport_view_mode_emits_popup_scaffold(self):
        project_data = {
            "devices": [
                {
                    "userFacing": {
                        "displayName": "RTI (Test Device)",
                        "deviceUI": {
                            "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                            "landscape": {"supported": True, "resolution": {"width": 854, "height": 480}},
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
                                                "viewportIdentity": {"viewportButtonId": 10},
                                                "viewportUI": {
                                                    "navigationMode": "page",
                                                    "orientations": {
                                                        "portrait": {"visible": True, "coordinates": {"top": 10, "left": 20, "height": 200, "width": 300}},
                                                        "landscape": {"visible": True, "coordinates": {"top": 5, "left": 8, "height": 210, "width": 310}},
                                                    },
                                                },
                                                "layers": [
                                                    {
                                                        "layerName": "Viewport Layer",
                                                        "layerOrder": 0,
                                                        "frames": [
                                                            {
                                                                "frameId": 0,
                                                                "buttonCategories": {"screenLabels": [], "hardButtons": [], "screenButtons": []},
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

        app_ui = {
            "layout": {
                "appCanvas": {"mode": "browser-viewport"},
                "appUIControls": {"top": 52, "bottom": 32, "left": 240, "right": 240},
                "rtiCanvas": {"deriveFromAppCanvas": True},
                "rtiDeviceCanvas": {"fitMode": "contain", "allowScaleAboveOne": True, "maxScale": 10, "minScale": 0.25},
            },
            "header": {"enabled": True, "titleTemplate": "{deviceName} - {pageName}", "placement": "top"},
            "appNavigation": {"enabled": True, "pageLinks": {"enabled": False}},
            "zoomControls": {"enabled": True},
            "viewportNavigation": {"enabled": True},
            "testingPopup": {"enabled": True},
            "buttonPresentation": {"fallbackFontSize": 10, "scaleRtiDerivedFontSizes": True},
            "state": {},
            "layerPanel": {"enabled": True},
        }

        html = render_single_device_html(project_data, app_ui, project_stem="sample_project_data", device_index=0)
        self.assertIn("id='vpOverlay'", html)
        self.assertIn("id='vpPopup'", html)
        self.assertIn("id='vpPopupPanel'", html)
        self.assertIn("id='vpPopupScroller'", html)
        self.assertIn("id='vpPopupStage'", html)
        self.assertIn("id='vpPopupClose'", html)
        self.assertIn("function enterViewportMode", html)
        self.assertIn("function exitViewportMode", html)
        self.assertIn("viewportMode", html)

    def test_viewport_view_mode_wires_handlers_and_matches_nav_mode_controls(self):
        project_data = {
            "devices": [
                {
                    "userFacing": {
                        "displayName": "RTI (Test Device)",
                        "deviceUI": {
                            "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                            "landscape": {"supported": True, "resolution": {"width": 854, "height": 480}},
                        },
                        "pages": [
                            {
                                "pageName": "Home",
                                "layers": [
                                    {
                                        "layerName": "Base Layer",
                                        "layerOrder": 0,
                                        "buttonCategories": {
                                            "screenLabels": [],
                                            "screenButtons": [
                                                {
                                                    "buttonIdentity": {"buttonTagName": "Outside", "text": "Outside", "buttonType": None},
                                                    "buttonUI": oriented_ui(
                                                        portrait={"visible": True, "coordinates": {"top": 20, "left": 20, "height": 44, "width": 120}},
                                                        landscape={"visible": True, "coordinates": {"top": 20, "left": 20, "height": 44, "width": 120}},
                                                    ),
                                                    "testTargets": {"text": True, "macros": False, "macroSteps": False, "variables": {}},
                                                }
                                            ],
                                            "hardButtons": [],
                                        },
                                        "viewports": [
                                            {
                                                "viewportIdentity": {"viewportButtonId": 123},
                                                "viewportUI": {
                                                    "navigationMode": "vertical",
                                                    "orientations": {
                                                        "portrait": {"visible": True, "coordinates": {"top": 100, "left": 50, "height": 200, "width": 300}},
                                                        "landscape": {"visible": True, "coordinates": {"top": 80, "left": 30, "height": 180, "width": 320}},
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
                                                                    "hardButtons": [],
                                                                    "screenButtons": [
                                                                        {
                                                                            "buttonIdentity": {
                                                                                "buttonTagName": "VP Child",
                                                                                "text": "VP Child",
                                                                                "buttonType": None,
                                                                            },
                                                                            "buttonUI": oriented_ui(
                                                                                portrait={
                                                                                    "visible": True,
                                                                                    "coordinates": {"top": 10, "left": 10, "height": 44, "width": 120},
                                                                                },
                                                                                landscape={
                                                                                    "visible": True,
                                                                                    "coordinates": {"top": 10, "left": 10, "height": 44, "width": 120},
                                                                                },
                                                                            ),
                                                                            "testTargets": {"text": True, "macros": False, "macroSteps": False, "variables": {}},
                                                                        }
                                                                    ],
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

        app_ui = {
            "layout": {
                "appCanvas": {"mode": "browser-viewport"},
                "appUIControls": {"top": 52, "bottom": 32, "left": 240, "right": 240},
                "rtiCanvas": {"deriveFromAppCanvas": True},
                "rtiDeviceCanvas": {"fitMode": "contain", "allowScaleAboveOne": True, "maxScale": 10, "minScale": 0.25},
            },
            "header": {"enabled": True, "titleTemplate": "{deviceName} - {pageName}", "placement": "top"},
            "appNavigation": {"enabled": True, "pageLinks": {"enabled": False}},
            "zoomControls": {"enabled": True},
            "viewportNavigation": {"enabled": True},
            "testingPopup": {"enabled": True},
            "buttonPresentation": {"fallbackFontSize": 10, "scaleRtiDerivedFontSizes": True},
            "state": {},
            "layerPanel": {"enabled": True},
        }

        html = render_single_device_html(project_data, app_ui, project_stem="sample_project_data", device_index=0)

        # Viewport click enters viewport view mode.
        self.assertIn("enterViewportMode(el.dataset.vp", html)

        # Close button exits viewport view mode.
        self.assertIn("getElementById('vpPopupClose')", html)
        self.assertIn("addEventListener('click',()=>exitViewportMode()", html)

        # Escape key exits viewport view mode.
        self.assertIn("addEventListener('keydown'", html)
        self.assertIn("Escape", html)

        # Overlay is visual, while pointer-events blocks interaction with the underlying rti canvas.
        self.assertIn("rgba(255,255,255,0.05)", html)
        self.assertIn("pointer-events:none", html)
        self.assertIn(".viewport-mode #rtiCanvas", html)

        # Viewport buttons are not clickable on the main canvas (viewport itself is the click target).
        self.assertIn(".device-page .btn-wrap.vp-btn", html)
        self.assertIn("pointer-events:none", html)
        # Popup duplicates must be clickable.
        self.assertIn(".vp-popup-stage .btn-wrap.vp-btn", html)
        self.assertIn("pointer-events:auto", html)

        # Clicking outside the popup panel closes it.
        self.assertIn("getElementById('vpPopup')", html)
        self.assertIn("e.target===vpPopup", html)

        # Controls differ based on viewport navigation mode.
        self.assertIn("id='vpPopupUp'", html)
        self.assertIn("id='vpPopupDown'", html)
        self.assertIn("id='vpPopupPrev'", html)
        self.assertIn("id='vpPopupNext'", html)
        self.assertIn("data-nav-mode", html)


if __name__ == "__main__":
    unittest.main()
