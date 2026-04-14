import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.extraction.extractor_core import _load_scrolling_list_item_heights


class ScrollingListItemHeightExtractionTest(unittest.TestCase):
    def test_load_maps_page_sharedlayer_button_to_item_height(self) -> None:
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(
            "CREATE TABLE ScrollingList (PageId INTEGER, SharedLayerId INTEGER, ButtonId INTEGER, ItemHeight INTEGER)"
        )
        cur.execute("INSERT INTO ScrollingList VALUES (5, 7, 42, 33)")
        cur.execute("INSERT INTO ScrollingList VALUES (1, 0, 0, 10)")
        cur.execute("INSERT INTO ScrollingList VALUES (2, 1, 3, 0)")
        got = _load_scrolling_list_item_heights(cur)
        self.assertEqual(got[(5, 7, 42)], 33)
        self.assertNotIn((1, 0, 0), got)
        self.assertNotIn((2, 1, 3), got)
        con.close()

    def test_missing_table_returns_empty(self) -> None:
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        self.assertEqual(_load_scrolling_list_item_heights(cur), {})
        con.close()


if __name__ == "__main__":
    unittest.main()
