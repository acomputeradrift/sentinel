import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.extraction.extractor_core import _build_next_in_group_sequences


class NextInGroupSequencesTest(unittest.TestCase):
    def test_orders_by_page_order_then_page_id(self) -> None:
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        cur = con.execute(
            """
            select 10 as PageId, 5 as RTIAddress, 7 as SourceDeviceId, 1 as PageOrder
            union all select 11, 5, 7, 1
            union all select 9, 5, 7, 0
            """
        )
        rows = cur.fetchall()
        page_room = {9: 2, 10: 2, 11: 2}
        m = _build_next_in_group_sequences(rows, page_room)
        self.assertEqual(m.get((5, 7, 2)), [9, 10, 11])

    def test_single_page_group_omitted(self) -> None:
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        cur = con.execute(
            "select 1 as PageId, 1 as RTIAddress, 0 as SourceDeviceId, 0 as PageOrder"
        )
        rows = cur.fetchall()
        m = _build_next_in_group_sequences(rows, {1: 0})
        self.assertEqual(m, {})


if __name__ == "__main__":
    unittest.main()
