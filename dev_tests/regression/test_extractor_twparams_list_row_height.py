import struct
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.extraction import extractor_core


class ExtractorTwparamsListRowHeightTest(unittest.TestCase):
    def test_reads_key_502_from_twparams_blob(self):
        blob = struct.pack(
            "<IIIIIIIIIIII",
            500,
            0,
            501,
            0,
            502,
            90,
            503,
            1,
            540,
            0,
            541,
            0,
        )
        self.assertEqual(extractor_core._list_item_height_from_twparams_blob(blob), 90)

    def test_returns_none_when_key_502_missing(self):
        blob = struct.pack("<IIII", 500, 0, 501, 0)
        self.assertIsNone(extractor_core._list_item_height_from_twparams_blob(blob))

    def test_returns_none_for_empty_blob(self):
        self.assertIsNone(extractor_core._list_item_height_from_twparams_blob(None))
        self.assertIsNone(extractor_core._list_item_height_from_twparams_blob(b""))


if __name__ == "__main__":
    unittest.main()
