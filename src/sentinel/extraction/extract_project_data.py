from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sentinel.extraction.extractor_core import ExtractContext, extract_project_data
from sentinel.logging.event_logger import EventLogger


SCRIPT_VERSION = "0.1.0"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Extract project data from apex into <filename>_project_data.json")
    p.add_argument("--apex", required=True, help="Path to .apex file")
    p.add_argument("--project-structure", required=True, help="Path to apex_project_structure.json")
    p.add_argument("--out-dir", default=".", help="Output directory")
    return p.parse_args()


def main() -> int:
    log = EventLogger()
    args = parse_args()
    apex = Path(args.apex).resolve()
    project_structure = Path(args.project_structure).resolve()
    out_dir = Path(args.out_dir).resolve()
    started_at = datetime.now(timezone.utc)
    started_perf = time.perf_counter()

    try:
        def _emit_progress(percent: int) -> None:
            pct = int(percent or 0)
            if pct < 0:
                pct = 0
            if pct > 100:
                pct = 100
            print(f"SENTINEL_PROGRESS EXTRACTING {pct}", flush=True)

        log.info(f"Extractor start version={SCRIPT_VERSION}")
        log.info(f"Extraction started_at={started_at.isoformat(timespec='seconds').replace('+00:00', 'Z')}")
        if not apex.exists():
            log.fail(f"Apex file not found: {apex}")
            return 1
        if not project_structure.exists():
            log.fail(f"apex_project_structure.json not found: {project_structure}")
            return 1

        out_dir.mkdir(parents=True, exist_ok=True)
        log.info(f"Loading apex database: {apex}")
        data = extract_project_data(ExtractContext(apex_path=apex, project_structure_path=project_structure), progress_hook=_emit_progress)
        data.setdefault("source", {})
        data["source"]["scriptVersion"] = SCRIPT_VERSION

        out_path = out_dir / f"{apex.stem}_project_data.json"
        log.info(f"Writing output json: {out_path}")
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=True)

        ended_at = datetime.now(timezone.utc)
        elapsed_seconds = time.perf_counter() - started_perf
        log.info(f"Extraction ended_at={ended_at.isoformat(timespec='seconds').replace('+00:00', 'Z')}")
        log.info(f"Extraction elapsed_seconds={elapsed_seconds:.3f}")
        log.success(f"Extraction complete: {out_path.name}")
        return 0
    except Exception as exc:  # pragma: no cover
        ended_at = datetime.now(timezone.utc)
        elapsed_seconds = time.perf_counter() - started_perf
        log.info(f"Extraction ended_at={ended_at.isoformat(timespec='seconds').replace('+00:00', 'Z')}")
        log.info(f"Extraction elapsed_seconds={elapsed_seconds:.3f}")
        log.fail(f"Extraction failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
