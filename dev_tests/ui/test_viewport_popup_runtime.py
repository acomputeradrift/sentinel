import sys
import tempfile
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


class ViewportPopupRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Playwright is intentionally only used from the temp env.
        from playwright.sync_api import sync_playwright

        cls._pw = sync_playwright().start()
        cls._browser = cls._pw.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls._browser.close()
        finally:
            cls._pw.stop()

    def _write_fixture_html(self) -> Path:
        project_data = {
            "devices": [
                {
                    "userFacing": {
                        "displayName": "RTI (Runtime Test Device)",
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
                                                        "portrait": {
                                                            "visible": True,
                                                            "coordinates": {"top": 200, "left": 90, "height": 260, "width": 300},
                                                        },
                                                        "landscape": {
                                                            "visible": True,
                                                            "coordinates": {"top": 120, "left": 160, "height": 220, "width": 420},
                                                        },
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

        html = render_single_device_html(project_data, app_ui, project_stem="runtime_test_project", device_index=0)
        tmp_dir = Path(tempfile.mkdtemp(prefix="sentinel-ui-"))
        out = tmp_dir / "runtime_viewport_popup.html"
        out.write_text(html, encoding="utf-8")
        return out

    def test_viewport_popup_opens_and_closes(self):
        from playwright.sync_api import expect

        html_path = self._write_fixture_html()
        page = self._browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            page.goto(html_path.as_uri(), wait_until="domcontentloaded")

            # Popup starts hidden.
            expect(page.locator("#vpPopup")).to_be_hidden()

            # Clicking the viewport opens the popup.
            page.locator(".vp-box").first.click()
            expect(page.locator("#vpPopup")).to_be_visible()

            # In viewport view mode, the underlying RTI canvas must not show scrollbars.
            # This avoids "mystery scroll wheels" that look like the popup itself is scrollable.
            rti_overflow = page.evaluate("getComputedStyle(document.getElementById('rtiCanvas')).overflow")
            self.assertEqual(rti_overflow, "hidden")

            # Default popup should not allow native scrolling unless user zooms.
            overflow_y = page.evaluate("getComputedStyle(document.getElementById('vpPopupScroller')).overflowY")
            self.assertIn(overflow_y, ("hidden", "clip"))

            # Popup viewport outline must match normal viewport outline.
            border = page.evaluate(
                """() => {
                  const a=document.querySelector('.device-page.active .vp-box');
                  const b=document.querySelector('.vp-popup-viewport');
                  if (!a || !b) return null;
                  const ca=getComputedStyle(a);
                  const cb=getComputedStyle(b);
                  return {
                    a: [ca.borderTopStyle, ca.borderTopWidth, ca.borderTopColor],
                    b: [cb.borderTopStyle, cb.borderTopWidth, cb.borderTopColor],
                  };
                }"""
            )
            self.assertIsNotNone(border)
            self.assertEqual(border["a"], border["b"])

            # Button coordinates must be offsets from viewport origin (VP Child is at 10,10).
            coords_ok = page.evaluate(
                """() => {
                  const win=document.querySelector('.vp-popup-viewport');
                  const btn=document.querySelector('.vp-popup-stage .btn-wrap.vp-btn');
                  if (!win || !btn) return null;
                  const wr=win.getBoundingClientRect();
                  const br=btn.getBoundingClientRect();
                  // allow small rounding error after scaling
                  const dx=Math.round(br.left - wr.left);
                  const dy=Math.round(br.top - wr.top);
                  return {dx, dy};
                }"""
            )
            self.assertIsNotNone(coords_ok)
            self.assertGreaterEqual(coords_ok["dx"], 6)
            self.assertGreaterEqual(coords_ok["dy"], 6)

            # Close X should be inset from the right edge of the popup panel.
            inset_ok = page.evaluate(
                """() => {
                  const panel=document.getElementById('vpPopupPanel');
                  const x=document.getElementById('vpPopupClose');
                  if (!panel || !x) return false;
                  const pr=panel.getBoundingClientRect();
                  const xr=x.getBoundingClientRect();
                  return (pr.right - xr.right) >= 10;
                }"""
            )
            self.assertTrue(inset_ok)

            # Underlying viewport buttons must not be clickable.
            pe_out = page.evaluate(
                "getComputedStyle(document.querySelector('.device-page .btn-wrap.vp-btn')||document.body).pointerEvents"
            )
            self.assertEqual(pe_out, "none")

            # Popup cloned viewport buttons are clickable.
            pe_in = page.evaluate(
                "getComputedStyle(document.querySelector('.vp-popup-stage .btn-wrap.vp-btn')||document.body).pointerEvents"
            )
            self.assertIn(pe_in, ("auto", "all"))

            # Close via X.
            page.locator("#vpPopupClose").click()
            expect(page.locator("#vpPopup")).to_be_hidden()

            # Re-open, then close by clicking backdrop (outside panel).
            page.locator(".vp-box").first.click()
            expect(page.locator("#vpPopup")).to_be_visible()
            page.locator("#vpPopup").click(position={"x": 5, "y": 5})
            expect(page.locator("#vpPopup")).to_be_hidden()
        finally:
            page.close()

    def test_vertical_scroll_viewport_popup_reserves_controls_and_centers_viewport(self):
        from playwright.sync_api import expect

        # Fixture: vertical scrolling viewport with a child button at (10, 10).
        project_data = {
            "devices": [
                {
                    "userFacing": {
                        "displayName": "RTI (Vertical Scroll Popup Test Device)",
                        "deviceUI": {
                            "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                            "landscape": {"supported": True, "resolution": {"width": 854, "height": 480}},
                        },
                        "pages": [
                            {
                                "pageName": "Home",
                                "layers": [
                                    {
                                        "layerName": "Viewport Layer",
                                        "layerOrder": 0,
                                        "buttonCategories": {"screenLabels": [], "screenButtons": [], "hardButtons": []},
                                        "viewports": [
                                            {
                                                "viewportIdentity": {"viewportButtonId": 10},
                                                "viewportUI": {
                                                    "navigationMode": "verticalScroll",
                                                    "orientations": {
                                                        "portrait": {"visible": True, "coordinates": {"top": 10, "left": 20, "height": 320, "width": 180}},
                                                        "landscape": {"visible": True, "coordinates": {"top": 5, "left": 8, "height": 240, "width": 300}},
                                                    },
                                                },
                                                "layers": [
                                                    {
                                                        "layerName": "Viewport Inner Layer",
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
                                                                                portrait={"visible": True, "coordinates": {"top": 10, "left": 10, "height": 44, "width": 120}},
                                                                                landscape={"visible": True, "coordinates": {"top": 10, "left": 10, "height": 44, "width": 120}},
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

        html = render_single_device_html(project_data, app_ui, project_stem="vertical_scroll_popup_test", device_index=0)
        tmp_dir = Path(tempfile.mkdtemp(prefix="sentinel-ui-"))
        html_path = tmp_dir / "vertical_scroll_popup_test.html"
        html_path.write_text(html, encoding="utf-8")

        page = self._browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            page.goto(html_path.as_uri(), wait_until="domcontentloaded")
            expect(page.locator("#vpPopup")).to_be_hidden()
            page.locator(".vp-box").first.click()
            expect(page.locator("#vpPopup")).to_be_visible()

            # Controls should be visible for vertical scroll.
            expect(page.locator("#vpPopupUp")).to_be_visible()
            expect(page.locator("#vpPopupDown")).to_be_visible()

            # The viewport window must not overlap the up/down controls, and should be centered
            # within the remaining space between them.
            layout = page.evaluate(
                """() => {
                  const win=document.querySelector('.vp-popup-viewport');
                  const up=document.getElementById('vpPopupUp');
                  const down=document.getElementById('vpPopupDown');
                  if (!win || !up || !down) return null;
                  const wr=win.getBoundingClientRect();
                  const ur=up.getBoundingClientRect();
                  const dr=down.getBoundingClientRect();
                  const wCenterY=(wr.top+wr.bottom)/2;
                  const midTop=ur.bottom;
                  const midBottom=dr.top;
                  const midCenterY=(midTop+midBottom)/2;
                  const wCenterX=(wr.left+wr.right)/2;
                  const uCenterX=(ur.left+ur.right)/2;
                  return {
                    gapTop: wr.top - ur.bottom,
                    gapBottom: dr.top - wr.bottom,
                    centerDeltaY: wCenterY - midCenterY,
                    centerDeltaX: wCenterX - uCenterX,
                  };
                }"""
            )
            self.assertIsNotNone(layout)
            self.assertGreaterEqual(layout["gapTop"], 6)
            self.assertGreaterEqual(layout["gapBottom"], 6)
            self.assertLessEqual(abs(layout["centerDeltaY"]), 10)
            self.assertLessEqual(abs(layout["centerDeltaX"]), 4)
        finally:
            page.close()

    def test_popup_positions_buttons_relative_to_viewport_origin(self):
        from playwright.sync_api import expect

        # Fixture: viewport at (left=0, top=187) in landscape, with a child at (left=15, top=0).
        project_data = {
            "devices": [
                {
                    "userFacing": {
                        "displayName": "RTI (Popup Origin Offset Test Device)",
                        "deviceUI": {
                            "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                            "landscape": {"supported": True, "resolution": {"width": 854, "height": 480}},
                        },
                        "pages": [
                            {
                                "pageName": "Home",
                                "layers": [
                                    {
                                        "layerName": "Viewport Layer",
                                        "layerOrder": 0,
                                        "buttonCategories": {"screenLabels": [], "screenButtons": [], "hardButtons": []},
                                        "viewports": [
                                            {
                                                "viewportIdentity": {"viewportButtonId": 10},
                                                "viewportUI": {
                                                    "navigationMode": "verticalScroll",
                                                    "orientations": {
                                                        "portrait": {"visible": True, "coordinates": {"top": 10, "left": 20, "height": 320, "width": 180}},
                                                        "landscape": {"visible": True, "coordinates": {"top": 187, "left": 0, "height": 973, "width": 150}},
                                                    },
                                                },
                                                "layers": [
                                                    {
                                                        "layerName": "Viewport Inner Layer",
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
                                                                                "buttonTagName": "NAVIGATION - Lights QuickLink",
                                                                                "text": "",
                                                                                "buttonType": None,
                                                                            },
                                                                            "buttonUI": oriented_ui(
                                                                                portrait={"visible": True, "coordinates": {"top": 10, "left": 10, "height": 44, "width": 120}},
                                                                                landscape={"visible": True, "coordinates": {"top": 0, "left": 15, "height": 110, "width": 110}},
                                                                            ),
                                                                            "testTargets": {"text": False, "macros": False, "macroSteps": False, "variables": {}},
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

        html = render_single_device_html(project_data, app_ui, project_stem="popup_origin_offset_test", device_index=0)
        tmp_dir = Path(tempfile.mkdtemp(prefix="sentinel-ui-"))
        html_path = tmp_dir / "popup_origin_offset_test.html"
        html_path.write_text(html, encoding="utf-8")

        page = self._browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            page.goto(html_path.as_uri(), wait_until="domcontentloaded")

            # Switch to landscape and open popup.
            page.locator("button.orientation-btn[data-orientation='landscape']").click()
            page.locator(".vp-box").first.click()
            expect(page.locator("#vpPopup")).to_be_visible()

            pos = page.evaluate(
                """() => {
                  const win=document.querySelector('.vp-popup-viewport');
                  const btn=document.querySelector('.vp-popup-stage .btn-wrap.vp-btn[data-button-tag=\"NAVIGATION - Lights QuickLink\"]');
                  if (!win || !btn) return null;
                  const wr=win.getBoundingClientRect();
                  const br=btn.getBoundingClientRect();
                  // dx/dy in CSS pixels
                  return {dx: br.left - wr.left, dy: br.top - wr.top, w: br.width, h: br.height, vw: wr.width};
                }"""
            )
            self.assertIsNotNone(pos)

            # Fit scale inferred from viewport box width (150 in source).
            scale = pos["vw"] / 150.0
            self.assertGreater(scale, 0)
            self.assertLess(scale, 10)

            # Expect the button at (left=15, top=0) relative to viewport origin (within rounding).
            self.assertLessEqual(abs(pos["dx"] - (15 * scale)), 2.0)
            self.assertLessEqual(abs(pos["dy"] - (0 * scale)), 2.0)
        finally:
            page.close()

    def test_viewport_popup_can_be_blocked_by_layers_until_toggled_off(self):
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import expect

        def overlay_button(*, tag: str, text: str, left: int, top: int, width: int, height: int) -> dict:
            return {
                "buttonIdentity": {"buttonTagName": tag, "text": text, "buttonType": None},
                "buttonUI": oriented_ui(
                    portrait={"visible": True, "coordinates": {"top": top, "left": left, "height": height, "width": width}},
                    landscape={"visible": True, "coordinates": {"top": top, "left": left, "height": height, "width": width}},
                ),
                "testTargets": {"text": True, "macros": False, "macroSteps": True, "variables": {}},
            }

        # Fixture: a full-screen overlay button on a higher-order layer that intercepts clicks.
        project_data = {
            "devices": [
                {
                    "userFacing": {
                        "displayName": "RTI (Layer Toggle Test Device)",
                        "deviceUI": {
                            "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                            "landscape": {"supported": True, "resolution": {"width": 854, "height": 480}},
                        },
                        "pages": [
                            {
                                "pageName": "Home",
                                "layers": [
                                    {
                                        "layerName": "Viewport Layer",
                                        "layerOrder": 0,
                                        "buttonCategories": {"screenLabels": [], "screenButtons": [], "hardButtons": []},
                                        "viewports": [
                                            {
                                                "viewportIdentity": {"viewportButtonId": 123},
                                                "viewportUI": {
                                                    "navigationMode": "page",
                                                    "orientations": {
                                                        "portrait": {
                                                            "visible": True,
                                                            "coordinates": {"top": 200, "left": 90, "height": 260, "width": 300},
                                                        },
                                                        "landscape": {
                                                            "visible": True,
                                                            "coordinates": {"top": 120, "left": 160, "height": 220, "width": 420},
                                                        },
                                                    },
                                                },
                                                "layers": [
                                                    {
                                                        "layerName": "Viewport Inner Layer",
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
                                    },
                                    {
                                        "layerName": "Blocking Overlay Layer",
                                        "layerOrder": 99,
                                        "buttonCategories": {
                                            "screenLabels": [],
                                            "screenButtons": [
                                                overlay_button(tag="BLOCK", text="BLOCK", left=0, top=0, width=900, height=900)
                                            ],
                                            "hardButtons": [],
                                        },
                                        "viewports": [],
                                    },
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

        html = render_single_device_html(project_data, app_ui, project_stem="layer_toggle_runtime_test", device_index=0)
        tmp_dir = Path(tempfile.mkdtemp(prefix="sentinel-ui-"))
        html_path = tmp_dir / "runtime_layer_toggle.html"
        html_path.write_text(html, encoding="utf-8")

        page = self._browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            page.goto(html_path.as_uri(), wait_until="domcontentloaded")
            expect(page.locator("#vpPopup")).to_be_hidden()

            # With the blocking layer on, viewport click should be intercepted (popup stays hidden).
            with self.assertRaises(PlaywrightTimeoutError):
                page.locator(".vp-box").first.click(timeout=1500)
            expect(page.locator("#vpPopup")).to_be_hidden()

            # Toggle off all non-viewport layers (simulate user intent via layer panel state).
            page.evaluate(
                """() => {
                  const vp=document.querySelector('.device-page.active .vp-box');
                  if (!vp) return;
                  const owner=String(vp.dataset.ownerLayerKey||'');
                  const state=activePageState();
                  const scope=layerScopeKey(state);
                  const vis=ensureLayerVisibility(state);
                  Object.keys(vis).forEach(k => { vis[k] = (k===owner); });
                  saveLayerVisibility(scope, vis);
                  renderLayerPanel();
                  applyLayerVisibility();
                }"""
            )

            # Now viewport click should open the popup.
            page.locator(".vp-box").first.click(timeout=3000)
            expect(page.locator("#vpPopup")).to_be_visible()
        finally:
            page.close()
