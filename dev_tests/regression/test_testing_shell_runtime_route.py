import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _require_fastapi():
    try:
        from fastapi.testclient import TestClient  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise unittest.SkipTest("fastapi is not installed") from exc
    return TestClient


class TestingShellRuntimeRouteTest(unittest.TestCase):
    def test_shell_device_route_uses_injected_runtime_shell_contract(self):
        TestClient = _require_fastapi()

        from sentinel.server.services import pipeline

        with tempfile.TemporaryDirectory() as td:
            os.environ["SENTINEL_UPLOAD_ROOT"] = str(Path(td) / "uploads")
            os.environ["SENTINEL_GENERATED_ROOT"] = str(Path(td) / "generated")

            original_regen = pipeline.regenerate_project

            def _regen_stub(*, projectId: str, apex_path: Path, phase_hook=None) -> dict:  # noqa: ARG001
                if callable(phase_hook):
                    phase_hook("extracting", 100)
                    phase_hook("generating", 100)

                out_dir = Path(td) / "generated" / projectId
                out_dir.mkdir(parents=True, exist_ok=True)

                home_name = "Fixture__project-home.html"
                device_name = "Fixture__device-Test-0.html"
                (out_dir / home_name).write_text(
                    (
                        "<!doctype html><html><head><meta charset='utf-8'></head><body>"
                        "<a class='home-row device-row' href='Fixture__device-Test-0.html'>Device</a>"
                        "</body></html>"
                    ),
                    encoding="utf-8",
                )
                (out_dir / device_name).write_text(
                    (
                        "<!doctype html><html><head><meta charset='utf-8'><title>Device</title></head><body>"
                        "<div id='appCanvas'><div id='topControls'></div><div id='rtiCanvas'><div id='rtiContent'><div id='rtiDeviceCanvas'><div class='device-page active'>runtime row</div></div></div></div></div>"
                        "<script>window.__sentinelOldRuntimeSource='fixture';</script>"
                        "</body></html>"
                    ),
                    encoding="utf-8",
                )
                (out_dir / "Fixture_project_data.json").write_text('{"events":{"system":[],"driver":[]},"devices":[]}', encoding="utf-8")
                return {"projectId": projectId, "outDir": str(out_dir), "projectData": "stub"}

            pipeline.regenerate_project = _regen_stub  # type: ignore[assignment]
            try:
                from sentinel.server.app.main import create_app

                app = create_app()
                client = TestClient(app)

                c = client.post("/api/v1/commissioning/clients", json={"name": "Client A"}).json()
                p = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Project A"}).json()
                up = client.post(
                    f"/api/v1/commissioning/projects/{p['projectId']}/upload-and-regenerate",
                    files={"apex": ("Project A v1.apex", b"not-a-real-apex", "application/octet-stream")},
                )
                self.assertEqual(up.status_code, 200)

                link = client.post(f"/api/v1/commissioning/projects/{p['projectId']}/tech-links", json={"label": "Onsite"}).json()
                tech_url = str(link.get("techUrl") or "")
                self.assertTrue(tech_url.startswith("/testing/"))
                tech_token = tech_url.split("/testing/")[1]

                shell_home = client.get(f"/testing/{tech_token}?runtime=shell")
                self.assertEqual(shell_home.status_code, 200)
                self.assertEqual(shell_home.headers.get("X-Sentinel-Runtime-Mode"), "shell")
                self.assertIn("u.searchParams.set('runtime','shell');", shell_home.text)

                shell_device = client.get(f"/testing/{tech_token}/files/Fixture__device-Test-0.html?runtime=shell")
                self.assertEqual(shell_device.status_code, 200)
                self.assertEqual(shell_device.headers.get("X-Sentinel-Runtime-Mode"), "shell")
                self.assertIn("id=\"rtiDeviceContent\"", shell_device.text)
                self.assertIn("data-shell-runtime-adapter=\"1\"", shell_device.text)
                self.assertIn("selectedRoomIndicator", shell_device.text)
                self.assertNotIn('["#orientationControls", "#deviceViewControlsCanvas"]', shell_device.text)
                self.assertNotIn('data-shell-source-style="', shell_device.text)

                default_device = client.get(f"/testing/{tech_token}/files/Fixture__device-Test-0.html")
                self.assertEqual(default_device.status_code, 200)
                self.assertEqual(default_device.headers.get("X-Sentinel-Runtime-Mode"), "shell")
                self.assertIn("id=\"rtiDeviceContent\"", default_device.text)
                self.assertIn("data-shell-runtime-adapter=\"1\"", default_device.text)
                self.assertNotIn("__sentinelOldRuntimeSource", default_device.text)

                source_device = client.get(f"/testing/{tech_token}/files/Fixture__device-Test-0.html?runtime=source")
                self.assertEqual(source_device.status_code, 200)
                self.assertEqual(source_device.headers.get("X-Sentinel-Runtime-Mode"), "source")
                self.assertIn("id='appCanvas'", source_device.text)
                self.assertIn("__sentinelOldRuntimeSource", source_device.text)
            finally:
                pipeline.regenerate_project = original_regen  # type: ignore[assignment]
