from __future__ import annotations

import os
import logging
import time
from pathlib import Path, PurePosixPath
import re

import asyncio
import json

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse
from fastapi.responses import Response

from sentinel.server.api.errors import http_error
from sentinel.server.services import progress
from sentinel.server.services import ws_broker
from sentinel.server.services.repositories import Repository


router = APIRouter(tags=["testing"])
log = logging.getLogger("uvicorn.error")
WS_KEEPALIVE_TIMEOUT_S = 15.0
WS_SEND_TIMEOUT_S = 5.0
SHELL_RUNTIME_MODE = "shell"


def _repo(request: Request) -> Repository:
    return request.app.state.repo


def _broker(request: Request) -> ws_broker.ProjectEventBroker:
    broker = getattr(request.app.state, "project_event_broker", None)
    if broker is None:
        broker = ws_broker.ProjectEventBroker()
        request.app.state.project_event_broker = broker
    return broker


def _ws_repo(websocket: WebSocket) -> Repository:
    return websocket.app.state.repo


def _ws_broker(websocket: WebSocket) -> ws_broker.ProjectEventBroker:
    broker = getattr(websocket.app.state, "project_event_broker", None)
    if broker is None:
        broker = ws_broker.ProjectEventBroker()
        websocket.app.state.project_event_broker = broker
    return broker


def _compute_progress_and_rollups(*, repo: Repository, projectId: str) -> tuple[dict | None, dict | None]:
    try:
        latest = repo.get_latest_results_for_project(projectId=projectId)
        prog = progress.commissioning_progress(projectId=projectId, latest_results=latest)
    except FileNotFoundError:
        log.info("[testing-ws] rollups:project-model-missing projectId=%s", projectId)
        return None, None
    except Exception:
        log.exception("[testing-ws] rollups:compute-failed projectId=%s", projectId)
        return None, None

    tags = repo.get_fail_tags_for_project(projectId=projectId)
    by_target: dict[str, int] = {}
    by_tag = {"NOT_STARTED": 0, "IN_PROGRESS": 0, "DONE": 0}
    total = 0
    for rec in latest.values():
        if rec.outcome != "FAIL":
            continue
        target = rec.target if isinstance(rec.target, dict) else {}
        target_key = str(target.get("targetKey") or "").strip()
        if not target_key:
            continue
        total += 1
        name = str(target.get("targetName") or "").strip() or "(unknown)"
        by_target[name] = by_target.get(name, 0) + 1
        tag = str(tags.get(target_key, "NOT_STARTED") or "NOT_STARTED").strip().upper()
        if tag not in by_tag:
            tag = "NOT_STARTED"
        by_tag[tag] += 1

    rollups = {
        "projectId": projectId,
        "progress": prog,
        "firstTimeFailTargets": repo.count_first_time_fail_targets(projectId=projectId),
        "currentFailures": {"total": total, "byTargetName": by_target, "byTag": by_tag},
    }
    return prog, rollups


def _build_test_result_event(*, repo: Repository, rec) -> dict:
    target_key = str(rec.target.get("targetKey") or "")
    progress_payload, rollups_payload = _compute_progress_and_rollups(repo=repo, projectId=rec.projectId)
    return {
        "type": "test_result",
        "projectId": rec.projectId,
        "recordedAtUtc": rec.recordedAtUtc,
        "targetKey": target_key,
        "outcome": rec.outcome,
        "targetName": rec.target.get("targetName"),
        "kind": rec.target.get("kind") or rec.target.get("targetKind"),
        "refs": rec.target.get("refs"),
        "failNote": rec.failNote,
        "progress": progress_payload,
        "rollups": rollups_payload,
    }


def _build_testing_snapshot(*, repo: Repository, projectId: str, seq: int = 0) -> dict:
    latest = repo.get_latest_results_for_project(projectId=projectId)
    rows = list(latest.values())
    rows.sort(key=lambda r: r.recordedAtUtc, reverse=True)
    results: list[dict] = []
    for rec in rows:
        target = rec.target if isinstance(rec.target, dict) else {}
        results.append(
            {
                "targetKey": str(target.get("targetKey") or ""),
                "outcome": str(rec.outcome or "").upper(),
                "recordedAtUtc": rec.recordedAtUtc,
                "targetName": target.get("targetName"),
                "kind": target.get("kind") or target.get("targetKind"),
                "refs": target.get("refs"),
                "failNote": rec.failNote,
            }
        )
    return {"type": "testing_snapshot", "seq": int(seq or 0), "projectId": projectId, "results": results}


