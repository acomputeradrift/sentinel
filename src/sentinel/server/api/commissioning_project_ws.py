from __future__ import annotations

import asyncio
import json
import logging
import time

from fastapi import WebSocket
from fastapi import WebSocketDisconnect

from sentinel.server.api import commissioning_snapshots
from sentinel.server.services import ws_broker
from sentinel.server.services.repositories import Repository

log = logging.getLogger("uvicorn.error")
WS_KEEPALIVE_TIMEOUT_S = 15.0
WS_SEND_TIMEOUT_S = 5.0


async def send_text_or_fail(*, websocket: WebSocket, text: str, projectId: str) -> None:
    try:
        await asyncio.wait_for(websocket.send_text(text), timeout=float(WS_SEND_TIMEOUT_S))
    except asyncio.TimeoutError:
        log.error("WS-ERR-320 SEND_TIMEOUT [commissioning-ws] projectId=%s", projectId)
        try:
            await websocket.close(code=1011)
        except Exception:
            log.exception("[commissioning-ws] close-after-timeout-failed projectId=%s", projectId)
        raise
    except Exception:
        log.exception("[commissioning-ws] send-failed projectId=%s", projectId)
        try:
            await websocket.close(code=1011)
        except Exception:
            log.exception("[commissioning-ws] close-after-send-failed projectId=%s", projectId)
        raise


async def run_commissioning_project_ws(
    *,
    websocket: WebSocket,
    projectId: str,
    repo: Repository,
    broker: ws_broker.ProjectEventBroker,
) -> None:
    log.info("[commissioning-ws] connect projectId=%s", projectId)

    q = broker.subscribe(projectId=projectId)
    perf: dict[str, float | int] = {
        "recv_count": 0,
        "recv_total_ms": 0.0,
        "send_count": 0,
        "send_total_ms": 0.0,
    }
    try:
        snapshot = commissioning_snapshots.commissioning_snapshot(
            repo=repo, projectId=projectId, seq=broker.latest_seq(projectId=projectId)
        )
        await send_text_or_fail(
            websocket=websocket,
            text=json.dumps(snapshot, separators=(",", ":"), ensure_ascii=False),
            projectId=projectId,
        )

        async def send_loop():
            while True:
                msg = await ws_broker.wait_for_next(q, timeout_s=WS_KEEPALIVE_TIMEOUT_S)
                send_started = time.perf_counter()
                send_kind = "event"
                if msg is None:
                    send_kind = "keepalive"
                    await send_text_or_fail(
                        websocket=websocket, text=json.dumps({"type": "keepalive"}), projectId=projectId
                    )
                else:
                    try:
                        parsed = json.loads(msg)
                        if isinstance(parsed, dict):
                            t = str(parsed.get("type") or "").strip()
                            if t:
                                log.info("[commissioning-ws] send type=%s projectId=%s", t, projectId)
                    except Exception:
                        log.warning("[commissioning-ws] send:parse-failed projectId=%s", projectId)
                    await send_text_or_fail(websocket=websocket, text=msg, projectId=projectId)
                send_ms = (time.perf_counter() - send_started) * 1000.0
                perf["send_count"] = int(perf["send_count"]) + 1
                perf["send_total_ms"] = float(perf["send_total_ms"]) + float(send_ms)
                send_count = int(perf["send_count"])
                if send_ms >= 50.0 or (send_count % 25 == 0):
                    send_avg = float(perf["send_total_ms"]) / max(send_count, 1)
                    log.info(
                        "[commissioning-ws] perf kind=send sendKind=%s sendMs=%.2f sendAvgMs=%.2f sendCount=%s projectId=%s",
                        send_kind,
                        send_ms,
                        send_avg,
                        send_count,
                        projectId,
                    )

        async def recv_loop():
            while True:
                raw = await websocket.receive_text()
                recv_started = time.perf_counter()
                msg_type = "(unknown)"
                try:
                    payload = json.loads(raw)
                except Exception:
                    log.warning("[commissioning-ws] recv:json-parse-failed projectId=%s raw=%s", projectId, str(raw)[:200])
                    continue
                try:
                    msg_type = str(payload.get("type") or "").strip()
                    if msg_type != "sync.request":
                        await send_text_or_fail(
                            websocket=websocket,
                            text=json.dumps({"type": "error", "code": "UNKNOWN_MESSAGE"}),
                            projectId=projectId,
                        )
                        continue

                    last_applied = int(payload.get("lastAppliedSeq") or 0)
                    replay = broker.replay_since(projectId=projectId, after_seq=last_applied)
                    replayable_from = int(replay.get("replayableFromSeq") or 0)
                    latest_seq = int(replay.get("latestSeq") or 0)
                    events = replay.get("events") or []
                    if replayable_from > (last_applied + 1):
                        snap = commissioning_snapshots.commissioning_snapshot(
                            repo=repo, projectId=projectId, seq=latest_seq
                        )
                        await send_text_or_fail(
                            websocket=websocket,
                            text=json.dumps(snap, separators=(",", ":"), ensure_ascii=False),
                            projectId=projectId,
                        )
                        continue
                    await send_text_or_fail(
                        websocket=websocket,
                        text=json.dumps(
                            {
                                "type": "replay.batch",
                                "projectId": projectId,
                                "afterSeq": last_applied,
                                "latestSeq": latest_seq,
                                "events": events,
                            },
                            separators=(",", ":"),
                            ensure_ascii=False,
                        ),
                        projectId=projectId,
                    )
                finally:
                    recv_ms = (time.perf_counter() - recv_started) * 1000.0
                    perf["recv_count"] = int(perf["recv_count"]) + 1
                    perf["recv_total_ms"] = float(perf["recv_total_ms"]) + float(recv_ms)
                    recv_count = int(perf["recv_count"])
                    if recv_ms >= 50.0 or (recv_count % 25 == 0):
                        recv_avg = float(perf["recv_total_ms"]) / max(recv_count, 1)
                        log.info(
                            "[commissioning-ws] perf kind=recv type=%s recvMs=%.2f recvAvgMs=%.2f recvCount=%s projectId=%s",
                            msg_type or "(unknown)",
                            recv_ms,
                            recv_avg,
                            recv_count,
                            projectId,
                        )

        send_task = asyncio.create_task(send_loop())
        recv_task = asyncio.create_task(recv_loop())
        try:
            done, pending = await asyncio.wait({send_task, recv_task}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                if task.cancelled():
                    continue
                exc = task.exception()
                if exc is None:
                    continue
                if isinstance(exc, (WebSocketDisconnect, asyncio.CancelledError)):
                    raise exc
                raise exc
        finally:
            send_task.cancel()
            recv_task.cancel()
            await asyncio.gather(send_task, recv_task, return_exceptions=True)
    except (WebSocketDisconnect, asyncio.CancelledError):
        log.info("[commissioning-ws] disconnect projectId=%s", projectId)
        return
    except Exception:
        log.exception("[commissioning-ws] stream-failed projectId=%s", projectId)
        return
    finally:
        try:
            broker.unsubscribe(projectId=projectId, q=q)
        except Exception:
            log.exception("[commissioning-ws] unsubscribe-failed projectId=%s", projectId)
