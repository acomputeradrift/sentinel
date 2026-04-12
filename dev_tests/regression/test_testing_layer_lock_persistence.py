import unittest


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

        set_resp = client.post(
            f"/api/v1/testing/{tech_token}/layer-locks",
            json={"scopeKey": "project::device::page", "layerKey": "layer-1", "visible": False, "locked": True},
        )
        self.assertEqual(set_resp.status_code, 200, set_resp.text)
        get_resp = client.get(
            f"/api/v1/testing/{tech_token}/layer-locks",
            params={"scopeKey": "project::device::page"},
        )
        self.assertEqual(get_resp.status_code, 200, get_resp.text)
        data = get_resp.json()
        self.assertIn("locks", data)
        self.assertEqual(len(data["locks"]), 1)
        self.assertEqual(data["locks"][0]["scopeKey"], "project::device::page")
        self.assertEqual(data["locks"][0]["layerKey"], "layer-1")
        self.assertEqual(data["locks"][0]["visible"], False)
        self.assertEqual(data["locks"][0]["locked"], True)


if __name__ == "__main__":
    unittest.main()
