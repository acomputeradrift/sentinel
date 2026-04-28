"""
Run `dev_tests/regression` and Playwright UI checks for synthetic list scroll using `.tmp_apex_env`.

Prerequisite: `python devtools/bootstrap_tmp_apex_env.py` once per machine (or after deps change).

UNC / agent shells: uses a non-UNC ``cwd`` for subprocess children when the repo is on
``\\\\server\\...`` (see ``devtools/repo_paths.py``). Override repo/venv with
``SENTINEL_REPO_ROOT`` / ``SENTINEL_VENV_PYTHON`` if needed.

Writes a short log to `devtools/last_regression_run.txt` for agents / CI that capture no stdout.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import repo_paths

_HERE = Path(__file__).resolve()
ROOT = repo_paths.repo_root(anchor_file=_HERE)
LOG = _HERE.parent / "last_regression_run.txt"


def _pythonpath() -> str:
    """Repo root (for ``dev_tests``) + ``src`` (for ``sentinel``)."""
    sep = os.pathsep
    return sep.join([str(ROOT), str(ROOT / "src")])


def _probe_playwright(py: Path, *, cwd: Path) -> tuple[bool, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = _pythonpath()
    r = subprocess.run(
        [str(py), "-c", "from playwright.sync_api import sync_playwright; print('import-ok')"],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
    )
    if r.returncode == 0:
        return True, (r.stdout or "").strip() or "ok"
    err = (r.stderr or r.stdout or "").strip() or f"exit {r.returncode}"
    return False, err


def main() -> int:
    py = repo_paths.venv_python(ROOT)
    cwd = repo_paths.subprocess_cwd(ROOT)
    if not py.exists():
        sys.stderr.write(
            f"Missing venv at {py}. Run: python devtools/bootstrap_tmp_apex_env.py\n"
            f"(repo root resolved to {ROOT}; override with SENTINEL_REPO_ROOT or SENTINEL_VENV_PYTHON)\n"
        )
        return 2
    env = os.environ.copy()
    env["PYTHONPATH"] = _pythonpath()
    reg_dir = ROOT / "dev_tests" / "regression"
    cmd = [
        str(py),
        "-m",
        "unittest",
        "discover",
        "-s",
        str(reg_dir),
        "-p",
        "test_*.py",
        "-v",
    ]
    parts: list[str] = []
    header = (
        f"REPO_ROOT={ROOT}\n"
        f"VENV_PYTHON={py}\n"
        f"SUBPROCESS_CWD={cwd}\n"
    )
    pw_ok, pw_msg = _probe_playwright(py, cwd=cwd)
    header += f"PLAYWRIGHT_IMPORT={'ok' if pw_ok else 'FAILED'}: {pw_msg}\n\n"
    parts.append(header)
    sys.stderr.write(header)

    p = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, text=True)
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
    p2 = subprocess.run(ui_cmd, cwd=str(cwd), env=env, capture_output=True, text=True)
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
