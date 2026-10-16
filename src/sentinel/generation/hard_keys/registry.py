"""Static registry of hard-key remote models supported by the split-layout pipeline.

Locked rules from `hard_keys.md` (Phase 0 lock-in):

* `productModel` is resolved exclusively from `RTIDeviceData.ProductId`.
* T4x = ProductId 102 / slot range 128..147 (20 slots). Geometry is the traced
  crop in ``t4x_trace.py``.
* ISR-2 = ProductId 110 / slot range 128..161 (34 slots). Geometry is the traced
  crop in ``isr2_trace.py``.
* ISR-4 = ProductId 111 / slot range 128..149 (22 slots). Geometry is the traced
  crop in ``isr4_trace.py``.
* T2x = ProductId 70 / slot range 128..179 (52 slots). Geometry is the traced
  crop in ``t2x_trace.py`` (not a flexbox ``.box`` template).
* T2i = ProductId 75 is the same model as T2x (key ``"t2x"``). The T2x
  ``HardKeyModel.product_id`` stays 70. Frame 254 ButtonLeft 128..179 (52 slots)
  and ignored gesture frame 252 ButtonLeft 0..2 are the T2x ones.
* Physical hard-key rows live at `FrameNumber = 254` with `ButtonLeft >= 128`; rows at
  `FrameNumber = 252` (gestures: Rotate Clockwise, Rotate Counterclockwise, Shake) are
  recorded but not rendered on the hard-key strip.

Canonical button layout (HTML/CSS) is ``src/sentinel/ui/testing/hard_keys/*.html`` — a
byte-for-byte copy of ``Assets/Hard Keys/*.html`` (sync when references change). The
generator reads only the ``src/`` copies at runtime.

`slot_dom_order` lists `ButtonLeft` values in the order empty ``.box`` slots appear in that
template's ``<body>`` (same order ``render_core._augment_template_with_slots`` walks the DOM).
Augmentation only injects children inside each empty ``<div …></div>``; opening tags are
unchanged from the template file.

Confidence:

* T4x: ``slot_dom_order`` matches probe-verified ``ButtonLeft`` ↔ layout (non-sequential
  d-pad / rows); template DOM matches approved ``T4x Hard Keys.html``.
* ISR-4: ``slot_by_data_label`` maps each template ``data-label`` to ``ButtonLeft`` (ISR-4
  strip is not sequential in DOM order); ``slot_dom_order`` remains ``128..149`` for tests
  and range checks only.
* ISR-2: ``slot_by_data_label`` maps each template ``data-label`` to ``ButtonLeft`` (ISR-2
  strip is not sequential in DOM order); ``slot_dom_order`` remains ``128..161`` for tests
  and range checks only.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sentinel.generation.hard_keys.isr2_trace import DESIGN_SIZE as ISR2_DESIGN_SIZE
from sentinel.generation.hard_keys.isr4_trace import DESIGN_SIZE as ISR4_DESIGN_SIZE
from sentinel.generation.hard_keys.t2x_trace import DESIGN_SIZE as T2X_DESIGN_SIZE
from sentinel.generation.hard_keys.t4x_trace import DESIGN_SIZE as T4X_DESIGN_SIZE

ROOT = Path(__file__).resolve().parents[3]

# ISR-2: template `data-label` → Apex ButtonLeft (ISR-2 data label mapping v2.xlsx).
# DOM walk order is not sequential in ButtonLeft; do not infer from `slot_dom_order`.
ISR2_SLOT_BY_DATA_LABEL: dict[str, int] = {
    "c1 r1": 128,
    "c3 r1": 129,
    "c1 r2": 130,
    "c3 r2": 132,
    "c1 r3": 133,
    "c3 r3": 137,
    "c1 r4": 138,
    "c3 r4": 140,
    "c1 r5": 141,
    "c2 r5": 142,
    "c3 r5": 143,
    "c1 r6": 144,
    "c2 r6": 145,
    "c3 r6": 146,
    "c1 r7": 147,
    "c2 r7": 148,
    "c3 r7": 149,
    "c1 r8": 150,
    "c2 r8": 151,
    "c3 r8": 152,
    "c1 r9": 153,
    "c2 r9": 154,
    "c3 r9": 155,
    "c1 r10": 156,
    "c2 r10": 157,
    "c3 r10": 158,
    "c1 r11": 159,
    "c2 r11": 160,
    "c3 r11": 161,
    "dpad up": 131,
    "dpad left": 134,
    "dpad ok": 135,
    "dpad right": 136,
    "dpad down": 139,
}

# ISR-4: template `data-label` → Apex ButtonLeft (ISR-4 data label mapping.xlsx).
# DOM walk order is not sequential in ButtonLeft; do not infer from `slot_dom_order`.
ISR4_SLOT_BY_DATA_LABEL: dict[str, int] = {
    "c1 r1": 128,
    "c3 r1": 129,
    "c1 r2": 130,
    "c1 r3": 133,
    "c1 r4": 138,
    "c3 r2": 132,
    "c3 r3": 137,
    "c3 r4": 140,
    "c1 r5": 141,
    "c2 r5": 142,
    "c3 r5": 143,
    "c1 r6": 144,
    "c2 r6": 145,
    "c3 r6": 146,
    "c1 r7": 147,
    "c2 r7": 148,
    "c3 r7": 149,
    "dpad up": 131,
    "dpad left": 134,
    "dpad ok": 135,
    "dpad right": 136,
    "dpad down": 139,
}
TEMPLATE_DIR = ROOT / "sentinel" / "ui" / "testing" / "hard_keys"


@dataclass(frozen=True)
class HardKeyModel:
    key: str
    product_id: int
    slot_range: tuple[int, int]
    slot_dom_order: tuple[int, ...]
    design_size: tuple[int, int]
    template_html_path: Path
    slot_by_data_label: Optional[dict[str, int]] = None

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
        design_size=T4X_DESIGN_SIZE,
        template_html_path=TEMPLATE_DIR / "t4x_hard_keys.html",
    ),
    "isr2": HardKeyModel(
        key="isr2",
        product_id=110,
        slot_range=(128, 161),
        slot_dom_order=_sequential_range(128, 161),
        design_size=ISR2_DESIGN_SIZE,
        template_html_path=TEMPLATE_DIR / "isr2_hard_keys.html",
        slot_by_data_label=ISR2_SLOT_BY_DATA_LABEL,
    ),
    "isr4": HardKeyModel(
        key="isr4",
        product_id=111,
        slot_range=(128, 149),
        slot_dom_order=_sequential_range(128, 149),
        design_size=ISR4_DESIGN_SIZE,
        template_html_path=TEMPLATE_DIR / "isr4_hard_keys.html",
        slot_by_data_label=ISR4_SLOT_BY_DATA_LABEL,
    ),
    "t2x": HardKeyModel(
        key="t2x",
        product_id=70,
        slot_range=(128, 179),
        slot_dom_order=_sequential_range(128, 179),
        design_size=T2X_DESIGN_SIZE,
        template_html_path=TEMPLATE_DIR / "t2x_hard_keys.html",
    ),
}


_PRODUCT_MODEL_BY_PRODUCT_ID: dict[int, str] = {m.product_id: m.key for m in MODELS.values()}
# T2i shares the T2x model. HardKeyModel.product_id for "t2x" stays 70.
_PRODUCT_MODEL_BY_PRODUCT_ID[75] = "t2x"


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
