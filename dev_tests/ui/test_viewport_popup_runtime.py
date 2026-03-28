import sys
import tempfile
import unittest
import json
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
        # Minimal fixture: a single page with one viewport and one button inside that viewport.
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
                                                                            "testTargets": {
                                                                                "text": True,
                                                                                "macros": False,
                                                                                "macroSteps": False,
                                                                                "variables": {},
                                                                            },
                                                                        }
                                                                     ],
                                                                 },
                                                             }
                                                            ,
                                                            {
                                                                "frameId": 1,
                                                                "buttonCategories": {
                                                                    "screenLabels": [],
                                                                    "hardButtons": [],
                                                                    "screenButtons": [
                                                                        {
                                                                            "buttonIdentity": {
                                                                                "buttonTagName": "DUMMY_FRAME1",
                                                                                "text": "DUMMY_FRAME1",
                                                                                "buttonType": None,
                                                                            },
                                                                            "buttonUI": oriented_ui(
                                                                                portrait={
                                                                                    "visible": True,
                                                                                    "coordinates": {"top": 260, "left": 10, "height": 44, "width": 120},
                                                                                },
                                                                                landscape={
                                                                                    "visible": True,
                                                                                    "coordinates": {"top": 260, "left": 10, "height": 44, "width": 120},
                                                                                },
                                                                            ),
                                                                            "testTargets": {"text": False, "macros": False, "macroSteps": False, "variables": {}},
                                                                        }
                                                                    ],
                                                                },
                                                            },
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

    def _write_real_dash_html(self) -> Path | None:
        """
        Render a real Dash output JSON to HTML so runtime tests can validate behavior
        against the actual (large) project structure, not just the minimal fixture.
        """
        # Prefer the most recent Dash OS iPhone JSON in output/, since filenames change as you iterate.
        out_dir = ROOT / "output"
        candidates = sorted(
            out_dir.glob("Dash OS v* iPhone_project_data.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            return None
        real_json = candidates[0]

        project_data = json.loads(real_json.read_text(encoding="utf-8"))

        # Keep UI chrome consistent with the fixture, so geometry assertions are comparable.
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

        html = render_single_device_html(project_data, app_ui, project_stem="real_dash_project", device_index=0)
        tmp_dir = Path(tempfile.mkdtemp(prefix="sentinel-ui-real-"))
        out = tmp_dir / "real_dash_viewport_popup.html"
        out.write_text(html, encoding="utf-8")
        return out

    def test_viewport_popup_opens_and_closes(self):
        from playwright.sync_api import expect

        html_path = self._write_fixture_html()
        page = self._browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            page.goto(html_path.as_uri(), wait_until="domcontentloaded")

            # Orientation controls should be bottom-left (not top-left).
            orient_pos = page.evaluate(
                """() => {
                  const oc=document.getElementById('orientationControls');
                  if (!oc) return null;
                  const r=oc.getBoundingClientRect();
                  return {top:r.top, bottom:r.bottom, h: window.innerHeight};
                }"""
            )
            self.assertIsNotNone(orient_pos)
            self.assertGreater(orient_pos["top"], orient_pos["h"] * 0.45)

            # Popup starts hidden.
            expect(page.locator("#vpPopup")).to_be_hidden()

            # Clicking the viewport opens the popup.
            page.locator(".vp-box").first.click()
            expect(page.locator("#vpPopup")).to_be_visible()
            # No separate close control should exist outside the popup; only the X closes.
            expect(page.locator("#vpClose")).to_have_count(0)

            # Popup must be bounded to the RTI canvas (so it doesn't cover the layer panel / UI chrome).
            bounds = page.evaluate(
                """() => {
                  const rti=document.getElementById('rtiCanvas');
                  const pop=document.getElementById('vpPopup');
                  if (!rti || !pop) return null;
                  const rr=rti.getBoundingClientRect();
                  const pr=pop.getBoundingClientRect();
                  return {rr, pr};
                }"""
            )
            self.assertIsNotNone(bounds)
            self.assertLessEqual(abs(bounds["rr"]["left"] - bounds["pr"]["left"]), 2.0)
            self.assertLessEqual(abs(bounds["rr"]["top"] - bounds["pr"]["top"]), 2.0)
            self.assertLessEqual(abs(bounds["rr"]["width"] - bounds["pr"]["width"]), 2.0)
            self.assertLessEqual(abs(bounds["rr"]["height"] - bounds["pr"]["height"]), 2.0)

            # Zoom controls must still work in viewport mode (they zoom the popup content).
            vw_before = page.evaluate(
                """() => {
                  const win=document.querySelector('.vp-popup-viewport');
                  return win ? win.getBoundingClientRect().width : null;
                }"""
            )
            self.assertIsNotNone(vw_before)
            self.assertEqual(page.locator(".zoom-reset").inner_text().strip(), "100%")

            page.locator(".zoom-inc").click()
            vw_after = page.evaluate(
                """() => {
                  const win=document.querySelector('.vp-popup-viewport');
                  return win ? win.getBoundingClientRect().width : null;
                }"""
            )
            self.assertIsNotNone(vw_after)
            self.assertGreater(vw_after, vw_before)
            self.assertEqual(page.locator(".zoom-reset").inner_text().strip(), "110%")

            # A second click should continue zooming.
            page.locator(".zoom-inc").click()
            vw_after2 = page.evaluate(
                """() => {
                  const win=document.querySelector('.vp-popup-viewport');
                  return win ? win.getBoundingClientRect().width : null;
                }"""
            )
            self.assertIsNotNone(vw_after2)
            self.assertGreater(vw_after2, vw_after)
            self.assertEqual(page.locator(".zoom-reset").inner_text().strip(), "120%")

            # Zoom caps at 300% and keeps the label in sync.
            for _ in range(20):
                page.locator(".zoom-inc").click()
            zoom_txt = page.locator(".zoom-reset").inner_text().strip()
            self.assertEqual(zoom_txt, "300%")

            # When zoomed in, the popup scroller must allow panning (like RTI canvas zoom).
            scrollable = page.evaluate(
                """() => {
                  const s=document.getElementById('vpPopupScroller');
                  if (!s) return null;
                  return {
                    overflowX: getComputedStyle(s).overflowX,
                    overflowY: getComputedStyle(s).overflowY,
                    canScroll: (s.scrollWidth > s.clientWidth) || (s.scrollHeight > s.clientHeight),
                    sw: s.scrollWidth, cw: s.clientWidth,
                    sh: s.scrollHeight, ch: s.clientHeight,
                  };
                }"""
            )
            self.assertIsNotNone(scrollable)
            self.assertIn(scrollable["overflowX"], ("auto", "scroll"))
            self.assertIn(scrollable["overflowY"], ("auto", "scroll"))
            self.assertTrue(scrollable["canScroll"])

            # Scroll to the far bottom-right and ensure the viewport window is still present (not shrunk).
            page.evaluate(
                """() => {
                  const s=document.getElementById('vpPopupScroller');
                  if (!s) return;
                  s.scrollLeft = s.scrollWidth - s.clientWidth;
                  s.scrollTop = s.scrollHeight - s.clientHeight;
                }"""
            )
            still_ok = page.evaluate(
                """() => {
                  const s=document.getElementById('vpPopupScroller');
                  const win=document.querySelector('.vp-popup-viewport');
                  if (!s || !win) return null;
                  const sr=s.getBoundingClientRect();
                  const wr=win.getBoundingClientRect();
                  return {
                    winW: wr.width,
                    winH: wr.height,
                    intersects: !(wr.right < sr.left || wr.left > sr.right || wr.bottom < sr.top || wr.top > sr.bottom),
                  };
                }"""
            )
            self.assertIsNotNone(still_ok)
            self.assertGreater(still_ok["winW"], 0)
            self.assertGreater(still_ok["winH"], 0)
            self.assertTrue(still_ok["intersects"])

            # Reset click returns to 100%.
            page.locator(".zoom-reset").click()
            self.assertEqual(page.locator(".zoom-reset").inner_text().strip(), "100%")

            # Layer panel must remain clickable while the popup is open.
            # (In viewport mode the layer list becomes viewport-layer toggles.)
            expect(page.locator("#layerPanel")).to_be_visible()
            toggle = page.locator("#layerList .layer-toggle").first
            expect(toggle).to_have_attribute("aria-pressed", "true")
            toggle.click()
            expect(toggle).to_have_attribute("aria-pressed", "false")
            # Toggle it back on so later geometry assertions still have a visible viewport button.
            toggle.click()
            expect(toggle).to_have_attribute("aria-pressed", "true")

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

            # Re-open. Backdrop click should NOT close; only the X closes.
            page.locator(".vp-box").first.click()
            expect(page.locator("#vpPopup")).to_be_visible()
            page.locator("#vpPopup").click(position={"x": 5, "y": 5})
            expect(page.locator("#vpPopup")).to_be_visible()

            # Escape should not close (only X).
            page.keyboard.press("Escape")
            expect(page.locator("#vpPopup")).to_be_visible()

            # Close via X again.
            page.locator("#vpPopupClose").click()
            expect(page.locator("#vpPopup")).to_be_hidden()
        finally:
            page.close()

    def test_real_dash_scrollbar_gutter_transition_does_not_shift_center(self):
        """
        Proves/falsifies the theory that when native scrollbars start taking layout space
        (classic gutters), the viewport content drifts off center by roughly half the gutter.

        Headless Chromium uses overlay/hidden scrollbars (no gutter), so we simulate a classic
        scrollbar environment by applying `scrollbar-gutter: stable` after zooming (when
        overflow is enabled).

        Visual centering contract: the viewport box stays centered relative to the nav arrows
        (the user's visual reference), not relative to the scroller's client area.
        """
        from playwright.sync_api import expect

        html_path = self._write_real_dash_html()
        if html_path is None:
            self.skipTest("Real Dash output JSON not found: output/Dash OS v* iPhone_project_data.json")

        page = self._browser.new_page(viewport={"width": 1400, "height": 900})
        try:
            page.goto(html_path.as_uri(), wait_until="domcontentloaded")

            def open_first_viewport(nav_mode: str) -> bool:
                picked = page.evaluate(
                    """(navMode) => {
                      // Find the first viewport of the requested nav mode anywhere in the project.
                      for (const p of document.querySelectorAll('.device-page')) {
                        const box=p.querySelector(`.vp-box[data-nav-mode="${navMode}"]`);
                        if (!box) continue;
                        return {pageIndex: Number(p.dataset.pageIndex||0), vpIndex: Number(box.dataset.vp||0)};
                      }
                      return null;
                    }""",
                    nav_mode,
                )
                if not picked:
                    return False
                page.evaluate(
                    """(p) => {
                      if (typeof setActivePage === 'function') setActivePage(p.pageIndex);
                      if (typeof enterViewportMode === 'function') enterViewportMode(p.vpIndex);
                    }""",
                    picked,
                )
                expect(page.locator("#vpPopup")).to_be_visible()
                return True

            def measure(tag: str) -> dict:
                # Visual centering: use the nav-arrow midpoint as the reference "center".
                out = page.evaluate(
                    """(tag) => {
                      const win=document.querySelector('.vp-popup-viewport');
                      const panel=document.getElementById('vpPopupPanel');
                      const prev=document.getElementById('vpPopupPrev');
                      const next=document.getElementById('vpPopupNext');
                      const up=document.getElementById('vpPopupUp');
                      const down=document.getElementById('vpPopupDown');
                      const s=document.getElementById('vpPopupScroller');
                      if (!win || !panel || !s) return null;
                      const wr=win.getBoundingClientRect();
                      const pr=panel.getBoundingClientRect();
                      const cx = (wr.left + wr.right)/2;
                      const cy = (wr.top + wr.bottom)/2;

                      const isVisible = (el) => !!el && getComputedStyle(el).display !== 'none';
                      const centers = [];
                      if (isVisible(prev) && isVisible(next)) {
                        const a=prev.getBoundingClientRect();
                        const b=next.getBoundingClientRect();
                        centers.push({x:(a.left+a.right)/2, y:(a.top+a.bottom)/2});
                        centers.push({x:(b.left+b.right)/2, y:(b.top+b.bottom)/2});
                      } else if (isVisible(up) && isVisible(down)) {
                        const a=up.getBoundingClientRect();
                        const b=down.getBoundingClientRect();
                        centers.push({x:(a.left+a.right)/2, y:(a.top+a.bottom)/2});
                        centers.push({x:(b.left+b.right)/2, y:(b.top+b.bottom)/2});
                      }

                      let desiredCx=(pr.left+pr.right)/2;
                      let desiredCy=(pr.top+pr.bottom)/2;
                      if (centers.length === 2) {
                        desiredCx = (centers[0].x + centers[1].x)/2;
                        desiredCy = (centers[0].y + centers[1].y)/2;
                      }

                      const gutterW = (s.offsetWidth - s.clientWidth);
                      const gutterH = (s.offsetHeight - s.clientHeight);
                      return {
                        tag,
                        zoom: (document.querySelector('.zoom-reset')||{innerText:''}).innerText.trim(),
                        dx: cx - desiredCx,
                        dy: cy - desiredCy,
                        gutterW,
                        gutterH,
                        desiredCx,
                        desiredCy,
                        winCx: cx,
                        winCy: cy,
                        scrollbarGutter: getComputedStyle(s).scrollbarGutter,
                      };
                    }""",
                    tag,
                )
                self.assertIsNotNone(out)
                return out

            for nav_mode in ("page", "verticalScroll"):
                if not open_first_viewport(nav_mode):
                    continue

                # Ensure each mode starts from a clean "visual baseline":
                # - zoom at 100%
                # - no forced scrollbar-gutter override
                page.locator(".zoom-reset").click()
                expect(page.locator(".zoom-reset")).to_have_text("100%")
                page.evaluate(
                    """() => {
                      const s=document.getElementById('vpPopupScroller');
                      if (!s) return;
                      s.style.removeProperty('scrollbar-gutter');
                      if (typeof applyViewportPopupLayout === 'function') applyViewportPopupLayout();
                    }"""
                )

                m0 = measure(f"{nav_mode}:zoom100")
                self.assertLessEqual(abs(m0["dx"]), 2.0, f"Pre-zoom visual drift too large: {m0}")
                self.assertLessEqual(abs(m0["dy"]), 2.0, f"Pre-zoom visual drift too large: {m0}")

                # Zoom in one step so native scrolling is enabled for the popup.
                page.locator(".zoom-inc").click()
                expect(page.locator(".zoom-reset")).to_have_text("110%")

                # Simulate a classic (non-overlay) scrollbar gutter appearing at this moment.
                page.evaluate(
                    """() => {
                      const s=document.getElementById('vpPopupScroller');
                      if (!s) return;
                      s.style.setProperty('scrollbar-gutter', 'stable');
                      if (typeof applyViewportPopupLayout === 'function') applyViewportPopupLayout();
                    }"""
                )

                m1 = measure(f"{nav_mode}:zoom110+stableGutter")

                # Visual centering contract: stay centered relative to nav arrows/panel.
                self.assertLessEqual(abs(m1["dx"]), 2.0, f"Visual center drift after gutter transition: {m1}")
                self.assertLessEqual(abs(m1["dy"]), 2.0, f"Visual center drift after gutter transition: {m1}")

                # Close and reset between modes.
                page.locator("#vpPopupClose").click()
                expect(page.locator("#vpPopup")).to_be_hidden()
        finally:
            page.close()

    def test_vertical_scroll_viewport_popup_controls_overlay_and_viewport_is_visually_centered(self):
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
                                                            ,
                                                            {
                                                                "frameId": 1,
                                                                "buttonCategories": {
                                                                    "screenLabels": [],
                                                                    "hardButtons": [],
                                                                    "screenButtons": [
                                                                        {
                                                                            "buttonIdentity": {
                                                                                "buttonTagName": "DUMMY_FRAME1",
                                                                                "text": "DUMMY_FRAME1",
                                                                                "buttonType": None,
                                                                            },
                                                                            "buttonUI": oriented_ui(
                                                                                portrait={
                                                                                    "visible": True,
                                                                                    "coordinates": {"top": 260, "left": 10, "height": 44, "width": 120},
                                                                                },
                                                                                landscape={
                                                                                    "visible": True,
                                                                                    "coordinates": {"top": 260, "left": 10, "height": 44, "width": 120},
                                                                                },
                                                                            ),
                                                                            "testTargets": {"text": False, "macros": False, "macroSteps": False, "variables": {}},
                                                                        }
                                                                    ],
                                                                },
                                                            },
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

            # Visual centering: viewport center should match the nav-arrow midpoint.
            # Controls overlay content (no reserved blank space), so the only hard requirement is:
            # controls remain clickable (topmost at their center points).
            layout = page.evaluate(
                """() => {
                  const win=document.querySelector('.vp-popup-viewport');
                  const up=document.getElementById('vpPopupUp');
                  const down=document.getElementById('vpPopupDown');
                  if (!win || !up || !down) return null;
                  const wr=win.getBoundingClientRect();
                  const ur=up.getBoundingClientRect();
                  const dr=down.getBoundingClientRect();
                  const wCenterX=(wr.left+wr.right)/2;
                  const wCenterY=(wr.top+wr.bottom)/2;
                  const uCenterX=(ur.left+ur.right)/2;
                  const uCenterY=(ur.top+ur.bottom)/2;
                  const dCenterX=(dr.left+dr.right)/2;
                  const dCenterY=(dr.top+dr.bottom)/2;
                  const desiredX=(uCenterX+dCenterX)/2;
                  const desiredY=(uCenterY+dCenterY)/2;

                  const hitUp=document.elementFromPoint(uCenterX, uCenterY);
                  const hitDown=document.elementFromPoint(dCenterX, dCenterY);
                  const upOk=hitUp && (hitUp===up || up.contains(hitUp));
                  const downOk=hitDown && (hitDown===down || down.contains(hitDown));
                  return {
                    dx: wCenterX - desiredX,
                    dy: wCenterY - desiredY,
                    upOk,
                    downOk,
                  };
                }"""
            )
            self.assertIsNotNone(layout)
            self.assertLessEqual(abs(layout["dx"]), 2.0, layout)
            self.assertLessEqual(abs(layout["dy"]), 2.0, layout)
            self.assertTrue(layout["upOk"], layout)
            self.assertTrue(layout["downOk"], layout)
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

    def test_vertical_scroll_popup_shows_frame_nav_and_indicator_is_right_centered(self):
        from playwright.sync_api import expect

        # Fixture: verticalScroll viewport with 2 frames.
        # Frame 0 has TOP only; Frame 1 has TOP + FRAME1_ONLY.
        project_data = {
            "devices": [
                {
                    "userFacing": {
                        "displayName": "RTI (Popup Frame Nav Test Device)",
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
                                                        "portrait": {"visible": True, "coordinates": {"top": 10, "left": 20, "height": 220, "width": 180}},
                                                        "landscape": {"visible": True, "coordinates": {"top": 30, "left": 10, "height": 240, "width": 200}},
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
                                                                            "buttonIdentity": {"buttonTagName": "TOP", "text": "TOP", "buttonType": None},
                                                                            "buttonUI": oriented_ui(
                                                                                portrait={"visible": True, "coordinates": {"top": 0, "left": 10, "height": 44, "width": 120}},
                                                                                landscape={"visible": True, "coordinates": {"top": 0, "left": 10, "height": 44, "width": 120}},
                                                                            ),
                                                                            "testTargets": {"text": False, "macros": False, "macroSteps": False, "variables": {}},
                                                                        }
                                                                    ],
                                                                },
                                                            },
                                                            {
                                                                "frameId": 1,
                                                                "buttonCategories": {
                                                                    "screenLabels": [],
                                                                    "hardButtons": [],
                                                                    "screenButtons": [
                                                                        {
                                                                            "buttonIdentity": {"buttonTagName": "TOP", "text": "TOP", "buttonType": None},
                                                                            "buttonUI": oriented_ui(
                                                                                portrait={"visible": True, "coordinates": {"top": 0, "left": 10, "height": 44, "width": 120}},
                                                                                landscape={"visible": True, "coordinates": {"top": 0, "left": 10, "height": 44, "width": 120}},
                                                                            ),
                                                                            "testTargets": {"text": False, "macros": False, "macroSteps": False, "variables": {}},
                                                                        },
                                                                        {
                                                                            "buttonIdentity": {
                                                                                "buttonTagName": "FRAME1_ONLY",
                                                                                "text": "FRAME1_ONLY",
                                                                                "buttonType": None,
                                                                            },
                                                                            "buttonUI": oriented_ui(
                                                                                portrait={"visible": True, "coordinates": {"top": 120, "left": 10, "height": 44, "width": 150}},
                                                                                landscape={"visible": True, "coordinates": {"top": 120, "left": 10, "height": 44, "width": 150}},
                                                                            ),
                                                                            "testTargets": {"text": False, "macros": False, "macroSteps": False, "variables": {}},
                                                                        },
                                                                    ],
                                                                },
                                                            },
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

        html = render_single_device_html(project_data, app_ui, project_stem="popup_frame_nav_test", device_index=0)
        tmp_dir = Path(tempfile.mkdtemp(prefix="sentinel-ui-"))
        html_path = tmp_dir / "popup_frame_nav_test.html"
        html_path.write_text(html, encoding="utf-8")

        page = self._browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            page.goto(html_path.as_uri(), wait_until="domcontentloaded")
            page.locator("button.orientation-btn[data-orientation='landscape']").click()
            page.locator(".vp-box").first.click()
            expect(page.locator("#vpPopup")).to_be_visible()

            # In verticalScroll, frame navigation uses up/down (prev/next are hidden).
            expect(page.locator("#vpPopupPrev")).to_be_hidden()
            expect(page.locator("#vpPopupNext")).to_be_hidden()
            expect(page.locator("#vpPopupUp")).to_be_visible()
            expect(page.locator("#vpPopupDown")).to_be_visible()
            expect(page.locator("#vpPopupIndicator")).to_be_visible()

            # Indicator should show 2 dots.
            expect(page.locator("#vpPopupIndicator .dot")).to_have_count(2)

            # Indicator must be absolutely positioned and not stretched to full-panel width.
            indicator_style = page.evaluate(
                """() => {
                  const ind=document.getElementById('vpPopupIndicator');
                  if (!ind) return null;
                  const cs=getComputedStyle(ind);
                  const r=ind.getBoundingClientRect();
                  return {position: cs.position, width: r.width};
                }"""
            )
            self.assertIsNotNone(indicator_style)
            self.assertEqual(indicator_style["position"], "absolute")
            self.assertLessEqual(indicator_style["width"], 160)
            flex_dir = page.evaluate(
                """() => {
                  const ind=document.getElementById('vpPopupIndicator');
                  if (!ind) return null;
                  return getComputedStyle(ind).flexDirection;
                }"""
            )
            self.assertEqual(flex_dir, "column")

            # Indicator must be to the right of the viewport box and vertically centered.
            pos = page.evaluate(
                """() => {
                  const win=document.querySelector('.vp-popup-viewport');
                  const ind=document.getElementById('vpPopupIndicator');
                  if (!win || !ind) return null;
                  const wr=win.getBoundingClientRect();
                  const ir=ind.getBoundingClientRect();
                  return {
                    rightGap: ir.left - wr.right,
                    centerDeltaY: ((ir.top+ir.bottom)/2) - ((wr.top+wr.bottom)/2),
                  };
                }"""
            )
            self.assertIsNotNone(pos)
            self.assertGreaterEqual(pos["rightGap"], 6)
            self.assertLessEqual(abs(pos["centerDeltaY"]), 8)

            # Frame1-only element should appear after clicking Down.
            expect(page.locator(".vp-popup-stage .btn-wrap.vp-btn[data-button-tag='FRAME1_ONLY']")).to_be_hidden()
            page.locator("#vpPopupDown").click()
            expect(page.locator(".vp-popup-stage .btn-wrap.vp-btn[data-button-tag='FRAME1_ONLY']")).to_be_visible()
        finally:
            page.close()

    def test_page_mode_popup_shows_frame_indicator_below_and_prev_next_changes_frame(self):
        from playwright.sync_api import expect

        # Fixture: page-mode viewport with 2 frames.
        project_data = {
            "devices": [
                {
                    "userFacing": {
                        "displayName": "RTI (Popup Page Frame Nav Test Device)",
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
                                                    "navigationMode": "page",
                                                    "orientations": {
                                                        "portrait": {"visible": True, "coordinates": {"top": 10, "left": 20, "height": 220, "width": 300}},
                                                        "landscape": {"visible": True, "coordinates": {"top": 30, "left": 10, "height": 240, "width": 360}},
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
                                                                            "buttonIdentity": {"buttonTagName": "FRAME0", "text": "FRAME0", "buttonType": None},
                                                                            "buttonUI": oriented_ui(
                                                                                portrait={"visible": True, "coordinates": {"top": 10, "left": 10, "height": 44, "width": 120}},
                                                                                landscape={"visible": True, "coordinates": {"top": 10, "left": 10, "height": 44, "width": 120}},
                                                                            ),
                                                                            "testTargets": {"text": False, "macros": False, "macroSteps": False, "variables": {}},
                                                                        }
                                                                    ],
                                                                },
                                                            },
                                                            {
                                                                "frameId": 1,
                                                                "buttonCategories": {
                                                                    "screenLabels": [],
                                                                    "hardButtons": [],
                                                                    "screenButtons": [
                                                                        {
                                                                            "buttonIdentity": {"buttonTagName": "FRAME1", "text": "FRAME1", "buttonType": None},
                                                                            "buttonUI": oriented_ui(
                                                                                portrait={"visible": True, "coordinates": {"top": 10, "left": 10, "height": 44, "width": 120}},
                                                                                landscape={"visible": True, "coordinates": {"top": 10, "left": 10, "height": 44, "width": 120}},
                                                                            ),
                                                                            "testTargets": {"text": False, "macros": False, "macroSteps": False, "variables": {}},
                                                                        }
                                                                    ],
                                                                },
                                                            },
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

        html = render_single_device_html(project_data, app_ui, project_stem="popup_page_frame_nav_test", device_index=0)
        tmp_dir = Path(tempfile.mkdtemp(prefix="sentinel-ui-"))
        html_path = tmp_dir / "popup_page_frame_nav_test.html"
        html_path.write_text(html, encoding="utf-8")

        page = self._browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            page.goto(html_path.as_uri(), wait_until="domcontentloaded")
            page.locator("button.orientation-btn[data-orientation='landscape']").click()
            page.locator(".vp-box").first.click()
            expect(page.locator("#vpPopup")).to_be_visible()

            expect(page.locator("#vpPopupPrev")).to_be_visible()
            expect(page.locator("#vpPopupNext")).to_be_visible()
            expect(page.locator("#vpPopupUp")).to_be_hidden()
            expect(page.locator("#vpPopupDown")).to_be_hidden()
            expect(page.locator("#vpPopupIndicator")).to_be_visible()
            expect(page.locator("#vpPopupIndicator .dot")).to_have_count(2)
            flex_dir = page.evaluate(
                """() => {
                  const ind=document.getElementById('vpPopupIndicator');
                  if (!ind) return null;
                  return getComputedStyle(ind).flexDirection;
                }"""
            )
            self.assertEqual(flex_dir, "row")

            # Indicator must be below the viewport box and horizontally centered.
            pos = page.evaluate(
                """() => {
                  const win=document.querySelector('.vp-popup-viewport');
                  const ind=document.getElementById('vpPopupIndicator');
                  if (!win || !ind) return null;
                  const wr=win.getBoundingClientRect();
                  const ir=ind.getBoundingClientRect();
                  return {
                    belowGap: ir.top - wr.bottom,
                    centerDeltaX: ((ir.left+ir.right)/2) - ((wr.left+wr.right)/2),
                  };
                }"""
            )
            self.assertIsNotNone(pos)
            self.assertGreaterEqual(pos["belowGap"], 6)
            self.assertLessEqual(abs(pos["centerDeltaX"]), 10)

            # Frame 0 visible at start.
            expect(page.locator(".vp-popup-stage .btn-wrap.vp-btn[data-button-tag='FRAME0']")).to_be_visible()
            expect(page.locator(".vp-popup-stage .btn-wrap.vp-btn[data-button-tag='FRAME1']")).to_be_hidden()
            page.locator("#vpPopupNext").click()
            expect(page.locator(".vp-popup-stage .btn-wrap.vp-btn[data-button-tag='FRAME0']")).to_be_hidden()
            expect(page.locator(".vp-popup-stage .btn-wrap.vp-btn[data-button-tag='FRAME1']")).to_be_visible()
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
                                                            ,
                                                            {
                                                                "frameId": 1,
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

    def test_viewport_layer_toggle_affects_popup_content(self):
        from playwright.sync_api import expect

        # Fixture: a viewport with 2 inner viewport layers; each layer has 1 button in the same frame.
        project_data = {
            "devices": [
                {
                    "userFacing": {
                        "displayName": "RTI (Popup Layer Toggle Test Device)",
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
                                                        "layerName": "VP Layer A",
                                                        "layerOrder": 2,
                                                        "frames": [
                                                            {
                                                                "frameId": 0,
                                                                "buttonCategories": {
                                                                    "screenLabels": [],
                                                                    "hardButtons": [],
                                                                    "screenButtons": [
                                                                        {
                                                                            "buttonIdentity": {"buttonTagName": "LAYER_A", "text": "LAYER_A", "buttonType": None},
                                                                            "buttonUI": oriented_ui(
                                                                                portrait={"visible": True, "coordinates": {"top": 10, "left": 10, "height": 44, "width": 120}},
                                                                                landscape={"visible": True, "coordinates": {"top": 10, "left": 10, "height": 44, "width": 120}},
                                                                            ),
                                                                            "testTargets": {"text": False, "macros": False, "macroSteps": False, "variables": {}},
                                                                        }
                                                                    ],
                                                                },
                                                            }
                                                        ],
                                                    },
                                                    {
                                                        "layerName": "VP Layer B",
                                                        "layerOrder": 1,
                                                        "frames": [
                                                            {
                                                                "frameId": 0,
                                                                "buttonCategories": {
                                                                    "screenLabels": [],
                                                                    "hardButtons": [],
                                                                    "screenButtons": [
                                                                        {
                                                                            "buttonIdentity": {"buttonTagName": "LAYER_B", "text": "LAYER_B", "buttonType": None},
                                                                            "buttonUI": oriented_ui(
                                                                                portrait={"visible": True, "coordinates": {"top": 70, "left": 10, "height": 44, "width": 120}},
                                                                                landscape={"visible": True, "coordinates": {"top": 70, "left": 10, "height": 44, "width": 120}},
                                                                            ),
                                                                            "testTargets": {"text": False, "macros": False, "macroSteps": False, "variables": {}},
                                                                        }
                                                                    ],
                                                                },
                                                            }
                                                        ],
                                                    },
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

        html = render_single_device_html(project_data, app_ui, project_stem="popup_layer_toggle_test", device_index=0)
        tmp_dir = Path(tempfile.mkdtemp(prefix="sentinel-ui-"))
        html_path = tmp_dir / "popup_layer_toggle_test.html"
        html_path.write_text(html, encoding="utf-8")

        page = self._browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            page.goto(html_path.as_uri(), wait_until="domcontentloaded")
            page.locator(".vp-box").first.click()
            expect(page.locator("#vpPopup")).to_be_visible()

            expect(page.locator(".vp-popup-stage .btn-wrap.vp-btn[data-button-tag='LAYER_A']")).to_be_visible()
            expect(page.locator(".vp-popup-stage .btn-wrap.vp-btn[data-button-tag='LAYER_B']")).to_be_visible()

            # Toggle off the topmost viewport layer (VP Layer A).
            layer_buttons = page.locator("#layerList .layer-toggle")
            expect(layer_buttons).to_have_count(2)
            layer_buttons.nth(0).click()
            expect(layer_buttons.nth(0)).to_have_attribute("aria-pressed", "false")
            expect(page.locator(".vp-popup-stage .btn-wrap.vp-btn[data-button-tag='LAYER_A']")).to_be_hidden()
            expect(page.locator(".vp-popup-stage .btn-wrap.vp-btn[data-button-tag='LAYER_B']")).to_be_visible()
        finally:
            page.close()

    def test_popup_zoom_keeps_vertical_center_when_only_horizontal_scroll_needed(self):
        from playwright.sync_api import expect

        # Fixture: page-mode viewport wide enough to overflow horizontally when zoomed, but short enough
        # to avoid vertical overflow; viewport must remain vertically centered in the popup.
        project_data = {
            "devices": [
                {
                    "userFacing": {
                        "displayName": "RTI (Popup Centering Page Mode Test)",
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
                                                    "navigationMode": "page",
                                                    "orientations": {
                                                        "portrait": {"visible": True, "coordinates": {"top": 10, "left": 10, "height": 90, "width": 520}},
                                                        "landscape": {"visible": True, "coordinates": {"top": 10, "left": 10, "height": 90, "width": 520}},
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
                                                            ,
                                                            {
                                                                "frameId": 1,
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

        html = render_single_device_html(project_data, app_ui, project_stem="popup_center_page_mode", device_index=0)
        tmp_dir = Path(tempfile.mkdtemp(prefix="sentinel-ui-"))
        html_path = tmp_dir / "popup_center_page_mode.html"
        html_path.write_text(html, encoding="utf-8")

        page = self._browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            page.goto(html_path.as_uri(), wait_until="domcontentloaded")
            page.locator(".vp-box").first.click()
            expect(page.locator("#vpPopup")).to_be_visible()
            for _ in range(7):
                page.locator(".zoom-inc").click()

            centered = page.evaluate(
                """() => {
                  const panel=document.getElementById('vpPopupPanel');
                  const scroller=document.getElementById('vpPopupScroller');
                  const win=document.querySelector('.vp-popup-viewport');
                  if (!panel || !scroller || !win) return null;
                  const pr=panel.getBoundingClientRect();
                  const wr=win.getBoundingClientRect();
                  const centerDy=((wr.top+wr.bottom)/2) - ((pr.top+pr.bottom)/2);
                  const hOverflow=scroller.scrollWidth > scroller.clientWidth;
                  const vOverflow=scroller.scrollHeight > scroller.clientHeight;
                  return {centerDy, hOverflow, vOverflow};
                }"""
            )
            self.assertIsNotNone(centered)
            self.assertTrue(centered["hOverflow"])
            self.assertFalse(centered["vOverflow"])
            self.assertLessEqual(abs(centered["centerDy"]), 6)
        finally:
            page.close()

    def test_popup_zoom_keeps_horizontal_center_when_only_vertical_scroll_needed(self):
        from playwright.sync_api import expect

        # Fixture: verticalScroll viewport tall enough to overflow vertically when zoomed, but narrow enough
        # to avoid horizontal overflow; viewport must remain horizontally centered in the popup.
        project_data = {
            "devices": [
                {
                    "userFacing": {
                        "displayName": "RTI (Popup Centering Vertical Scroll Test)",
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
                                                        "portrait": {"visible": True, "coordinates": {"top": 10, "left": 10, "height": 760, "width": 90}},
                                                        "landscape": {"visible": True, "coordinates": {"top": 10, "left": 10, "height": 760, "width": 90}},
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
                                                            },
                                                            {
                                                                "frameId": 1,
                                                                "buttonCategories": {"screenLabels": [], "hardButtons": [], "screenButtons": []},
                                                            },
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

        html = render_single_device_html(project_data, app_ui, project_stem="popup_center_vertical_scroll", device_index=0)
        tmp_dir = Path(tempfile.mkdtemp(prefix="sentinel-ui-"))
        html_path = tmp_dir / "popup_center_vertical_scroll.html"
        html_path.write_text(html, encoding="utf-8")

        page = self._browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            page.goto(html_path.as_uri(), wait_until="domcontentloaded")
            page.locator(".vp-box").first.click()
            expect(page.locator("#vpPopup")).to_be_visible()
            for _ in range(7):
                page.locator(".zoom-inc").click()

            centered = page.evaluate(
                """() => {
                  const panel=document.getElementById('vpPopupPanel');
                  const scroller=document.getElementById('vpPopupScroller');
                  const win=document.querySelector('.vp-popup-viewport');
                  if (!panel || !scroller || !win) return null;
                  const pr=panel.getBoundingClientRect();
                  const wr=win.getBoundingClientRect();
                  const centerDx=((wr.left+wr.right)/2) - ((pr.left+pr.right)/2);
                  const hOverflow=scroller.scrollWidth > scroller.clientWidth;
                  const vOverflow=scroller.scrollHeight > scroller.clientHeight;
                  return {centerDx, hOverflow, vOverflow};
                }"""
            )
            self.assertIsNotNone(centered)
            self.assertFalse(centered["hOverflow"])
            self.assertTrue(centered["vOverflow"])
            self.assertLessEqual(abs(centered["centerDx"]), 6)
        finally:
            page.close()

    def test_popup_page_mode_controls_overlay_and_viewport_is_visually_centered(self):
        from playwright.sync_api import expect

        # Fixture: page-mode viewport wide enough that the viewport may overlap prev/next.
        # Controls overlay content (no reserved blank space), so controls must remain clickable
        # and the viewport should be visually centered relative to the nav arrows.
        project_data = {
            "devices": [
                {
                    "userFacing": {
                        "displayName": "RTI (Popup Prev/Next Overlay Page Mode Test)",
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
                                                    "navigationMode": "page",
                                                    "orientations": {
                                                        "portrait": {"visible": True, "coordinates": {"top": 10, "left": 10, "height": 90, "width": 820}},
                                                        "landscape": {"visible": True, "coordinates": {"top": 10, "left": 10, "height": 90, "width": 820}},
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
                                                            },
                                                            {
                                                                "frameId": 1,
                                                                "buttonCategories": {"screenLabels": [], "hardButtons": [], "screenButtons": []},
                                                            },
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

        html = render_single_device_html(project_data, app_ui, project_stem="popup_reserve_prev_next_page_mode", device_index=0)
        tmp_dir = Path(tempfile.mkdtemp(prefix="sentinel-ui-"))
        html_path = tmp_dir / "popup_reserve_prev_next_page_mode.html"
        html_path.write_text(html, encoding="utf-8")

        page = self._browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            page.goto(html_path.as_uri(), wait_until="domcontentloaded")
            page.locator(".vp-box").first.click()
            expect(page.locator("#vpPopup")).to_be_visible()

            measured = page.evaluate(
                """() => {
                  const panel=document.getElementById('vpPopupPanel');
                  const prev=document.getElementById('vpPopupPrev');
                  const next=document.getElementById('vpPopupNext');
                  const win=document.querySelector('.vp-popup-viewport');
                  if (!panel || !prev || !next || !win) return null;
                  const ps=getComputedStyle(prev);
                  const ns=getComputedStyle(next);
                  const ws=getComputedStyle(win);
                  const pr=panel.getBoundingClientRect();
                  const vr=win.getBoundingClientRect();
                  const lr=prev.getBoundingClientRect();
                  const rr=next.getBoundingClientRect();
                  const vcy=(vr.top+vr.bottom)/2;
                  const vcx=(vr.left+vr.right)/2;
                  const lcy=(lr.top+lr.bottom)/2;
                  const lcx=(lr.left+lr.right)/2;
                  const rcy=(rr.top+rr.bottom)/2;
                  const rcx=(rr.left+rr.right)/2;
                  const desiredX=(lcx+rcx)/2;
                  const desiredY=(lcy+rcy)/2;

                  const hitPrev=document.elementFromPoint(lcx, lcy);
                  const hitNext=document.elementFromPoint(rcx, rcy);
                  const prevOk=hitPrev && (hitPrev===prev || prev.contains(hitPrev));
                  const nextOk=hitNext && (hitNext===next || next.contains(hitNext));
                  return {
                    viewport:{left:vr.left, right:vr.right, top:vr.top, bottom:vr.bottom, cy:vcy},
                    prev:{left:lr.left, right:lr.right, cy:lcy},
                    next:{left:rr.left, right:rr.right, cy:rcy},
                    panel:{left:pr.left, right:pr.right},
                    display:{prev:ps.display, next:ns.display, viewport:ws.display},
                    dx: vcx - desiredX,
                    dy: vcy - desiredY,
                    prevOk,
                    nextOk,
                    vpFrames: (typeof PAGE_STATE!=='undefined' && typeof activePageIndex!=='undefined' && PAGE_STATE[activePageIndex]) ? (PAGE_STATE[activePageIndex].vpFrames||null) : null,
                    vpIndex: (typeof viewportMode!=='undefined' && viewportMode) ? (viewportMode.vpIndex||null) : null
                  };
                }"""
            )
            self.assertIsNotNone(measured)

            # Sanity: frame nav must be visible for this fixture.
            self.assertNotEqual(measured["display"]["prev"], "none", measured)
            self.assertNotEqual(measured["display"]["next"], "none", measured)

            # Visual centering and clickability.
            self.assertLessEqual(abs(measured["dx"]), 2.0, measured)
            self.assertLessEqual(abs(measured["dy"]), 2.0, measured)
            self.assertTrue(measured["prevOk"], measured)
            self.assertTrue(measured["nextOk"], measured)
        finally:
            page.close()

    def test_popup_scrollbars_do_not_shift_content_css_contract(self):
        # Contract: the viewport popup must not change scrollbar *width* on hover; otherwise layouts can shift.
        # This is enforced at the CSS output level because Chromium doesn't implement `scrollbar-width`.
        project_data = {
            "devices": [
                {
                    "userFacing": {
                        "displayName": "RTI (Popup Scrollbar Width Contract Test)",
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
                                                    "navigationMode": "page",
                                                    "orientations": {
                                                        "portrait": {"visible": True, "coordinates": {"top": 10, "left": 10, "height": 90, "width": 520}},
                                                        "landscape": {"visible": True, "coordinates": {"top": 10, "left": 10, "height": 90, "width": 520}},
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

        html = render_single_device_html(project_data, app_ui, project_stem="popup_scrollbar_css_contract", device_index=0)
        self.assertIn(".vp-popup-scroller", html)

        # Expect stable width: always `thin` (in Firefox) and never toggled between none/thin on hover.
        self.assertIn(".vp-popup-scroller{", html)
        self.assertIn("scrollbar-width:thin", html)
        self.assertNotIn("vp-popup-scroller.scroll-hover:hover{scrollbar-width:thin", html)
        self.assertNotIn("vp-popup-scroller{position:absolute;inset:0;overflow:hidden;scrollbar-width:none", html)

    def test_viewport_popup_scroller_fills_panel(self):
        from playwright.sync_api import expect

        # Contract: popup scroller should always fill the popup panel; reserve only exists as a
        # sizing calculation for the default fit, not as real blank margins.
        html_path = self._write_fixture_html()
        page = self._browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            page.goto(html_path.as_uri(), wait_until="domcontentloaded")
            page.locator(".vp-box").first.click()
            expect(page.locator("#vpPopup")).to_be_visible()
            sc = page.evaluate(
                """() => {
                  const s=document.getElementById('vpPopupScroller');
                  const p=document.getElementById('vpPopupPanel');
                  if (!s || !p) return null;
                  const sr=s.getBoundingClientRect();
                  const pr=p.getBoundingClientRect();
                  const cs=getComputedStyle(s);
                  return {
                    left: sr.left - pr.left,
                    top: sr.top - pr.top,
                    right: pr.right - sr.right,
                    bottom: pr.bottom - sr.bottom,
                    styleLeft: cs.left,
                    styleTop: cs.top,
                    styleRight: cs.right,
                    styleBottom: cs.bottom,
                  };
                }"""
            )
            self.assertIsNotNone(sc)
            self.assertLessEqual(abs(sc["left"]), 2.0, sc)
            self.assertLessEqual(abs(sc["top"]), 2.0, sc)
            self.assertLessEqual(abs(sc["right"]), 2.0, sc)
            self.assertLessEqual(abs(sc["bottom"]), 2.0, sc)
            self.assertIn(sc["styleLeft"], ("0px", "auto"), sc)
            self.assertIn(sc["styleTop"], ("0px", "auto"), sc)
            self.assertIn(sc["styleRight"], ("0px", "auto"), sc)
            self.assertIn(sc["styleBottom"], ("0px", "auto"), sc)
        finally:
            page.close()

    def test_viewport_popup_100_percent_does_not_overlap_controls(self):
        from playwright.sync_api import expect

        # Contract: at 100% the viewport fits between controls (reserve used only for sizing),
        # so viewport is not under the nav controls.
        html_path = self._write_fixture_html()
        page = self._browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            page.goto(html_path.as_uri(), wait_until="domcontentloaded")
            page.locator(".vp-box").first.click()
            expect(page.locator("#vpPopup")).to_be_visible()
            expect(page.locator(".zoom-reset")).to_have_text("100%")

            m = page.evaluate(
                """() => {
                  const win=document.querySelector('.vp-popup-viewport');
                  const prev=document.getElementById('vpPopupPrev');
                  const next=document.getElementById('vpPopupNext');
                  const up=document.getElementById('vpPopupUp');
                  const down=document.getElementById('vpPopupDown');
                  if (!win) return null;
                  const wr=win.getBoundingClientRect();
                  function rect(el){
                    if (!el) return null;
                    const st=getComputedStyle(el);
                    if (st.display==='none' || st.visibility==='hidden') return null;
                    const r=el.getBoundingClientRect();
                    return {left:r.left,right:r.right,top:r.top,bottom:r.bottom};
                  }
                  function intersects(a,b){
                    if(!a||!b) return false;
                    return !(a.right<=b.left || a.left>=b.right || a.bottom<=b.top || a.top>=b.bottom);
                  }
                  const rWin={left:wr.left,right:wr.right,top:wr.top,bottom:wr.bottom};
                  const rPrev=rect(prev);
                  const rNext=rect(next);
                  const rUp=rect(up);
                  const rDown=rect(down);
                  return {
                    overlapPrev: intersects(rWin, rPrev),
                    overlapNext: intersects(rWin, rNext),
                    overlapUp: intersects(rWin, rUp),
                    overlapDown: intersects(rWin, rDown),
                    rPrev, rNext, rUp, rDown,
                    rWin,
                  };
                }"""
            )
            self.assertIsNotNone(m)
            self.assertFalse(m["overlapPrev"], m)
            self.assertFalse(m["overlapNext"], m)
            self.assertFalse(m["overlapUp"], m)
            self.assertFalse(m["overlapDown"], m)
        finally:
            page.close()

    def test_viewport_popup_zoom_steps_are_linear_in_pixels(self):
        from playwright.sync_api import expect

        # Contract: 100->110 should not visually \"jump\" due to reserve/inset changes.
        # With a fixed base fit scale, each +10% step increases the viewport by a constant pixel delta.
        html_path = self._write_fixture_html()
        page = self._browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            page.goto(html_path.as_uri(), wait_until="domcontentloaded")
            page.locator(".vp-box").first.click()
            expect(page.locator("#vpPopup")).to_be_visible()

            def viewport_w() -> float:
                return page.evaluate(
                    """() => {
                      const win=document.querySelector('.vp-popup-viewport');
                      if (!win) return null;
                      return win.getBoundingClientRect().width;
                    }"""
                )

            w100 = viewport_w()
            self.assertIsNotNone(w100)
            page.locator(".zoom-inc").click()
            expect(page.locator(".zoom-reset")).to_have_text("110%")
            w110 = viewport_w()
            self.assertIsNotNone(w110)
            page.locator(".zoom-inc").click()
            expect(page.locator(".zoom-reset")).to_have_text("120%")
            w120 = viewport_w()
            self.assertIsNotNone(w120)

            d1 = w110 - w100
            d2 = w120 - w110
            self.assertLessEqual(abs(d1 - d2), 2.0, {"w100": w100, "w110": w110, "w120": w120, "d1": d1, "d2": d2})
        finally:
            page.close()

    def test_viewport_viewer_button_click_opens_testing_popup(self):
        from playwright.sync_api import expect

        html_path = self._write_fixture_html()
        page = self._browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            page.goto(html_path.as_uri(), wait_until="domcontentloaded")
            page.locator(".vp-box").first.click()
            expect(page.locator("#vpPopup")).to_be_visible()

            # Click a viewport button clone inside the viewer.
            page.locator(".vp-popup-stage .vp-btn .test-btn").first.click()

            # The testing overlay should open.
            expect(page.locator("#ov")).to_have_class("ov open")
            title = page.locator("#pt").inner_text().strip()
            self.assertIn("VP Child", title)

            # Close overlay.
            page.locator("#close").click()
            expect(page.locator("#ov")).not_to_have_class("ov open")
        finally:
            page.close()

    def test_page_link_click_closes_viewer_and_navigates(self):
        from playwright.sync_api import expect

        # Fixture: viewport contains a button with an enabled page link to a second page.
        project_data = {
            "devices": [
                {
                    "userFacing": {
                        "displayName": "RTI (Viewport Viewer Page Link Test)",
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
                                                    "navigationMode": "page",
                                                    "orientations": {
                                                        "portrait": {"visible": True, "coordinates": {"top": 10, "left": 10, "height": 120, "width": 420}},
                                                        "landscape": {"visible": True, "coordinates": {"top": 10, "left": 10, "height": 120, "width": 420}},
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
                                                                                "buttonTagName": "GO - Lights",
                                                                                "text": "Lights",
                                                                                "buttonType": None,
                                                                            },
                                                                            "buttonUI": oriented_ui(
                                                                                portrait={"visible": True, "coordinates": {"top": 10, "left": 10, "height": 44, "width": 160}},
                                                                                landscape={"visible": True, "coordinates": {"top": 10, "left": 10, "height": 44, "width": 160}},
                                                                            ),
                                                                            "testTargets": {
                                                                                "text": True,
                                                                                "macro": False,
                                                                                "variables": {"Text": False},
                                                                                "pageLink": {"enabled": True, "targetPageId": 2},
                                                                            },
                                                                            "resolvedPageLink": {"targetPageId": 2},
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
                            },
                            {
                                "pageName": "Lights",
                                "buttonCategories": {"screenLabels": [], "screenButtons": [], "hardButtons": []},
                                "viewports": [],
                            },
                        ],
                    },
                    "diagnostics": {"deviceId": 1, "pages": [{"pageId": 1, "pageName": "Home"}, {"pageId": 2, "pageName": "Lights"}]},
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
            "appNavigation": {
                "enabled": True,
                "placement": "canvas-adjacent",
                "showPageControls": True,
                "pageLinks": {
                    "enabled": True,
                    "showLinkAffordanceOnHover": False,
                    "iconPlacement": "right-center-inside-button",
                    "iconStyle": "inline-svg",
                    "iconSize": 16,
                    "iconPaddingRight": 8,
                    "hoverActivationArea": {"width": 28, "fullButtonHeight": True},
                },
            },
            "zoomControls": {"enabled": True},
            "viewportNavigation": {"enabled": True},
            "testingPopup": {"enabled": True},
            "buttonPresentation": {"fallbackFontSize": 10, "scaleRtiDerivedFontSizes": True},
            "state": {},
            "layerPanel": {"enabled": True},
        }

        html = render_single_device_html(project_data, app_ui, project_stem="viewport_viewer_page_link", device_index=0)
        tmp_dir = Path(tempfile.mkdtemp(prefix="sentinel-ui-"))
        html_path = tmp_dir / "viewport_viewer_page_link.html"
        html_path.write_text(html, encoding="utf-8")

        page = self._browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            page.goto(html_path.as_uri(), wait_until="domcontentloaded")
            page.locator(".vp-box").first.click()
            expect(page.locator("#vpPopup")).to_be_visible()

            # Click the page link hit area inside the viewer.
            page.locator(".vp-popup-stage .page-link-hit").first.click()

            # Viewer should close and active page should switch.
            expect(page.locator("#vpPopup")).to_be_hidden()
            active = page.evaluate("document.querySelector('.device-page.active')?.dataset?.pageIndex || null")
            self.assertEqual(active, "1")
        finally:
            page.close()

    def test_frame_change_resets_zoom_label_in_viewer(self):
        from playwright.sync_api import expect

        # Fixture: two-frame viewport; changing frames resets popup zoom (OK) but must also reset the label.
        project_data = {
            "devices": [
                {
                    "userFacing": {
                        "displayName": "RTI (Viewport Viewer Zoom Label Test)",
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
                                                    "navigationMode": "page",
                                                    "orientations": {
                                                        "portrait": {"visible": True, "coordinates": {"top": 10, "left": 10, "height": 120, "width": 420}},
                                                        "landscape": {"visible": True, "coordinates": {"top": 10, "left": 10, "height": 120, "width": 420}},
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
                                                            },
                                                            {
                                                                "frameId": 1,
                                                                "buttonCategories": {"screenLabels": [], "hardButtons": [], "screenButtons": []},
                                                            },
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

        html = render_single_device_html(project_data, app_ui, project_stem="viewport_viewer_zoom_label", device_index=0)
        tmp_dir = Path(tempfile.mkdtemp(prefix="sentinel-ui-"))
        html_path = tmp_dir / "viewport_viewer_zoom_label.html"
        html_path.write_text(html, encoding="utf-8")

        page = self._browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            page.goto(html_path.as_uri(), wait_until="domcontentloaded")
            page.locator(".vp-box").first.click()
            expect(page.locator("#vpPopup")).to_be_visible()

            expect(page.locator(".zoom-reset")).to_have_text("100%")
            page.locator(".zoom-inc").click()
            expect(page.locator(".zoom-reset")).to_have_text("110%")

            # Change frame (should reset zoom and label).
            page.locator("#vpPopupNext").click()
            expect(page.locator(".zoom-reset")).to_have_text("100%")
        finally:
            page.close()

    def test_popup_page_mode_does_not_drift_off_center_on_first_zoom_steps(self):
        from playwright.sync_api import expect

        # Regression: on page-mode viewports, first zoom steps used to lock the left edge and shift the viewport right
        # because the scroller didn't become scrollable even though the viewport exceeded the usable area.
        project_data = {
            "devices": [
                {
                    "userFacing": {
                        "displayName": "RTI (Popup Center Drift Page)",
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
                                                    "navigationMode": "page",
                                                    "orientations": {
                                                        "portrait": {"visible": True, "coordinates": {"top": 10, "left": 10, "height": 90, "width": 820}},
                                                        "landscape": {"visible": True, "coordinates": {"top": 10, "left": 10, "height": 90, "width": 820}},
                                                    },
                                                },
                                                "layers": [
                                                    {
                                                        "layerName": "Viewport Inner Layer",
                                                        "layerOrder": 0,
                                                        "frames": [
                                                            {"frameId": 0, "buttonCategories": {"screenLabels": [], "hardButtons": [], "screenButtons": []}},
                                                            {"frameId": 1, "buttonCategories": {"screenLabels": [], "hardButtons": [], "screenButtons": []}},
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

        html = render_single_device_html(project_data, app_ui, project_stem="popup_center_drift_page", device_index=0)
        tmp_dir = Path(tempfile.mkdtemp(prefix="sentinel-ui-"))
        html_path = tmp_dir / "popup_center_drift_page.html"
        html_path.write_text(html, encoding="utf-8")

        page = self._browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            page.goto(html_path.as_uri(), wait_until="domcontentloaded")
            page.locator(".vp-box").first.click()
            expect(page.locator("#vpPopup")).to_be_visible()

            def centered_dx():
                return page.evaluate(
                    """() => {
                      const sc=document.getElementById('vpPopupScroller');
                      const win=document.querySelector('.vp-popup-viewport');
                      if (!sc || !win) return null;
                      const sr=sc.getBoundingClientRect();
                      const wr=win.getBoundingClientRect();
                      const cs=getComputedStyle(sc);
                      const pl=parseFloat(cs.paddingLeft)||0;
                      const pr=parseFloat(cs.paddingRight)||0;
                      const pt=parseFloat(cs.paddingTop)||0;
                      const pb=parseFloat(cs.paddingBottom)||0;
                      const availW=sc.clientWidth - pl - pr;
                      const availH=sc.clientHeight - pt - pb;
                      const desiredCx=sr.left + pl + (availW/2);
                      const desiredCy=sr.top + pt + (availH/2);
                      const cx=(wr.left+wr.right)/2;
                      const cy=(wr.top+wr.bottom)/2;
                      return {dx: cx-desiredCx, dy: cy-desiredCy, sw: sc.scrollWidth, cw: sc.clientWidth};
                    }"""
                )

            c0 = centered_dx()
            self.assertIsNotNone(c0)
            self.assertLessEqual(abs(c0["dx"]), 6)

            page.locator(".zoom-inc").click()
            c1 = centered_dx()
            self.assertIsNotNone(c1)
            self.assertLessEqual(abs(c1["dx"]), 6)

            page.locator(".zoom-inc").click()
            c2 = centered_dx()
            self.assertIsNotNone(c2)
            self.assertLessEqual(abs(c2["dx"]), 6)
        finally:
            page.close()

    def test_popup_vertical_scroll_does_not_drift_off_center_on_first_zoom_steps(self):
        from playwright.sync_api import expect

        project_data = {
            "devices": [
                {
                    "userFacing": {
                        "displayName": "RTI (Popup Center Drift Vertical)",
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
                                                        "portrait": {"visible": True, "coordinates": {"top": 10, "left": 10, "height": 760, "width": 90}},
                                                        "landscape": {"visible": True, "coordinates": {"top": 10, "left": 10, "height": 760, "width": 90}},
                                                    },
                                                },
                                                "layers": [
                                                    {
                                                        "layerName": "Viewport Inner Layer",
                                                        "layerOrder": 0,
                                                        "frames": [
                                                            {"frameId": 0, "buttonCategories": {"screenLabels": [], "hardButtons": [], "screenButtons": []}},
                                                            {"frameId": 1, "buttonCategories": {"screenLabels": [], "hardButtons": [], "screenButtons": []}},
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

        html = render_single_device_html(project_data, app_ui, project_stem="popup_center_drift_vertical", device_index=0)
        tmp_dir = Path(tempfile.mkdtemp(prefix="sentinel-ui-"))
        html_path = tmp_dir / "popup_center_drift_vertical.html"
        html_path.write_text(html, encoding="utf-8")

        page = self._browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            page.goto(html_path.as_uri(), wait_until="domcontentloaded")
            page.locator(".vp-box").first.click()
            expect(page.locator("#vpPopup")).to_be_visible()

            centered = page.evaluate(
                """() => {
                  const sc=document.getElementById('vpPopupScroller');
                  const win=document.querySelector('.vp-popup-viewport');
                  if (!sc || !win) return null;
                  const sr=sc.getBoundingClientRect();
                  const wr=win.getBoundingClientRect();
                  const cs=getComputedStyle(sc);
                  const pl=parseFloat(cs.paddingLeft)||0;
                  const pr=parseFloat(cs.paddingRight)||0;
                  const pt=parseFloat(cs.paddingTop)||0;
                  const pb=parseFloat(cs.paddingBottom)||0;
                  const availW=sc.clientWidth - pl - pr;
                  const availH=sc.clientHeight - pt - pb;
                  const desiredCx=sr.left + pl + (availW/2);
                  const desiredCy=sr.top + pt + (availH/2);
                  const cx=(wr.left+wr.right)/2;
                  const cy=(wr.top+wr.bottom)/2;
                  return {dx: cx-desiredCx, dy: cy-desiredCy};
                }"""
            )
            self.assertIsNotNone(centered)
            self.assertLessEqual(abs(centered["dx"]), 6)
            self.assertLessEqual(abs(centered["dy"]), 6)

            page.locator(".zoom-inc").click()
            centered2 = page.evaluate(
                """() => {
                  const sc=document.getElementById('vpPopupScroller');
                  const win=document.querySelector('.vp-popup-viewport');
                  if (!sc || !win) return null;
                  const sr=sc.getBoundingClientRect();
                  const wr=win.getBoundingClientRect();
                  const cs=getComputedStyle(sc);
                  const pl=parseFloat(cs.paddingLeft)||0;
                  const pr=parseFloat(cs.paddingRight)||0;
                  const pt=parseFloat(cs.paddingTop)||0;
                  const pb=parseFloat(cs.paddingBottom)||0;
                  const availW=sc.clientWidth - pl - pr;
                  const availH=sc.clientHeight - pt - pb;
                  const desiredCx=sr.left + pl + (availW/2);
                  const desiredCy=sr.top + pt + (availH/2);
                  const cx=(wr.left+wr.right)/2;
                  const cy=(wr.top+wr.bottom)/2;
                  return {dx: cx-desiredCx, dy: cy-desiredCy};
                }"""
            )
            self.assertIsNotNone(centered2)
            self.assertLessEqual(abs(centered2["dx"]), 6)
            self.assertLessEqual(abs(centered2["dy"]), 6)
        finally:
            page.close()

    def test_popup_zoom_contract_centering_and_controls_on_top(self):
        from playwright.sync_api import expect

        # Contract harness: for both nav modes, across zoom steps, the viewport stays centered
        # in the usable content area (after reserving control space), viewport content never
        # overlaps reserved control zones, and popup controls remain topmost (not covered).
        #
        # Tolerance: allow <= 1 CSS pixel after rounding to device pixels to avoid flake from
        # fractional rects at different zoom/devicePixelRatio.
        def build_project_data(nav: str) -> dict:
            if nav == "page":
                coords = {"top": 10, "left": 10, "height": 90, "width": 820}
            else:
                coords = {"top": 10, "left": 10, "height": 760, "width": 90}
            return {
                "devices": [
                    {
                        "userFacing": {
                            "displayName": f"RTI (Popup Zoom Contract {nav})",
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
                                                        "navigationMode": nav,
                                                        "orientations": {
                                                            "portrait": {"visible": True, "coordinates": dict(coords)},
                                                            "landscape": {"visible": True, "coordinates": dict(coords)},
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
                                                                                    portrait={
                                                                                        "visible": True,
                                                                                        "coordinates": {"top": 15, "left": 15, "height": 60, "width": 110},
                                                                                    },
                                                                                    landscape={
                                                                                        "visible": True,
                                                                                        "coordinates": {"top": 15, "left": 15, "height": 60, "width": 110},
                                                                                    },
                                                                                ),
                                                                                "testTargets": {
                                                                                    "text": True,
                                                                                    "macros": False,
                                                                                    "macroSteps": False,
                                                                                    "variables": {},
                                                                                },
                                                                            }
                                                                        ],
                                                                    },
                                                                },
                                                                {
                                                                    "frameId": 1,
                                                                    "buttonCategories": {
                                                                        "screenLabels": [],
                                                                        "hardButtons": [],
                                                                        "screenButtons": [
                                                                            {
                                                                                "buttonIdentity": {
                                                                                    "buttonTagName": "VP Child 2",
                                                                                    "text": "VP Child 2",
                                                                                    "buttonType": None,
                                                                                },
                                                                                "buttonUI": oriented_ui(
                                                                                    portrait={
                                                                                        "visible": True,
                                                                                        "coordinates": {"top": 15, "left": 15, "height": 60, "width": 110},
                                                                                    },
                                                                                    landscape={
                                                                                        "visible": True,
                                                                                        "coordinates": {"top": 15, "left": 15, "height": 60, "width": 110},
                                                                                    },
                                                                                ),
                                                                                "testTargets": {
                                                                                    "text": True,
                                                                                    "macros": False,
                                                                                    "macroSteps": False,
                                                                                    "variables": {},
                                                                                },
                                                                            }
                                                                        ],
                                                                    },
                                                                },
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

        def run_nav(nav: str) -> None:
            html = render_single_device_html(build_project_data(nav), app_ui, project_stem=f"popup_zoom_contract_{nav}", device_index=0)
            tmp_dir = Path(tempfile.mkdtemp(prefix="sentinel-ui-"))
            html_path = tmp_dir / f"popup_zoom_contract_{nav}.html"
            html_path.write_text(html, encoding="utf-8")

            page = self._browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                page.goto(html_path.as_uri(), wait_until="domcontentloaded")
                page.locator(".vp-box").first.click()
                expect(page.locator("#vpPopup")).to_be_visible()

                # Helper: measure center deltas in device pixels and check overlap & stacking.
                def measure():
                    return page.evaluate(
                        """() => {
                          const sc=document.getElementById('vpPopupScroller');
                          const win=document.querySelector('.vp-popup-viewport');
                          const close=document.getElementById('vpPopupClose');
                          const prev=document.getElementById('vpPopupPrev');
                          const next=document.getElementById('vpPopupNext');
                          const up=document.getElementById('vpPopupUp');
                          const down=document.getElementById('vpPopupDown');
                          if (!sc || !win || !close) return null;
                          const dpr=window.devicePixelRatio || 1;
	                          const sr=sc.getBoundingClientRect();
	                          const wr=win.getBoundingClientRect();
	                          // Visual centering: match the nav-arrow midpoint (user reference), not scroller client center.
	                          function rect(el){
	                            if (!el) return null;
	                            const st=getComputedStyle(el);
	                            if (st.display==='none' || st.visibility==='hidden') return null;
	                            const r=el.getBoundingClientRect();
	                            return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,cx:(r.left+r.right)/2,cy:(r.top+r.bottom)/2};
	                          }
	                          const rPrev=rect(prev);
	                          const rNext=rect(next);
	                          const rUp=rect(up);
	                          const rDown=rect(down);
	                          let desiredCx = sr.left + (sc.clientWidth/2);
	                          let desiredCy = sr.top + (sc.clientHeight/2);
	                          if (rPrev && rNext) {
	                            desiredCx = (rPrev.cx + rNext.cx)/2;
	                            desiredCy = (rPrev.cy + rNext.cy)/2;
	                          } else if (rUp && rDown) {
	                            desiredCx = (rUp.cx + rDown.cx)/2;
	                            desiredCy = (rUp.cy + rDown.cy)/2;
	                          }
	                          const cx=(wr.left+wr.right)/2;
	                          const cy=(wr.top+wr.bottom)/2;
	                          const dx=Math.round((cx-desiredCx)*dpr)/dpr;
	                          const dy=Math.round((cy-desiredCy)*dpr)/dpr;

	                          function intersects(a,b){
	                            if(!a||!b) return false;
	                            return !(a.right<=b.left || a.left>=b.right || a.bottom<=b.top || a.top>=b.bottom);
	                          }
	                          const rWin=rect(win);
	                          const rScroller=rect(sc);
	                          const rClose=rect(close);

                          function topmostAt(el){
                            if (!el) return null;
                            const r=el.getBoundingClientRect();
                            const x=r.left + r.width/2;
                            const y=r.top + r.height/2;
                            const top=document.elementFromPoint(x,y);
                            return top ? top.closest('#' + el.id) != null : false;
                          }

                          return {
                            zoom:(document.querySelector('.zoom-reset')||{}).textContent||'',
                            dx, dy,
                            sc:rScroller, win:rWin, prev:rPrev, next:rNext, up:rUp, down:rDown, close:rClose,
                            overlapPrev: intersects(rWin, rPrev),
                            overlapNext: intersects(rWin, rNext),
                            overlapUp: intersects(rWin, rUp),
                            overlapDown: intersects(rWin, rDown),
                            topClose: topmostAt(close),
                            topPrev: rPrev ? topmostAt(prev) : null,
                            topNext: rNext ? topmostAt(next) : null,
                            topUp: rUp ? topmostAt(up) : null,
                            topDown: rDown ? topmostAt(down) : null,
                          };
                        }"""
                    )

                m0 = measure()
                self.assertIsNotNone(m0)
                self.assertLessEqual(abs(m0["dx"]), 1, m0)
                self.assertLessEqual(abs(m0["dy"]), 1, m0)

                # Continuous zoom contract 100% -> 300%.
                for _i in range(20):
                    page.locator(".zoom-inc").click()
                    m = measure()
                    self.assertIsNotNone(m)
                    self.assertLessEqual(abs(m["dx"]), 1, m)
                    self.assertLessEqual(abs(m["dy"]), 1, m)
                    self.assertTrue(m["topClose"], m)
                    if m["topPrev"] is not None:
                        self.assertTrue(m["topPrev"], m)
                    if m["topNext"] is not None:
                        self.assertTrue(m["topNext"], m)
                    if m["topUp"] is not None:
                        self.assertTrue(m["topUp"], m)
                    if m["topDown"] is not None:
                        self.assertTrue(m["topDown"], m)
            finally:
                page.close()

        run_nav("page")
        run_nav("verticalScroll")