async def _send_text_or_fail(*, websocket: WebSocket, text: str, project_id: str, tech_token: str) -> None:
    try:
        await asyncio.wait_for(websocket.send_text(text), timeout=float(WS_SEND_TIMEOUT_S))
    except asyncio.TimeoutError:
        log.error("WS-ERR-320 SEND_TIMEOUT [testing-ws] projectId=%s techToken=%s", project_id, tech_token)
        try:
            await websocket.close(code=1011)
        except Exception:
            log.exception("[testing-ws] close-after-timeout-failed projectId=%s techToken=%s", project_id, tech_token)
        raise
    except Exception:
        log.exception("[testing-ws] send-failed projectId=%s techToken=%s", project_id, tech_token)
        try:
            await websocket.close(code=1011)
        except Exception:
            log.exception("[testing-ws] close-after-send-failed projectId=%s techToken=%s", project_id, tech_token)
        raise


def _generated_root() -> Path:
    return Path(os.environ.get("SENTINEL_GENERATED_ROOT") or "generated").resolve()


def _project_dir(*, projectId: str) -> Path:
    return (_generated_root() / projectId).resolve()


def _find_project_home(project_dir: Path) -> Path | None:
    if not project_dir.exists() or not project_dir.is_dir():
        return None
    candidates = list(project_dir.glob("*__project-home.html"))
    if candidates:
        return max(candidates, key=lambda p: (p.stat().st_mtime, p.name))
    fallback = project_dir / "project-home.html"
    return fallback if fallback.exists() else None


def _find_project_manifest(project_dir: Path) -> Path | None:
    if not project_dir.exists() or not project_dir.is_dir():
        return None
    candidates = list(project_dir.glob("*__project-manifest.json"))
    if candidates:
        return max(candidates, key=lambda p: (p.stat().st_mtime, p.name))
    return None


def _inject_base_href(html: str, *, base_href: str) -> str:
    if "<base " in html or "<base>" in html:
        return html
    needle = "<head>"
    if needle in html:
        return html.replace(needle, needle + f'<base href="{base_href}">', 1)
    needle2 = "<head"
    idx = html.find(needle2)
    if idx >= 0:
        close = html.find(">", idx)
        if close >= 0:
            return html[: close + 1] + f'<base href="{base_href}">' + html[close + 1 :]
    return f'<base href="{base_href}">' + html


def _inject_shell_runtime_home_navigation(html: str) -> str:
    script = (
        "<script>"
        "(function(){"
        "function patch(a){"
        "if(!a||!a.getAttribute)return;"
        "var href=a.getAttribute('href')||'';"
        "if(!href||href.charAt(0)==='#'||href.indexOf('javascript:')===0||href.indexOf('mailto:')===0||href.indexOf('tel:')===0)return;"
        "try{"
        "var base=(document.baseURI&&String(document.baseURI||'').length)?document.baseURI:window.location.href;"
        "var u=new URL(href,base);"
        "var p=(u.pathname||'').toLowerCase();"
        "if(!p.endsWith('.html'))return;"
        "if((u.searchParams.get('runtime')||'').toLowerCase()==='shell')return;"
        "u.searchParams.set('runtime','shell');"
        "a.setAttribute('href',u.pathname+u.search+u.hash);"
        "}catch(_e){}"
        "}"
        "document.querySelectorAll('a[href]').forEach(patch);"
        "document.addEventListener('click',function(e){var a=e.target&&e.target.closest?e.target.closest('a[href]'):null;patch(a);},true);"
        "})();"
        "</script>"
    )
    needle = "</body>"
    if needle in html:
        return html.replace(needle, script + needle, 1)
    return html + script


def _shell_template_path() -> Path:
    return (Path(__file__).resolve().parents[2] / "ui" / "commissioning" / "project_device_static_layout.html").resolve()


