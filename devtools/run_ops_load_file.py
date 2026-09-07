"""Run the ops suite inside Docker: Postgres + app + Playwright.

Single method. Host Chromium and host Uvicorn are not used.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import repo_paths

_HERE = Path(__file__).resolve()
ROOT = repo_paths.repo_root(anchor_file=_HERE)
COMPOSE = ROOT / "dev_tests" / "ops" / "compose.yml"
LOG = _HERE.parent / "last_ops_load_file.txt"


def _compose(*args: str) -> list[str]:
    return ["docker", "compose", "-f", str(COMPOSE), "--project-directory", str(ROOT), *args]


def main() -> int:
    if not COMPOSE.is_file():
        sys.stderr.write(f"Missing {COMPOSE}\n")
        return 2
    parts = [f"REPO_ROOT={ROOT}\nCOMPOSE={COMPOSE}\nMETHOD=docker-compose\n"]
    try:
        subprocess.run(_compose("down", "-v", "--remove-orphans"), cwd=str(ROOT), check=False)
        run = subprocess.run(
            _compose("run", "--rm", "ops"),
            cwd=str(ROOT),
            text=True,
            capture_output=True,
        )
        parts.append(run.stdout or "")
        parts.append("\n--- STDERR ---\n")
        parts.append(run.stderr or "")
        if run.returncode != 0:
            logs = subprocess.run(
                _compose("logs", "app"),
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            parts.append("\n--- APP LOGS ---\n")
            parts.append(logs.stdout or "")
            parts.append(logs.stderr or "")
        sys.stdout.write(run.stdout or "")
        sys.stderr.write(run.stderr or "")
        LOG.write_text("".join(parts), encoding="utf-8")
        return 0 if run.returncode == 0 else 1
    except Exception as e:
        parts.append(f"\nRUNNER_ERROR: {e}\n")
        LOG.write_text("".join(parts), encoding="utf-8")
        sys.stderr.write(f"{e}\n")
        return 1
    finally:
        subprocess.run(_compose("down", "-v", "--remove-orphans"), cwd=str(ROOT), check=False)


if __name__ == "__main__":
    raise SystemExit(main())
