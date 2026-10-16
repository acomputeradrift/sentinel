"""Minimal proof: commissioning shell copyFilteredStyles allow-list (mirrors static layout).

Hard-key template CSS is copied via ``data-sentinel-hard-key-template`` (whole block).
The filtered pass keeps device-page / split / popup rules whose selectors match allowTokens.
"""
from __future__ import annotations

import re
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

    def test_hk_button_font_size_token_in_theme(self) -> None:
        from pathlib import Path

        theme = (Path(__file__).resolve().parents[2] / "src/sentinel/ui/commissioning/sentinel_device_theme.css").read_text(
            encoding="utf-8"
        )
        self.assertIn("--sentinel-hard-button-font-size: 12px", theme)
        self.assertIn(".rti-device-canvas-hk .hk-btn-wrap .test-btn", theme)

    def test_hk_strip_row_surround_color_override_in_theme(self) -> None:
        from pathlib import Path

        theme = (Path(__file__).resolve().parents[2] / "src/sentinel/ui/commissioning/sentinel_device_theme.css").read_text(
            encoding="utf-8"
        )
        self.assertIn(".hk-split-right .frame > .middle-row", theme)
        self.assertIn("border-color: var(--sentinel-hk-remote-surround-bg)", theme)

    def test_testing_popup_selectors_survive_filter(self) -> None:
        self.assertTrue(_shell_style_selector_allowed(".ov"))
        self.assertTrue(_shell_style_selector_allowed(".pop h3"))
        self.assertTrue(_shell_style_selector_allowed(".rows-scroll"))
        self.assertTrue(_shell_style_selector_allowed(".row"))
        self.assertTrue(_shell_style_selector_allowed("#close"))
        self.assertTrue(_shell_style_selector_allowed("#passAll:disabled"))

    def test_live_shell_html_allows_overlay_action_button_rules(self) -> None:
        from pathlib import Path

        html = (
            Path(__file__).resolve().parents[2]
            / "src/sentinel/ui/commissioning/project_device_static_layout.html"
        ).read_text(encoding="utf-8")
        start = html.find("const allowTokens = [")
        self.assertGreaterEqual(start, 0)
        block = html[start : html.find("];", start) + 2]
        self.assertIn('".ov"', block)
        self.assertIn('".actions"', block)
        self.assertIn('".pop"', block)

    def test_live_shell_html_allows_viewport_indicator_rules(self) -> None:
        from pathlib import Path

        html = (
            Path(__file__).resolve().parents[2]
            / "src/sentinel/ui/commissioning/project_device_static_layout.html"
        ).read_text(encoding="utf-8")
        start = html.find("const allowTokens = [")
        self.assertGreaterEqual(start, 0)
        block = html[start : html.find("];", start) + 2]
        self.assertIn('".vp-popup-indicator"', block)
        self.assertIn('".vp-indicator"', block)
        self.assertIn('".dot"', block)

    def test_shell_css_defines_viewport_indicator_dots(self) -> None:
        from pathlib import Path

        css = (
            Path(__file__).resolve().parents[2]
            / "src/sentinel/ui/commissioning/project_device_static_layout.css"
        ).read_text(encoding="utf-8")
        self.assertIn(".vp-popup-indicator", css)
        self.assertIn(".vp-popup-indicator.is-vertical", css)
        self.assertIn(".vp-indicator", css)
        self.assertIn(".dot", css)
        self.assertIn(".dot.active", css)
        self.assertIn("z-index: 205", css)
        self.assertIn("#9fb4c6", css)
        self.assertIn("#2d5f81", css)


_CSS_RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.DOTALL)


def _css_rules(css: str) -> list[tuple[str, str]]:
    stripped = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    return [(selector.strip(), body) for selector, body in _CSS_RULE_RE.findall(stripped)]


def _sets_overflow(body: str, value: str) -> bool:
    return re.search(rf"overflow\s*:\s*{re.escape(value)}\b", body) is not None


class HardKeyScrollportOverflowTest(unittest.TestCase):
    def test_shell_hard_key_rule_keeps_usable_canvas_scrollable(self) -> None:
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        css = (
            root / "src/sentinel/ui/commissioning/project_device_static_layout.css"
        ).read_text(encoding="utf-8")
        rules = _css_rules(css)
        for selector, body in rules:
            if "rtiUsableCanvas" in selector:
                self.assertFalse(
                    _sets_overflow(body, "visible"),
                    msg=f"hard-key shell must not set the scrollport to overflow: visible ({selector})",
                )
            if "rti-device-canvas-hk" in selector and "deviceLayoutStage" in selector:
                self.assertFalse(
                    _sets_overflow(body, "visible"),
                    msg=f"hard-key shell must not force the stage to overflow: visible ({selector})",
                )
        usable = next(body for selector, body in rules if selector == ".rtiUsableCanvas")
        self.assertTrue(_sets_overflow(usable, "auto"))
        stage = next(body for selector, body in rules if selector == ".deviceLayoutStage")
        self.assertTrue(_sets_overflow(stage, "hidden"))
        device = next(body for selector, body in rules if selector == ".rtiDeviceContent.rti-device-canvas-hk")
        self.assertTrue(_sets_overflow(device, "visible"))

    def test_theme_keeps_hard_key_ring_overflow_visible(self) -> None:
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        theme = (root / "src/sentinel/ui/commissioning/sentinel_device_theme.css").read_text(encoding="utf-8")
        rules = _css_rules(theme)
        ring_selectors = (
            ".rti-device-canvas.rti-device-canvas-hk",
            ".rtiDeviceContent.rti-device-canvas-hk",
            ".rti-device-canvas-hk .hk-touch-stack",
            ".rti-device-canvas-hk .device-page .hk-split-right.hk-tight-cluster",
            ".rti-device-canvas-hk .device-page .hk-split-right.hk-traced-remote",
            ".rti-device-canvas-hk .device-page.active",
        )
        for fragment in ring_selectors:
            bodies = [body for selector, body in rules if fragment in selector and _sets_overflow(body, "visible")]
            self.assertTrue(bodies, msg=f"ring rule must stay overflow: visible ({fragment})")

    def test_source_runtime_hard_key_scrollport_stays_auto(self) -> None:
        from pathlib import Path

        text = (
            Path(__file__).resolve().parents[2] / "src/sentinel/generation/render_core.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(".app-canvas:has(.rti-device-canvas-hk){{overflow:visible !important;}}", text)
        self.assertNotIn(
            ".app-canvas:has(.rti-device-canvas-hk) .rti-canvas{{overflow:visible !important;}}",
            text,
        )
        self.assertIn(".rti-canvas{{position:absolute;box-sizing:border-box;z-index:1;overflow:auto;", text)
        self.assertIn(
            ".rti-device-canvas.rti-device-canvas-hk{{position:absolute;border:0;overflow:visible;",
            text,
        )
        self.assertIn(
            ".rti-device-canvas-hk .device-page.active{{display:block;padding:0;height:100%;min-height:0;max-height:100%;overflow:visible;",
            text,
        )
        self.assertIn(
            ".rti-device-canvas-hk .device-page .hk-split-left{{position:absolute;top:0;bottom:0;height:auto;display:flex;align-items:center;justify-content:center;overflow:visible;",
            text,
        )


if __name__ == "__main__":
    unittest.main()
