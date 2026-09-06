import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.server.services import progress
from sentinel.server.services import testing_types
from sentinel.server.services.repositories import TestResultRecord


def _require_fastapi():
    try:
        from fastapi.testclient import TestClient  # type: ignore
    except Exception:  # pragma: no cover
        raise unittest.SkipTest("fastapi is not installed")
    return TestClient


class TestingTypesCatalogTest(unittest.TestCase):
    def test_catalog_labels_match_extract_resolved_names(self):
        button_labels = progress._button_target_labels(
            {
                "testTargets": {
                    "text": True,
                    "macros": True,
                    "macroSteps": True,
                    "variables": {
                        "Text": True,
                        "Reversed": True,
                        "Inactive": True,
                        "Visible": True,
                        "Value": True,
                        "State": True,
                        "Command": True,
                        "Image": True,
                        "List": True,
                    },
                    "graphics": {"bitmap": True, "icon": True},
                    "pageLink": True,
                }
            }
        )
        self.assertEqual(
            button_labels,
            [
                "Text",
                "System Macro",
                "Macro Step",
                "Variable - Text",
                "Variable - Reversed",
                "Variable - Inactive",
                "Variable - Visible",
                "Variable - Value",
                "Variable - State",
                "Variable - Command",
                "Variable - Image",
                "Variable - List",
                "Bitmap",
                "Icon",
                "Page Link",
            ],
        )
        event_labels = progress._event_target_labels(
            {"userFacing": {"testTargets": {"Trigger": True, "Macro": True, "MacroStep": True}}}
        )
        self.assertEqual(event_labels, ["Event Trigger", "System Macro", "Macro Step"])
        catalog_button = [row.label for row in testing_types.CATALOG if row.family == "button"]
        catalog_event = [row.label for row in testing_types.CATALOG if row.family == "event"]
        self.assertEqual(catalog_button, button_labels)
        self.assertEqual(catalog_event, event_labels)

    def test_canonicalize_key_suffixes_used_in_resolved_targets(self):
        self.assertEqual(
            testing_types.type_id_for_target_key("btn:89:353:41392:Bitmap"),
            "button:Bitmap",
        )
        self.assertEqual(
            testing_types.type_id_for_target_key("btn:81:513:48551:Var.Reversed"),
            "button:Variable - Reversed",
        )
        self.assertEqual(
            testing_types.type_id_for_target_key("tt2:2:ROOM:23:74:20:macro:3122:Macro"),
            "button:System Macro",
        )
        self.assertEqual(
            testing_types.type_id_for_target_key("event:126:Event Trigger"),
            "event:Event Trigger",
        )
        self.assertEqual(
            testing_types.type_id_for_target_key("event:136:System Macro"),
            "event:System Macro",
        )

    def test_unknown_type_stays_enabled(self):
        self.assertTrue(testing_types.is_target_key_enabled("event:1:Command", ["button:Bitmap"]))

    def test_default_payload_all_on(self):
        payload = testing_types.settings_payload(project_id="p1", disabled_types=[])
        self.assertEqual(payload["offBehavior"], "exclude")
        self.assertEqual(payload["disabledTypes"], [])
        self.assertTrue(all(row["enabled"] for row in payload["types"]))
        self.assertEqual(
            payload["graphicsTypeIds"],
            ["button:Bitmap", "button:Icon", "button:Variable - Image"],
        )

    def test_excluded_from_testing_message_uses_settings_plurals(self):
        self.assertEqual(
            testing_types.excluded_from_testing_message("Text"),
            "Text Labels are not included in testing",
        )
        self.assertEqual(
            testing_types.excluded_from_testing_message("text"),
            "Text Labels are not included in testing",
        )
        self.assertEqual(
            testing_types.excluded_from_testing_message("Bitmap"),
            "Bitmaps are not included in testing",
        )
        self.assertEqual(
            testing_types.excluded_from_testing_message("System Macro"),
            "System Macros are not included in testing",
        )
        self.assertEqual(
            testing_types.excluded_from_testing_message("Macro Step"),
            "Macro Steps are not included in testing",
        )
        self.assertEqual(
            testing_types.excluded_from_testing_message("Event Trigger"),
            "Event Triggers are not included in testing",
        )
        self.assertEqual(
            testing_types.excluded_from_testing_message("Page Link"),
            "Page Links are not included in testing",
        )
        self.assertEqual(
            testing_types.excluded_from_testing_message("Icon"),
            "Icons are not included in testing",
        )
        self.assertEqual(
            testing_types.excluded_from_testing_message("Variable - Reversed"),
            "Variable - Reversed are not included in testing",
        )


