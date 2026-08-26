import json
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


class TestResultSourceAndBatchTest(unittest.TestCase):
    def _client_and_token(self):
        TestClient = _require_fastapi()
        from sentinel.server.app.main import create_app
        from sentinel.server.services.repositories import InMemoryRepository

        repo = InMemoryRepository()
        app = create_app(repo=repo)
        client = TestClient(app)
        c = client.post("/api/v1/commissioning/clients", json={"name": "Client Source"}).json()
        p = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Project Source"}).json()
        tech = client.post(f"/api/v1/commissioning/projects/{p['projectId']}/tech-links", json={"label": "Onsite"}).json()
        token = str(tech.get("techUrl") or "").split("/")[-1]
        return client, repo, p["projectId"], token

    def test_http_individual_default_and_selection_source_persist_in_history(self):
        client, repo, project_id, token = self._client_and_token()
        first = client.post(
            f"/api/v1/testing/{token}/results",
            json={
                "target": {"targetKey": "btn:1:2:3:Text", "targetName": "Text", "kind": "BUTTON", "refs": {"pageName": "Home"}},
                "outcome": "PASS",
                "source": "SELECTION_PASS_ALL",
                "sourceDetail": {"selectionId": "abc", "pageName": "Home", "pageId": 2, "buttonCount": 4, "targetCount": 1},
            },
        )
        self.assertEqual(first.status_code, 200)
        body = first.json()
        self.assertEqual(body.get("source"), "SELECTION_PASS_ALL")
        self.assertEqual((body.get("sourceDetail") or {}).get("selectionId"), "abc")

        second = client.post(
            f"/api/v1/testing/{token}/results",
            json={
                "target": {"targetKey": "btn:1:2:3:Text", "targetName": "Text", "kind": "BUTTON", "refs": {"pageName": "Home"}},
                "outcome": "PASS",
            },
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json().get("source"), "INDIVIDUAL")

        latest = repo.get_latest_results_for_project(projectId=project_id)
        rec = latest["btn:1:2:3:Text"]
        self.assertEqual(rec.outcome, "PASS")
        self.assertEqual(rec.source, "INDIVIDUAL")

        history = repo._results_by_project_target[(project_id, "btn:1:2:3:Text")]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].source, "SELECTION_PASS_ALL")
        self.assertEqual(history[1].source, "INDIVIDUAL")

        from sentinel.server.api.commissioning_snapshots import activities_from_latest

        acts = activities_from_latest(latest_results=latest)
        self.assertEqual(acts[0].get("source"), "INDIVIDUAL")

    def test_ws_batch_publishes_each_result_with_selection_source(self):
        client, repo, project_id, token = self._client_and_token()
        with client.websocket_connect(f"/api/v1/testing/{token}/ws") as ws:
            ws.send_text(
                json.dumps(
                    {
                        "type": "test_result.submit_batch",
                        "results": [
                            {
                                "target": {"targetKey": "btn:1:2:3:Text", "targetName": "Text", "kind": "BUTTON", "refs": {"pageName": "Home", "buttonName": "A"}},
                                "outcome": "PASS",
                                "source": "SELECTION_PASS_ALL",
                                "sourceDetail": {"selectionId": "sel-1", "pageName": "Home", "buttonCount": 2, "targetCount": 2},
                            },
                            {
                                "target": {"targetKey": "btn:1:2:4:Text", "targetName": "Text", "kind": "BUTTON", "refs": {"pageName": "Home", "buttonName": "B"}},
                                "outcome": "PASS",
                                "source": "SELECTION_PASS_ALL",
                                "sourceDetail": {"selectionId": "sel-1", "pageName": "Home", "buttonCount": 2, "targetCount": 2},
                            },
                        ],
                    }
                )
            )
            got = {}
            for _ in range(40):
                raw = ws.receive_text()
                msg = json.loads(raw)
                if not isinstance(msg, dict):
                    continue
                t = msg.get("type")
                if t == "test_result":
                    got[str(msg.get("targetKey") or "")] = msg
                elif t == "test_result.submit_batch.ok":
                    got["ack"] = msg
                if "btn:1:2:3:Text" in got and "btn:1:2:4:Text" in got and "ack" in got:
                    break
            else:
                self.fail(f"Did not receive batch results and ack, got keys={list(got)}")
            self.assertEqual(got["btn:1:2:3:Text"].get("source"), "SELECTION_PASS_ALL")
            self.assertEqual(got["btn:1:2:4:Text"].get("source"), "SELECTION_PASS_ALL")
            self.assertEqual((got["btn:1:2:3:Text"].get("sourceDetail") or {}).get("selectionId"), "sel-1")
            self.assertEqual(got["ack"].get("accepted"), 2)

        latest = repo.get_latest_results_for_project(projectId=project_id)
        self.assertEqual(latest["btn:1:2:3:Text"].source, "SELECTION_PASS_ALL")
        self.assertEqual(latest["btn:1:2:4:Text"].source, "SELECTION_PASS_ALL")

    def test_http_batch_and_button_pass_all_source(self):
        client, repo, project_id, token = self._client_and_token()
        resp = client.post(
            f"/api/v1/testing/{token}/results-batch",
            json={
                "results": [
                    {
                        "target": {"targetKey": "btn:9:1:1:Text", "targetName": "Text", "kind": "BUTTON"},
                        "outcome": "PASS",
                        "source": "BUTTON_PASS_ALL",
                        "sourceDetail": {"buttonCount": 1, "targetCount": 2},
                    },
                    {
                        "target": {"targetKey": "btn:9:1:1:Page Link", "targetName": "Page Link", "kind": "BUTTON"},
                        "outcome": "PASS",
                        "source": "BUTTON_PASS_ALL",
                        "sourceDetail": {"buttonCount": 1, "targetCount": 2},
                    },
                ]
            },
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body.get("accepted"), 2)
        self.assertEqual(body["results"][0].get("source"), "BUTTON_PASS_ALL")
        latest = repo.get_latest_results_for_project(projectId=project_id)
        self.assertEqual(latest["btn:9:1:1:Text"].source, "BUTTON_PASS_ALL")

    def test_batch_fail_without_note_is_rejected(self):
        client, _repo, _project_id, token = self._client_and_token()
        resp = client.post(
            f"/api/v1/testing/{token}/results-batch",
            json={
                "results": [
                    {
                        "target": {"targetKey": "btn:1:2:3:Text", "targetName": "Text", "kind": "BUTTON"},
                        "outcome": "FAIL",
                    }
                ]
            },
        )
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
