from __future__ import annotations

from datetime import datetime, timezone


class EventLogger:
    LEVELS = {"info": "INFO", "warn": "WARN", "success": "SUCCESS", "fail": "FAIL"}

    def _log(self, level: str, message: str) -> None:
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        print(f"{ts} [{self.LEVELS[level]}] {message}")

    def info(self, message: str) -> None:
        self._log("info", message)

    def warn(self, message: str) -> None:
        self._log("warn", message)

    def success(self, message: str) -> None:
        self._log("success", message)

    def fail(self, message: str) -> None:
        self._log("fail", message)
