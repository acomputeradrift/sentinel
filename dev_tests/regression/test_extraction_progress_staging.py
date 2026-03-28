import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


from sentinel.extraction.extractor_core import _map_staged_progress


class ExtractionProgressStagingTest(unittest.TestCase):
    def test_staged_progress_ranges(self):
        self.assertEqual(_map_staged_progress("setup", 0), 0)
        self.assertEqual(_map_staged_progress("setup", 100), 15)
        self.assertEqual(_map_staged_progress("work", 0), 15)
        self.assertEqual(_map_staged_progress("work", 100), 92)
        self.assertEqual(_map_staged_progress("finalize", 0), 92)
        self.assertEqual(_map_staged_progress("finalize", 100), 100)


if __name__ == "__main__":
    unittest.main()
