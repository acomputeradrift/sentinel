import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _row(**kw):
    return SimpleNamespace(**kw)


def _btn(*, button_id, button_left, button_top=0, frame=254, order=0, width=0, height=0, tag_id=0):
    """Build a stub button row mimicking sqlite3.Row indexing semantics used by the extractor helper."""
    data = {
        "ButtonId": button_id,
        "ButtonLeft": button_left,
        "ButtonTop": button_top,
        "FrameNumber": frame,
        "ButtonOrder": order,
        "ButtonWidth": width,
        "ButtonHeight": height,
        "ButtonTagId": tag_id,
    }
    return data


class ExtractorProductModelTest(unittest.TestCase):
    def test_resolve_product_model_via_extractor_helper(self) -> None:
        from sentinel.extraction import extractor_core

        self.assertEqual(extractor_core._resolve_product_model({"ProductId": 102}), "t4x")
        self.assertEqual(extractor_core._resolve_product_model({"ProductId": 110}), "isr2")
        self.assertEqual(extractor_core._resolve_product_model({"ProductId": 111}), "isr4")
        self.assertIsNone(extractor_core._resolve_product_model({"ProductId": 95}))
        self.assertIsNone(extractor_core._resolve_product_model({"ProductId": None}))
        self.assertIsNone(extractor_core._resolve_product_model({}))


class ExtractorHardKeyClassificationTest(unittest.TestCase):
    def test_split_rows_into_slots_gestures_and_unmapped(self) -> None:
        from sentinel.extraction import extractor_core

        rows = [
            # gestures (frame 252)
            _btn(button_id=21, button_left=0, frame=252, order=20, tag_id=21),
            _btn(button_id=22, button_left=1, frame=252, order=21, tag_id=22),
            _btn(button_id=23, button_left=2, frame=252, order=22, tag_id=23),
            # in-range physical slots (frame 254, ButtonLeft 128..147 for t4x)
            _btn(button_id=1, button_left=128, frame=254, order=0, tag_id=1),
            _btn(button_id=2, button_left=129, frame=254, order=1, tag_id=2),
            _btn(button_id=3, button_left=147, frame=254, order=19, tag_id=3),
            # out-of-range physical slot (above max for t4x -> unmapped)
            _btn(button_id=4, button_left=150, frame=254, order=20, tag_id=4),
            # noise: width/height non-zero -> not a hard key at all
            _btn(button_id=5, button_left=10, frame=254, order=21, tag_id=5, width=40, height=40),
        ]

        result = extractor_core._classify_hard_key_rows(rows, product_model="t4x")
        self.assertEqual([s["buttonId"] for s in result["slots"]], [1, 2, 3])
        self.assertEqual([s["slotKey"] for s in result["slots"]], [128, 129, 147])
        self.assertEqual([g["buttonId"] for g in result["gestures"]], [21, 22, 23])
        self.assertEqual([u["buttonId"] for u in result["unmappedSlots"]], [4])
        self.assertEqual(result["unmappedSlots"][0]["reason"], "outsideTemplateRange")

    def test_sort_order_is_frame_top_left_order(self) -> None:
        from sentinel.extraction import extractor_core

        rows = [
            _btn(button_id=10, button_left=130, frame=254, order=2, tag_id=10),
            _btn(button_id=11, button_left=128, frame=254, order=0, tag_id=11),
            _btn(button_id=12, button_left=129, frame=254, order=1, tag_id=12),
        ]
        result = extractor_core._classify_hard_key_rows(rows, product_model="t4x")
        self.assertEqual([s["slotKey"] for s in result["slots"]], [128, 129, 130])

    def test_unknown_product_model_yields_none(self) -> None:
        from sentinel.extraction import extractor_core

        rows = [_btn(button_id=1, button_left=128, frame=254, order=0, tag_id=1)]
        result = extractor_core._classify_hard_key_rows(rows, product_model=None)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
