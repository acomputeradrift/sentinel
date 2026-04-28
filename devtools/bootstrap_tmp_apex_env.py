"""
Create `.tmp_apex_env` if missing and install Sentinel with dev extras (Playwright).

Run from repo root:
  python devtools/bootstrap_tmp_apex_env.py

Or with an explicit Python (creates venv using that interpreter):
  py -3.12 devtools/bootstrap_tmp_apex_env.py

UNC: subprocess children use a local ``cwd`` when the repo is on ``\\\\server\\...``
(see ``devtools/repo_paths.py``). Set ``SENTINEL_REPO_ROOT`` / ``SENTINEL_VENV_PYTHON`` if needed.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import repo_paths

_HERE = Path(__file__).resolve()
ROOT = repo_paths.repo_root(anchor_file=_HERE)
VENV_DIR = ROOT / ".tmp_apex_env"


def _venv_python() -> Path:
    return repo_paths.venv_python(ROOT)


def main() -> int:
    cwd = repo_paths.subprocess_cwd(ROOT)
    if not _venv_python().exists():
        rc = subprocess.run(
            [sys.executable, "-m", "venv", str(VENV_DIR.resolve(strict=False))],
            cwd=str(cwd),
            check=False,
        ).returncode
        if rc != 0:
            return rc
    py = _venv_python()
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    editable = f"{ROOT.resolve(strict=False)}[dev]"
    steps = [
        [str(py), "-m", "pip", "install", "-U", "pip"],
        [str(py), "-m", "pip", "install", "-e", editable],
        [str(py), "-m", "playwright", "install", "chromium"],
    ]
    for cmd in steps:
        rc = subprocess.run(cmd, cwd=str(cwd), env=env, check=False).returncode
        if rc != 0:
            return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
