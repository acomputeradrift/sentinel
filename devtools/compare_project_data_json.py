from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare two project_data JSON files and report structural/value differences."
    )
    parser.add_argument("--left", required=True, help="Path to left JSON file")
    parser.add_argument("--right", required=True, help="Path to right JSON file")
    parser.add_argument("--out", default="", help="Optional path to write full diff JSON report")
    parser.add_argument(
        "--max-items",
        type=int,
        default=200,
        help="Maximum number of detailed diff entries to print to stdout (default: 200)",
    )
    return parser.parse_args()


def _format_path(base: str, key: str) -> str:
    if not base:
        return key
    return f"{base}.{key}"


def _format_index(base: str, idx: int) -> str:
    return f"{base}[{idx}]" if base else f"[{idx}]"


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return type(value).__name__


def _short_value(value: Any, limit: int = 120) -> str:
    text = json.dumps(value, ensure_ascii=True, sort_keys=True)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _walk_diff(left: Any, right: Any, path: str, out: dict[str, list[dict[str, Any]]]) -> None:
    if isinstance(left, dict) and isinstance(right, dict):
        left_keys = set(left.keys())
        right_keys = set(right.keys())
        for key in sorted(left_keys - right_keys):
            out["removed"].append(
                {
                    "path": _format_path(path, str(key)),
                    "leftType": _json_type(left[key]),
                    "leftValueSample": _short_value(left[key]),
                }
            )
        for key in sorted(right_keys - left_keys):
            out["added"].append(
                {
                    "path": _format_path(path, str(key)),
                    "rightType": _json_type(right[key]),
                    "rightValueSample": _short_value(right[key]),
                }
            )
        for key in sorted(left_keys & right_keys):
            _walk_diff(left[key], right[key], _format_path(path, str(key)), out)
        return

    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            out["lengthChanged"].append({"path": path or "$", "leftLength": len(left), "rightLength": len(right)})
        for idx in range(min(len(left), len(right))):
            _walk_diff(left[idx], right[idx], _format_index(path, idx), out)
        for idx in range(len(right), len(left)):
            out["removed"].append(
                {
                    "path": _format_index(path, idx),
                    "leftType": _json_type(left[idx]),
                    "leftValueSample": _short_value(left[idx]),
                }
            )
        for idx in range(len(left), len(right)):
            out["added"].append(
                {
                    "path": _format_index(path, idx),
                    "rightType": _json_type(right[idx]),
                    "rightValueSample": _short_value(right[idx]),
                }
            )
        return

    left_type = _json_type(left)
    right_type = _json_type(right)
    if left_type != right_type:
        out["typeChanged"].append(
            {
                "path": path or "$",
                "leftType": left_type,
                "rightType": right_type,
                "leftValueSample": _short_value(left),
                "rightValueSample": _short_value(right),
            }
        )
        return

    if left != right:
        out["valueChanged"].append(
            {
                "path": path or "$",
                "type": left_type,
                "leftValueSample": _short_value(left),
                "rightValueSample": _short_value(right),
            }
        )


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _print_section(name: str, rows: list[dict[str, Any]], max_items: int) -> None:
    print(f"\n{name}: {len(rows)}")
    for entry in rows[:max_items]:
        print(" - " + json.dumps(entry, ensure_ascii=True, sort_keys=True))
    hidden = len(rows) - min(len(rows), max_items)
    if hidden > 0:
        print(f" - ... {hidden} more omitted (increase --max-items to show more)")


def main() -> int:
    args = _parse_args()
    left_path = Path(args.left).resolve()
    right_path = Path(args.right).resolve()

    if not left_path.exists():
        print(f"ERROR: left file not found: {left_path}")
        return 1
    if not right_path.exists():
        print(f"ERROR: right file not found: {right_path}")
        return 1

    left_data = _load_json(left_path)
    right_data = _load_json(right_path)

    report: dict[str, Any] = {
        "left": str(left_path),
        "right": str(right_path),
        "leftSizeBytes": left_path.stat().st_size,
        "rightSizeBytes": right_path.stat().st_size,
        "diff": {"added": [], "removed": [], "typeChanged": [], "lengthChanged": [], "valueChanged": []},
    }

    _walk_diff(left_data, right_data, "", report["diff"])

    summary = {
        "added": len(report["diff"]["added"]),
        "removed": len(report["diff"]["removed"]),
        "typeChanged": len(report["diff"]["typeChanged"]),
        "lengthChanged": len(report["diff"]["lengthChanged"]),
        "valueChanged": len(report["diff"]["valueChanged"]),
    }
    report["summary"] = summary

    print("JSON comparison summary")
    print(json.dumps(summary, ensure_ascii=True, sort_keys=True))

    _print_section("Added", report["diff"]["added"], args.max_items)
    _print_section("Removed", report["diff"]["removed"], args.max_items)
    _print_section("Type changed", report["diff"]["typeChanged"], args.max_items)
    _print_section("Length changed", report["diff"]["lengthChanged"], args.max_items)
    _print_section("Value changed", report["diff"]["valueChanged"], args.max_items)

    if args.out:
        out_path = Path(args.out).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8")
        print(f"\nWrote full report: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
