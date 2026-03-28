from __future__ import annotations

import asyncio
import json
import queue
import threading
import logging
from typing import Any


class ProjectEventBroker:
    def __init__(self, replay_capacity: int = 500) -> None:
        self._log = logging.getLogger("uvicorn.error")
        self._lock = threading.Lock()
        self._subscribers: dict[str, set[queue.Queue[str]]] = {}
        self._last_event: dict[str, str] = {}
        self._seq_by_project: dict[str, int] = {}
        self._history_by_project: dict[str, list[dict[str, Any]]] = {}
        self._replay_capacity = max(10, int(replay_capacity or 500))

    def _next_seq_locked(self, projectId: str) -> int:
        next_seq = int(self._seq_by_project.get(projectId, 0)) + 1
        self._seq_by_project[projectId] = next_seq
        return next_seq

    def latest_seq(self, *, projectId: str) -> int:
        with self._lock:
            return int(self._seq_by_project.get(projectId, 0))

    def replay_since(self, *, projectId: str, after_seq: int) -> dict[str, Any]:
        with self._lock:
            history = list(self._history_by_project.get(projectId, []))
            latest_seq = int(self._seq_by_project.get(projectId, 0))
        replayable_from = int(history[0]["seq"]) if history else max(1, latest_seq)
        events = [ev for ev in history if int(ev.get("seq") or 0) > int(after_seq or 0)]
        return {
            "projectId": projectId,
            "latestSeq": latest_seq,
            "replayableFromSeq": replayable_from,
            "events": events,
        }

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

    def publish(self, *, projectId: str, event: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            payload = dict(event or {})
            seq = int(payload.get("seq") or 0)
            if seq <= 0:
                seq = self._next_seq_locked(projectId)
            else:
                self._seq_by_project[projectId] = max(int(self._seq_by_project.get(projectId, 0)), seq)
            payload["seq"] = seq
            msg = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
            self._last_event[projectId] = msg
            history = self._history_by_project.setdefault(projectId, [])
            history.append(payload)
            if len(history) > self._replay_capacity:
                del history[: len(history) - self._replay_capacity]
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
        return payload

    def publish_transient(self, *, projectId: str, event: dict[str, Any]) -> dict[str, Any]:
        payload = dict(event or {})
        payload.pop("seq", None)
        msg = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        with self._lock:
            subs = list(self._subscribers.get(projectId, set()))
        self._log.info("[broker] publish_transient projectId=%s broker_id=%s subs=%s", projectId, id(self), len(subs))
        for q in subs:
            try:
                q.put_nowait(msg)
            except queue.Full:
                try:
                    _ = q.get_nowait()
                except Exception:
                    self._log.exception(
                        "[broker] publish_transient-queue-drop-failed projectId=%s broker_id=%s", projectId, id(self)
                    )
                try:
                    q.put_nowait(msg)
                except Exception:
                    self._log.exception(
                        "[broker] publish_transient-delivery-failed projectId=%s broker_id=%s", projectId, id(self)
                    )
        return payload


async def wait_for_next(q: queue.Queue[str], *, timeout_s: float) -> str | None:
    deadline = asyncio.get_running_loop().time() + max(0.0, float(timeout_s or 0.0))
    while True:
        try:
            item = q.get_nowait()
            return item
        except queue.Empty:
            if asyncio.get_running_loop().time() >= deadline:
                return None
            await asyncio.sleep(0.05)
