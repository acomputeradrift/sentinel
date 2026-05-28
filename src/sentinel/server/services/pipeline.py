from __future__ import annotations

import logging
import os
import re
import subprocess
import shutil
import tempfile
import time
import threading
from pathlib import Path
import sys
from uuid import uuid4
from collections import deque

_log = logging.getLogger("uvicorn.error")


class PipelineNotImplementedError(RuntimeError):
    pass


_PROGRESS_RE = re.compile(r"^SENTINEL_PROGRESS\s+([A-Z_]+)\s+(\d{1,3}(?:\.\d+)?)\s*$")
_SUBPROCESS_STDOUT_TAIL_LINES = 80
_SUBPROCESS_STDERR_TAIL_LINES = 80
_ACTIVE_REGENERATES_LOCK = threading.Lock()
_ACTIVE_REGENERATE_PROJECT_IDS: set[str] = set()


def _python_exe() -> str:
    return os.environ.get("PYTHON") or sys.executable


def _repo_root() -> Path:
    # This file lives at src/sentinel/server/services/pipeline.py
    return Path(__file__).resolve().parents[4]


def _upload_root() -> Path:
    return Path(os.environ.get("SENTINEL_UPLOAD_ROOT") or "uploads").resolve()


def _generated_root() -> Path:
    return Path(os.environ.get("SENTINEL_GENERATED_ROOT") or "generated").resolve()


def _project_out_dir(*, projectId: str) -> Path:
    return (_generated_root() / projectId).resolve()


def _project_upload_dir(*, projectId: str) -> Path:
    return (_upload_root() / projectId).resolve()


def save_upload(*, projectId: str, uploadId: str, filename: str, content: bytes) -> Path:
    upload_dir = _project_upload_dir(projectId=projectId)
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(filename).name or "upload.apex"
    path = upload_dir / f"{uploadId}__{safe_name}"
    path.write_bytes(content)
    return path


def prune_project_upload_dir_to_single_file(*, projectId: str, keep_path: Path) -> None:
    """
    Remove every file under the project upload directory except the active upload file.

    Called after a successful extract+generate so disk holds a single current .apex per project.
    """
    upload_dir = _project_upload_dir(projectId=projectId)
    if not upload_dir.exists():
        return
    try:
        keep_resolved = keep_path.resolve()
    except OSError:
        keep_resolved = keep_path
    for child in list(upload_dir.iterdir()):
        if not child.is_file():
            continue
        try:
            if child.resolve() == keep_resolved:
                continue
        except OSError:
            pass
        try:
            child.unlink()
        except OSError as exc:
            _log.warning(
                "[pipeline] upload-prune: failed to remove %s projectId=%s err=%s",
                child,
                projectId,
                exc,
            )


def _call_phase_hook(phase_hook, phase: str, percent: float) -> None:
    if not callable(phase_hook):
        return
    try:
        pct = float(percent or 0.0)
    except Exception:
        pct = 0.0
    if pct < 0:
        pct = 0.0
    if pct > 100:
        pct = 100.0
    try:
        phase_hook(str(phase or ""), pct)
        return
    except TypeError:
        pass
    phase_hook(str(phase or ""))


