from __future__ import annotations

from datetime import datetime, timezone


class EventLogger:
    LEVELS = {"info": "INFO", "warn": "WARN", "success": "SUCCESS", "fail": "FAIL"}

    def _log(self, level: str, message: str) -> None:
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        print(f"{ts} [{self.LEVELS[level]}] {message}")

    def info(self, message: str) -> None:
        self._log("info", message)

    def info_kv(self, message: str, **fields: object) -> None:
        self.info(self._with_fields(message, **fields))

    def warn(self, message: str) -> None:
        self._log("warn", message)

    def success(self, message: str) -> None:
        self._log("success", message)

    def fail(self, message: str) -> None:
        self._log("fail", message)

    @staticmethod
    def _with_fields(message: str, **fields: object) -> str:
        if not fields:
            return message
        rendered: list[str] = []
        for key, value in fields.items():
            rendered.append(f"{str(key)}={value}")
        return f"{message} {' '.join(rendered)}"
