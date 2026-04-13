from __future__ import annotations

import os
import unittest
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def apex_fixture_path() -> Path | None:
    """
    Return path to a real .apex (SQLite) fixture if one is available.

    Resolution order:
    1. SENTINEL_TEST_APEX environment variable (absolute or repo-relative path)
    2. dev_tests/fixtures/sample.apex
    3. Assets/TEST - System Manager v11.3.apex (local dev; often gitignored)
    4. Smallest *.apex under Assets/
    """
    root = _repo_root()
    env = (os.environ.get("SENTINEL_TEST_APEX") or "").strip()
    if env:
        p = Path(env)
        if not p.is_absolute():
            p = (root / p).resolve()
        if p.is_file():
            return p
    for rel in (Path("dev_tests/fixtures/sample.apex"),):
        p = (root / rel).resolve()
        if p.is_file():
            return p
    assets = root / "Assets"
    preferred = assets / "TEST - System Manager v11.3.apex"
    if preferred.is_file():
        return preferred
    candidates = sorted(assets.glob("*.apex"), key=lambda x: x.stat().st_size)
    if candidates:
        return candidates[0]
    return None


def apex_fixture_available() -> bool:
    return apex_fixture_path() is not None


def create_test_apex(path: Path) -> None:
    """
    Copy a real .apex fixture to ``path`` for extraction / pipeline tests.

    Raises ``unittest.SkipTest`` when no fixture is available (e.g. CI without binary).
    """
    src = apex_fixture_path()
    if src is None:
        raise unittest.SkipTest(
            "No .apex fixture: set SENTINEL_TEST_APEX to a file path, or add "
            "dev_tests/fixtures/sample.apex — see dev_tests/fixtures/README.md"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(src.read_bytes())