class TestingTypeSettingsApiTest(unittest.TestCase):
    def tearDown(self):
        cache = getattr(progress, "_RESOLVED_TARGETS_CACHE", None)
        if isinstance(cache, dict):
            cache.clear()

    def _app_with_targets(self):
        TestClient = _require_fastapi()
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        gen_root = Path(td.name) / "generated"
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
        c = client.post("/api/v1/commissioning/clients", json={"name": "Type Client"}).json()
        p = client.post(
            f"/api/v1/commissioning/clients/{c['clientId']}/projects",
            json={"name": "Type Job"},
        ).json()
        project_id = p["projectId"]
        project_dir = gen_root / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        project_data = {
            "events": {
                "system": [
                    {
                        "userFacing": {"testTargets": {"Trigger": True, "Macro": True}},
                        "diagnostics": {"eventId": 126},
                    }
                ],
                "driver": [],
            },
            "devices": [
                {
                    "userFacing": {
                        "displayName": "Panel",
                        "pages": [
                            {
                                "layers": [
                                    {
                                        "buttonCategories": {
                                            "screenButtons": [
                                                {
                                                    "buttonIdentity": {
                                                        "buttonTagName": "BTN-1",
                                                        "text": "Lights",
                                                    },
                                                    "testTargets": {
                                                        "text": True,
                                                        "macros": False,
                                                        "macroSteps": False,
                                                        "variables": {},
                                                        "graphics": {"bitmap": True, "icon": False},
                                                        "pageLink": False,
                                                    },
                                                }
                                            ]
                                        }
                                    }
                                ]
                            }
                        ],
                    },
                    "diagnostics": {
                        "deviceId": 89,
                        "pages": [
                            {
                                "pageId": 353,
                                "buttons": [
                                    {
                                        "buttonId": 41392,
                                        "buttonTagName": "BTN-1",
                                        "identifiers": {"text": "Lights"},
                                    }
                                ],
                            }
                        ],
                    },
                }
            ],
        }
        (project_dir / "fixture_project_data.json").write_text(json.dumps(project_data), encoding="utf-8")
        return client, project_id

    def test_default_all_on_matches_current_required_targets(self):
        client, project_id = self._app_with_targets()
        settings = client.get(f"/api/v1/commissioning/projects/{project_id}/testing-types")
        self.assertEqual(settings.status_code, 200, settings.text)
        body = settings.json()
        self.assertEqual(body.get("offBehavior"), "exclude")
        self.assertEqual(body.get("disabledTypes"), [])
        self.assertTrue(all(row.get("enabled") for row in body.get("types") or []))

        prog = client.get(f"/api/v1/commissioning/projects/{project_id}/progress").json()
        self.assertEqual(prog["counts"]["totalTargets"], 4)
        self.assertEqual(prog["eventSections"]["system"]["counts"]["totalTargets"], 2)
        self.assertEqual(prog["devices"][0]["counts"]["totalTargets"], 2)

    def test_disable_graphics_excludes_from_progress_not_auto_pass(self):
        client, project_id = self._app_with_targets()
        tech = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"label": "Alex"},
        ).json()
        token = tech["techUrl"].split("/testing/")[1]
        bitmap_key = "btn:89:353:41392:Bitmap"
        client.post(
            f"/api/v1/testing/{token}/results",
            json={
                "target": {"targetKey": bitmap_key, "kind": "BUTTON", "targetName": "Bitmap", "refs": {}},
                "outcome": "PASS",
            },
        )

        before = client.get(f"/api/v1/commissioning/projects/{project_id}/progress").json()
        self.assertEqual(before["counts"]["totalTargets"], 4)
        self.assertEqual(before["counts"]["pass"], 1)

        put = client.put(
            f"/api/v1/commissioning/projects/{project_id}/testing-types",
            json={"disabledTypes": ["button:Bitmap", "button:Icon", "button:Variable - Image"]},
        )
        self.assertEqual(put.status_code, 200, put.text)
        self.assertEqual(put.json().get("offBehavior"), "exclude")
        self.assertIn("button:Bitmap", put.json().get("disabledTypes") or [])

        after = client.get(f"/api/v1/commissioning/projects/{project_id}/progress").json()
        self.assertEqual(after["counts"]["totalTargets"], 3)
        self.assertEqual(after["counts"]["pass"], 0)
        self.assertEqual(after["devices"][0]["counts"]["totalTargets"], 1)

        fails = client.get(f"/api/v1/commissioning/projects/{project_id}/fails").json()
        self.assertEqual(fails, [])

        snap = client.get(f"/api/v1/commissioning/projects/{project_id}/rollups").json()
        by_name = (snap.get("currentFailures") or {}).get("byTargetName") or {}
        self.assertNotIn("Bitmap", by_name)

    def test_disable_event_macro_independent_of_button_macro(self):
        client, project_id = self._app_with_targets()
        put = client.put(
            f"/api/v1/commissioning/projects/{project_id}/testing-types",
            json={"disabledTypes": ["event:System Macro"]},
        )
        self.assertEqual(put.status_code, 200, put.text)
        prog = client.get(f"/api/v1/commissioning/projects/{project_id}/progress").json()
        self.assertEqual(prog["eventSections"]["system"]["counts"]["totalTargets"], 1)
        self.assertEqual(prog["devices"][0]["counts"]["totalTargets"], 2)
        self.assertEqual(prog["counts"]["totalTargets"], 3)

    def test_settings_on_snapshots_and_ws_event(self):
        client, project_id = self._app_with_targets()
        tech = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"label": "Alex"},
        ).json()
        token = tech["techUrl"].split("/testing/")[1]
        with client.websocket_connect(f"/api/v1/testing/{token}/ws") as tech_ws:
            snap = json.loads(tech_ws.receive_text())
            self.assertEqual(snap.get("type"), "testing_snapshot")
            self.assertEqual((snap.get("testingTypeSettings") or {}).get("disabledTypes"), [])
            with client.websocket_connect(f"/api/v1/commissioning/projects/{project_id}/ws") as cws:
                _ = json.loads(cws.receive_text())
                put = client.put(
                    f"/api/v1/commissioning/projects/{project_id}/testing-types",
                    json={"disabledTypes": ["button:Bitmap"]},
                )
                self.assertEqual(put.status_code, 200, put.text)
                found_settings = False
                found_rollups = False
                for _ in range(12):
                    msg = json.loads(cws.receive_text())
                    if msg.get("type") == "testing_type_settings":
                        found_settings = True
                        self.assertEqual(msg.get("offBehavior"), "exclude")
                        self.assertIn("button:Bitmap", msg.get("disabledTypes") or [])
                    if msg.get("type") == "commissioning_rollups":
                        found_rollups = True
                        self.assertEqual((msg.get("progress") or {}).get("counts", {}).get("totalTargets"), 3)
                    if found_settings and found_rollups:
                        break
                self.assertTrue(found_settings, "commissioning WS should receive testing_type_settings")
                self.assertTrue(found_rollups, "commissioning WS should receive filtered rollups")


