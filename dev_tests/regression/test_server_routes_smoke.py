import unittest
from pathlib import Path
import sys
import tempfile


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


class ServerRoutesSmokeTest(unittest.TestCase):
    def test_commissioning_and_testing_flow(self):
        TestClient = _require_fastapi()

        import os

        from sentinel.server.services import pipeline

        with tempfile.TemporaryDirectory() as td:
            os.environ["SENTINEL_UPLOAD_ROOT"] = str(Path(td) / "uploads")
            os.environ["SENTINEL_GENERATED_ROOT"] = str(Path(td) / "generated")

            calls: dict[str, object] = {"regen_called": False}
            original_regen = pipeline.regenerate_project

            def _regen_stub(*, projectId: str, apex_path: Path) -> dict:  # noqa: ARG001
                calls["regen_called"] = True
                return {"projectId": projectId, "outDir": str(Path(td) / "generated" / projectId), "projectData": "stub"}

            pipeline.regenerate_project = _regen_stub  # type: ignore[assignment]
            try:
                from sentinel.server.app.main import create_app

                app = create_app()
                client = TestClient(app)

                c = client.post("/api/v1/commissioning/clients", json={"name": "Client A"}).json()
                self.assertIn("clientId", c)

                p = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Project A"}).json()
                self.assertIn("projectId", p)
                self.assertEqual(p["clientId"], c["clientId"])

                with client.stream("GET", f"/api/v1/commissioning/projects/{p['projectId']}/events") as sse:
                    self.assertEqual(sse.status_code, 200)
                    self.assertIn("text/event-stream", sse.headers.get("content-type", ""))
                    first = next(sse.iter_text())
                    self.assertIn(": connected", first)

                up = client.post(
                    f"/api/v1/commissioning/projects/{p['projectId']}/upload-and-regenerate",
                    files={"apex": ("Project A v1.apex", b"not-a-real-apex", "application/octet-stream")},
                )
                self.assertEqual(up.status_code, 200)
                upj = up.json()
                self.assertIn("uploadId", upj)
                self.assertEqual(upj["originalFilename"], "Project A v1.apex")
                self.assertEqual(upj["generation"]["status"], "READY")
                self.assertIn("storagePath", upj)
                self.assertEqual(calls["regen_called"], True)

                link = client.post(f"/api/v1/commissioning/projects/{p['projectId']}/tech-links", json={"label": "Onsite"}).json()
                self.assertIn("techLinkId", link)
                self.assertIn("techUrl", link)

                links = client.get(f"/api/v1/commissioning/projects/{p['projectId']}/tech-links").json()
                self.assertEqual(len(links), 1)
                self.assertEqual(links[0]["techLinkId"], link["techLinkId"])
                self.assertEqual(links[0]["label"], "Onsite")
                self.assertIn("createdAtUtc", links[0])

                token = client.post(f"/api/v1/commissioning/projects/{p['projectId']}/tech-links/{link['techLinkId']}/rotate").json()
                tech_url = token["techUrl"]
                self.assertTrue(tech_url.startswith("/testing/"))
                tech_token = tech_url.split("/testing/")[1]

                html = client.get(f"/testing/{tech_token}")
                self.assertEqual(html.status_code, 200)
                self.assertIn("text/html", html.headers.get("content-type", ""))

                revoke = client.post(f"/api/v1/commissioning/projects/{p['projectId']}/tech-links/{link['techLinkId']}/revoke").json()
                self.assertEqual(revoke["techLinkId"], link["techLinkId"])

                links2 = client.get(f"/api/v1/commissioning/projects/{p['projectId']}/tech-links").json()
                self.assertEqual(links2, [])

                revoked_html = client.get(f"/testing/{tech_token}")
                self.assertEqual(revoked_html.status_code, 410)
                self.assertEqual(revoked_html.json()["error"]["code"], "TECH_LINK_REVOKED")

                fail = client.post(
                    f"/api/v1/testing/{tech_token}/results",
                    json={
                        "target": {"targetKey": "event:126:Trigger", "kind": "EVENT", "refs": {"eventId": 126}, "targetName": "Trigger"},
                        "outcome": "FAIL",
                        "failNote": "",
                    },
                )
                self.assertEqual(fail.status_code, 400)
                self.assertEqual(fail.json()["error"]["code"], "FAIL_NOTE_REQUIRED")

                ok = client.post(
                    f"/api/v1/testing/{tech_token}/results",
                    json={
                        "target": {"targetKey": "event:126:Trigger", "kind": "EVENT", "refs": {"eventId": 126}, "targetName": "Trigger"},
                        "outcome": "PASS",
                        "failNote": None,
                    },
                )
                self.assertEqual(ok.status_code, 200)
                self.assertEqual(ok.json()["outcome"], "PASS")

                status = client.get(f"/api/v1/testing/{tech_token}/target-status", params={"targetKey": "event:126:Trigger"}).json()
                self.assertEqual(status["currentOutcome"], "PASS")
            finally:
                pipeline.regenerate_project = original_regen  # type: ignore[assignment]

