"""Resolve repo / venv paths and a subprocess ``cwd`` that works on Windows UNC shares.

``cmd.exe`` rejects a UNC current directory ("UNC paths are not supported"). Child
processes should use a local ``cwd`` (e.g. ``%TEMP%``) while argv paths stay absolute.

Optional environment overrides (agents / mapped-drive setups):

* ``SENTINEL_REPO_ROOT`` — directory that contains ``pyproject.toml`` (use when UNC
  resolution from this file disagrees with your working tree).
* ``SENTINEL_VENV_PYTHON`` — absolute path to the venv ``python.exe`` (or ``python`` on
  POSIX) to use instead of ``<repo>/.tmp_apex_env/...``.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def repo_root(*, anchor_file: Path) -> Path:
    """Return the repository root (directory containing ``pyproject.toml``)."""
    env = (os.environ.get("SENTINEL_REPO_ROOT") or "").strip()
    if env:
        p = Path(env).expanduser()
        try:
            p = p.resolve(strict=False)
        except OSError:
            pass
        marker = p / "pyproject.toml"
        if marker.is_file():
            return p
    here = anchor_file.resolve(strict=False)
    return here.parents[1]


def venv_python(repo: Path) -> Path:
    """Return the ``.tmp_apex_env`` interpreter path."""
    env = (os.environ.get("SENTINEL_VENV_PYTHON") or "").strip()
    if env:
        return Path(env).expanduser().resolve(strict=False)
    if os.name == "nt":
        return (repo / ".tmp_apex_env" / "Scripts" / "python.exe").resolve(strict=False)
    return (repo / ".tmp_apex_env" / "bin" / "python").resolve(strict=False)


def subprocess_cwd(repo: Path) -> Path:
    """``cwd`` for ``subprocess.run`` when the repo is on a UNC path (Windows)."""
    try:
        repo_s = str(repo.resolve(strict=False))
    except OSError:
        repo_s = str(repo)
    if os.name == "nt" and (repo_s.startswith("\\\\") or repo_s.startswith("//")):
        return Path(tempfile.gettempdir()).resolve(strict=False)
    try:
        return repo.resolve(strict=False)
    except OSError:
        return Path(tempfile.gettempdir()).resolve(strict=False)
