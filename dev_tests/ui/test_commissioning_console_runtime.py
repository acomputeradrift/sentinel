import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import re
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import request as urlrequest


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class _StaticServer:
    def __init__(self, directory: Path):
        self._directory = directory
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.base_url: str | None = None

    def start(self) -> None:
        directory = self._directory

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(directory), **kwargs)

            def log_message(self, fmt: str, *args) -> None:
                return

        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        host, port = sock.getsockname()
        sock.close()

        self._httpd = ThreadingHTTPServer((host, port), Handler)
        self.base_url = f"http://{host}:{port}"
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

        deadline = time.time() + 2.0
        while time.time() < deadline:
            try:
                s = socket.create_connection((host, port), timeout=0.2)
                s.close()
                return
            except OSError:
                time.sleep(0.05)
        raise RuntimeError("Static server failed to start.")

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None


class _AppServer:
    def __init__(self, *, generated_root: Path, upload_root: Path):
        self._generated_root = generated_root
        self._upload_root = upload_root
        self._proc: subprocess.Popen[str] | None = None
        self.base_url: str | None = None

    def start(self) -> None:
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        host, port = sock.getsockname()
        sock.close()
        self.base_url = f"http://{host}:{port}"

        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC)
        env["SENTINEL_GENERATED_ROOT"] = str(self._generated_root)
        env["SENTINEL_UPLOAD_ROOT"] = str(self._upload_root)

        self._proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "sentinel.server.app.main:app",
                "--host",
                host,
                "--port",
                str(port),
            ],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )

        deadline = time.time() + 25.0
        while time.time() < deadline:
            if self._proc.poll() is not None:
                raise RuntimeError("App server exited before becoming healthy.")
            try:
                with urlrequest.urlopen(f"{self.base_url}/health", timeout=0.5) as resp:
                    if int(resp.status) == 200:
                        return
            except Exception:
                time.sleep(0.1)
        raise RuntimeError("App server failed health check.")

    def stop(self) -> None:
        if self._proc is None:
            return
        self._proc.terminate()
        try:
            self._proc.wait(timeout=10.0)
        except Exception:
            self._proc.kill()
            self._proc.wait(timeout=5.0)
        self._proc = None


class CommissioningConsoleRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ModuleNotFoundError as e:
            raise unittest.SkipTest(
                "Playwright is not installed in the current Python environment. "
                "Install it in the active venv, e.g. `python -m pip install playwright` "
                "and ensure browsers are available (typically `python -m playwright install chromium`)."
            ) from e

        cls._static = _StaticServer(ROOT)
        cls._static.start()

        cls._pw = sync_playwright().start()
        cls._browser = cls._pw.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls._browser.close()
        finally:
            cls._pw.stop()
            cls._static.stop()

    def test_commissioning_ui_drives_core_mvp_flow(self):
        from playwright.sync_api import expect

        page = self._browser.new_page()
        console_logs: list[str] = []
        page.on("console", lambda msg: console_logs.append(str(msg.text or "")))

        state: dict[str, object] = {
            "clients": [],
            "clients_by_id": {},
            "projects_by_client": {},
            "projects_by_id": {},
            "tech_links_by_project": {},
            "fail_tags_by_target_key": {},
            "last_upload_content_type": None,
            "expected_upload_filename": "TEST - System Manager v11.3.apex",
            "last_upload_body_contains_expected": None,
            "upload_counter": 0,
            "tech_link_counter": 0,
            "tech_link_revoke_counter": 0,
            "progress_fetch_count": 0,
            "fails_fetch_count": 0,
            "rollups_fetch_count": 0,
        }

        def is_blue_rgb(value: str) -> bool:
            match = re.fullmatch(r"rgb\((\d+),\s*(\d+),\s*(\d+)\)", str(value).strip())
            if not match:
                return False
            red, green, blue = (int(part) for part in match.groups())
            return blue > red and blue > green and blue >= 120

        def fulfill_json(route, payload, status: int = 200):
            route.fulfill(
                status=status,
                headers={"Content-Type": "application/json"},
                body=json.dumps(payload),
            )

        def handle_clients(route, request):
            if request.method == "GET":
                fulfill_json(route, state["clients"])
                return
            if request.method == "POST":
                data = json.loads(request.post_data or "{}")
                client = {"clientId": "client-1", "name": data.get("name", ""), "createdAtUtc": "2026-03-21T00:00:00Z"}
                state["clients"] = [client]
                state["clients_by_id"]["client-1"] = client
                state["projects_by_client"]["client-1"] = []
                fulfill_json(route, client)
                return
            route.fulfill(status=405, body="method not allowed")

        def handle_projects_create_and_list(route, request):
            parts = request.url.split("/commissioning/clients/")[-1].split("/projects")
            client_id = parts[0].strip("/")
            if request.method == "GET":
                fulfill_json(route, state["projects_by_client"].get(client_id, []))
                return
            if request.method == "POST":
                data = json.loads(request.post_data or "{}")
                proj = {
                    "projectId": "proj-1",
                    "clientId": client_id,
                    "clientName": state["clients_by_id"].get(client_id, {}).get("name", ""),
                    "name": data.get("name", ""),
                    "createdAtUtc": "2026-03-21T00:00:00Z",
                    "status": "EMPTY",
                    "activeUploadId": None,
                    "activeExtractionRunId": None,
                    "activeGenerationRunId": None,
                    "activeTechLinkIds": [],
                }
                state["projects_by_client"][client_id] = [proj]
                state["projects_by_id"][proj["projectId"]] = proj
                state["tech_links_by_project"][proj["projectId"]] = []
                fulfill_json(route, proj)
                return
            route.fulfill(status=405, body="method not allowed")

        def handle_project_detail(route, request):
            project_id = request.url.split("/commissioning/projects/")[-1].split("?")[0].strip("/")
            if request.method != "GET":
                route.fulfill(status=405, body="method not allowed")
                return
            proj = dict(state["projects_by_id"].get(project_id, {}))
            if not proj:
                route.fulfill(status=404, body="not found")
                return
            active_links = [link for link in state["tech_links_by_project"].get(project_id, []) if not link.get("revokedAtUtc")]
            proj["activeTechLinks"] = active_links
            proj["lastGeneratedFilename"] = state.get("expected_upload_filename")
            fulfill_json(route, proj)

        def handle_upload(route, request):
            headers = {k.lower(): v for k, v in request.headers.items()}
            ct = headers.get("content-type", "")
            state["last_upload_content_type"] = ct
            body = request.post_data_buffer or b""
            expected = str(state.get("expected_upload_filename") or "")
            state["last_upload_body_contains_expected"] = expected.encode("utf-8") in body
            state["upload_counter"] = int(state.get("upload_counter") or 0) + 1
            upload_id = f"upload-{state['upload_counter']}"
            fulfill_json(
                route,
                {
                    "uploadId": upload_id,
                    "projectId": "proj-1",
                    "receivedAtUtc": "2026-03-21T00:00:00Z",
                    "originalFilename": expected,
                    "sha256": "deadbeef",
                    "bytes": len(body),
                    "contentType": "application/octet-stream",
                },
            )

        def handle_regenerate(route, request):
            self.assertEqual(request.method, "POST")
            data = json.loads(request.post_data or "{}")
            self.assertRegex(str(data.get("uploadId") or ""), r"^upload-\d+$")
            fulfill_json(
                route,
                {
                    "projectId": "proj-1",
                    "status": "READY",
                },
            )

        def handle_tech_links(route, request):
            path = request.url.split("?")[0]
            project_id = path.split("/commissioning/projects/")[-1].split("/tech-links")[0].strip("/")

            if request.method == "GET":
                active_links = [link for link in state["tech_links_by_project"].get(project_id, []) if not link.get("revokedAtUtc")]
                fulfill_json(route, active_links)
                return

            if request.method == "POST" and path.endswith("/tech-links"):
                data = json.loads(request.post_data or "{}")
                state["tech_link_counter"] = int(state.get("tech_link_counter") or 0) + 1
                tech_link_id = f"tl-{state['tech_link_counter']}"
                created_at_utc = f"2026-03-21 00:0{state['tech_link_counter']}:00Z"
                link = {
                    "techLinkId": tech_link_id,
                    "label": data.get("label") or "Onsite Tech",
                    "techUrl": "/testing/token-abc",
                    "createdAtUtc": created_at_utc,
                    "revokedAtUtc": None,
                }
                state["tech_links_by_project"].setdefault(project_id, []).append(link)
                proj = state["projects_by_id"].get(project_id)
                if proj is not None:
                    proj["activeTechLinkIds"] = [item["techLinkId"] for item in state["tech_links_by_project"][project_id] if not item.get("revokedAtUtc")]
                fulfill_json(route, {"techLinkId": tech_link_id, "techUrl": link["techUrl"], "label": link["label"]})
                return

            if request.method in {"DELETE", "POST"} and "/tech-links/" in path:
                suffix = path.split("/tech-links/", 1)[1]
                tech_link_id = suffix.split("/")[0]
                links = state["tech_links_by_project"].get(project_id, [])
                for link in links:
                    if link.get("techLinkId") == tech_link_id and not link.get("revokedAtUtc"):
                        state["tech_link_revoke_counter"] = int(state.get("tech_link_revoke_counter") or 0) + 1
                        link["revokedAtUtc"] = f"2026-03-21T00:0{state['tech_link_revoke_counter']}:00Z"
                        break
                proj = state["projects_by_id"].get(project_id)
                if proj is not None:
                    proj["activeTechLinkIds"] = [item["techLinkId"] for item in links if not item.get("revokedAtUtc")]
                route.fulfill(status=204, body="")
                return

            route.fulfill(status=405, body="method not allowed")

        def handle_progress(route, request):
            self.assertEqual(request.method, "GET")
            state["progress_fetch_count"] = int(state.get("progress_fetch_count") or 0) + 1
            fulfill_json(
                route,
                {
                    "projectId": "proj-1",
                    "asOfGenerationRunId": "gen-1",
                    "counts": {"totalTargets": 12, "testedTargets": 3, "pass": 2, "fail": 1, "untested": 9, "percentComplete": 0.25},
                    "lastTestedAtUtc": "2026-03-21T00:00:00Z",
                    "eventSections": {
                        "system": {"counts": {"totalTargets": 4, "testedTargets": 1, "pass": 1, "fail": 0, "untested": 3, "percentComplete": 0.25}, "lastTestedAtUtc": "2026-03-21T00:00:00Z"},
                        "driver": {"counts": {"totalTargets": 4, "testedTargets": 2, "pass": 1, "fail": 1, "untested": 2, "percentComplete": 0.5}, "lastTestedAtUtc": "2026-03-21T00:00:00Z"},
                    },
                    "devices": [
                        {"deviceId": "dev-1", "deviceName": "Device A", "counts": {"totalTargets": 2, "testedTargets": 1, "pass": 1, "fail": 0, "untested": 1, "percentComplete": 0.5}, "lastTestedAtUtc": "2026-03-21T00:00:00Z"},
                        {"deviceId": "dev-2", "deviceName": "Device B", "counts": {"totalTargets": 0, "testedTargets": 0, "pass": 0, "fail": 0, "untested": 0, "percentComplete": 0.0}, "lastTestedAtUtc": None},
                    ],
                },
            )

        def handle_fails(route, request):
            self.assertEqual(request.method, "GET")
            state["fails_fetch_count"] = int(state.get("fails_fetch_count") or 0) + 1
            tags_by_key = state.get("fail_tags_by_target_key") or {}
            fulfill_json(
                route,
                [
                    {
                        "targetKey": "btn:81:513:48551:Macro",
                        "targetName": "Macro",
                        "deviceName": "Device A",
                        "pageName": "Home",
                        "buttonName": "Button 1",
                        "scope": "BUTTON",
                        "tag": tags_by_key.get("btn:81:513:48551:Macro", "NOT_STARTED"),
                        "currentOutcome": "FAIL",
                        "lastTestedAtUtc": "2026-03-21T00:00:00Z",
                        "lastFailNote": "Macro did not run",
                        "resolvedData": {"reason": "Macro did not run"},
                        "recordedBy": {"role": "TECHNICIAN", "actorId": None},
                    },
                    {
                        "targetKey": "event:126:Trigger",
                        "targetName": "Trigger",
                        "deviceName": "Device B",
                        "pageName": "Scene",
                        "buttonName": "",
                        "scope": "EVENT_SECTION",
                        "tag": tags_by_key.get("event:126:Trigger", "NOT_STARTED"),
                        "currentOutcome": "FAIL",
                        "lastTestedAtUtc": "2026-03-20T23:00:00Z",
                        "lastFailNote": "Trigger not firing",
                        "resolvedData": {"reason": "Trigger not firing"},
                        "recordedBy": {"role": "TECHNICIAN", "actorId": None},
                    },
                ],
            )

        def handle_rollups(route, request):
            self.assertEqual(request.method, "GET")
            state["rollups_fetch_count"] = int(state.get("rollups_fetch_count") or 0) + 1
            fulfill_json(
                route,
                {
                    "projectId": "proj-1",
                    "counts": {"totalTargets": 12, "firstTimeFailTargets": 2},
                    "currentFailures": {"byTargetName": {"macro": 1, "trigger": 1}},
                },
            )

        def handle_fail_tags(route, request):
            self.assertEqual(request.method, "PUT")
            data = json.loads(request.post_data or "{}")
            target_key = str(data.get("targetKey") or "")
            tag = str(data.get("tag") or "")
            state["fail_tags_by_target_key"][target_key] = tag
            fulfill_json(route, {"projectId": "proj-1", "targetKey": target_key, "tag": tag})

        page.route("**/api/v1/commissioning/clients", handle_clients)
        page.route("**/api/v1/commissioning/clients/*/projects", handle_projects_create_and_list)
        page.route("**/api/v1/commissioning/projects/*", handle_project_detail)
        page.route("**/api/v1/commissioning/projects/*/uploads", handle_upload)
        page.route("**/api/v1/commissioning/projects/*/regenerate", handle_regenerate)
        page.route("**/api/v1/commissioning/projects/*/tech-links**", handle_tech_links)
        page.route("**/api/v1/commissioning/projects/*/progress", handle_progress)
        page.route("**/api/v1/commissioning/projects/*/fails", handle_fails)
        page.route("**/api/v1/commissioning/projects/*/rollups", handle_rollups)
        page.route("**/api/v1/commissioning/projects/*/fail-tags", handle_fail_tags)

        url = f"{self._static.base_url}/src/sentinel/ui/commissioning/index.html"
        page.add_init_script(
            """
(() => {
  let wsConnectCount = 0;
  let wsCloseCount = 0;
  const wsPeers = new Set();
  class FakeWebSocket {
    constructor(url) {
      this.url = url;
      this.readyState = 0;
      wsPeers.add(this);
      wsConnectCount += 1;
      setTimeout(() => {
        this.readyState = 1;
        if (this.onopen) this.onopen({});
        setTimeout(() => {
          const messages = [
            {
              type: "commissioning_snapshot",
              projectId: "proj-1",
              activeUpload: null,
              progress: {
                projectId: "proj-1",
                asOfGenerationRunId: "gen-1",
                counts: { totalTargets: 12, testedTargets: 3, pass: 2, fail: 1, untested: 9, percentComplete: 0.25 },
                lastTestedAtUtc: "2026-03-21T00:00:00Z",
                eventSections: {
                  system: { counts: { totalTargets: 4, testedTargets: 1, pass: 1, fail: 0, untested: 3, percentComplete: 0.25 }, lastTestedAtUtc: "2026-03-21T00:00:00Z" },
                  driver: { counts: { totalTargets: 4, testedTargets: 2, pass: 1, fail: 1, untested: 2, percentComplete: 0.5 }, lastTestedAtUtc: "2026-03-21T00:00:00Z" },
                },
                devices: [
                  { deviceId: "dev-1", deviceName: "Device A", counts: { totalTargets: 2, testedTargets: 1, pass: 1, fail: 0, untested: 1, percentComplete: 0.5 }, lastTestedAtUtc: "2026-03-21T00:00:00Z" },
                  { deviceId: "dev-2", deviceName: "Device B", counts: { totalTargets: 0, testedTargets: 0, pass: 0, fail: 0, untested: 0, percentComplete: 0.0 }, lastTestedAtUtc: null },
                ],
              },
              rollups: {
                projectId: "proj-1",
                counts: { totalTargets: 12, firstTimeFailTargets: 2 },
                currentFailures: { byTargetName: { macro: 1, trigger: 1 } },
              },
              fails: [
                {
                  targetKey: "tt2:2:ROOM:23:74:20:macro:3122:Macro",
                  targetName: "Macro",
                  deviceName: "Device A",
                  pageName: "Home",
                  layerName: "Layer Alpha",
                  viewport: "No",
                  buttonName: "Button 1",
                  scope: "BUTTON",
                  scopeType: "ROOM",
                  effectiveRoomId: 23,
                  effectiveSourceId: 74,
                  effectiveRoomName: "Living Room",
                  effectiveSourceName: "Main AVR",
                  effectiveScopeNames: "Living Room -> Main AVR",
                  techName: "Taylor",
                  tag: "NOT_STARTED",
                  currentOutcome: "FAIL",
                  lastTestedAtUtc: "2026-03-21T00:00:00Z",
                  lastFailNote: "Macro did not run",
                  resolvedData: { reason: "Macro did not run" }
                },
                {
                  targetKey: "btn:81:513:48551:PageLink",
                  targetName: "PageLink",
                  deviceName: "Device B",
                  pageName: "Scene",
                  layerName: "Layer Beta",
                  viewport: "Frame 2",
                  buttonName: "",
                  scope: "BUTTON",
                  scopeType: "GLOBAL",
                  effectiveRoomId: 0,
                  effectiveSourceId: 74,
                  effectiveRoomName: "Global",
                  effectiveSourceName: "Main AVR",
                  effectiveScopeNames: "Global -> Main AVR",
                  techName: "Morgan",
                  tag: "NOT_STARTED",
                  currentOutcome: "FAIL",
                  lastTestedAtUtc: "2026-03-20T23:00:00Z",
                  lastFailNote: "Page link broken",
                  resolvedData: { reason: "Page link broken" }
                },
                {
                  targetKey: "btn:81:700:48552:Icon",
                  targetName: "Wrong Icon",
                  deviceName: "IST-5 (Global)",
                  pageName: "Sound",
                  layerName: "SOURCE - Set To CABLE MUSIC",
                  viewport: "icon",
                  buttonName: "Room 4 -> 1",
                  scope: "BUTTON",
                  scopeType: "",
                  effectiveRoomId: null,
                  effectiveSourceId: null,
                  effectiveRoomName: "",
                  effectiveSourceName: "",
                  techName: "Alex",
                  tag: "NOT_STARTED",
                  currentOutcome: "FAIL",
                  lastTestedAtUtc: "2026-03-20T22:00:00Z",
                  lastFailNote: "",
                  resolvedData: { reason: "Wrong Icon" }
                },
              ],
              activities: [],
            },
            {
              type: "test_result.recorded",
              projectId: "proj-1",
              recordedAtUtc: "2026-03-21T00:00:01Z",
              targetKey: "btn:99:1:2:New Button",
              outcome: "PASS",
              targetName: "New Button",
              kind: "BUTTON",
              refs: { deviceName: "Device A", pageName: "Home", buttonName: "Button 2", scope: "BUTTON" },
              progress: {
                projectId: "proj-1",
                asOfGenerationRunId: "gen-1",
                counts: { totalTargets: 12, testedTargets: 4, pass: 3, fail: 1, untested: 8, percentComplete: 0.3333 },
                lastTestedAtUtc: "2026-03-21T00:00:01Z",
                eventSections: {
                  system: { counts: { totalTargets: 4, testedTargets: 2, pass: 2, fail: 0, untested: 2, percentComplete: 0.5 }, lastTestedAtUtc: "2026-03-21T00:00:01Z" },
                  driver: { counts: { totalTargets: 4, testedTargets: 2, pass: 1, fail: 1, untested: 2, percentComplete: 0.5 }, lastTestedAtUtc: "2026-03-21T00:00:01Z" },
                },
                devices: [
                  { deviceId: "dev-1", deviceName: "Device A", counts: { totalTargets: 2, testedTargets: 2, pass: 2, fail: 0, untested: 0, percentComplete: 1.0 }, lastTestedAtUtc: "2026-03-21T00:00:01Z" },
                  { deviceId: "dev-2", deviceName: "Device B", counts: { totalTargets: 0, testedTargets: 0, pass: 0, fail: 0, untested: 0, percentComplete: 0.0 }, lastTestedAtUtc: null },
                ],
              },
            },
            {
              type: "test_result.recorded",
              projectId: "proj-1",
              recordedAtUtc: "2026-03-21T00:00:03Z",
              targetKey: "tt2:2:GLOBAL:0:88:20:macro:4000:Fail Button",
              outcome: "FAIL",
              targetName: "Fail Button",
              kind: "BUTTON",
              failNote: "Button does not respond",
              refs: {
                deviceName: "Device B",
                pageName: "Scene",
                layerName: "Layer Gamma",
                viewport: "No",
                buttonName: "Button 9",
                scope: "BUTTON",
                scopeType: "GLOBAL",
                effectiveRoomId: 0,
                effectiveSourceId: 88,
                effectiveRoomName: "Global",
                effectiveSourceName: "Lighting Processor"
                ,effectiveScopeNames: "Global -> Lighting Processor",
                techName: "Jordan"
              },
              progress: {
                projectId: "proj-1",
                asOfGenerationRunId: "gen-1",
                counts: { totalTargets: 12, testedTargets: 5, pass: 3, fail: 2, untested: 7, percentComplete: 0.4167 },
                lastTestedAtUtc: "2026-03-21T00:00:03Z",
                eventSections: {
                  system: { counts: { totalTargets: 4, testedTargets: 2, pass: 2, fail: 0, untested: 2, percentComplete: 0.5 }, lastTestedAtUtc: "2026-03-21T00:00:03Z" },
                  driver: { counts: { totalTargets: 4, testedTargets: 3, pass: 1, fail: 2, untested: 1, percentComplete: 0.75 }, lastTestedAtUtc: "2026-03-21T00:00:03Z" },
                },
                devices: [
                  { deviceId: "dev-1", deviceName: "Device A", counts: { totalTargets: 2, testedTargets: 2, pass: 2, fail: 0, untested: 0, percentComplete: 1.0 }, lastTestedAtUtc: "2026-03-21T00:00:03Z" },
                  { deviceId: "dev-2", deviceName: "Device B", counts: { totalTargets: 0, testedTargets: 0, pass: 0, fail: 0, untested: 0, percentComplete: 0.0 }, lastTestedAtUtc: null },
                ],
              },
              rollups: {
                counts: { totalTargets: 12, firstTimeFailTargets: 3 },
                currentFailures: { byTargetName: { "Fail Button": 1 } },
              },
            },
          ];
          let idx = 0;
          const emit = () => {
            if (idx >= messages.length) return;
            if (this.onmessage) this.onmessage({ data: JSON.stringify(messages[idx]) });
            idx += 1;
            if (idx < messages.length) setTimeout(emit, 25);
          };
          emit();
        }, 25);
      }, 0);
    }
    send(_data) {}
    close() {
      this.readyState = 3;
      wsPeers.delete(this);
      wsCloseCount += 1;
      if (this.onclose) this.onclose({});
    }
  }
  window.__broadcastWsEvent = (payload) => {
    for (const ws of wsPeers) {
      try {
        if (ws.readyState === 1 && ws.onmessage) ws.onmessage({ data: JSON.stringify(payload) });
      } catch (_e) {}
    }
  };
  const originalOpen = XMLHttpRequest.prototype.open;
  const originalSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(method, url, ...rest) {
    this.__sentinelUrl = String(url || "");
    return originalOpen.call(this, method, url, ...rest);
  };
  XMLHttpRequest.prototype.send = function(body) {
    this.addEventListener("load", () => {
      const url = String(this.__sentinelUrl || "");
      if (!url.includes("/commissioning/projects/") || !url.includes("/upload")) return;
      let parsed = {};
      try {
        parsed = JSON.parse(String(this.responseText || "{}"));
      } catch (_e) {
        return;
      }
      const projectId = String(parsed.projectId || "proj-1");
      const uploadId = String(parsed.uploadId || "");
      const originalFilename = String(parsed.originalFilename || "");
      window.__broadcastWsEvent({
        type: "generation",
        status: "READY",
        projectId,
        uploadId,
        originalFilename,
        activeUpload: {
          uploadId,
          projectId,
          originalFilename,
          storagePath: String(parsed.storagePath || ""),
          uploadedAtUtc: "2026-03-21T00:00:00Z",
        },
      });
    });
    return originalSend.call(this, body);
  };
  window.__wsConnectCount = () => wsConnectCount;
  window.__wsCloseCount = () => wsCloseCount;
  window.WebSocket = FakeWebSocket;
})();
"""
        )
        page.goto(url)
        self.assertTrue(
            page.evaluate(
                "(() => !!(window.__sentinelProjectWsManager && typeof window.__sentinelProjectWsManager.dispatchIncoming === 'function'))()"
            )
        )
        self.assertTrue(
            page.evaluate(
                "(() => !!(window.__sentinelProjectStore && typeof window.__sentinelProjectStore.getState === 'function' && typeof window.__sentinelProjectStore.dispatch === 'function'))()"
            )
        )

        # Shell + tabs
        expect(page.get_by_role("button", name="Projects")).to_be_visible()
        expect(page.get_by_role("button", name="Commission")).to_be_visible()
        expect(page.get_by_role("button", name="Diagnostics")).to_be_visible()
        expect(page.get_by_role("button", name=re.compile("refresh", re.I))).to_have_count(0)
        expect(page.get_by_role("heading", name="Sentinel Console")).to_be_visible()
        expect(page.locator("#panel-commission")).to_be_visible()
        expect(page.locator("#panel-manage")).to_be_hidden()
        expect(page.locator("#manageClientCard")).to_be_hidden()
        expect(page.locator("#manageProjectCard")).to_be_hidden()
        expect(page.locator("#manageProjectDetails")).to_be_hidden()

        # Manage must not render Progress/Fails sections.
        expect(page.locator("#panel-manage [data-testid='progress']")).to_have_count(0)
        expect(page.locator("#panel-manage [data-testid='fails-count']")).to_have_count(0)
        expect(page.locator("#panel-manage [data-testid='fails-list']")).to_have_count(0)
        expect(page.locator("#newClientName")).to_have_attribute("placeholder", "Enter here...")
        expect(page.locator("#newProjectName")).to_have_attribute("placeholder", "Enter here...")

        page.get_by_role("button", name="Projects").click()
        expect(page.locator("#panel-manage")).to_be_visible()

        page.get_by_label("New client name").fill("Client A")
        page.get_by_role("button", name="Create client").click()
        expect(page.get_by_label("Client", exact=True)).to_have_value("client-1")
        expect(page.get_by_label("New client name")).to_have_value("")
        expect(page.locator("#manageProjectCard")).to_be_visible()
        expect(page.locator("#manageProjectDetails")).to_be_hidden()

        page.get_by_label("New project name").fill("Project 1")
        page.get_by_role("button", name="Create project").click()
        expect(page.get_by_label("Project", exact=True)).to_have_value("proj-1")
        expect(page.get_by_label("New project name")).to_have_value("")
        expect(page.locator("#manageProjectDetails")).to_be_visible()
        expect(page.locator("#panel-manage")).to_contain_text("Current File")
        expect(page.locator("#panel-manage")).to_contain_text("Current Tech Links")
        expect(page.locator("#manageProjectDetails h3", has_text="Upload + Generate")).to_have_count(0)
        expect(page.locator("#manageProjectDetails span", has_text=".apex file")).to_have_count(0)
        expect(page.locator("#clientStatus")).to_have_count(0)
        expect(page.locator("#projectStatus")).to_have_count(0)
        expect(page.locator("#regenProgress")).to_have_count(0)
        expect(page.locator("#regenProgressLabel")).to_have_count(0)
        expect(page.locator("#regenStatus")).to_have_count(0)
        expect(page.locator("#lastGeneratedLabel")).to_have_text("None")
        self.assertLessEqual(page.locator("#manageProjectDetails").evaluate("el => parseFloat(getComputedStyle(el).marginTop)"), 12)
        self.assertIn(
            page.locator("#manageProjectDetails").evaluate("el => getComputedStyle(el).borderTopStyle"),
            ("none", "hidden"),
        )

        apex_path = ROOT / "Assets" / "TEST - System Manager v11.3.apex"
        self.assertTrue(apex_path.exists(), f"Missing apex fixture: {apex_path}")
        page.set_input_files("input[type=file][name=apex]", str(apex_path))
        page.get_by_role("button", name="Load File").click()
        expect(page.get_by_test_id("upload-status")).to_contain_text("upload-1")
        expect(page.locator("#uploadProgressLabel")).to_have_count(1)
        self.assertEqual(page.locator("#uploadProgress").evaluate("el => Number(el.value)"), 100)
        expect(page.locator("#lastGeneratedLabel")).to_have_text(apex_path.name)
        self.assertIsNotNone(state["last_upload_content_type"])
        self.assertIn("multipart/form-data", str(state["last_upload_content_type"]))
        self.assertEqual(state["last_upload_body_contains_expected"], True)

        expect(page.get_by_role("button", name="Regenerate")).to_have_count(0)

        page.get_by_label("Tech label").fill("   ")
        page.get_by_role("button", name="Create tech link").click()
        expect(page.locator("#techLinkStatus")).to_contain_text("Tech label is required.")
        self.assertEqual(int(state.get("tech_link_counter") or 0), 0)
        page.get_by_label("Tech label").fill("Onsite Tech")
        expect(page.get_by_role("button", name="Create tech link")).to_be_enabled()
        page.get_by_role("button", name="Create tech link").click()
        expect(page.get_by_test_id("tech-url")).to_contain_text("/testing/token-abc?runtime=payload")
        with page.expect_popup() as open_popup_info:
            page.get_by_role("button", name="Open").click()
        open_popup = open_popup_info.value
        self.assertIn("/testing/token-abc?runtime=payload", str(open_popup.url))
        open_popup.close()
        expect(page.get_by_role("button", name="Legacy")).to_have_count(0)
        row_actions = page.locator("#techLinksBody tr").first.locator("td").nth(2).locator("button")
        expect(row_actions).to_have_count(2)
        expect(row_actions.nth(0)).to_have_text("Open")
        expect(row_actions.nth(1)).to_have_text("Revoke")
        expect(page.locator("#panel-manage")).to_contain_text("Onsite Tech")
        expect(page.locator("#panel-manage")).to_contain_text(re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}Z"))
        expect(page.get_by_role("button", name="Revoke")).to_be_visible()
        page.get_by_role("button", name="Revoke").click()
        expect(page.locator("#panel-manage")).not_to_contain_text("Onsite Tech")

        # Tab switching
        page.get_by_role("button", name="Commission").click()
        expect(page.locator("#panel-commission")).to_be_visible()
        expect(page.locator("#commissionSelection")).to_have_count(0)
        expect(page.locator("[data-testid='commission-selected-client']")).to_have_count(0)
        expect(page.locator("[data-testid='commission-selected-project']")).to_have_count(0)
        expect(page.locator("[data-testid='commission-client-project-line']")).to_have_count(0)
        expect(page.locator("#commissionTopline")).to_have_count(0)
        expect(page.locator("#panel-commission .panel-context-title")).to_contain_text("Client A -> Project 1 -> TEST - System Manager v11.3.apex")
        expect(page.locator("#commissionKpiComplete")).to_have_count(0)
        expect(page.locator("#commissionKpiTested")).to_have_count(0)
        expect(page.locator("#commissionKpiUntested")).to_have_count(0)
        expect(page.locator("[data-testid='commission-pie-project'], [data-testid='commission-pie-system-events'], [data-testid='commission-pie-driver-events']")).to_have_count(3)
        expect(page.locator("#commissionPies")).not_to_contain_text("Device 1")
        expect(page.locator("#commissionPies")).not_to_contain_text("Device 2")
        expect(page.locator("#commissionPies")).not_to_contain_text("Device 3")
        expect(page.get_by_test_id("commission-pie-project")).to_contain_text(re.compile(r"\d+/12 tested"))
        expect(page.locator("#commissionPie-project .piecard-count")).to_have_text("3/12")
        expect(page.locator("#commissionPie-system-events .piecard-count")).to_have_text("2/4")
        expect(page.locator("#commissionPie-driver-events .piecard-count")).to_have_text("1/4")
        expect(page.locator("[data-testid^='commission-pie-device-']")).to_have_count(1)
        expect(page.get_by_test_id("commission-pie-device-dev-1")).to_be_visible()
        expect(page.locator("[data-testid='commission-pie-device-dev-2']")).to_have_count(0)
        expect(page.locator("#commissionActivityBody tr")).to_have_count(2)
        expect(page.locator("#commissionActivityBody")).to_contain_text("Device A")
        expect(page.locator("#commissionActivityBody")).to_contain_text("Home")
        expect(page.locator("#commissionActivityBody")).to_contain_text("Button 2")
        expect(page.locator("#commissionActivityBody")).to_contain_text("New Button")
        expect(page.locator("#commissionActivityBody")).to_contain_text("Pass")
        expect(page.locator("#commissionActivityBody")).to_contain_text("Fail")
        expect(page.locator("#commissionActivityBody tr").first.locator("td").nth(0)).to_contain_text(re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$"))
        expect(page.locator("#commissionActivityBody tr").first.locator("td").nth(3)).to_contain_text("Layer Gamma")
        expect(page.locator("#commissionActivityBody tr").first.locator("td").nth(4)).to_contain_text("No")
        expect(page.locator("#commissionActivityBody tr").first.locator("td").nth(7)).to_contain_text("Fail")
        page.get_by_role("columnheader", name="Device").click()
        expect(page.locator("#commissionActivityBody tr").first.locator("td").nth(1)).to_contain_text("Device A")
        page.get_by_role("columnheader", name="Device").click()
        expect(page.locator("#commissionActivityBody tr").first.locator("td").nth(1)).to_contain_text("Device B")
        expect(page.get_by_test_id("commission-pie-project")).to_contain_text("3/12")
        expect(page.get_by_test_id("commission-pie-system-events")).to_contain_text("2/4")
        expect(page.get_by_test_id("commission-pie-driver-events")).to_contain_text("1/4")
        page.evaluate(
            """
() => {
  if (!window.__sentinelProjectWsManager || typeof window.__sentinelProjectWsManager.dispatchIncoming !== "function") return;
  window.__sentinelProjectWsManager.dispatchIncoming({
    type: "test_result.recorded",
    projectId: "proj-1",
    recordedAtUtc: "2026-03-21T00:00:04Z",
    targetKey: "btn:101:1:2:Store Driven",
    outcome: "PASS",
    targetName: "Store Driven",
    kind: "BUTTON",
    refs: { deviceName: "Device A", pageName: "Home", buttonName: "Button X", scope: "BUTTON" },
  });
}
"""
        )
        expect(page.locator("#commissionActivityBody")).to_contain_text("Store Driven")
        page.evaluate(
            """
() => {
  if (!window.__sentinelProjectWsManager || typeof window.__sentinelProjectWsManager.dispatchIncoming !== "function") return;
  window.__sentinelProjectWsManager.dispatchIncoming({
    type: "test_result.recorded",
    projectId: "proj-1",
    recordedAtUtc: "2026-03-21T00:00:05Z",
    targetKey: "btn:101:1:2:Zero Case",
    outcome: "PASS",
    targetName: "Zero Case",
    kind: "BUTTON",
    refs: { deviceName: "Device A", pageName: "Home", buttonName: "Button Z", scope: "BUTTON" },
    progress: {
      projectId: "proj-1",
      asOfGenerationRunId: "gen-1",
      counts: { totalTargets: 12, testedTargets: 6, pass: 4, fail: 2, untested: 6, percentComplete: 0.5 },
      lastTestedAtUtc: "2026-03-21T00:00:05Z",
      eventSections: {
        system: { counts: { totalTargets: 0, testedTargets: 0, pass: 0, fail: 0, untested: 0, percentComplete: 0.0 }, lastTestedAtUtc: null },
        driver: { counts: { totalTargets: 0, testedTargets: 0, pass: 0, fail: 0, untested: 0, percentComplete: 0.0 }, lastTestedAtUtc: null },
      },
      devices: [
        { deviceId: "dev-1", deviceName: "Device A", counts: { totalTargets: 2, testedTargets: 2, pass: 2, fail: 0, untested: 0, percentComplete: 1.0 }, lastTestedAtUtc: "2026-03-21T00:00:05Z" }
      ],
    },
  });
}
"""
        )
        expect(page.locator("#commissionPie-system-events .pie")).to_have_attribute("data-center", "None")
        expect(page.locator("#commissionPie-driver-events .pie")).to_have_attribute("data-center", "None")
        self.assertEqual(
            page.evaluate(
                """
(() => {
  const store = window.__sentinelProjectStore;
  if (!store || typeof store.getState !== "function") return -1;
  const state = store.getState();
  const project = state && state.projects ? state.projects["proj-1"] : null;
  return project && Array.isArray(project.activities) ? project.activities.length : -1;
})()
"""
            ),
            4,
        )

        static_diag_structure = page.evaluate(
            """() => Array.from(document.querySelectorAll("#diagnosticsSummary > *"))
              .map((el) => ({ tag: el.tagName, cls: el.className }))"""
        )

        page.get_by_role("button", name="Diagnostics").click()
        expect(page.locator("#panel-diagnostics")).to_be_visible()
        expect(page.locator("#panel-diagnostics .panel-context-title")).to_contain_text("Client A -> Project 1 -> TEST - System Manager v11.3.apex")
        expect(page.locator("[data-testid='diagnostics-pie-failure-rate'], [data-testid='diagnostics-pie-failure-types'], [data-testid='diagnostics-pie-task-completion']")).to_have_count(3)
        expect(page.get_by_test_id("diagnostics-summary-block")).to_have_count(0)
        expect(page.locator("#diagnosticsSummary .diag-center-label")).to_have_count(0)
        expect(page.locator("[data-testid='diagnostics-pie-failure-rate'] .pie")).to_have_attribute("data-center", "50%")
        expect(page.locator("[data-testid='diagnostics-pie-failure-types'] .pie")).to_have_attribute("data-center", "")
        expect(page.locator("[data-testid='diagnostics-pie-task-completion'] .pie")).to_have_attribute("data-center", "0%")
        expect(page.locator("[data-testid='diagnostics-pie-failure-rate'] .piecard-count")).to_have_text("6/12")
        expect(page.locator("[data-testid='diagnostics-pie-failure-types'] .piecard-count")).to_have_text("4/6")
        expect(page.locator("[data-testid='diagnostics-pie-task-completion'] .piecard-count")).to_have_text("0/4")
        self.assertEqual(
            page.evaluate(
                """() => Array.from(document.querySelectorAll("#diagnosticsSummary > *"))
                  .map((el) => ({ tag: el.tagName, cls: el.className }))"""
            ),
            static_diag_structure,
        )
        expect(page.get_by_role("columnheader", name="Status")).to_be_visible()
        expect(page.get_by_role("columnheader", name="Timestamp")).to_be_visible()
        expect(page.get_by_role("columnheader", name="Device")).to_be_visible()
        expect(page.get_by_role("columnheader", name="Page Name")).to_be_visible()
        expect(page.get_by_role("columnheader", name="Layer")).to_be_visible()
        expect(page.get_by_role("columnheader", name="Viewport")).to_be_visible()
        expect(page.get_by_role("columnheader", name="Button Identity")).to_be_visible()
        expect(page.get_by_role("columnheader", name="Test Target")).to_be_visible()
        expect(page.get_by_role("columnheader", name="Effective Scope")).to_be_visible()
        expect(page.get_by_role("columnheader", name="Tech Notes")).to_be_visible()
        diag_headers = page.evaluate(
            """() => Array.from(document.querySelectorAll("#diagnosticsTaskTable thead th"))
              .map((th) => String(th.textContent || "").trim())"""
        )
        self.assertEqual(
            diag_headers,
            [
                "Status",
                "Timestamp",
                "Device",
                "Page Name",
                "Layer",
                "Viewport",
                "Button Identity",
                "Test Target",
                "Effective Scope",
                "Tech Notes",
            ],
        )
        diag_header_bg = page.locator("#diagnosticsTaskTable th").first.evaluate("el => getComputedStyle(el).backgroundColor")
        self.assertTrue(is_blue_rgb(diag_header_bg), diag_header_bg)
        diag_timestamp_text = page.locator("#diagnosticsTaskTable tbody tr").first.locator("td").nth(1).inner_text()
        self.assertRegex(diag_timestamp_text, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
        expect(page.locator("#diagnosticsTaskTable tbody tr")).to_have_count(4)
        expect(page.locator("#diagnosticsTaskTable tbody")).to_contain_text(re.compile(r"fail button", re.I))
        expect(page.locator("#diagnosticsTaskTable tbody")).to_contain_text("Layer Gamma")
        expect(page.locator("#diagnosticsTaskTable tbody")).to_contain_text("Frame 2")
        expect(page.locator("#diagnosticsTaskTable tbody")).to_contain_text("No")
        expect(page.locator("#diagnosticsTaskTable tbody")).to_contain_text("SOURCE - Set To CABLE MUSIC")
        expect(page.locator("#diagnosticsTaskTable tbody")).to_contain_text("icon")
        expect(page.locator("#diagnosticsTaskTable tbody")).to_contain_text("wrong icon")
        expect(page.locator("#diagnosticsTaskTable tbody")).to_contain_text("Living Room -> Main AVR")
        expect(page.locator("#diagnosticsTaskTable tbody")).to_contain_text("Global -> Lighting Processor")
        expect(page.locator("#diagnosticsTaskTable tbody")).to_contain_text("Global")
        expect(page.locator("#diagnosticsTaskTable tbody tr").first.locator("td").nth(8)).to_contain_text("Global")
        expect(page.locator("#diagnosticsTaskTable tbody tr").first.locator("td").nth(9).get_by_role("button", name="Show")).to_be_visible()
        expect(page.locator("#diagnosticsTaskTable tbody tr").first.locator("td").nth(0).locator("select")).to_have_class(re.compile(r"status-template-select"))
        expect(page.get_by_test_id("diagnostics-pie-failure-types")).to_contain_text("macros")
        expect(page.get_by_test_id("diagnostics-pie-failure-types")).to_contain_text("pageLink")
        expect(page.get_by_test_id("diagnostics-pie-failure-types")).to_contain_text("text")
        expect(page.get_by_test_id("diagnostics-pie-failure-rate")).to_contain_text("Fail (3")
        expect(page.get_by_test_id("diagnostics-pie-failure-rate")).to_contain_text("Pass (3")
        expect(page.get_by_test_id("diagnostics-pie-task-completion")).to_contain_text("Not Started (4")
        expect(page.get_by_test_id("diagnostics-pie-task-completion")).to_contain_text("In Progress (0")
        expect(page.get_by_test_id("diagnostics-pie-task-completion")).to_contain_text("Complete (0")

        page.locator("#diagnosticsTaskTable tbody tr").first.locator("td").nth(9).get_by_role("button", name="Show").click()
        expect(page.get_by_role("dialog", name="Tech Notes")).to_be_visible()
        expect(page.get_by_test_id("tech-notes-content")).to_contain_text('Jordan says: "Button does not respond."')
        page.keyboard.press("Escape")
        expect(page.get_by_role("dialog", name="Tech Notes")).to_have_count(0)

        first_tag = page.locator("#diagnosticsTaskTable tbody tr").first.locator("select")
        first_tag.select_option(label="Complete")
        expect(page.get_by_test_id("diagnostics-pie-task-completion")).to_contain_text("Complete (1")

        page.get_by_role("columnheader", name="Status").click()
        expect(page.locator("#diagnosticsTaskTable tbody tr").first.locator("td").nth(0).locator("select")).to_have_value("Not Started")
        page.get_by_role("columnheader", name="Status").click()
        expect(page.locator("#diagnosticsTaskTable tbody tr").first.locator("td").nth(0).locator("select")).to_have_value("Complete")

        page.get_by_role("button", name="Commission").click()
        expect(page.locator("#panel-commission")).to_be_visible()
        self.assertEqual(page.evaluate("window.__wsConnectCount()"), 1)
        self.assertEqual(page.evaluate("window.__wsCloseCount()"), 0)

        page.get_by_role("button", name="Projects").click()
        expect(page.locator("#panel-manage")).to_be_visible()

        # Tab switches inside same project should not force diagnostics consumer close churn.
        self.assertFalse(
            any("[diagnostics-ws] close" in line for line in console_logs),
            f"Unexpected diagnostics close log in same-project tab movement: {console_logs}",
        )
        self.assertTrue(
            any("WS-INFO-100 SOCKET_OPEN" in line for line in console_logs),
            f"Expected readable WS open code in console logs: {console_logs}",
        )
        self.assertFalse(
            any("WS-ERR-310 SOCKET_CLOSE_UNEXPECTED" in line for line in console_logs),
            f"Unexpected close code seen in console logs: {console_logs}",
        )
        diag_connect_attempts = [
            line
            for line in console_logs
            if "WS-INFO-103 CONNECT_ATTEMPT [diagnostics-ws]" in line
        ]
        self.assertLessEqual(
            len(diag_connect_attempts),
            1,
            f"Expected single diagnostics connect attempt on initial stable project load: {console_logs}",
        )

        # Upload a completely different file name (should warn).
        with tempfile.TemporaryDirectory() as td:
            other_path = Path(td) / "Completely Different Project v1.0.apex"
            other_path.write_bytes(apex_path.read_bytes())
            state["expected_upload_filename"] = other_path.name
            page.set_input_files("input[type=file][name=apex]", str(other_path))
            page.get_by_role("button", name="Load File").click()
            expect(page.get_by_test_id("upload-status")).to_contain_text("upload-2")

        self.assertEqual(state.get("progress_fetch_count"), 0)
        self.assertEqual(state.get("fails_fetch_count"), 0)
        self.assertEqual(state.get("rollups_fetch_count"), 0)

        page.close()

    def test_live_smoke_real_asset_no_unexpected_ws_disconnects(self):
        from playwright.sync_api import expect

        try:
            import websockets  # noqa: F401
        except Exception as e:
            raise unittest.SkipTest("websockets runtime is not installed in this environment") from e

        apex_path = ROOT / "Assets" / "TEST - System Manager v11.3.apex"
        if not apex_path.exists():
            raise unittest.SkipTest(f"Missing apex fixture: {apex_path}")

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            app_server = _AppServer(generated_root=(tmp / "generated"), upload_root=(tmp / "uploads"))
            app_server.start()
            try:
                base_url = str(app_server.base_url or "").rstrip("/")
                page = self._browser.new_page()
                console_logs: list[str] = []
                page.on("console", lambda msg: console_logs.append(str(msg.text or "")))

                page.goto(f"{base_url}/commissioning/index.html")
                page.get_by_role("button", name="Projects").click()
                page.get_by_label("New client name").fill("Live Client")
                page.get_by_role("button", name="Create client").click()
                page.get_by_label("New project name").fill("Live Project")
                page.get_by_role("button", name="Create project").click()
                expect(page.get_by_label("Project", exact=True)).not_to_have_value("")

                project_id = str(page.locator("#projectSelect").input_value() or "").strip()
                self.assertTrue(project_id, "Expected selected project id.")

                page.set_input_files("input[type=file][name=apex]", str(apex_path))
                page.get_by_role("button", name="Load File").click()
                expect(page.get_by_test_id("upload-status")).to_contain_text("Uploaded", timeout=120000)
                expect(page.get_by_test_id("upload-status")).to_contain_text(apex_path.name, timeout=120000)

                page.get_by_role("button", name="Commission").click()
                expect(page.locator("#panel-commission")).to_be_visible()
                page.get_by_role("button", name="Diagnostics").click()
                expect(page.locator("#panel-diagnostics")).to_be_visible()
                page.get_by_role("button", name="Projects").click()
                expect(page.locator("#panel-manage")).to_be_visible()
                page.get_by_role("button", name="Commission").click()
                expect(page.locator("#panel-commission")).to_be_visible()
                page.get_by_role("button", name="Diagnostics").click()
                expect(page.locator("#panel-diagnostics")).to_be_visible()

                create_link_req = urlrequest.Request(
                    f"{base_url}/api/v1/commissioning/projects/{project_id}/tech-links",
                    data=b"{}",
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with urlrequest.urlopen(create_link_req, timeout=10.0) as resp:
                    tech_link = json.loads(resp.read().decode("utf-8"))
                tech_url = str(tech_link.get("techUrl") or "").strip()
                self.assertTrue(tech_url.startswith("/testing/"), f"Unexpected techUrl: {tech_url}")
                tech_token = tech_url.split("/")[-1]
                self.assertTrue(tech_token, "Expected tech token.")

                result_payload = {
                    "target": {
                        "targetKey": "live:smoke:target:1",
                        "targetName": "Live Smoke Target",
                        "kind": "BUTTON",
                        "refs": {
                            "deviceName": "Live Device",
                            "pageName": "Live Page",
                            "buttonName": "Live Button",
                            "scope": "BUTTON",
                        },
                    },
                    "outcome": "FAIL",
                    "failNote": "Live smoke fail note",
                }
                post_req = urlrequest.Request(
                    f"{base_url}/api/v1/testing/{tech_token}/results",
                    data=json.dumps(result_payload).encode("utf-8"),
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with urlrequest.urlopen(post_req, timeout=10.0) as resp:
                    self.assertEqual(int(resp.status), 200)

                page.get_by_role("button", name="Commission").click()
                expect(page.locator("#commissionActivityBody")).to_contain_text("Live Smoke Target", timeout=30000)
                page.get_by_role("button", name="Diagnostics").click()
                expect(page.locator("#diagnosticsTaskTable tbody")).to_contain_text("live smoke target", timeout=30000)

                self.assertFalse(
                    any("[project-ws] close unexpected" in line for line in console_logs),
                    f"Unexpected project ws close seen in smoke logs: {console_logs}",
                )
                self.assertFalse(
                    any("[diagnostics-ws] close" in line and "missing-project" not in line for line in console_logs),
                    f"Unexpected diagnostics close seen in smoke logs: {console_logs}",
                )
                page.close()
            finally:
                app_server.stop()

    def test_live_status_bar_shows_extracting_and_generating_phases(self):
        from playwright.sync_api import expect

        try:
            import websockets  # noqa: F401
        except Exception as e:
            raise unittest.SkipTest("websockets runtime is not installed in this environment") from e

        apex_path = ROOT / "Assets" / "TEST - System Manager v11.3.apex"
        if not apex_path.exists():
            raise unittest.SkipTest(f"Missing apex fixture: {apex_path}")

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            app_server = _AppServer(generated_root=(tmp / "generated"), upload_root=(tmp / "uploads"))
            app_server.start()
            try:
                base_url = str(app_server.base_url or "").rstrip("/")
                page = self._browser.new_page()
                page.goto(f"{base_url}/commissioning/index.html")
                page.get_by_role("button", name="Projects").click()

                page.get_by_label("New client name").fill("Live Client")
                page.get_by_role("button", name="Create client").click()
                page.get_by_label("New project name").fill("Live Project")
                page.get_by_role("button", name="Create project").click()
                expect(page.get_by_label("Project", exact=True)).not_to_have_value("")

                # Record all phase-label transitions, even brief ones.
                page.evaluate(
                    """() => {
                      window.__phaseLabelHistory = [];
                      const target = document.getElementById('uploadProgressLabel');
                      const push = () => {
                        const t = String((target && target.textContent) || '').trim();
                        if (!t) return;
                        window.__phaseLabelHistory.push(t);
                      };
                      if (target) {
                        push();
                        const obs = new MutationObserver(push);
                        obs.observe(target, { childList: true, subtree: true, characterData: true });
                        window.__phaseObserver = obs;
                      }
                    }"""
                )

                page.set_input_files("input[type=file][name=apex]", str(apex_path))
                page.get_by_role("button", name="Load File").click()
                expect(page.get_by_test_id("upload-status")).to_contain_text("Uploaded", timeout=120000)

                phases = page.evaluate("() => Array.isArray(window.__phaseLabelHistory) ? window.__phaseLabelHistory.slice() : []")
                self.assertTrue(any(str(p) == "Extracting..." for p in phases), f"Missing Extracting... phase. history={phases}")
                self.assertTrue(any(str(p) == "Generating..." for p in phases), f"Missing Generating... phase. history={phases}")
                page.close()
            finally:
                app_server.stop()

    def test_live_status_bar_recovers_phase_updates_after_manage_ws_gap(self):
        from playwright.sync_api import expect

        try:
            import websockets  # noqa: F401
        except Exception as e:
            raise unittest.SkipTest("websockets runtime is not installed in this environment") from e

        apex_path = ROOT / "Assets" / "TEST - System Manager v11.3.apex"
        if not apex_path.exists():
            raise unittest.SkipTest(f"Missing apex fixture: {apex_path}")

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            app_server = _AppServer(generated_root=(tmp / "generated"), upload_root=(tmp / "uploads"))
            app_server.start()
            try:
                base_url = str(app_server.base_url or "").rstrip("/")
                page = self._browser.new_page()
                page.goto(f"{base_url}/commissioning/index.html")
                page.get_by_role("button", name="Projects").click()

                page.get_by_label("New client name").fill("Live Client")
                page.get_by_role("button", name="Create client").click()
                page.get_by_label("New project name").fill("Live Project")
                page.get_by_role("button", name="Create project").click()
                expect(page.get_by_label("Project", exact=True)).not_to_have_value("")

                page.evaluate(
                    """() => {
                      window.__phaseLabelHistory = [];
                      const target = document.getElementById('uploadProgressLabel');
                      const push = () => {
                        const t = String((target && target.textContent) || '').trim();
                        if (!t) return;
                        window.__phaseLabelHistory.push(t);
                      };
                      if (target) {
                        const obs = new MutationObserver(push);
                        obs.observe(target, { childList: true, subtree: true, characterData: true });
                        window.__phaseObserver = obs;
                      }
                    }"""
                )

                # Simulate a temporary manage-consumer drop during an in-flight upload/regenerate.
                page.evaluate(
                    """() => {
                      const mgr = window.__sentinelProjectWsManager;
                      if (mgr && typeof mgr.setConsumer === 'function') {
                        mgr.setConsumer('manage', { active: false });
                      }
                    }"""
                )

                page.set_input_files("input[type=file][name=apex]", str(apex_path))
                page.get_by_role("button", name="Load File").click()
                page.wait_for_timeout(900)

                page.evaluate(
                    """() => {
                      const mgr = window.__sentinelProjectWsManager;
                      if (mgr && typeof mgr.setConsumer === 'function') {
                        mgr.setConsumer('manage', { active: true });
                      }
                    }"""
                )

                expect(page.get_by_test_id("upload-status")).to_contain_text("Uploaded", timeout=120000)
                phases = page.evaluate("() => Array.isArray(window.__phaseLabelHistory) ? window.__phaseLabelHistory.slice() : []")
                self.assertTrue(any(str(p) == "Extracting..." for p in phases), f"Missing Extracting... after ws gap. history={phases}")
                self.assertTrue(any(str(p) == "Generating..." for p in phases), f"Missing Generating... after ws gap. history={phases}")
                page.close()
            finally:
                app_server.stop()
