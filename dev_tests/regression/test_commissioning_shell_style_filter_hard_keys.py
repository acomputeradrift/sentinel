"""Minimal proof: commissioning shell copyFilteredStyles allow-list (mirrors static layout).

Hard-key template CSS is copied via ``data-sentinel-hard-key-template`` (whole block).
The filtered pass keeps device-page / split / popup rules whose selectors match allowTokens.
"""
from __future__ import annotations

import unittest

# Mirrors project_device_static_layout.html copyFilteredStyles → allowSelector (keep in sync).
_ALLOW_TOKENS: tuple[str, ...] = (
    ".rti-canvas",
    ".rti-content",
    ".rti-device-canvas",
    ".rti-device-canvas-hk",
    ".rtiDeviceContent",
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
    ".hk-split-right .",
    ".hk-split-left .",
    ".hk-touch-stack",
    ".hk-btn-wrap",
    ".ov",
    ".pop",
    ".rows-scroll",
    ".row",
    ".row-head",
    ".row-meta",
    ".n",
    ".actions",
    "textarea",
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
    t = " ".join(s.split()).strip()
    if t in ("#close", "#close:disabled", "#passAll", "#passAll:disabled"):
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
        self.assertFalse(_shell_style_selector_allowed(".box"))
        self.assertFalse(_shell_style_selector_allowed(".cell"))
        self.assertFalse(_shell_style_selector_allowed('.hk-split-right[data-hk-model="isr2"]'))

    def test_split_chrome_selectors_survive_filter(self) -> None:
        self.assertTrue(_shell_style_selector_allowed(".rti-device-canvas-hk .device-page .hk-split-left"))
        self.assertTrue(_shell_style_selector_allowed(".rti-device-canvas-hk .device-page .hk-split-right"))
        self.assertTrue(
            _shell_style_selector_allowed(".rti-device-canvas-hk .device-page .hk-split-right.hk-tight-cluster")
        )
        self.assertTrue(
            _shell_style_selector_allowed(
                ".rti-device-canvas-hk .device-page .hk-split-right.hk-tight-cluster .hk-cluster-rim"
            )
        )
        self.assertTrue(
            _shell_style_selector_allowed(".rtiDeviceContent:not(.rti-device-canvas-hk)"),
            msg="shared sentinel_device_theme.css uses .rtiDeviceContent for commissioning mount",
        )

    def test_hk_slot_and_frame_rules_survive_filter(self) -> None:
        self.assertTrue(_shell_style_selector_allowed(".hk-split-right .box"))
        self.assertTrue(_shell_style_selector_allowed(".hk-split-right .frame"))
        self.assertTrue(_shell_style_selector_allowed(".hk-btn-wrap .test-btn"))

    def test_hk_strip_row_surround_color_override_in_theme(self) -> None:
        from pathlib import Path

        theme = (Path(__file__).resolve().parents[2] / "src/sentinel/ui/commissioning/sentinel_device_theme.css").read_text(
            encoding="utf-8"
        )
        self.assertIn(".hk-split-right .frame > .row", theme)
        self.assertIn("border-color: var(--sentinel-hk-remote-surround-bg)", theme)

    def test_testing_popup_selectors_survive_filter(self) -> None:
        self.assertTrue(_shell_style_selector_allowed(".ov"))
        self.assertTrue(_shell_style_selector_allowed(".pop h3"))
        self.assertTrue(_shell_style_selector_allowed(".rows-scroll"))
        self.assertTrue(_shell_style_selector_allowed(".row"))
        self.assertTrue(_shell_style_selector_allowed("#close"))
        self.assertTrue(_shell_style_selector_allowed("#passAll:disabled"))


if __name__ == "__main__":
    unittest.main()