class TestingTypeEmbedTest(unittest.TestCase):
    def test_technician_embeds_filter_disabled_types(self):
        root = Path(__file__).resolve().parents[2]
        status_js = (root / "src" / "sentinel" / "ui" / "testing" / "sentinel_test_status_embed.js").read_text(
            encoding="utf-8"
        )
        group_js = (root / "src" / "sentinel" / "ui" / "testing" / "sentinel_group_pass_embed.js").read_text(
            encoding="utf-8"
        )
        render = (root / "src" / "sentinel" / "generation" / "render_core.py").read_text(encoding="utf-8")
        self.assertIn("filterWorkTargets", status_js)
        self.assertIn("applySettingsPayload", status_js)
        self.assertIn("pruneDisabled", group_js)
        self.assertIn("testing_type_settings", render)
        self.assertIn("workTargets(m)", render)
        html = (root / "src" / "sentinel" / "ui" / "commissioning" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="tab-settings"', html)
        self.assertIn("settings_tab.js", html)

    def test_technician_dialogue_shows_excluded_type_message(self):
        root = Path(__file__).resolve().parents[2]
        status_js = (root / "src" / "sentinel" / "ui" / "testing" / "sentinel_test_status_embed.js").read_text(
            encoding="utf-8"
        )
        render = (root / "src" / "sentinel" / "generation" / "render_core.py").read_text(encoding="utf-8")
        self.assertIn("excludedFromTestingMessage", status_js)
        self.assertIn("dialogueRowsHtml", status_js)
        self.assertIn(" are not included in testing", status_js)
        for display in (
            "Text Labels",
            "System Macros",
            "Macro Steps",
            "Event Triggers",
            "Page Links",
            "Bitmaps",
            "Icons",
        ):
            self.assertIn(display, status_js)
        self.assertIn("dialogueRowsHtml", render)
        self.assertGreaterEqual(render.count("dialogueRowsHtml"), 2)
        self.assertIn("workTargets(m)", render)

    def test_disabled_type_dialogue_html_uses_plural_message(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        root = Path(__file__).resolve().parents[2]
        embed = root / "src" / "sentinel" / "ui" / "testing" / "sentinel_test_status_embed.js"
        script = (
            "const fs=require('fs');"
            f"const src=fs.readFileSync({str(embed)!r},'utf8');"
            "const globalThis={};"
            "eval(src);"
            "const api=globalThis.__sentinelTestStatus;"
            "api.setDisabledTypeIds(['button:Text']);"
            "const mixed=api.dialogueRowsHtml({kind:'BUTTON',targets:['Text','Bitmap']},s=>String(s));"
            "const only=api.dialogueRowsHtml({kind:'BUTTON',targets:['Text']},s=>String(s));"
            "process.stdout.write(JSON.stringify({mixed:mixed,only:only}));"
        )
        proc = subprocess.run([node, "-e", script], capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        body = json.loads(proc.stdout)
        self.assertIn("Text Labels are not included in testing", body["mixed"])
        self.assertIn(">Bitmap<", body["mixed"])
        self.assertIn("Pass", body["mixed"])
        self.assertIn("Text Labels are not included in testing", body["only"])
        self.assertNotIn("Pass", body["only"])
        self.assertNotIn("Fail", body["only"])


if __name__ == "__main__":
    unittest.main()
