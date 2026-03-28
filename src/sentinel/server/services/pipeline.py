from __future__ import annotations

import os
import subprocess
from pathlib import Path
import sys


class PipelineNotImplementedError(RuntimeError):
    pass


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


def regenerate_project(*, projectId: str, apex_path: Path, phase_hook=None) -> dict:
    root = _repo_root()
    extract = root / "src" / "sentinel" / "extraction" / "extract_project_data.py"
    generate = root / "src" / "sentinel" / "generation" / "generate_html.py"
    project_structure = root / "src" / "sentinel" / "contracts" / "apex_project_structure_v2.json"
    app_ui = root / "src" / "sentinel" / "contracts" / "app_ui_structure.json"

    out_dir = _project_out_dir(projectId=projectId)
    out_dir.mkdir(parents=True, exist_ok=True)

    if callable(phase_hook):
        phase_hook("extracting")

    try:
        subprocess.run(
            [
                _python_exe(),
                str(extract),
                "--apex",
                str(apex_path),
                "--project-structure",
                str(project_structure),
                "--out-dir",
                str(out_dir),
            ],
            check=True,
            cwd=str(root),
            env={**os.environ, "PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Extraction failed: rc={e.returncode}\nstdout:\n{e.stdout}\nstderr:\n{e.stderr}") from e

    # Extraction produces "*_project_data.json" into out_dir; pass the first match into generation.
    project_data = next(iter(sorted(out_dir.glob("*_project_data.json"))), None)
    if project_data is None:
        raise RuntimeError("Extraction did not produce *_project_data.json")

    if callable(phase_hook):
        phase_hook("generating")

    try:
        subprocess.run(
            [
                _python_exe(),
                str(generate),
                "--project-data",
                str(project_data),
                "--app-ui",
                str(app_ui),
                "--out-dir",
                str(out_dir),
            ],
            check=True,
            cwd=str(root),
            env={**os.environ, "PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Generation failed: rc={e.returncode}\nstdout:\n{e.stdout}\nstderr:\n{e.stderr}") from e

    return {"projectId": projectId, "outDir": str(out_dir), "projectData": str(project_data)}
