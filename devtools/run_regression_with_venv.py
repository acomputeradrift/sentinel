"""
Run `dev_tests/regression` and Playwright UI checks for synthetic list scroll using `.tmp_apex_env`.

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
    parts: list[str] = []
    p = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    parts.append(p.stdout or "")
    parts.append("\n--- STDERR (regression) ---\n")
    parts.append(p.stderr or "")
    sys.stdout.write(p.stdout or "")
    sys.stderr.write(p.stderr or "")

    ui_cmd = [
        str(py),
        "-m",
        "unittest",
        "dev_tests.ui.test_synthetic_list_scroll_runtime",
        "-v",
    ]
    p2 = subprocess.run(ui_cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    parts.append("\n\n=== unittest dev_tests.ui.test_synthetic_list_scroll_runtime ===\n")
    parts.append(p2.stdout or "")
    parts.append("\n--- STDERR (synthetic list UI) ---\n")
    parts.append(p2.stderr or "")
    sys.stdout.write("\n")
    sys.stdout.write(p2.stdout or "")
    sys.stderr.write(p2.stderr or "")
    rc = 0 if (p.returncode == 0 and p2.returncode == 0) else 1

    LOG.write_text("".join(parts), encoding="utf-8")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
