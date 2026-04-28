"""Static registry of hard-key remote models supported by the split-layout pipeline.

Locked rules from `hard_keys.md` (Phase 0 lock-in):

* `productModel` is resolved exclusively from `RTIDeviceData.ProductId`.
* T4x = ProductId 102 / slot range 128..147 (20 slots).
* ISR-2 = ProductId 110 / slot range 128..161 (34 slots).
* ISR-4 = ProductId 111 / slot range 128..149 (22 slots).
* Physical hard-key rows live at `FrameNumber = 254` with `ButtonLeft >= 128`; rows at
  `FrameNumber = 252` (gestures: Rotate Clockwise, Rotate Counterclockwise, Shake) are
  recorded but not rendered on the hard-key strip.

`slot_dom_order` lists `ButtonLeft` values in the order their template slots appear in
the corresponding `*_hard_keys.html` document tree. The renderer pairs each Apex
hard-key row to a template slot via this order.

Confidence:

* T4x slot order is tag-name verified against the Dash OS apex
  (`devtools/probe_hk_layer_detail.run.txt`).
* ISR-2 / ISR-4 slot order is provisional ("natural sequential reading"); the
  authoritative `Hard Key IDs.png` slot maps from `Assets/Hard Keys/` should be applied
  in a follow-up to lock these in. Test target wiring and split layout work regardless
  of the specific mapping; only on-screen position is affected.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_DIR = ROOT / "sentinel" / "ui" / "testing" / "hard_keys"


@dataclass(frozen=True)
class HardKeyModel:
    key: str
    product_id: int
    slot_range: tuple[int, int]
    slot_dom_order: tuple[int, ...]
    design_size: tuple[int, int]
    template_html_path: Path

    def slot_count(self) -> int:
        lo, hi = self.slot_range
        return hi - lo + 1


_T4X_SLOT_DOM_ORDER: tuple[int, ...] = (
    128, 129, 130,
    131, 132, 133, 134,
    140, 141,
    135,
    136, 139, 137,
    138,
    142, 143,
    144, 145, 146, 147,
)


def _sequential_range(lo: int, hi: int) -> tuple[int, ...]:
    return tuple(range(lo, hi + 1))


MODELS: dict[str, HardKeyModel] = {
    "t4x": HardKeyModel(
        key="t4x",
        product_id=102,
        slot_range=(128, 147),
        slot_dom_order=_T4X_SLOT_DOM_ORDER,
        design_size=(608, 732),
        template_html_path=TEMPLATE_DIR / "t4x_hard_keys.html",
    ),
    "isr2": HardKeyModel(
        key="isr2",
        product_id=110,
        slot_range=(128, 161),
        slot_dom_order=_sequential_range(128, 161),
        design_size=(468, 862),
        template_html_path=TEMPLATE_DIR / "isr2_hard_keys.html",
    ),
    "isr4": HardKeyModel(
        key="isr4",
        product_id=111,
        slot_range=(128, 149),
        slot_dom_order=_sequential_range(128, 149),
        design_size=(602, 734),
        template_html_path=TEMPLATE_DIR / "isr4_hard_keys.html",
    ),
}


_PRODUCT_MODEL_BY_PRODUCT_ID: dict[int, str] = {m.product_id: m.key for m in MODELS.values()}


def product_model_for_product_id(product_id: Optional[int]) -> Optional[str]:
    if product_id is None:
        return None
    try:
        pid = int(product_id)
    except (TypeError, ValueError):
        return None
    return _PRODUCT_MODEL_BY_PRODUCT_ID.get(pid)


def model_for_key(model_key: Optional[str]) -> Optional[HardKeyModel]:
    if not model_key:
        return None
    return MODELS.get(str(model_key))


def slot_in_range(model_key: str, button_left: int) -> bool:
    model = model_for_key(model_key)
    if model is None:
        return False
    lo, hi = model.slot_range
    return lo <= int(button_left) <= hi
