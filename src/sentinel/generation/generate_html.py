from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sentinel.generation.render_core import device_filename, load_json, project_home_filename, render_project_home_html, render_single_device_html
from sentinel.logging.event_logger import EventLogger


SCRIPT_VERSION = "0.1.0"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate a project home page and single-device HTML shells from <filename>_project_data.json and app_ui_structure.json")
    p.add_argument("--project-data", required=True, help="Path to <filename>_project_data.json")
    p.add_argument("--app-ui", required=True, help="Path to app_ui_structure.json")
    p.add_argument("--out-dir", help="Output directory. Defaults to the project data file directory.")
    return p.parse_args()


def main() -> int:
    log = EventLogger()
    args = parse_args()
    project_data_path = Path(args.project_data).resolve()
    app_ui_path = Path(args.app_ui).resolve()
    out_dir = Path(args.out_dir).resolve() if args.out_dir else project_data_path.parent
    started_at = datetime.now(timezone.utc)
    started_perf = time.perf_counter()

    try:
        def _emit_progress(percent: int) -> None:
            pct = int(percent or 0)
            if pct < 0:
                pct = 0
            if pct > 100:
                pct = 100
            print(f"SENTINEL_PROGRESS GENERATING {pct}", flush=True)

        log.info(f"Generator start version={SCRIPT_VERSION}")
        log.info(f"Generation started_at={started_at.isoformat(timespec='seconds').replace('+00:00', 'Z')}")
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
        written = 0

        devices = project_data.get("devices", [])
        renderable_device_count = 0
        for device in devices:
            user = device.get("userFacing", {})
            pages = user.get("pages", [])
            if isinstance(pages, list) and pages:
                renderable_device_count += 1
        total_units = 1 + renderable_device_count

        _emit_progress(0)
        home_html = render_project_home_html(project_data, app_ui, project_stem=project_data_path.stem)
        home_out_path = out_dir / project_home_filename(project_data_path.stem)
        log.info(f"Writing html output: {home_out_path}")
        home_out_path.write_text(home_html, encoding="utf-8")
        written += 1
        _emit_progress(int((written * 100) / max(total_units, 1)))

        for device_index, device in enumerate(devices):
            user = device.get("userFacing", {})
            pages = user.get("pages", [])
            if not isinstance(pages, list) or not pages:
                continue
            html = render_single_device_html(project_data, app_ui, project_stem=project_data_path.stem, device_index=device_index)
            device_name = user.get("displayName", f"device-{device_index}")
            out_path = out_dir / device_filename(project_data_path.stem, str(device_name), device_index)
            log.info(f"Writing html output: {out_path}")
            out_path.write_text(html, encoding="utf-8")
            written += 1
            _emit_progress(int((written * 100) / max(total_units, 1)))

        ended_at = datetime.now(timezone.utc)
        elapsed_seconds = time.perf_counter() - started_perf
        log.info(f"Generation ended_at={ended_at.isoformat(timespec='seconds').replace('+00:00', 'Z')}")
        log.info(f"Generation elapsed_seconds={elapsed_seconds:.3f}")
        log.success(f"Generation complete: wrote {written} html file(s)")
        return 0
    except Exception as exc:  # pragma: no cover
        ended_at = datetime.now(timezone.utc)
        elapsed_seconds = time.perf_counter() - started_perf
        log.info(f"Generation ended_at={ended_at.isoformat(timespec='seconds').replace('+00:00', 'Z')}")
        log.info(f"Generation elapsed_seconds={elapsed_seconds:.3f}")
        log.fail(f"Generation failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
