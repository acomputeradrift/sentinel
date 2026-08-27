import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib import request as urlrequest


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


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


class CommissioningSettingsRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ModuleNotFoundError as e:
            raise unittest.SkipTest("Playwright is not installed.") from e
        cls._pw = sync_playwright().start()
        cls._browser = cls._pw.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls._browser.close()
        finally:
            cls._pw.stop()

    def test_settings_tab_toggles_bitmap_off(self):
        from playwright.sync_api import expect

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            app_server = _AppServer(generated_root=(tmp / "generated"), upload_root=(tmp / "uploads"))
            app_server.start()
            context = self._browser.new_context()
            try:
                base_url = str(app_server.base_url or "").rstrip("/")
                page = context.new_page()
                page.goto(f"{base_url}/commissioning/index.html")
                page.get_by_role("button", name="File").click()
                page.locator("#clientSelect").select_option(value="__new_client__")
                page.locator("#modalNewClientName").fill("Settings Client")
                page.locator("#modalNewClientSubmit").click()
                page.locator("#projectSelect").select_option(value="__new_project__")
                page.locator("#modalNewProjectName").fill("Settings Job")
                page.locator("#modalNewProjectSubmit").click()
                expect(page.get_by_label("Project", exact=True)).not_to_have_value("")
                project_id = str(page.locator("#projectSelect").input_value() or "").strip()
                self.assertTrue(project_id)

                page.get_by_role("button", name="Settings").click()
                expect(page.locator("#panel-settings")).to_be_visible()
                bitmap = page.get_by_test_id("settings-type-button-Bitmap")
                expect(bitmap).to_be_checked()
                expect(page.get_by_test_id("settings-type-event-Event-Trigger")).to_be_checked()
                bitmap.uncheck()
                expect(bitmap).not_to_be_checked(timeout=5000)

                with urlrequest.urlopen(
                    f"{base_url}/api/v1/commissioning/projects/{project_id}/testing-types",
                    timeout=10.0,
                ) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                self.assertIn("button:Bitmap", body.get("disabledTypes") or [])
                enabled = {row["id"]: row["enabled"] for row in body.get("types") or []}
                self.assertFalse(enabled.get("button:Bitmap"))
                self.assertTrue(enabled.get("button:Text"))
            finally:
                context.close()
                app_server.stop()


if __name__ == "__main__":
    unittest.main()
