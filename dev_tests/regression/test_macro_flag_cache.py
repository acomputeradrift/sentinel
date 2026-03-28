import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.extraction import extractor_core


class MacroFlagCacheTest(unittest.TestCase):
    def test_build_macro_flag_summary_cache_dedupes_and_formats(self):
        rows = [
            (101, 1, 2),
            (101, 1, 2),  # duplicate row should dedupe
            (101, None, 3),
            (101, 4, None),
            (102, None, None),  # no summary emitted
            (103, 7, 8),
        ]
        out = extractor_core._build_macro_flag_summary_cache(rows)
        self.assertEqual(
            {
                101: ["FlagIndex=1, FlagType=2", "FlagType=3", "FlagIndex=4"],
                103: ["FlagIndex=7, FlagType=8"],
            },
            out,
        )


if __name__ == "__main__":
    unittest.main()
