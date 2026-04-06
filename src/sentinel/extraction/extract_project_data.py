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

from sentinel.extraction.extractor_core import ExtractContext, extract_project_data, validate_contract_shape
from sentinel.logging.event_logger import EventLogger


SCRIPT_VERSION = "0.1.0"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Extract project data from apex into <filename>_project_data.json")
    p.add_argument("--apex", required=True, help="Path to .apex file")
    p.add_argument("--project-structure", required=True, help="Path to apex_project_structure_v4.json")
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
    current_progress = 0.0

    try:
        def _emit_progress(percent: float) -> None:
            nonlocal current_progress
            try:
                pct = float(percent or 0.0)
            except Exception:
                pct = 0.0
            if pct < 0:
                pct = 0.0
            if pct > 100:
                pct = 100.0
            if pct < current_progress:
                pct = current_progress
            current_progress = pct
            # Preserve high precision from real extraction progress events.
            print(f"SENTINEL_PROGRESS EXTRACTING {pct:.4f}", flush=True)

        log.info(f"Extractor start version={SCRIPT_VERSION}")
        log.info(f"Extraction started_at={started_at.isoformat(timespec='seconds').replace('+00:00', 'Z')}")
        if not apex.exists():
            log.fail(f"Apex file not found: {apex}")
            return 1
        if not project_structure.exists():
            log.fail(f"apex_project_structure_v4.json not found: {project_structure}")
            return 1

        out_dir.mkdir(parents=True, exist_ok=True)
        apex_size_bytes = apex.stat().st_size
        contract_size_bytes = project_structure.stat().st_size
        log.info_kv(
            "Extraction inputs",
            apex_path=apex,
            apex_size_bytes=apex_size_bytes,
            contract_path=project_structure,
            contract_size_bytes=contract_size_bytes,
        )
        log.info(f"Loading apex database: {apex}")
        data = extract_project_data(ExtractContext(apex_path=apex, project_structure_path=project_structure), progress_hook=_emit_progress)
        _emit_progress(99)
        data.setdefault("source", {})
        data["source"]["scriptVersion"] = SCRIPT_VERSION
        contract = json.loads(project_structure.read_text(encoding="utf-8"))
        _emit_progress(99.2)
        validate_contract_shape(contract=contract, payload=data)
        _emit_progress(99.4)

        out_path = out_dir / f"{apex.stem}_project_data.json"
        log.info(f"Writing output json: {out_path}")
        class _ProgressWriter:
            def __init__(self, file_obj):
                self._f = file_obj
                self._next_tick_bytes = 256 * 1024
                self._written = 0
                self._current = 99.4

            def write(self, s):
                out = self._f.write(s)
                self._written += len(str(s).encode("utf-8"))
                while self._written >= self._next_tick_bytes and self._current < 99.95:
                    self._current = min(99.95, self._current + 0.05)
                    _emit_progress(self._current)
                    self._next_tick_bytes += 256 * 1024
                return out

            def __getattr__(self, name):
                return getattr(self._f, name)

        with out_path.open("w", encoding="utf-8") as f:
            json.dump(data, _ProgressWriter(f), indent=2, ensure_ascii=True)
        _emit_progress(99.99)
        _emit_progress(100)

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

