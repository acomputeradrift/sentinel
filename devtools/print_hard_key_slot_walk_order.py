#!/usr/bin/env python3
"""Print empty `.box` slot walk order for a hard-key template (matches registry `slot_dom_order`).

Use this when aligning `HardKeyModel.slot_dom_order` with an approved ID map image
(e.g. `Assets/Hard Keys/ISR-2 Hard Key IDs.png`): transcribe ButtonLeft values from the
map **in this exact order** into a tuple in `hard_keys/registry.py`.

Usage (from repo root):
  python devtools/print_hard_key_slot_walk_order.py isr2
  python devtools/print_hard_key_slot_walk_order.py t4x
  python devtools/print_hard_key_slot_walk_order.py isr4
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

BOX_RE = re.compile(r'<div\s+class="([^"]*\bbox\b[^"]*)"([^>]*?)>\s*</div>', re.DOTALL)


def main() -> None:
    from sentinel.generation.hard_keys import registry as hk

    key = (sys.argv[1] if len(sys.argv) > 1 else "").strip().lower()
    if not key:
        print("usage: python devtools/print_hard_key_slot_walk_order.py <t4x|isr2|isr4>")
        sys.exit(2)
    model = hk.model_for_key(key)
    if model is None:
        print(f"unknown model key: {key!r}")
        sys.exit(2)
    html = model.template_html_path.read_text(encoding="utf-8")
    matches = BOX_RE.findall(html)
    print(f"# model={key} template={model.template_html_path.name}")
    print(f"# empty.box count={len(matches)} registry.slot_dom_order length={model.slot_count()}")
    for i, (_cls, attrs) in enumerate(matches):
        m = re.search(r'data-label="([^"]*)"', attrs)
        label = m.group(1) if m else "(no data-label)"
        print(f"{i:2d}  {label}")


if __name__ == "__main__":
    main()
