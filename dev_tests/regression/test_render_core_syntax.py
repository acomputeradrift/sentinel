import unittest
from pathlib import Path
import py_compile


class RenderCoreSyntaxTest(unittest.TestCase):
    def test_render_core_py_compiles(self):
        root = Path(__file__).resolve().parents[2]
        target = root / "src" / "sentinel" / "generation" / "render_core.py"
        self.assertTrue(target.exists(), f"Missing file: {target}")
        py_compile.compile(str(target), doraise=True)

    def test_render_core_uses_split_device_theme_css_asset(self):
        root = Path(__file__).resolve().parents[2]
        render_core = root / "src" / "sentinel" / "generation" / "render_core.py"
        theme_css = root / "src" / "sentinel" / "ui" / "testing" / "sentinel_device_theme.css"
        self.assertTrue(render_core.exists(), f"Missing file: {render_core}")
        self.assertTrue(theme_css.exists(), f"Missing file: {theme_css}")
        text = render_core.read_text(encoding="utf-8")
        self.assertIn("def _sentinel_device_theme_css()", text)
        self.assertIn("sentinel_device_theme.css", text)
        self.assertIn("{device_theme_css}", text)

    def test_commissioning_sentinel_device_theme_matches_testing_copy(self):
        """Commissioning static must include a copy that stays byte-identical to the testing theme."""
        root = Path(__file__).resolve().parents[2]
        a = root / "src" / "sentinel" / "ui" / "testing" / "sentinel_device_theme.css"
        b = root / "src" / "sentinel" / "ui" / "commissioning" / "sentinel_device_theme.css"
        self.assertTrue(a.exists(), f"Missing file: {a}")
        self.assertTrue(b.exists(), f"Missing file: {b}")
        self.assertEqual(
            a.read_text(encoding="utf-8"),
            b.read_text(encoding="utf-8"),
            "Update both files together (or copy testing → commissioning) so /commissioning/ shell matches embed.",
        )

    def test_runtime_radius_reads_both_base_and_px_theme_vars(self):
        root = Path(__file__).resolve().parents[2]
        render_core = root / "src" / "sentinel" / "generation" / "render_core.py"
        self.assertTrue(render_core.exists(), f"Missing file: {render_core}")
        text = render_core.read_text(encoding="utf-8")
        self.assertIn("--sentinel-device-button-radius-base", text)
        self.assertIn("--sentinel-device-button-radius", text)

    def test_group_pass_embed_is_injected(self):
        root = Path(__file__).resolve().parents[2]
        render_core = root / "src" / "sentinel" / "generation" / "render_core.py"
        embed = root / "src" / "sentinel" / "ui" / "testing" / "sentinel_group_pass_embed.js"
        self.assertTrue(embed.exists(), f"Missing file: {embed}")
        text = render_core.read_text(encoding="utf-8")
        self.assertIn("def _sentinel_group_pass_embed_js()", text)
        self.assertIn("{_group_embed}", text)
        self.assertIn("handleViewportBoxClick", text)
        js = embed.read_text(encoding="utf-8")
        self.assertIn("test_result.submit_batch", js)
        self.assertIn("handleTestButtonClick", js)
        self.assertIn("handleViewportBoxClick", js)
        self.assertIn("shiftKey", js)
        self.assertIn("sentinelGroupMarquee", js)
        self.assertIn("sentinelGroupActions", js)
        self.assertIn("touch-action:none", js)
        self.assertNotIn("sentinelGroupBar", js)
        self.assertNotIn("padding-bottom:84px", js)
        self.assertIn("pruneDisabled", js)
        self.assertIn('textContent = "Select"', js)
        status_js = (root / "src" / "sentinel" / "ui" / "testing" / "sentinel_test_status_embed.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("filterWorkTargets", status_js)
