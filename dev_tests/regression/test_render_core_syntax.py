import unittest
from pathlib import Path
import py_compile


class RenderCoreSyntaxTest(unittest.TestCase):
    def test_render_core_py_compiles(self):
        root = Path(__file__).resolve().parents[2]
        target = root / "src" / "sentinel" / "generation" / "render_core.py"
        self.assertTrue(target.exists(), f"Missing file: {target}")
        py_compile.compile(str(target), doraise=True)