def _build_static_shell_device_html(*, tech_token: str) -> str:
    template_path = _shell_template_path()
    if not template_path.exists():
        raise FileNotFoundError(str(template_path))
    html = template_path.read_text(encoding="utf-8", errors="replace")
    html = re.sub(
        r'href\s*=\s*["\']\./project_device_static_layout\.css["\']',
        'href="/commissioning/project_device_static_layout.css"',
        html,
        count=1,
    )
    html = re.sub(
        r'href\s*=\s*["\']#["\']',
        f'href="/testing/{tech_token}?runtime={SHELL_RUNTIME_MODE}"',
        html,
        count=1,
    )
    if "<meta name=\"sentinel-runtime-mode\"" not in html:
        html = html.replace("</head>", '<meta name="sentinel-runtime-mode" content="shell"></head>', 1)
    html = html.replace(
        '<div class="projectDeviceStaticLayout" aria-label="Project Device Static Layout">',
        '<div class="projectDeviceStaticLayout" data-runtime-mode="shell" aria-label="Project Device Static Layout">',
        1,
    )
    return html


def _log_display_baseline(
    *,
    stage: str,
    project_id: str,
    tech_token: str,
    serve_ms: float,
    size_bytes: int,
    path: str = "",
    is_device_html: bool = False,
) -> None:
    log.info(
        "DISPLAY_BASELINE stage=%s projectId=%s techToken=%s path=%s serveMs=%.3f sizeBytes=%s isDeviceHtml=%s",
        str(stage or ""),
        str(project_id or ""),
        str(tech_token or ""),
        str(path or ""),
        float(serve_ms),
        int(size_bytes),
        "1" if bool(is_device_html) else "0",
    )


@router.get("/testing/{techToken}", response_class=HTMLResponse)
def testing_html(request: Request, techToken: str) -> HTMLResponse:
    t0 = time.perf_counter()
    try:
        tok = _repo(request).resolve_active_token(techToken=techToken)
    except KeyError:
        raise http_error(410, code="TECH_LINK_REVOKED", message="This technician link has been revoked.")

    project_dir = _project_dir(projectId=tok.projectId)
    runtime_mode = str(request.query_params.get("runtime") or "").strip().lower()
    if runtime_mode == "payload":
        manifest = _find_project_manifest(project_dir)
        if manifest is None:
            html = (
                "<!doctype html><html><head><meta charset='utf-8'><title>Sentinel Testing Runtime</title></head>"
                "<body><h1>Sentinel Testing Runtime</h1><p>Payload has not been generated yet.</p></body></html>"
            )
            with_base = _inject_base_href(html, base_href=f"/testing/{techToken}/files/")
            _log_display_baseline(
                stage="home",
                project_id=tok.projectId,
                tech_token=techToken,
                serve_ms=(time.perf_counter() - t0) * 1000.0,
                size_bytes=len(with_base.encode("utf-8")),
                path="/testing/{techToken}",
                is_device_html=False,
            )
            return HTMLResponse(content=with_base, headers={"X-Sentinel-Runtime-Mode": "payload"})

    home = _find_project_home(project_dir)
    if home is None:
        html = "<!doctype html><html><head><meta charset='utf-8'><title>Sentinel Testing</title></head><body><h1>Sentinel Testing</h1><p>Testing UI has not been generated yet.</p></body></html>"
        with_base = _inject_base_href(html, base_href=f"/testing/{techToken}/files/")
        _log_display_baseline(
            stage="home",
            project_id=tok.projectId,
            tech_token=techToken,
            serve_ms=(time.perf_counter() - t0) * 1000.0,
            size_bytes=len(with_base.encode("utf-8")),
            path="/testing/{techToken}",
            is_device_html=False,
        )
        mode_header = SHELL_RUNTIME_MODE if runtime_mode == SHELL_RUNTIME_MODE else "default"
        return HTMLResponse(content=with_base, headers={"X-Sentinel-Runtime-Mode": mode_header})

    raw = home.read_text(encoding="utf-8", errors="replace")
    if runtime_mode == SHELL_RUNTIME_MODE:
        raw = _inject_shell_runtime_home_navigation(raw)
    with_base = _inject_base_href(raw, base_href=f"/testing/{techToken}/files/")
    _log_display_baseline(
        stage="home",
        project_id=tok.projectId,
        tech_token=techToken,
        serve_ms=(time.perf_counter() - t0) * 1000.0,
        size_bytes=len(with_base.encode("utf-8")),
        path=home.name,
        is_device_html=False,
    )
    mode_header = SHELL_RUNTIME_MODE if runtime_mode == SHELL_RUNTIME_MODE else "default"
    return HTMLResponse(content=with_base, headers={"X-Sentinel-Runtime-Mode": mode_header})


