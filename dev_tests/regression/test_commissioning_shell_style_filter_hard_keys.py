"""Minimal proof: commissioning shell style filter drops hard-key template selectors.

The shell's copyFilteredStyles (project_device_static_layout.html) only keeps rules whose
selector substring-matches allowTokens. Hard-key layout CSS uses .frame, .row, .box, and
the scoped :root rewrite (.hk-split-right[data-hk-model="..."]); those do not match, so
geometry never reaches the shell — independent of Apex or render_core slot logic.
"""
from __future__ import annotations

import unittest

# Mirrors project_device_static_layout.html copyFilteredStyles → allowSelector (2026-04).
_ALLOW_TOKENS: tuple[str, ...] = (
    ".rti-canvas",
    ".rti-content",
    ".rti-device-canvas",
    ".device-page",
    ".vp-box",
    ".vp-overlay",
    ".btn-wrap",
    ".synthetic-list-scroll",
    ".test-btn",
    ".btn-pass-total",
    ".page-link-hit",
    ".page-link-icon",
    ".material-symbols-outlined",
    ".vp-popup",
    ".vp-popup-panel",
    ".vp-popup-scroller",
    ".vp-popup-stage",
    ".vp-popup-scrollpad",
    ".vp-popup-close",
    ".vp-popup-nav",
    ".vp-popup-prev",
    ".vp-popup-next",
    ".vp-popup-up",
    ".vp-popup-down",
    ".vp-popup-indicator",
    ".vp-popup-viewport",
    ".vp-popup-vcontent",
    ".vp-indicator",
    ".dot",
    ".viewport-mode",
)

_BLOCK_TOKENS: tuple[str, ...] = (
    ".app-canvas",
    ".app-ui-controls",
    ".top-controls",
    ".bottom-controls",
    ".left-controls",
    ".right-controls",
    ".layer-controls",
    ".orientation-controls",
    ".zoom-controls",
    "#topControls",
    "#bottomControls",
    "#layerControls",
    "#orientationControls",
    "#zoomControls",
    "#rtiCanvas",
    "#rtiContent",
    "#rtiDeviceCanvas",
)


def _shell_style_selector_allowed(selector: str) -> bool:
    s = str(selector or "")
    if not s:
        return False
    if ".viewport-mode #rtiCanvas" in s:
        return True
    if "#" in s:
        return False
    for tok in _BLOCK_TOKENS:
        if tok in s:
            return False
    for tok in _ALLOW_TOKENS:
        if tok in s:
            return True
    return False


class CommissioningShellHardKeyStyleFilterTest(unittest.TestCase):
    def test_hard_key_template_selectors_are_filtered_out(self) -> None:
        self.assertFalse(_shell_style_selector_allowed(".frame"))
        self.assertFalse(_shell_style_selector_allowed(".row"))
        self.assertFalse(_shell_style_selector_allowed(".box"))
        self.assertFalse(_shell_style_selector_allowed(".cell"))
        self.assertFalse(_shell_style_selector_allowed('.hk-split-right[data-hk-model="isr2"]'))

    def test_split_chrome_selectors_survive_filter(self) -> None:
        self.assertTrue(_shell_style_selector_allowed(".rti-device-canvas-hk .device-page .hk-split-left"))
        self.assertTrue(_shell_style_selector_allowed(".rti-device-canvas-hk .device-page .hk-split-right"))


if __name__ == "__main__":
    unittest.main()
