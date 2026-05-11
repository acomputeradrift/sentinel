"""Detail probe of hard-key SharedLayers for T4x and ISR-4 from accessible apex files."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path


def dump_layer(label: str, apex: str, slid: int) -> None:
    tmp = Path(os.environ["TEMP"]) / f"sentinel_layer_detail_{slid}.apex"
    shutil.copyfile(apex, tmp)
    con = sqlite3.connect(str(tmp))
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    print(f"=== {label} SharedLayerId={slid} ({apex}) ===")
    cur.execute(
        "select * from RTIDeviceButtonData where SharedLayerId = ? "
        "order by FrameNumber, ButtonTop, ButtonLeft, ButtonOrder",
        (slid,),
    )
    rows = list(cur.fetchall())
    print(f"total rows in layer: {len(rows)}")

    cur2 = con.cursor()
    cur2.execute("select ButtonTagId, ButtonTagName from ButtonTagNames")
    tag_by_id = {int(r["ButtonTagId"]): str(r["ButtonTagName"] or "") for r in cur2.fetchall()}

    print(f"{'Frame':>5} {'Top':>6} {'Left':>5} {'Order':>5} {'W':>3} {'H':>3} {'BtnId':>7} {'TagId':>6} TagName")
    for r in rows:
        d = {k: r[k] for k in r.keys()}
        tag = tag_by_id.get(int(d.get("ButtonTagId") or 0), "")
        print(
            f"  {int(d['FrameNumber'] or 0):>5} {int(d['ButtonTop'] or 0):>6} "
            f"{int(d['ButtonLeft'] or 0):>5} {int(d['ButtonOrder'] or 0):>5} "
            f"{int(d['ButtonWidth'] or 0):>3} {int(d['ButtonHeight'] or 0):>3} "
            f"{int(d['ButtonId'] or 0):>7} {int(d['ButtonTagId'] or 0):>6} {tag!r}"
        )

    only_hk = [
        r for r in rows
        if int(r["ButtonWidth"] or 0) == 0
        and int(r["ButtonHeight"] or 0) == 0
        and int(r["ButtonLeft"] or 0) >= 128
    ]
    lefts = sorted({int(r["ButtonLeft"]) for r in only_hk})
    frames = sorted({int(r["FrameNumber"] or 0) for r in only_hk})
    print(
        f"\nFiltered (W=H=0 AND ButtonLeft>=128): rows={len(only_hk)} "
        f"distinctLefts={len(lefts)} leftRange=({lefts[0] if lefts else None}..{lefts[-1] if lefts else None}) frames={frames}"
    )
    con.close()
    print()


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    dash = str(root / "Assets" / "Dash OS v55.2 iPhone.apex")
    sung = str(root / "Assets" / "Sung Residence v207.2.apex")
    rockett = str(
        root
        / "Assets"
        / "cea2a845-c91e-40d2-9584-ebc5154b5a1d__Rockett RTI FarmHouse_RTI_iD11.14.6_Killed off ISR-2_2026-04-08_1151.apex"
    )

    dump_layer("T4x (Dash OS)", dash, 1574)
    dump_layer("ISR-4 (Sung)", sung, 482)
    dump_layer("ISR-4 first (Rockett)", rockett, 388)
    return 0


if __name__ == "__main__":
    sys.exit(main())
