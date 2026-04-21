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