@router.get("/testing/{techToken}/files/{path:path}")
def testing_file(request: Request, techToken: str, path: str) -> Response:
    t0 = time.perf_counter()
    try:
        tok = _repo(request).resolve_active_token(techToken=techToken)
    except KeyError:
        raise http_error(410, code="TECH_LINK_REVOKED", message="This technician link has been revoked.")

    rel = PurePosixPath("/" + path).relative_to("/")
    if any(part in ("..", "") for part in rel.parts):
        raise http_error(404, code="NOT_FOUND", message="File not found.")

    project_dir = _project_dir(projectId=tok.projectId)
    target = (project_dir / Path(*rel.parts)).resolve()
    if project_dir not in target.parents and target != project_dir:
        raise http_error(404, code="NOT_FOUND", message="File not found.")
    if not target.exists() or not target.is_file():
        raise http_error(404, code="NOT_FOUND", message="File not found.")

    is_device_html = target.suffix.lower() == ".html" and "__device-" in target.name.lower()
    runtime_mode = str(request.query_params.get("runtime") or "").strip().lower()
    if runtime_mode == SHELL_RUNTIME_MODE and is_device_html:
        shell_html = _build_static_shell_device_html(tech_token=techToken)
        _log_display_baseline(
            stage="file",
            project_id=tok.projectId,
            tech_token=techToken,
            serve_ms=(time.perf_counter() - t0) * 1000.0,
            size_bytes=len(shell_html.encode("utf-8")),
            path=str(path or ""),
            is_device_html=True,
        )
        return HTMLResponse(content=shell_html, headers={"X-Sentinel-Runtime-Mode": SHELL_RUNTIME_MODE})
    _log_display_baseline(
        stage="file",
        project_id=tok.projectId,
        tech_token=techToken,
        serve_ms=(time.perf_counter() - t0) * 1000.0,
        size_bytes=int(target.stat().st_size),
        path=str(path or ""),
        is_device_html=is_device_html,
    )
    return FileResponse(path=str(target), headers={"X-Sentinel-Runtime-Mode": "default"})


@router.post("/api/v1/testing/{techToken}/ready")
def post_ready_baseline(request: Request, techToken: str, payload: dict) -> dict:
    try:
        tok = _repo(request).resolve_active_token(techToken=techToken)
    except KeyError:
        raise http_error(410, code="TECH_LINK_REVOKED", message="This technician link has been revoked.")

    ready_raw = (payload or {}).get("readySec")
    try:
        ready_sec = float(ready_raw)
    except (TypeError, ValueError):
        raise http_error(400, code="VALIDATION_ERROR", message="readySec must be a number.")
    if ready_sec < 0:
        raise http_error(400, code="VALIDATION_ERROR", message="readySec must be >= 0.")

    log.info(
        "READY_BASELINE projectId=%s techToken=%s readySec=%.3f",
        str(tok.projectId or ""),
        str(techToken or ""),
        ready_sec,
    )
    return {"projectId": tok.projectId, "techToken": techToken, "readySec": round(float(ready_sec), 3)}


@router.post("/api/v1/testing/{techToken}/results")
def post_result(request: Request, techToken: str, payload: dict) -> dict:
    target = payload.get("target") or {}
    outcome = str(payload.get("outcome") or "").strip().upper()
    fail_note = payload.get("failNote")

    if outcome not in ("PASS", "FAIL"):
        raise http_error(400, code="VALIDATION_ERROR", message="Outcome must be PASS or FAIL.")
    if outcome == "FAIL" and not str(fail_note or "").strip():
        raise http_error(400, code="FAIL_NOTE_REQUIRED", message="Fail note is required when outcome is FAIL.")

    try:
        rec = _repo(request).append_test_result(techToken=techToken, target=target, outcome=outcome, failNote=(str(fail_note).strip() if fail_note is not None else None))
    except KeyError:
        raise http_error(410, code="TECH_LINK_REVOKED", message="This technician link has been revoked.")

    target_key = str(rec.target.get("targetKey") or "")
    _broker(request).publish(projectId=rec.projectId, event=_build_test_result_event(repo=_repo(request), rec=rec))

    return {
        "testResultId": rec.testResultId,
        "projectId": rec.projectId,
        "generationRunId": None,
        "recordedAtUtc": rec.recordedAtUtc,
        "recordedBy": rec.recordedBy,
        "target": rec.target,
        "outcome": rec.outcome,
        "failNote": rec.failNote,
    }


