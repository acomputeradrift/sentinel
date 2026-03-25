from __future__ import annotations

import asyncio
import json
import queue
import threading
import logging
from typing import Any


class ProjectEventBroker:
    def __init__(self) -> None:
        self._log = logging.getLogger("uvicorn.error")
        self._lock = threading.Lock()
        self._subscribers: dict[str, set[queue.Queue[str]]] = {}
        self._last_event: dict[str, str] = {}

    def subscribe(self, *, projectId: str, max_queue: int = 100) -> queue.Queue[str]:
        q: queue.Queue[str] = queue.Queue(maxsize=max_queue)
        with self._lock:
            self._subscribers.setdefault(projectId, set()).add(q)
            last = self._last_event.get(projectId)
            sub_count = len(self._subscribers.get(projectId, set()))
        self._log.info("[broker] subscribe projectId=%s broker_id=%s subs=%s", projectId, id(self), sub_count)
        if last is not None:
            try:
                q.put_nowait(last)
            except Exception:
                self._log.exception("[broker] subscribe-replay-failed projectId=%s broker_id=%s", projectId, id(self))
        return q

    def unsubscribe(self, *, projectId: str, q: queue.Queue[str]) -> None:
        with self._lock:
            subs = self._subscribers.get(projectId)
            if not subs:
                return
            subs.discard(q)
            if not subs:
                self._subscribers.pop(projectId, None)
            sub_count = len(self._subscribers.get(projectId, set()))
        self._log.info("[broker] unsubscribe projectId=%s broker_id=%s subs=%s", projectId, id(self), sub_count)

    def publish(self, *, projectId: str, event: dict[str, Any]) -> None:
        msg = json.dumps(event, separators=(",", ":"), ensure_ascii=False)
        with self._lock:
            self._last_event[projectId] = msg
        with self._lock:
            subs = list(self._subscribers.get(projectId, set()))
        self._log.info("[broker] publish projectId=%s broker_id=%s subs=%s", projectId, id(self), len(subs))
        for q in subs:
            try:
                q.put_nowait(msg)
            except queue.Full:
                try:
                    _ = q.get_nowait()
                except Exception:
                    self._log.exception("[broker] publish-queue-drop-failed projectId=%s broker_id=%s", projectId, id(self))
                try:
                    q.put_nowait(msg)
                except Exception:
                    self._log.exception("[broker] publish-delivery-failed projectId=%s broker_id=%s", projectId, id(self))


async def wait_for_next(q: queue.Queue[str], *, timeout_s: float) -> str | None:
    try:
        log = logging.getLogger("uvicorn.error")
        log.info("[broker-wait] enter thread=%s qsize=%s", threading.current_thread().name, q.qsize() if hasattr(q, "qsize") else "na")
        item = await asyncio.wait_for(asyncio.to_thread(q.get), timeout=timeout_s)
        log.info("[broker-wait] exit thread=%s qsize=%s", threading.current_thread().name, q.qsize() if hasattr(q, "qsize") else "na")
        return item
    except asyncio.TimeoutError:
        return None