def _run_subprocess_with_progress(*, args: list[str], cwd: Path, env: dict[str, str], phase_hook=None) -> tuple[str, str]:
    proc = subprocess.Popen(
        args,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    stdout_tail: deque[str] = deque(maxlen=_SUBPROCESS_STDOUT_TAIL_LINES)
    stdout_line_count = 0
    stderr_text = ""
    assert proc.stdout is not None
    assert proc.stderr is not None
    try:
        for line in proc.stdout:
            stdout_tail.append(line)
            stdout_line_count += 1
            m = _PROGRESS_RE.match(str(line or "").strip())
            if not m:
                continue
            phase = str(m.group(1) or "").strip().lower()
            percent = float(m.group(2) or 0.0)
            _call_phase_hook(phase_hook, phase, percent)
        stderr_text = proc.stderr.read()
        rc = proc.wait()
        stdout_text = "".join(stdout_tail)
        if rc != 0:
            stderr_lines = str(stderr_text or "").splitlines()
            stderr_tail = "\n".join(stderr_lines[-_SUBPROCESS_STDERR_TAIL_LINES:])
            raise RuntimeError(
                "\n".join(
                    [
                        f"subprocess failed rc={rc}",
                        f"stdout_lines={stdout_line_count}",
                        "stdout_tail:",
                        stdout_text.strip(),
                        "stderr_tail:",
                        stderr_tail,
                    ]
                ).strip()
            )
        return stdout_text, stderr_text
    finally:
        try:
            proc.stdout.close()
        except Exception:
            pass
        try:
            proc.stderr.close()
        except Exception:
            pass


def regenerate_project(
    *,
    projectId: str,
    apex_path: Path,
    phase_hook=None,
    client_name: str = "",
    project_name: str = "",
) -> dict:
    with _ACTIVE_REGENERATES_LOCK:
        if projectId in _ACTIVE_REGENERATE_PROJECT_IDS:
            raise RuntimeError(f"Regenerate already in progress for projectId={projectId}")
        _ACTIVE_REGENERATE_PROJECT_IDS.add(projectId)

    root = _repo_root()
    extract = root / "src" / "sentinel" / "extraction" / "extract_project_data.py"
    generate = root / "src" / "sentinel" / "generation" / "generate_html.py"
    project_structure = root / "src" / "sentinel" / "contracts" / "apex_project_structure_v4.json"
    app_ui = root / "src" / "sentinel" / "contracts" / "app_ui_structure.json"

    out_dir = _project_out_dir(projectId=projectId)
    out_dir.mkdir(parents=True, exist_ok=True)
    stage_root = (_generated_root() / ".staging").resolve()
    stage_root.mkdir(parents=True, exist_ok=True)
    stage_dir = Path(tempfile.mkdtemp(prefix=f"{projectId[:8]}-", dir=str(stage_root))).resolve()
    total_t0 = time.perf_counter()
    extract_elapsed_s = 0.0
    generate_elapsed_s = 0.0

    _call_phase_hook(phase_hook, "extracting", 0)

    try:
        try:
            extract_t0 = time.perf_counter()
            _run_subprocess_with_progress(
                args=[
                    _python_exe(),
                    str(extract),
                    "--apex",
                    str(apex_path),
                    "--project-structure",
                    str(project_structure),
                    "--out-dir",
                    str(stage_dir),
                ],
                cwd=root,
                env={**os.environ, "PYTHONPATH": str(root / "src"), "PYTHONUNBUFFERED": "1"},
                phase_hook=phase_hook,
            )
            extract_elapsed_s = max(0.0, time.perf_counter() - extract_t0)
        except Exception as e:
            raise RuntimeError(f"Extraction failed: {e}") from e

        # Extraction produces "*_project_data.json" into stage_dir; pass the first match into generation.
        project_data = next(iter(sorted(stage_dir.glob("*_project_data.json"))), None)
        if project_data is None:
            raise RuntimeError("Extraction did not produce *_project_data.json")

        _call_phase_hook(phase_hook, "generating", 0)

        try:
            generate_t0 = time.perf_counter()
            generate_args = [
                _python_exe(),
                str(generate),
                "--project-data",
                str(project_data),
                "--app-ui",
                str(app_ui),
                "--out-dir",
                str(stage_dir),
            ]
            client_display = str(client_name or "").strip()
            project_display = str(project_name or "").strip()
            if client_display:
                generate_args.extend(["--client-name", client_display])
            if project_display:
                generate_args.extend(["--project-name", project_display])
            _run_subprocess_with_progress(
                args=generate_args,
                cwd=root,
                env={**os.environ, "PYTHONPATH": str(root / "src"), "PYTHONUNBUFFERED": "1"},
                phase_hook=phase_hook,
            )
            generate_elapsed_s = max(0.0, time.perf_counter() - generate_t0)
        except Exception as e:
            raise RuntimeError(f"Generation failed: {e}") from e

        # Move new artifacts into the project directory first, then remove anything stale.
        new_names: set[str] = set()
        for child in sorted(stage_dir.iterdir(), key=lambda p: p.name):
            target = out_dir / child.name
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            child.replace(target)
            new_names.add(target.name)

        for child in list(out_dir.iterdir()):
            if child.name in new_names:
                continue
            if child.name.startswith(".stage-"):
                # Never remove foreign in-flight stage dirs from another run.
                # The current run always removes its own stage_dir in finally.
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()

        final_project_data = out_dir / project_data.name
        resolved_targets = out_dir / project_data.name.replace("_project_data.json", "_resolved_targets.json")
        total_elapsed_s = max(0.0, time.perf_counter() - total_t0)
        return {
            "projectId": projectId,
            "outDir": str(out_dir),
            "projectData": str(final_project_data),
            "resolvedTargets": str(resolved_targets) if resolved_targets.exists() else None,
            "timings": {
                "extractSec": round(float(extract_elapsed_s), 3),
                "generateSec": round(float(generate_elapsed_s), 3),
                "totalSec": round(float(total_elapsed_s), 3),
            },
        }
    finally:
        if stage_dir.exists():
            shutil.rmtree(stage_dir, ignore_errors=True)
        with _ACTIVE_REGENERATES_LOCK:
            _ACTIVE_REGENERATE_PROJECT_IDS.discard(projectId)
