import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.extraction import extractor_core


class _StubCursor:
    def __init__(self, rows_by_shared_layer):
        self.rows_by_shared_layer = dict(rows_by_shared_layer)
        self.execute_calls = []
        self._active_rows = []

    def execute(self, sql, params=()):
        self.execute_calls.append((str(sql), tuple(params)))
        shared_layer_id = int(params[0])
        self._active_rows = list(self.rows_by_shared_layer.get(shared_layer_id, []))

    def fetchall(self):
        return list(self._active_rows)


class SharedLayerButtonCacheTest(unittest.TestCase):
    def test_fetch_uses_cache_for_repeated_shared_layer(self):
        cur = _StubCursor({300: [{"ButtonId": 1}, {"ButtonId": 2}]})
        cache = {}

        first = extractor_core._shared_layer_buttons(cur, 300, cache)
        second = extractor_core._shared_layer_buttons(cur, 300, cache)

        self.assertEqual(first, second)
        self.assertEqual(len(cur.execute_calls), 1)
        self.assertEqual(cur.execute_calls[0][1], (300,))

    def test_fetch_caches_empty_results(self):
        cur = _StubCursor({})
        cache = {}

        first = extractor_core._shared_layer_buttons(cur, 999, cache)
        second = extractor_core._shared_layer_buttons(cur, 999, cache)

        self.assertEqual(first, [])
        self.assertEqual(second, [])
        self.assertEqual(len(cur.execute_calls), 1)

if __name__ == "__main__":
    unittest.main()
