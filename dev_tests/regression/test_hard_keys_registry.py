import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class HardKeysRegistryTest(unittest.TestCase):
    def test_known_product_models_present(self) -> None:
        from sentinel.generation.hard_keys import registry as hk

        models = set(hk.MODELS.keys())
        self.assertEqual(models, {"t4x", "isr2", "isr4"})

    def test_t4x_locked_slot_range_and_design(self) -> None:
        from sentinel.generation.hard_keys import registry as hk

        t4x = hk.MODELS["t4x"]
        self.assertEqual(t4x.product_id, 102)
        self.assertEqual(t4x.slot_range, (128, 147))
        self.assertEqual(len(t4x.slot_dom_order), 20)
        self.assertEqual(t4x.design_size, (608, 732))
        self.assertTrue(t4x.template_html_path.exists(), f"missing template: {t4x.template_html_path}")

    def test_isr4_locked_slot_range_and_design(self) -> None:
        from sentinel.generation.hard_keys import registry as hk

        isr4 = hk.MODELS["isr4"]
        self.assertEqual(isr4.product_id, 111)
        self.assertEqual(isr4.slot_range, (128, 149))
        self.assertEqual(len(isr4.slot_dom_order), 22)
        self.assertEqual(isr4.design_size, (602, 734))
        self.assertTrue(isr4.template_html_path.exists())

    def test_isr2_locked_slot_range_and_design(self) -> None:
        from sentinel.generation.hard_keys import registry as hk

        isr2 = hk.MODELS["isr2"]
        self.assertEqual(isr2.product_id, 110)
        self.assertEqual(isr2.slot_range, (128, 161))
        self.assertEqual(len(isr2.slot_dom_order), 34)
        self.assertEqual(isr2.design_size, (468, 862))
        self.assertTrue(isr2.template_html_path.exists())
        self.assertIsNotNone(isr2.slot_by_data_label)
        lbl = isr2.slot_by_data_label or {}
        self.assertEqual(len(lbl), 34)
        lo, hi = isr2.slot_range
        self.assertEqual(sorted(lbl.values()), list(range(lo, hi + 1)))

    def test_t4x_isr4_use_dom_order_not_data_labels(self) -> None:
        from sentinel.generation.hard_keys import registry as hk

        self.assertIsNone(hk.MODELS["t4x"].slot_by_data_label)
        self.assertIsNone(hk.MODELS["isr4"].slot_by_data_label)

    def test_resolve_product_model_from_product_id(self) -> None:
        from sentinel.generation.hard_keys import registry as hk

        self.assertEqual(hk.product_model_for_product_id(102), "t4x")
        self.assertEqual(hk.product_model_for_product_id(110), "isr2")
        self.assertEqual(hk.product_model_for_product_id(111), "isr4")
        self.assertIsNone(hk.product_model_for_product_id(0))
        self.assertIsNone(hk.product_model_for_product_id(95))
        self.assertIsNone(hk.product_model_for_product_id(None))

    def test_slot_dom_order_within_range(self) -> None:
        from sentinel.generation.hard_keys import registry as hk

        for key, model in hk.MODELS.items():
            lo, hi = model.slot_range
            for slot in model.slot_dom_order:
                self.assertGreaterEqual(slot, lo, f"{key}: slot {slot} below range {lo}")
                self.assertLessEqual(slot, hi, f"{key}: slot {slot} above range {hi}")
            self.assertEqual(len(set(model.slot_dom_order)), len(model.slot_dom_order), f"{key}: duplicate slot in dom order")


if __name__ == "__main__":
    unittest.main()
