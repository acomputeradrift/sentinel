"""Probe .apex SQLite for list row / line height storage (any table, any column name)."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APEX = ROOT / "Assets" / "Dash OS v55.2 iPhone.apex"


def qident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def main() -> int:
    apex = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else DEFAULT_APEX
    apex = apex.resolve()
    if not apex.is_file():
        print(f"NOT_A_FILE {apex}", file=sys.stderr)
        return 2

    con = sqlite3.connect(str(apex))
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY 1")]

    needles = ("height", "row", "item", "line", "scroll", "list")
    interesting: list[tuple[str, str, str]] = []
    for t in tables:
        cols = cur.execute("PRAGMA table_info(" + qident(t) + ")").fetchall()
        for _cid, cname, ctype, _nn, _dflt, _pk in cols:
            low = (cname or "").lower()
            if any(n in low for n in needles):
                interesting.append((t, cname, ctype or ""))

    print(f"FILE={apex}")
    print(f"TABLES={len(tables)}")
    print("--- columns (name contains height|row|item|line|scroll|list) ---")
    for t, c, ty in sorted(interesting):
        print(f"{t}\t{c}\t{ty}")

    # Row counts for list-shaped tables
    print("--- row counts ---")
    for t in sorted(set(x[0] for x in interesting) | {"ScrollingList", "ScrollingListItems", "ButtonsAndListItems", "AllListItems", "RTIDeviceButtonData"}):
        if t not in tables:
            continue
        n = cur.execute(f"SELECT COUNT(*) AS n FROM {qident(t)}").fetchone()["n"]
        print(f"{t}\t{n}")

    # Sample ScrollingList if any rows
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ScrollingList'")
    if cur.fetchone():
        rows = cur.execute("SELECT * FROM ScrollingList LIMIT 20").fetchall()
        print(f"--- ScrollingList sample rows={len(rows)} ---")
        for row in rows:
            print(dict(row))

    # Search numeric columns that equal 90 in tables tied to list-ish names
    print("--- scan for value 90 in list-related tables (first 50 hits per table) ---")
    listish = {t for t in tables if any(x in t.lower() for x in ("list", "scroll", "button", "item", "layer"))}
    for t in sorted(listish):
        cols = [r[1] for r in cur.execute("PRAGMA table_info(" + qident(t) + ")").fetchall()]
        int_cols = []
        for c in cols:
            low = c.lower()
            if any(n in low for n in ("height", "row", "item", "line", "size", "offset", "padding")):
                int_cols.append(c)
        if not int_cols:
            continue
        hits = 0
        for c in int_cols:
            try:
                q = f"SELECT COUNT(*) AS n FROM {qident(t)} WHERE {qident(c)} = 90"
                n = int(cur.execute(q).fetchone()["n"] or 0)
            except sqlite3.Error:
                continue
            if n:
                print(f"HIT_90\t{t}\t{c}\trows={n}")
                hits += 1
                sample = cur.execute(
                    f"SELECT * FROM {qident(t)} WHERE {qident(c)} = 90 LIMIT 3"
                ).fetchall()
                for row in sample:
                    print(f"  SAMPLE\t{dict(row)}")
        if hits:
            continue

    # Any column anywhere = 90 with 'height' or 'item' in name
    print("--- broad: any table.column (name has height|itemheight|row) with value 90 ---")
    for t in tables:
        cols = [r[1] for r in cur.execute("PRAGMA table_info(" + qident(t) + ")").fetchall()]
        for c in cols:
            low = c.lower()
            if not any(k in low for k in ("height", "itemheight", "rowheight", "line")):
                continue
            try:
                n = int(cur.execute(f"SELECT COUNT(*) AS n FROM {qident(t)} WHERE {qident(c)} = 90").fetchone()["n"] or 0)
            except sqlite3.Error:
                continue
            if n:
                print(f"HIT_90_BROAD\t{t}\t{c}\t{n}")

    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
