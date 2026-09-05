import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class CommissioningClearTestsRemovedTest(unittest.TestCase):
    def test_console_does_not_expose_clear_tests_tab(self):
        html = (ROOT / "src" / "sentinel" / "ui" / "commissioning" / "index.html").read_text(
            encoding="utf-8"
        )
        js = (ROOT / "src" / "sentinel" / "ui" / "commissioning" / "commissioning.js").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("tab-clear-tests", html)
        self.assertNotIn("panel-clear-tests", html)
        self.assertNotIn("clearTestsBtn", html)
        self.assertNotIn("Clear Tests", html)
        self.assertNotIn("clearTestsForProject", js)
        self.assertNotIn("/clear-tests", js)
        self.assertNotIn("clear-tests", js)
