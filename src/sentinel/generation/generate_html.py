from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sentinel.generation.render_core import device_filename, load_json, page_filename, render_html, render_single_device_html
from sentinel.logging.event_logger import EventLogger


SCRIPT_VERSION = "0.1.0"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate html from <filename>_project_data.json and app_ui_structure.json")
    p.add_argument("--project-data", required=True, help="Path to <filename>_project_data.json")
    p.add_argument("--app-ui", required=True, help="Path to app_ui_structure.json")
    p.add_argument("--out-dir", help="Output directory. Defaults to the project data file directory.")
    p.add_argument("--device-index", type=int, default=0)
    p.add_argument("--page-index", type=int)
    p.add_argument("--single-device", action="store_true", help="Generate one HTML file for the selected device containing all of its pages.")
    return p.parse_args()


def main() -> int:
    log = EventLogger()
    args = parse_args()
    project_data_path = Path(args.project_data).resolve()
    app_ui_path = Path(args.app_ui).resolve()
    out_dir = Path(args.out_dir).resolve() if args.out_dir else project_data_path.parent

    try:
        log.info(f"Generator start version={SCRIPT_VERSION}")
        if not project_data_path.exists():
            log.fail(f"project data file not found: {project_data_path}")
            return 1
        if not app_ui_path.exists():
            log.fail(f"app ui file not found: {app_ui_path}")
            return 1

        log.info(f"Loading project data: {project_data_path}")
        project_data = load_json(project_data_path)
        log.info(f"Loading app ui config: {app_ui_path}")
        app_ui = load_json(app_ui_path)

        out_dir.mkdir(parents=True, exist_ok=True)
        device = project_data["devices"][args.device_index]
        pages = device["userFacing"]["pages"]
        written = 0
        if args.single_device:
            html = render_single_device_html(project_data, app_ui, project_stem=project_data_path.stem, device_index=args.device_index)
            device_name = device["userFacing"].get("displayName", f"device-{args.device_index}")
            out_path = out_dir / device_filename(project_data_path.stem, str(device_name), args.device_index)
            log.info(f"Writing html output: {out_path}")
            out_path.write_text(html, encoding="utf-8")
            written += 1
        else:
            page_indexes = [args.page_index] if args.page_index is not None else list(range(len(pages)))
            for page_index in page_indexes:
                html = render_html(project_data, app_ui, project_stem=project_data_path.stem, device_index=args.device_index, page_index=page_index)
                page_name = pages[page_index].get("pageName", "")
                out_path = out_dir / page_filename(project_data_path.stem, str(page_name), page_index)
                log.info(f"Writing html output: {out_path}")
                out_path.write_text(html, encoding="utf-8")
                written += 1
        log.success(f"Generation complete: wrote {written} html file(s)")
        return 0
    except Exception as exc:  # pragma: no cover
        log.fail(f"Generation failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
