"""
Create `.tmp_apex_env` if missing and install Sentinel with dev extras (Playwright).

Run from repo root:
  python devtools/bootstrap_tmp_apex_env.py

Or with an explicit Python (creates venv using that interpreter):
  py -3.12 devtools/bootstrap_tmp_apex_env.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = ROOT / ".tmp_apex_env"


def _venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def main() -> int:
    if not _venv_python().exists():
        rc = subprocess.run(
            [sys.executable, "-m", "venv", str(VENV_DIR)],
            cwd=ROOT,
            check=False,
        ).returncode
        if rc != 0:
            return rc
    py = _venv_python()
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    steps = [
        [str(py), "-m", "pip", "install", "-U", "pip"],
        [str(py), "-m", "pip", "install", "-e", ".[dev]"],
        [str(py), "-m", "playwright", "install", "chromium"],
    ]
    for cmd in steps:
        rc = subprocess.run(cmd, cwd=ROOT, env=env, check=False).returncode
        if rc != 0:
            return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
