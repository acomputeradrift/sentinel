import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.extraction import extractor_core


class DiagUiItemsMergeTest(unittest.TestCase):
    def test_merge_adds_missing_and_dedupes(self):
        base = [{"buttonId": 10}, {"buttonId": 20}]
        incoming = [20, 30, 30, 40]
        out = extractor_core._merge_diag_ui_items(base, incoming)
        self.assertEqual([{"buttonId": 10}, {"buttonId": 20}, {"buttonId": 30}, {"buttonId": 40}], out)


if __name__ == "__main__":
    unittest.main()
