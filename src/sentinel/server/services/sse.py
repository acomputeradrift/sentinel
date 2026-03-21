from __future__ import annotations

import asyncio
import json
import queue
import threading
from typing import Any


class ProjectEventBroker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[str, set[queue.Queue[str]]] = {}
        self._last_event: dict[str, str] = {}

    def subscribe(self, *, projectId: str, max_queue: int = 100) -> queue.Queue[str]:
        q: queue.Queue[str] = queue.Queue(maxsize=max_queue)
        with self._lock:
            self._subscribers.setdefault(projectId, set()).add(q)
            last = self._last_event.get(projectId)
        if last is not None:
            try:
                q.put_nowait(last)
            except Exception:
                pass
        return q

    def unsubscribe(self, *, projectId: str, q: queue.Queue[str]) -> None:
        with self._lock:
            subs = self._subscribers.get(projectId)
            if not subs:
                return
            subs.discard(q)
            if not subs:
                self._subscribers.pop(projectId, None)

    def publish(self, *, projectId: str, event: dict[str, Any]) -> None:
        msg = json.dumps(event, separators=(",", ":"), ensure_ascii=False)
        with self._lock:
            self._last_event[projectId] = msg
        with self._lock:
            subs = list(self._subscribers.get(projectId, set()))
        for q in subs:
            try:
                q.put_nowait(msg)
            except queue.Full:
                try:
                    _ = q.get_nowait()
                except Exception:
                    pass
                try:
                    q.put_nowait(msg)
                except Exception:
                    pass


async def wait_for_next(q: queue.Queue[str], *, timeout_s: float) -> str | None:
    try:
        return await asyncio.wait_for(asyncio.to_thread(q.get), timeout=timeout_s)
    except asyncio.TimeoutError:
        return None
