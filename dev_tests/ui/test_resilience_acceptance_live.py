import json
import os
import subprocess
import time
import unittest
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest


ROOT = Path(__file__).resolve().parents[2]


def _json_request(url: str, *, method: str = "GET", payload: dict | None = None, timeout_s: float = 20.0) -> dict | list:
    body = None
    headers: dict[str, str] = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urlrequest.Request(url, data=body, method=method, headers=headers)
    with urlrequest.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def _multipart_upload(url: str, *, file_path: Path, field_name: str = "apex", timeout_s: float = 120.0) -> dict:
    boundary = f"----sentinel-boundary-{int(time.time() * 1000)}"
    file_bytes = file_path.read_bytes()
    file_name = file_path.name
    pre = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{file_name}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8")
    post = f"\r\n--{boundary}--\r\n".encode("utf-8")
    body = pre + file_bytes + post
    req = urlrequest.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urlrequest.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw else {}


class ResilienceAcceptanceLiveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:  # pragma: no cover
            raise unittest.SkipTest(
                f"playwright import failed ({type(e).__name__}: {e!s}); "
                "install with devtools/bootstrap_tmp_apex_env.py or set SENTINEL_VENV_PYTHON"
            ) from e

        cls._pw = sync_playwright().start()
        cls._browser = cls._pw.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls._browser.close()
        finally:
            cls._pw.stop()

    def _wait_for_text(self, page, selector: str, needle: str, *, timeout_s: float = 30.0) -> None:  # noqa: ANN001
        deadline = time.time() + timeout_s
        needle_l = str(needle or "").lower()
        while time.time() < deadline:
            try:
                text = str(page.locator(selector).inner_text() or "")
            except Exception:
                text = ""
            if needle_l in text.lower():
                return
            time.sleep(0.2)
        self.fail(f"Expected {selector} to contain {needle!r}")

    def _wait_for_project_options(self, page, expected_project_ids: list[str], *, timeout_s: float = 30.0) -> None:  # noqa: ANN001
        deadline = time.time() + timeout_s
        expected = {str(x) for x in expected_project_ids}
        while time.time() < deadline:
            try:
                values = page.eval_on_selector_all("#projectSelect option", "opts => opts.map(o => String(o.value || '').trim())")
                got = {str(v) for v in (values or []) if str(v).strip()}
            except Exception:
                got = set()
            if expected.issubset(got):
                return
            time.sleep(0.2)
        self.fail(f"Expected project options to include ids={sorted(expected)}")

    def _wait_for_select_value(self, page, selector: str, expected_value: str, *, timeout_s: float = 30.0) -> None:  # noqa: ANN001
        deadline = time.time() + timeout_s
        want = str(expected_value or "").strip()
        while time.time() < deadline:
            try:
                got = str(page.locator(selector).input_value() or "").strip()
            except Exception:
                got = ""
            if got == want:
                return
            time.sleep(0.2)
        self.fail(f"Expected {selector} value={want!r}")

    def _ensure_projects_tab_open(self, page, *, timeout_s: float = 20.0) -> None:  # noqa: ANN001
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                is_visible = bool(page.locator("#panel-manage").is_visible())
            except Exception:
                is_visible = False
            if is_visible:
                return
            try:
                page.get_by_role("button", name="Projects").click()
            except Exception:
                pass
            time.sleep(0.2)
        self.fail("Expected Projects panel to be visible.")

    def _wait_for_health(self, base_url: str, *, timeout_s: float = 60.0) -> None:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                out = _json_request(f"{base_url}/health", timeout_s=5.0)
                if isinstance(out, dict) and str(out.get("status") or "").lower() == "ok":
                    return
            except Exception:
                pass
            time.sleep(1.0)
        self.fail("Server did not return healthy /health response in time.")

    def _create_live_project(self, base_url: str) -> tuple[str, str, str]:
        run_id = str(int(time.time()))
        client_name = f"Resilience Client {run_id}"
        project_name = f"Resilience Project {run_id}"
        client = _json_request(f"{base_url}/api/v1/commissioning/clients", method="POST", payload={"name": client_name})
        client_id = str((client or {}).get("clientId") or "")
        self.assertTrue(client_id)
        project = _json_request(
            f"{base_url}/api/v1/commissioning/clients/{client_id}/projects",
            method="POST",
            payload={"name": project_name},
        )
        project_id = str((project or {}).get("projectId") or "")
        self.assertTrue(project_id)
        return client_name, project_name, project_id

    def _create_live_project_for_client(self, base_url: str, client_id: str, project_name: str) -> str:
        project = _json_request(
            f"{base_url}/api/v1/commissioning/clients/{client_id}/projects",
            method="POST",
            payload={"name": project_name},
        )
        project_id = str((project or {}).get("projectId") or "")
        self.assertTrue(project_id)
        return project_id

    def _post_result(self, base_url: str, tech_token: str, *, key: str, name: str, outcome: str, fail_note: str | None = None) -> None:
        payload = {
            "target": {
                "targetKey": key,
                "targetName": name,
                "kind": "BUTTON",
                "refs": {
                    "deviceName": "Live Device",
                    "pageName": "Live Page",
                    "buttonName": "Live Button",
                    "scope": "BUTTON",
                },
            },
            "outcome": outcome,
            "failNote": fail_note,
        }
        _json_request(f"{base_url}/api/v1/testing/{tech_token}/results", method="POST", payload=payload)

    def test_live_refresh_and_network_recovery(self):
        base_url = str(os.environ.get("SENTINEL_LIVE_BASE_URL") or "http://24.199.106.213").rstrip("/")
        apex_path = Path(os.environ.get("SENTINEL_LIVE_APEX") or (ROOT / "Assets" / "TEST - System Manager v11.3.apex"))
        if not apex_path.exists():
            raise unittest.SkipTest(f"Missing apex file for live acceptance test: {apex_path}")

        self._wait_for_health(base_url)
        client_name, project_name, project_id = self._create_live_project(base_url)
        _multipart_upload(f"{base_url}/api/v1/commissioning/projects/{project_id}/upload-and-regenerate", file_path=apex_path)
        link = _json_request(f"{base_url}/api/v1/commissioning/projects/{project_id}/tech-links", method="POST", payload={})
        tech_url = str((link or {}).get("techUrl") or "")
        self.assertTrue(tech_url.startswith("/testing/"), f"Unexpected techUrl: {tech_url}")
        tech_token = tech_url.split("/")[-1]

        context = self._browser.new_context()
        page = context.new_page()
        console_logs: list[str] = []
        page.on("console", lambda msg: console_logs.append(str(msg.text or "")))
        page.goto(f"{base_url}/commissioning/")
        self._ensure_projects_tab_open(page)

        page.select_option("#clientSelect", label=client_name)
        page.select_option("#projectSelect", label=project_name)
        page.get_by_role("button", name="Commission").click()

        key1 = f"live:resilience:{int(time.time())}:1"
        name1 = "Resilience Event 1"
        self._post_result(base_url, tech_token, key=key1, name=name1, outcome="FAIL", fail_note="offline/recovery test")

        self._wait_for_text(page, "#commissionActivityBody", name1, timeout_s=40.0)
        page.get_by_role("button", name="Diagnostics").click()
        self._wait_for_text(page, "#diagnosticsTaskBody", name1.lower(), timeout_s=40.0)

        page.reload()
        self._ensure_projects_tab_open(page)
        page.select_option("#clientSelect", label=client_name)
        page.select_option("#projectSelect", label=project_name)
        page.get_by_role("button", name="Commission").click()
        self._wait_for_text(page, "#commissionActivityBody", name1, timeout_s=40.0)

        context.set_offline(True)
        time.sleep(1.2)
        key2 = f"live:resilience:{int(time.time())}:2"
        name2 = "Resilience Event 2"
        self._post_result(base_url, tech_token, key=key2, name=name2, outcome="PASS")
        context.set_offline(False)

        page.get_by_role("button", name="Commission").click()
        self._wait_for_text(page, "#commissionActivityBody", name2, timeout_s=50.0)
        page.get_by_role("button", name="Diagnostics").click()
        self._wait_for_text(page, "#diagnosticsTaskBody", name1.lower(), timeout_s=30.0)

        self.assertFalse(
            any("WS-ERR-310 SOCKET_CLOSE_UNEXPECTED" in line for line in console_logs),
            f"Unexpected close code in live run: {console_logs}",
        )
        self.assertTrue(
            any("WS-INFO-100 SOCKET_OPEN" in line for line in console_logs),
            f"Missing SOCKET_OPEN code in live run logs: {console_logs}",
        )
        context.close()

    def test_live_project_switch_preserves_fanout_context(self):
        base_url = str(os.environ.get("SENTINEL_LIVE_BASE_URL") or "http://24.199.106.213").rstrip("/")
        apex_path = Path(os.environ.get("SENTINEL_LIVE_APEX") or (ROOT / "Assets" / "TEST - System Manager v11.3.apex"))
        if not apex_path.exists():
            raise unittest.SkipTest(f"Missing apex file for live acceptance test: {apex_path}")

        self._wait_for_health(base_url)
        run_id = str(int(time.time()))
        client_name = f"Resilience Switch Client {run_id}"
        project_a_name = f"Resilience Switch Project A {run_id}"
        project_b_name = f"Resilience Switch Project B {run_id}"
        client = _json_request(f"{base_url}/api/v1/commissioning/clients", method="POST", payload={"name": client_name})
        client_id = str((client or {}).get("clientId") or "")
        self.assertTrue(client_id)
        project_a_id = self._create_live_project_for_client(base_url, client_id, project_a_name)
        self._create_live_project_for_client(base_url, client_id, project_b_name)

        _multipart_upload(f"{base_url}/api/v1/commissioning/projects/{project_a_id}/upload-and-regenerate", file_path=apex_path)
        link = _json_request(f"{base_url}/api/v1/commissioning/projects/{project_a_id}/tech-links", method="POST", payload={})
        tech_url = str((link or {}).get("techUrl") or "")
        self.assertTrue(tech_url.startswith("/testing/"), f"Unexpected techUrl: {tech_url}")
        tech_token = tech_url.split("/")[-1]

        context = self._browser.new_context()
        page = context.new_page()
        page.goto(f"{base_url}/commissioning/")
        self._ensure_projects_tab_open(page)

        page.select_option("#clientSelect", label=client_name)
        self._wait_for_project_options(page, [project_a_id], timeout_s=30.0)
        page.select_option("#projectSelect", value=project_a_id)
        self.assertEqual(str(page.locator("#projectSelect").input_value() or "").strip(), project_a_id)
        page.get_by_role("button", name="Commission").click()
        page.get_by_role("button", name="Diagnostics").click()
        page.get_by_role("button", name="Commission").click()

        key1 = f"live:switch:{int(time.time())}:1"
        name1 = "Switch Fanout Event 1"
        self._post_result(base_url, tech_token, key=key1, name=name1, outcome="FAIL", fail_note="switch context fanout")
        self._wait_for_text(page, "#commissionActivityBody", name1, timeout_s=40.0)
        page.get_by_role("button", name="Diagnostics").click()
        self._wait_for_text(page, "#diagnosticsTaskBody", name1.lower(), timeout_s=40.0)

        self._ensure_projects_tab_open(page)
        page.select_option("#projectSelect", label=project_b_name)
        page.get_by_role("button", name="Commission").click()
        self._ensure_projects_tab_open(page)
        page.select_option("#projectSelect", value=project_a_id)
        self.assertEqual(str(page.locator("#projectSelect").input_value() or "").strip(), project_a_id)
        page.get_by_role("button", name="Commission").click()

        key2 = f"live:switch:{int(time.time())}:2"
        name2 = "Switch Fanout Event 2"
        self._post_result(base_url, tech_token, key=key2, name=name2, outcome="PASS")
        self._wait_for_text(page, "#commissionActivityBody", name2, timeout_s=40.0)
        page.get_by_role("button", name="Diagnostics").click()
        self._wait_for_text(page, "#diagnosticsTaskBody", name1.lower(), timeout_s=40.0)
        context.close()

    def test_live_refresh_keeps_selected_project_context(self):
        base_url = str(os.environ.get("SENTINEL_LIVE_BASE_URL") or "http://24.199.106.213").rstrip("/")
        apex_path = Path(os.environ.get("SENTINEL_LIVE_APEX") or (ROOT / "Assets" / "TEST - System Manager v11.3.apex"))
        if not apex_path.exists():
            raise unittest.SkipTest(f"Missing apex file for live acceptance test: {apex_path}")

        self._wait_for_health(base_url)
        run_id = str(int(time.time()))
        client_name = f"Resilience Refresh Client {run_id}"
        project_a_name = f"Resilience Refresh Project A {run_id}"
        project_b_name = f"Resilience Refresh Project B {run_id}"
        client = _json_request(f"{base_url}/api/v1/commissioning/clients", method="POST", payload={"name": client_name})
        client_id = str((client or {}).get("clientId") or "")
        self.assertTrue(client_id)
        project_a_id = self._create_live_project_for_client(base_url, client_id, project_a_name)
        self._create_live_project_for_client(base_url, client_id, project_b_name)

        _multipart_upload(f"{base_url}/api/v1/commissioning/projects/{project_a_id}/upload-and-regenerate", file_path=apex_path)
        link = _json_request(f"{base_url}/api/v1/commissioning/projects/{project_a_id}/tech-links", method="POST", payload={})
        tech_url = str((link or {}).get("techUrl") or "")
        self.assertTrue(tech_url.startswith("/testing/"), f"Unexpected techUrl: {tech_url}")
        tech_token = tech_url.split("/")[-1]

        context = self._browser.new_context()
        page = context.new_page()
        page.goto(f"{base_url}/commissioning/")
        self._ensure_projects_tab_open(page)
        page.select_option("#clientSelect", label=client_name)
        self._wait_for_project_options(page, [project_a_id], timeout_s=30.0)
        page.select_option("#projectSelect", value=project_a_id)
        self._wait_for_select_value(page, "#projectSelect", project_a_id, timeout_s=10.0)

        page.reload()
        self._ensure_projects_tab_open(page)
        self._wait_for_select_value(page, "#clientSelect", client_id, timeout_s=30.0)
        self._wait_for_select_value(page, "#projectSelect", project_a_id, timeout_s=30.0)
        page.get_by_role("button", name="Commission").click()

        key = f"live:refresh-ctx:{int(time.time())}:1"
        name = "Refresh Context Event 1"
        self._post_result(base_url, tech_token, key=key, name=name, outcome="FAIL", fail_note="refresh selected project context")
        self._wait_for_text(page, "#commissionActivityBody", name, timeout_s=40.0)
        page.get_by_role("button", name="Diagnostics").click()
        self._wait_for_text(page, "#diagnosticsTaskBody", name.lower(), timeout_s=40.0)
        context.close()

    def test_live_server_restart_recovery_optional(self):
        base_url = str(os.environ.get("SENTINEL_LIVE_BASE_URL") or "http://24.199.106.213").rstrip("/")
        restart_cmd = str(os.environ.get("SENTINEL_LIVE_RESTART_CMD") or "").strip()
        if not restart_cmd:
            raise unittest.SkipTest("Set SENTINEL_LIVE_RESTART_CMD to run restart acceptance phase.")

        apex_path = Path(os.environ.get("SENTINEL_LIVE_APEX") or (ROOT / "Assets" / "TEST - System Manager v11.3.apex"))
        if not apex_path.exists():
            raise unittest.SkipTest(f"Missing apex file for live acceptance test: {apex_path}")

        self._wait_for_health(base_url)
        client_name, project_name, project_id = self._create_live_project(base_url)
        _multipart_upload(f"{base_url}/api/v1/commissioning/projects/{project_id}/upload-and-regenerate", file_path=apex_path)
        link = _json_request(f"{base_url}/api/v1/commissioning/projects/{project_id}/tech-links", method="POST", payload={})
        tech_token = str((link or {}).get("techUrl") or "").split("/")[-1]
        self.assertTrue(tech_token)

        context = self._browser.new_context()
        page = context.new_page()
        page.goto(f"{base_url}/commissioning/")
        self._ensure_projects_tab_open(page)
        page.select_option("#clientSelect", label=client_name)
        page.select_option("#projectSelect", label=project_name)
        page.get_by_role("button", name="Commission").click()

        pre_key = f"live:restart:{int(time.time())}:pre"
        pre_name = "Restart Event Pre"
        self._post_result(base_url, tech_token, key=pre_key, name=pre_name, outcome="PASS")
        self._wait_for_text(page, "#commissionActivityBody", pre_name, timeout_s=40.0)

        proc = subprocess.run(restart_cmd, shell=True, capture_output=True, text=True)
        if proc.returncode != 0:
            raise AssertionError(f"Restart command failed rc={proc.returncode}\nstdout={proc.stdout}\nstderr={proc.stderr}")
        self._wait_for_health(base_url, timeout_s=120.0)

        post_key = f"live:restart:{int(time.time())}:post"
        post_name = "Restart Event Post"
        self._post_result(base_url, tech_token, key=post_key, name=post_name, outcome="FAIL", fail_note="after restart")
        self._wait_for_text(page, "#commissionActivityBody", post_name, timeout_s=60.0)
        context.close()
