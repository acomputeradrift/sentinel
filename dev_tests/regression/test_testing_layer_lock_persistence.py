import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _session_key_from_html(html: str) -> str:
    match = re.search(r"const PROJECT_SESSION_KEY=(.*?);", html)
    if not match:
        raise AssertionError("PROJECT_SESSION_KEY missing from generated HTML")
    return json.loads(match.group(1))


def _minimal_project_data() -> dict:
    return {
        "devices": [
            {
                "userFacing": {
                    "displayName": "ISR-4",
                    "deviceUI": {
                        "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                        "landscape": {"supported": False, "resolution": {"width": 0, "height": 0}},
                    },
                    "pages": [
                        {
                            "pageName": "Home",
                            "layers": [
                                {
                                    "layerName": "Main",
                                    "sharedLayerId": 1,
                                    "layerOrder": 0,
                                    "isKeypadLayer": False,
                                    "buttonCategories": {
                                        "screenLabels": [],
                                        "screenButtons": [],
                                        "hardButtons": [],
                                        "emptyTag": [],
                                        "uiItems": [],
                                    },
                                    "viewports": [],
                                }
                            ],
                        }
                    ],
                },
                "diagnostics": {
                    "deviceId": 1,
                    "deviceName": "ISR-4",
                    "displayName": "ISR-4",
                    "rtiAddress": 1,
                    "isClonedController": False,
                    "rooms": [],
                    "sourceListRows": [],
                    "pages": [{"pageId": 1, "pageName": "Home", "pageOrder": 0, "pageNumber": 1, "uiItems": [], "buttons": [], "viewports": []}],
                },
            }
        ],
        "events": {"system": [], "macro": [], "macroStep": []},
        "source": {"file": "uploads/demo/file.apex"},
    }


def _require_fastapi():
    try:
        from fastapi.testclient import TestClient  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise unittest.SkipTest("fastapi is not installed") from exc
    return TestClient


class TestingLayerLockPersistenceTest(unittest.TestCase):
    def test_testing_layer_locks_persist_per_project_scope(self):
        TestClient = _require_fastapi()
        from sentinel.server.app.main import create_app

        app = create_app()
        client = TestClient(app)

        c = client.post("/api/v1/commissioning/clients", json={"name": "Layer Lock Client"}).json()
        p = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Layer Lock Project"}).json()
        link = client.post(f"/api/v1/commissioning/projects/{p['projectId']}/tech-links", json={"label": "Tech"}).json()
        tech_token = str(link.get("techUrl") or "").split("/testing/")[1]

        with client.websocket_connect(f"/api/v1/testing/{tech_token}/ws") as ws:
            first = json.loads(ws.receive_text())
            self.assertEqual(first.get("type"), "testing_snapshot")
            self.assertEqual(first.get("layerLocks"), [])
            ws.send_text(
                json.dumps(
                    {
                        "type": "layer_lock.set",
                        "scopeKey": "project::device::page",
                        "layerKey": "layer-1",
                        "visible": False,
                        "locked": True,
                    }
                )
            )
            seen = None
            for _ in range(20):
                msg = json.loads(ws.receive_text())
                if msg.get("type") != "layer_lock_state":
                    continue
                seen = msg
                break
            self.assertIsNotNone(seen)
            self.assertEqual(seen.get("scopeKey"), "project::device::page")
            self.assertEqual(seen.get("layerKey"), "layer-1")
            self.assertEqual(seen.get("visible"), False)
            self.assertEqual(seen.get("locked"), True)

        with client.websocket_connect(f"/api/v1/testing/{tech_token}/ws") as ws2:
            snap = json.loads(ws2.receive_text())
            self.assertEqual(snap.get("type"), "testing_snapshot")
            locks = list(snap.get("layerLocks") or [])
            self.assertEqual(len(locks), 1)
            self.assertEqual(locks[0].get("scopeKey"), "project::device::page")
            self.assertEqual(locks[0].get("layerKey"), "layer-1")
            self.assertEqual(locks[0].get("visible"), False)
            self.assertEqual(locks[0].get("locked"), True)

    def test_generated_layer_lock_session_key_uses_project_id_not_filename_stem(self):
        from sentinel.generation.render_core import build_device_render_bundle, load_json

        project_data = _minimal_project_data()
        app_ui = load_json(ROOT / "src" / "sentinel" / "contracts" / "app_ui_structure.json")
        project_id = "proj-stable-lock"
        html_v1 = str(
            build_device_render_bundle(
                project_data,
                app_ui,
                project_stem="Sung_Residence_v207_2_project_data",
                device_index=0,
                project_id=project_id,
            ).get("html")
            or ""
        )
        html_v2 = str(
            build_device_render_bundle(
                project_data,
                app_ui,
                project_stem="Sung_Residence_v208_project_data",
                device_index=0,
                project_id=project_id,
            ).get("html")
            or ""
        )
        self.assertEqual(_session_key_from_html(html_v1), project_id)
        self.assertEqual(_session_key_from_html(html_v2), project_id)
        self.assertNotIn("Sung_Residence_v207_2_project_data", _session_key_from_html(html_v1))
        self.assertNotIn("Sung_Residence_v208_project_data", _session_key_from_html(html_v2))


if __name__ == "__main__":
    unittest.main()
