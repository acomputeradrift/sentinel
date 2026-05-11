"""Smoke test: extract Dash OS apex + render T4x device and write HTML to /tmp."""
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
    src = ROOT / "Assets" / "Dash OS v55.2 iPhone.apex"
    dst = Path(os.environ["TEMP"]) / "sentinel_hk_render_smoke.apex"
    shutil.copyfile(src, dst)

    from sentinel.extraction.extractor_core import ExtractContext, extract_project_data
    from sentinel.generation.render_core import render_single_device_html

    contract_path = SRC / "sentinel" / "contracts" / "apex_project_structure_v4.json"
    ctx = ExtractContext(apex_path=dst, project_structure_path=contract_path)
    data = extract_project_data(ctx)
    data.setdefault("source", {})["scriptVersion"] = "smoke"

    target_idx = None
    for i, d in enumerate(data.get("devices", [])):
        uf = d.get("userFacing", {})
        if uf.get("productModel") == "t4x":
            target_idx = i
            break
    if target_idx is None:
        print("No T4x device found.")
        return 2

    app_ui = {
        "header": {"titleTemplate": "{deviceName} - {pageName}"},
        "buttonPresentation": {"fallbackFontSize": 10},
        "appNavigation": {"pageLinks": {"enabled": True}},
    }
    html = render_single_device_html(
        project_data=data,
        app_ui=app_ui,
        project_stem="hk_smoke",
        device_index=target_idx,
    )
    out = Path(os.environ["TEMP"]) / "sentinel_hk_smoke.html"
    out.write_text(html, encoding="utf-8")

    markers = ["hk-split-left", "hk-split-right", "data-hk-model=", "data-hard-key-slot=", "data-meta="]
    print(f"wrote {out} ({len(html)} bytes)")
    for m in markers:
        present = m in html
        count = html.count(m)
        print(f"  {m!r:36s} present={present} count={count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
