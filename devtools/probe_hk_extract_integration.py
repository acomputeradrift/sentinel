"""Run full extraction against a copied apex and report hard-key fields."""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main() -> int:
    src = Path(r"\\mac\Home\Desktop\Development\Sentinel\Assets\Dash OS v55.2 iPhone.apex")
    dst = Path(os.environ["TEMP"]) / "sentinel_hk_extract.apex"
    shutil.copyfile(src, dst)

    from sentinel.extraction.extractor_core import (
        ExtractContext,
        extract_project_data,
        validate_contract_shape,
    )

    contract_path = SRC / "sentinel" / "contracts" / "apex_project_structure_v4.json"
    ctx = ExtractContext(apex_path=dst, project_structure_path=contract_path)
    data = extract_project_data(ctx)
    data.setdefault("source", {})["scriptVersion"] = "probe"

    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    try:
        validate_contract_shape(contract=contract, payload=data)
        print("contract validation: PASS")
    except ValueError as exc:
        print("contract validation: FAIL")
        print(str(exc))
        return 1

    for dev in data.get("devices", []):
        uf = dev.get("userFacing", {})
        print(
            f"device {uf.get('displayName')!r}: productModel={uf.get('productModel')!r}, pages={len(uf.get('pages', []))}"
        )
        for page in uf.get("pages", []):
            for layer in page.get("layers", []):
                hk = layer.get("hardKeyLayer", {}) or {}
                if layer.get("isKeypadLayer"):
                    print(
                        f"  page={page.get('pageName')!r} layer={layer.get('layerName')!r} "
                        f"isKeypad={layer.get('isKeypadLayer')} slots={len(hk.get('slots', []))} "
                        f"gestures={len(hk.get('gestures', []))} unmapped={len(hk.get('unmappedSlots', []))}"
                    )
                    if hk.get("slots"):
                        first = hk["slots"][0]
                        print(f"    first slot: {first}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