@router.websocket("/api/v1/testing/{techToken}/ws")
async def testing_ws(websocket: WebSocket, techToken: str):
    await websocket.accept()
    log.info("[testing-ws] connect techToken=%s", techToken)

    repo = getattr(websocket.app.state, "repo", None)
    if repo is None:
        log.error("[testing-ws] repo_missing techToken=%s", techToken)
        await websocket.close(code=1011)
        return

    try:
        tok = repo.resolve_active_token(techToken=techToken)
    except KeyError:
        try:
            log.error("WS-ERR-330 TERMINAL_AUTH_REVOKED [testing-ws] techToken=%s", techToken)
            await websocket.send_text(json.dumps({"type": "error", "code": "TECH_LINK_REVOKED"}))
        finally:
            await websocket.close(code=1008)
        return

    project_id = tok.projectId
    broker = _ws_broker(websocket)
    log.info("[testing-ws] broker_id=%s projectId=%s", id(broker), project_id)
    q = broker.subscribe(projectId=project_id)
    perf: dict[str, float | int] = {
        "recv_count": 0,
        "recv_total_ms": 0.0,
        "send_count": 0,
        "send_total_ms": 0.0,
    }
    try:
        snapshot = _build_testing_snapshot(repo=repo, projectId=project_id, seq=broker.latest_seq(projectId=project_id))
        log.info("[testing-ws] snapshot-send projectId=%s count=%s", project_id, len(snapshot.get("results") or []))
        await _send_text_or_fail(
            websocket=websocket,
            text=json.dumps(snapshot, separators=(",", ":"), ensure_ascii=False),
            project_id=project_id,
            tech_token=techToken,
        )
    except Exception:
        log.exception("[testing-ws] snapshot-send-failed projectId=%s techToken=%s", project_id, techToken)

    async def send_loop():
        while True:
            msg = await ws_broker.wait_for_next(q, timeout_s=WS_KEEPALIVE_TIMEOUT_S)
            send_started = time.perf_counter()
            send_kind = "event"
            if msg is None:
                send_kind = "keepalive"
                await _send_text_or_fail(websocket=websocket, text=json.dumps({"type": "keepalive"}), project_id=project_id, tech_token=techToken)
            else:
                await _send_text_or_fail(websocket=websocket, text=msg, project_id=project_id, tech_token=techToken)
            send_ms = (time.perf_counter() - send_started) * 1000.0
            perf["send_count"] = int(perf["send_count"]) + 1
            perf["send_total_ms"] = float(perf["send_total_ms"]) + float(send_ms)
            send_count = int(perf["send_count"])
            if send_ms >= 50.0 or (send_count % 25 == 0):
                send_avg = float(perf["send_total_ms"]) / max(send_count, 1)
                log.info(
                    "[testing-ws] perf kind=send sendKind=%s sendMs=%.2f sendAvgMs=%.2f sendCount=%s projectId=%s techToken=%s",
                    send_kind,
                    send_ms,
                    send_avg,
                    send_count,
                    project_id,
                    techToken,
                )

    async def recv_loop():
        while True:
            raw = await websocket.receive_text()
            recv_started = time.perf_counter()
            msg_type = "(unknown)"
            try:
                payload = json.loads(raw)
            except Exception:
                log.warning("[testing-ws] recv:json-parse-failed techToken=%s raw=%s", techToken, str(raw)[:200])
                continue
            try:
                msg_type = str(payload.get("type") or "").strip()
                log.info("[testing-ws] recv type=%s techToken=%s", msg_type, techToken)
                if msg_type == "sync.request":
                    last_applied = int(payload.get("lastAppliedSeq") or 0)
                    replay = broker.replay_since(projectId=project_id, after_seq=last_applied)
                    replayable_from = int(replay.get("replayableFromSeq") or 0)
                    latest_seq = int(replay.get("latestSeq") or 0)
                    events = replay.get("events") or []
                    if replayable_from > (last_applied + 1):
                        snap = _build_testing_snapshot(repo=repo, projectId=project_id, seq=latest_seq)
                        await _send_text_or_fail(
                            websocket=websocket,
                            text=json.dumps(snap, separators=(",", ":"), ensure_ascii=False),
                            project_id=project_id,
                            tech_token=techToken,
                        )
                        continue
                    await _send_text_or_fail(
                        websocket=websocket,
                        text=json.dumps(
                            {
                                "type": "replay.batch",
                                "projectId": project_id,
                                "afterSeq": last_applied,
                                "latestSeq": latest_seq,
                                "events": events,
                            },
                            separators=(",", ":"),
                            ensure_ascii=False,
                        ),
                        project_id=project_id,
                        tech_token=techToken,
                    )
                    continue
                if msg_type not in ("test_result.submit", "test_result"):
                    await _send_text_or_fail(
                        websocket=websocket,
                        text=json.dumps({"type": "error", "code": "UNKNOWN_MESSAGE"}),
                        project_id=project_id,
                        tech_token=techToken,
                    )
                    continue
                target = payload.get("target") or {}
                outcome = str(payload.get("outcome") or "").strip().upper()
                fail_note = payload.get("failNote")
                if outcome not in ("PASS", "FAIL"):
                    await _send_text_or_fail(
                        websocket=websocket,
                        text=json.dumps({"type": "error", "code": "VALIDATION_ERROR", "message": "Outcome must be PASS or FAIL."}),
                        project_id=project_id,
                        tech_token=techToken,
                    )
                    continue
                if outcome == "FAIL" and not str(fail_note or "").strip():
                    await _send_text_or_fail(
                        websocket=websocket,
                        text=json.dumps({"type": "error", "code": "FAIL_NOTE_REQUIRED", "message": "Fail note is required when outcome is FAIL."}),
                        project_id=project_id,
                        tech_token=techToken,
                    )
                    continue
                try:
                    rec = repo.append_test_result(
                        techToken=techToken,
                        target=target,
                        outcome=outcome,
                        failNote=(str(fail_note).strip() if fail_note is not None else None),
                    )
                except KeyError:
                    await _send_text_or_fail(
                        websocket=websocket,
                        text=json.dumps({"type": "error", "code": "TECH_LINK_REVOKED"}),
                        project_id=project_id,
                        tech_token=techToken,
                    )
                    await websocket.close(code=1008)
                    return
                event = _build_test_result_event(repo=repo, rec=rec)
                published_event = broker.publish(projectId=rec.projectId, event=event)
                if not isinstance(published_event, dict):
                    published_event = dict(event)
                    published_event["seq"] = int(broker.latest_seq(projectId=rec.projectId))
                log.info(
                    "[testing-ws] publish projectId=%s targetKey=%s outcome=%s broker_id=%s",
                    rec.projectId,
                    str(event.get("targetKey") or ""),
                    str(event.get("outcome") or ""),
                    id(broker),
                )
                try:
                    await _send_text_or_fail(
                        websocket=websocket,
                        text=json.dumps(published_event, separators=(",", ":"), ensure_ascii=False),
                        project_id=project_id,
                        tech_token=techToken,
                    )
                except Exception:
                    log.exception("[testing-ws] direct_send_failed techToken=%s", techToken)
            finally:
                recv_ms = (time.perf_counter() - recv_started) * 1000.0
                perf["recv_count"] = int(perf["recv_count"]) + 1
                perf["recv_total_ms"] = float(perf["recv_total_ms"]) + float(recv_ms)
                recv_count = int(perf["recv_count"])
                if recv_ms >= 50.0 or (recv_count % 25 == 0):
                    recv_avg = float(perf["recv_total_ms"]) / max(recv_count, 1)
                    log.info(
                        "[testing-ws] perf kind=recv type=%s recvMs=%.2f recvAvgMs=%.2f recvCount=%s projectId=%s techToken=%s",
                        msg_type or "(unknown)",
                        recv_ms,
                        recv_avg,
                        recv_count,
                        project_id,
                        techToken,
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
    except (WebSocketDisconnect, asyncio.CancelledError):
        log.info("[testing-ws] disconnect techToken=%s", techToken)
    finally:
        send_task.cancel()
        recv_task.cancel()
        await asyncio.gather(send_task, recv_task, return_exceptions=True)
        try:
            broker.unsubscribe(projectId=project_id, q=q)
        except Exception:
            log.exception("[testing-ws] unsubscribe-failed techToken=%s projectId=%s", techToken, project_id)


@router.get("/api/v1/testing/{techToken}/target-status")
def target_status(request: Request, techToken: str, targetKey: str) -> dict:
    try:
        return _repo(request).get_target_status(techToken=techToken, targetKey=targetKey)
    except KeyError:
        raise http_error(410, code="TECH_LINK_REVOKED", message="This technician link has been revoked.")
