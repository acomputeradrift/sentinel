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


def _error_code(resp) -> str | None:
    body = resp.json()
    error = (body.get("detail") or {}).get("error") if isinstance(body.get("detail"), dict) else body.get("error")
    return (error or {}).get("code")


class ProjectTestPassTest(unittest.TestCase):
    def _app_client(self):
        TestClient = _require_fastapi()
        from sentinel.server.app.main import create_app
        from sentinel.server.services.repositories import InMemoryRepository

        repo = InMemoryRepository()
        app = create_app(repo=repo)
        return TestClient(app), repo

    def _job(self, client, *, client_name="Pass Client", project_name="Pass Job"):
        c = client.post("/api/v1/commissioning/clients", json={"name": client_name}).json()
        p = client.post(
            f"/api/v1/commissioning/clients/{c['clientId']}/projects",
            json={"name": project_name},
        ).json()
        return c, p

    def test_start_test_pass_keeps_history_and_resets_current_outcome(self):
        client, repo = self._app_client()
        _c, p = self._job(client)
        project_id = p["projectId"]
        project_name = p["name"]

        tech = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"name": "Alex"},
        ).json()
        token = str(tech["techUrl"]).split("/testing/")[1]
        target_key = "btn:1:2:3:Lights"
        target = {
            "targetKey": target_key,
            "kind": "BUTTON",
            "targetName": "Lights",
            "refs": {"deviceName": "Keypad"},
        }
        fail = client.post(
            f"/api/v1/testing/{token}/results",
            json={"target": target, "outcome": "FAIL", "failNote": "No voltage"},
        )
        self.assertEqual(fail.status_code, 200, fail.text)
        client.put(
            f"/api/v1/commissioning/projects/{project_id}/fail-tags",
            json={"targetKey": target_key, "tag": "IN_PROGRESS"},
        )

        wrong = client.post(
            f"/api/v1/commissioning/projects/{project_id}/test-passes",
            json={"confirmName": "Wrong Name", "reason": "new pass"},
        )
        self.assertEqual(wrong.status_code, 400)
        self.assertEqual(_error_code(wrong), "CONFIRM_NAME_MISMATCH")

        missing = client.post(
            f"/api/v1/commissioning/projects/{project_id}/test-passes",
            json={"reason": "new pass"},
        )
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(_error_code(missing), "CONFIRM_NAME_REQUIRED")

        started = client.post(
            f"/api/v1/commissioning/projects/{project_id}/test-passes",
            json={"confirmName": project_name, "reason": "Start over after punch list"},
        )
        self.assertEqual(started.status_code, 200, started.text)
        body = started.json()
        self.assertEqual(body.get("projectId"), project_id)
        self.assertTrue(body.get("testPassId"))
        self.assertTrue(body.get("startedAtUtc"))
        self.assertEqual((body.get("recordedBy") or {}).get("role"), "PROGRAMMER")
        self.assertEqual(body.get("reason"), "Start over after punch list")
        self.assertEqual(body.get("type"), "commissioning_snapshot")
        self.assertEqual(body.get("fails"), [])
        self.assertEqual(((body.get("progress") or {}).get("counts") or {}).get("testedTargets"), 0)

        history = repo.list_test_results_for_project(projectId=project_id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].outcome, "FAIL")
        self.assertEqual(history[0].target.get("targetKey"), target_key)

        latest = repo.get_latest_results_for_project(projectId=project_id)
        self.assertEqual(latest, {})

        status = client.get(
            f"/api/v1/testing/{token}/target-status",
            params={"targetKey": target_key},
        )
        self.assertEqual(status.status_code, 200, status.text)
        self.assertEqual(status.json().get("currentOutcome"), "UNTESTED")

        fails = client.get(f"/api/v1/commissioning/projects/{project_id}/fails")
        self.assertEqual(fails.status_code, 200)
        self.assertEqual(fails.json(), [])

        tags = repo.get_fail_tags_for_project(projectId=project_id)
        self.assertEqual(tags, {})
        archived = repo.list_fail_tag_history_for_project(projectId=project_id)
        self.assertEqual(len(archived), 1)
        self.assertEqual(archived[0].get("targetKey"), target_key)
        self.assertEqual(archived[0].get("tag"), "IN_PROGRESS")

    def test_clear_tests_alias_starts_a_pass_without_deleting_history(self):
        client, repo = self._app_client()
        _c, p = self._job(client, client_name="Alias Client", project_name="Alias Job")
        project_id = p["projectId"]
        tech = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"name": "Morgan"},
        ).json()
        token = str(tech["techUrl"]).split("/testing/")[1]
        target_key = "btn:9:8:7:Button Z"
        client.post(
            f"/api/v1/testing/{token}/results",
            json={
                "target": {
                    "targetKey": target_key,
                    "kind": "BUTTON",
                    "targetName": "Button Z",
                    "refs": {"deviceName": "Device Z"},
                },
                "outcome": "FAIL",
                "failNote": "Broken",
            },
        )
        client.put(
            f"/api/v1/commissioning/projects/{project_id}/fail-tags",
            json={"targetKey": target_key, "tag": "IN_PROGRESS"},
        )

        cleared = client.post(f"/api/v1/commissioning/projects/{project_id}/clear-tests")
        self.assertEqual(cleared.status_code, 200, cleared.text)
        payload = cleared.json()
        self.assertEqual(payload.get("projectId"), project_id)
        self.assertEqual(payload.get("type"), "commissioning_snapshot")
        self.assertEqual(payload.get("fails"), [])
        self.assertTrue(payload.get("testPassId"))

        self.assertEqual(len(repo.list_test_results_for_project(projectId=project_id)), 1)
        self.assertEqual(repo.get_latest_results_for_project(projectId=project_id), {})
        self.assertEqual(client.get(f"/api/v1/commissioning/projects/{project_id}/fails").json(), [])


if __name__ == "__main__":
    unittest.main()
