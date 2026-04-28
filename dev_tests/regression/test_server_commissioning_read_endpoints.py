import json
import os
import tempfile
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _require_fastapi():
    try:
        from fastapi.testclient import TestClient  # type: ignore
    except Exception:  # pragma: no cover
        raise unittest.SkipTest("fastapi is not installed")
    return TestClient


class CommissioningReadEndpointsTest(unittest.TestCase):
    def test_create_client_duplicate_name_returns_conflict(self):
        TestClient = _require_fastapi()

        from sentinel.server.app.main import create_app
        from sentinel.server.services.repositories import InMemoryRepository

        app = create_app(repo=InMemoryRepository())
        client = TestClient(app)

        first = client.post("/api/v1/commissioning/clients", json={"name": "Client A"})
        self.assertEqual(first.status_code, 200)

        dup = client.post("/api/v1/commissioning/clients", json={"name": "Client A"})
        self.assertEqual(dup.status_code, 409)
        body = dup.json()
        error = (body.get("detail") or {}).get("error") if isinstance(body.get("detail"), dict) else body.get("error")
        self.assertEqual((error or {}).get("code"), "CLIENT_EXISTS")

    def test_list_clients_and_projects(self):
        TestClient = _require_fastapi()

        from sentinel.server.app.main import create_app
        from sentinel.server.services.repositories import InMemoryRepository

        app = create_app(repo=InMemoryRepository())
        client = TestClient(app)

        c1 = client.post("/api/v1/commissioning/clients", json={"name": "Client A"}).json()
        c2 = client.post("/api/v1/commissioning/clients", json={"name": "Client B"}).json()

        p1 = client.post(f"/api/v1/commissioning/clients/{c1['clientId']}/projects", json={"name": "Project 1"}).json()
        _ = client.post(f"/api/v1/commissioning/clients/{c2['clientId']}/projects", json={"name": "Project 2"}).json()

        listed = client.get("/api/v1/commissioning/clients").json()
        self.assertEqual({c["clientId"] for c in listed}, {c1["clientId"], c2["clientId"]})

        c1_projects = client.get(f"/api/v1/commissioning/clients/{c1['clientId']}/projects").json()
        self.assertEqual([p["projectId"] for p in c1_projects], [p1["projectId"]])
        self.assertEqual([p["clientId"] for p in c1_projects], [c1["clientId"]])

    def test_fails_and_progress_rollups_events_and_devices(self):
        TestClient = _require_fastapi()

        with tempfile.TemporaryDirectory() as td:
            gen_root = Path(td) / "generated"
            old_root = os.environ.get("SENTINEL_GENERATED_ROOT")
            os.environ["SENTINEL_GENERATED_ROOT"] = str(gen_root)
            if old_root is None:
                self.addCleanup(lambda: os.environ.pop("SENTINEL_GENERATED_ROOT", None))
            else:
                self.addCleanup(lambda: os.environ.__setitem__("SENTINEL_GENERATED_ROOT", old_root))

            from sentinel.server.app.main import create_app
            from sentinel.server.services.repositories import InMemoryRepository

            app = create_app(repo=InMemoryRepository())
            client = TestClient(app)

            c = client.post("/api/v1/commissioning/clients", json={"name": "Client A"}).json()
            p = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Project A"}).json()
            project_id = p["projectId"]

            tech = client.post(f"/api/v1/commissioning/projects/{project_id}/tech-links", json={"label": "Onsite"}).json()
            tech_token = tech["techUrl"].split("/testing/")[1]

            # Write a minimal extracted project model for rollups.
            project_dir = gen_root / project_id
            project_dir.mkdir(parents=True, exist_ok=True)

            device_id = 81
            page_id = 513
            button_id = 48551
            viewport_button_id = 48248
            frame_id = 0
            vp_child_button_id = 48249

            project_data = {
                "events": {
                    "system": [
                        {
                            "userFacing": {"testTargets": {"Trigger": True, "Macro": True}},
                            "diagnostics": {"eventId": 126},
                        }
                    ],
                    "driver": [
                        {
                            "userFacing": {"testTargets": {"Macro": True}},
                            "diagnostics": {"eventId": 136},
                        }
                    ],
                },
                "devices": [
                    {
                        "userFacing": {
                            "displayName": "iPhone (Sean)",
                            "pages": [
                                {
                                    "pageName": "Room Select",
                                    "layers": [
                                        {
                                            "layerName": "Main",
                                            "layerOrder": 0,
                                            "buttonCategories": {
                                                "screenLabels": [],
                                                "screenButtons": [
                                                    {
                                                        "buttonIdentity": {"buttonTagName": "BTN-1", "text": "", "buttonType": None},
                                                        "testTargets": {"text": False, "macros": True, "macroSteps": False, "variables": {"Reversed": True}, "pageLink": False},
                                                    }
                                                ],
                                                "hardButtons": [],
                                            },
                                            "viewports": [
                                                {
                                                    "viewportIdentity": {"viewportButtonId": viewport_button_id},
                                                    "layers": [
                                                        {
                                                            "layerName": "Viewport",
                                                            "layerOrder": 0,
                                                            "frames": [
                                                                {
                                                                    "frameId": frame_id,
                                                                    "buttonCategories": {
                                                                        "screenLabels": [],
                                                                        "screenButtons": [
                                                                            {
                                                                                "buttonIdentity": {"buttonTagName": "VPBTN-1", "text": "", "buttonType": None},
                                                                                "testTargets": {"text": False, "macros": True, "macroSteps": False, "variables": {}, "pageLink": False},
                                                                            }
                                                                        ],
                                                                        "hardButtons": [],
                                                                    },
                                                                }
                                                            ],
                                                        }
                                                    ],
                                                }
                                            ],
                                        }
                                    ],
                                }
                            ],
                        },
                        "diagnostics": {
                            "deviceId": device_id,
                            "displayName": "iPhone (Sean)",
                            "pages": [
                                {
                                    "pageId": page_id,
                                    "pageName": "Room Select",
                                    "buttons": [
                                        {
                                            "buttonId": button_id,
                                            "identifiers": {"text": "", "buttonTagId": None},
                                            "buttonTagName": "BTN-1",
                                        }
                                    ],
                                    "viewports": [
                                        {
                                            "viewportButtonId": viewport_button_id,
                                            "frames": [
                                                {
                                                    "frameId": frame_id,
                                                    "buttons": [
                                                        {
                                                            "buttonId": vp_child_button_id,
                                                            "identifiers": {"text": "", "buttonTagId": None},
                                                            "buttonTagName": "VPBTN-1",
                                                        }
                                                    ],
                                                }
                                            ],
                                        }
                                    ],
                                }
                            ],
                        },
                    }
                ],
            }
            (project_dir / "fixture_project_data.json").write_text(json.dumps(project_data), encoding="utf-8")

            # Post some results (including a fail that later becomes pass).
            event_trigger_key = "event:126:Event Trigger"
            driver_macro_key = "event:136:System Macro"
            btn_var_key = f"btn:{device_id}:{page_id}:{button_id}:Var.Reversed"
            vp_macro_key = f"vpbtn:{device_id}:{page_id}:{viewport_button_id}:{frame_id}:{vp_child_button_id}:System Macro"

            r1 = client.post(
                f"/api/v1/testing/{tech_token}/results",
                json={"target": {"targetKey": btn_var_key, "kind": "BUTTON", "refs": {}, "targetName": "Var.Reversed"}, "outcome": "FAIL", "failNote": "Bad reverse"},
            )
            self.assertEqual(r1.status_code, 200)

            r2 = client.post(
                f"/api/v1/testing/{tech_token}/results",
                json={"target": {"targetKey": event_trigger_key, "kind": "EVENT", "refs": {"eventId": 126}, "targetName": "Event Trigger"}, "outcome": "PASS", "failNote": None},
            )
            self.assertEqual(r2.status_code, 200)

            r3 = client.post(
                f"/api/v1/testing/{tech_token}/results",
                json={"target": {"targetKey": vp_macro_key, "kind": "VIEWPORT_BUTTON", "refs": {}, "targetName": "System Macro"}, "outcome": "PASS", "failNote": None},
            )
            self.assertEqual(r3.status_code, 200)

            # Resolve the earlier fail (latest-wins should remove it from fails).
            r4 = client.post(
                f"/api/v1/testing/{tech_token}/results",
                json={"target": {"targetKey": btn_var_key, "kind": "BUTTON", "refs": {}, "targetName": "Var.Reversed"}, "outcome": "PASS", "failNote": None},
            )
            self.assertEqual(r4.status_code, 200)

            fails = client.get(f"/api/v1/commissioning/projects/{project_id}/fails").json()
            self.assertEqual(fails, [])

            # Now create a real failure and ensure it shows.
            r5 = client.post(
                f"/api/v1/testing/{tech_token}/results",
                json={"target": {"targetKey": driver_macro_key, "kind": "EVENT", "refs": {"eventId": 136}, "targetName": "System Macro"}, "outcome": "FAIL", "failNote": "Driver macro broken"},
            )
            self.assertEqual(r5.status_code, 200)

            fails = client.get(f"/api/v1/commissioning/projects/{project_id}/fails").json()
            self.assertEqual([f["targetKey"] for f in fails], [driver_macro_key])
            self.assertEqual(fails[0]["currentOutcome"], "FAIL")
            self.assertEqual(fails[0]["lastFailNote"], "Driver macro broken")

            progress = client.get(f"/api/v1/commissioning/projects/{project_id}/progress").json()

            # Event sections: system has Trigger+Macro (2 total, 1 tested), driver has Macro (1 total, failed).
            self.assertEqual(progress["eventSections"]["system"]["counts"]["totalTargets"], 2)
            self.assertEqual(progress["eventSections"]["system"]["counts"]["testedTargets"], 1)
            self.assertEqual(progress["eventSections"]["system"]["counts"]["pass"], 1)
            self.assertEqual(progress["eventSections"]["system"]["counts"]["untested"], 1)
            self.assertEqual(progress["eventSections"]["driver"]["counts"]["totalTargets"], 1)
            self.assertEqual(progress["eventSections"]["driver"]["counts"]["fail"], 1)

            # Device rollup: expected targets are btn Macro + btn Var.Reversed + vp Macro (3 total, 2 tested).
            self.assertEqual(len(progress["devices"]), 1)
            dev = progress["devices"][0]
            self.assertEqual(dev["deviceId"], device_id)
            self.assertEqual(dev["counts"]["totalTargets"], 3)
            self.assertEqual(dev["counts"]["testedTargets"], 2)
            self.assertEqual(dev["counts"]["pass"], 2)
            self.assertEqual(dev["counts"]["untested"], 1)

            # Project rollup: events (3) + device (3) = 6 total, tested 4, pass 3, fail 1, untested 2.
            self.assertEqual(progress["counts"]["totalTargets"], 6)
            self.assertEqual(progress["counts"]["testedTargets"], 4)
            self.assertEqual(progress["counts"]["pass"], 3)
            self.assertEqual(progress["counts"]["fail"], 1)
            self.assertEqual(progress["counts"]["untested"], 2)

    def test_tech_link_rotate_and_revoke_require_matching_project(self):
        TestClient = _require_fastapi()

        from sentinel.server.app.main import create_app
        from sentinel.server.services.repositories import InMemoryRepository

        app = create_app(repo=InMemoryRepository())
        client = TestClient(app)

        c = client.post("/api/v1/commissioning/clients", json={"name": "Client A"}).json()
        p1 = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Project 1"}).json()
        p2 = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Project 2"}).json()

        link = client.post(f"/api/v1/commissioning/projects/{p1['projectId']}/tech-links", json={"label": "Onsite"}).json()
        tech_link_id = link["techLinkId"]

        wrong_rotate = client.post(f"/api/v1/commissioning/projects/{p2['projectId']}/tech-links/{tech_link_id}/rotate")
        self.assertEqual(wrong_rotate.status_code, 404)

        wrong_revoke = client.post(f"/api/v1/commissioning/projects/{p2['projectId']}/tech-links/{tech_link_id}/revoke")
        self.assertEqual(wrong_revoke.status_code, 404)
