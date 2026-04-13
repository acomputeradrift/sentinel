"""
Run `dev_tests/regression` using `.tmp_apex_env` (same interpreter as local UI tests).

Prerequisite: `python devtools/bootstrap_tmp_apex_env.py` once per machine (or after deps change).

Writes a short log to `devtools/last_regression_run.txt` for agents / CI that capture no stdout.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = Path(__file__).resolve().parent / "last_regression_run.txt"


def _venv_python() -> Path:
    if os.name == "nt":
        return ROOT / ".tmp_apex_env" / "Scripts" / "python.exe"
    return ROOT / ".tmp_apex_env" / "bin" / "python"


def main() -> int:
    py = _venv_python()
    if not py.exists():
        sys.stderr.write(
            f"Missing venv at {py}. Run: python devtools/bootstrap_tmp_apex_env.py\n"
        )
        return 2
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    cmd = [
        str(py),
        "-m",
        "unittest",
        "discover",
        "-s",
        "dev_tests/regression",
        "-p",
        "test_*.py",
        "-v",
    ]
    p = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    LOG.write_text(
        (p.stdout or "") + "\n--- STDERR ---\n" + (p.stderr or ""),
        encoding="utf-8",
    )
    sys.stdout.write(p.stdout or "")
    sys.stderr.write(p.stderr or "")
    return p.returncode


if __name__ == "__main__":
    raise SystemExit(main())
