import unittest
from pathlib import Path
import sys
from unittest import mock


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


class ManagementAllTechLinksTest(unittest.TestCase):
    def _app(self):
        TestClient = _require_fastapi()
        from sentinel.server.app.main import create_app
        from sentinel.server.services.repositories import InMemoryRepository

        repo = InMemoryRepository()
        app = create_app(repo=repo)
        return TestClient(app), repo

    def _job_via_api(self, client, *, client_name, project_name):
        created = client.post("/api/v1/commissioning/clients", json={"name": client_name}).json()
        project = client.post(
            f"/api/v1/commissioning/clients/{created['clientId']}/projects",
            json={"name": project_name},
        ).json()
        return created, project

    def test_lists_active_links_across_owners_and_revokes_one(self):
        client, repo = self._app()
        _acme, acme_job = self._job_via_api(client, client_name="Acme", project_name="Acme Job")
        acme_link = client.post(
            f"/api/v1/commissioning/projects/{acme_job['projectId']}/tech-links",
            json={"name": "Alex"},
        ).json()

        other = repo.create_client(userId="aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb", name="Other Co")
        other_job = repo.create_project(
            userId=other.userId, clientId=other.clientId, name="Other Job"
        )
        other_link, _token = repo.create_tech_link(projectId=other_job.projectId, label="Sam")

        listed = client.get("/api/v1/commissioning/tech-links")
        self.assertEqual(listed.status_code, 200, listed.text)
        rows = listed.json()
        self.assertEqual(len(rows), 2)
        by_id = {row["techLinkId"]: row for row in rows}
        self.assertIn(acme_link["techLinkId"], by_id)
        self.assertIn(other_link.techLinkId, by_id)
        acme_row = by_id[acme_link["techLinkId"]]
        other_row = by_id[other_link.techLinkId]
        self.assertEqual(acme_row["clientName"], "Acme")
        self.assertEqual(acme_row["projectName"], "Acme Job")
        self.assertEqual(acme_row["name"], "Alex")
        self.assertTrue(str(acme_row.get("techUrl") or "").startswith("/testing/"))
        self.assertEqual(other_row["clientName"], "Other Co")
        self.assertEqual(other_row["projectName"], "Other Job")
        self.assertEqual(other_row["name"], "Sam")
        self.assertNotEqual(acme_row.get("ownerUserId"), other_row.get("ownerUserId"))

        revoked = client.post(f"/api/v1/commissioning/tech-links/{other_link.techLinkId}/revoke")
        self.assertEqual(revoked.status_code, 200, revoked.text)
        self.assertTrue(revoked.json().get("revoked"))

        after = client.get("/api/v1/commissioning/tech-links").json()
        self.assertEqual([row["techLinkId"] for row in after], [acme_link["techLinkId"]])
        still = client.get(f"/api/v1/commissioning/projects/{acme_job['projectId']}/tech-links").json()
        self.assertEqual(len(still), 1)
        self.assertEqual(still[0]["techLinkId"], acme_link["techLinkId"])

    def test_revoke_unknown_link_is_404(self):
        client, _repo = self._app()
        missing = client.post("/api/v1/commissioning/tech-links/not-a-real-link/revoke")
        self.assertEqual(missing.status_code, 404, missing.text)

    def test_list_all_active_tech_links_passes_empty_params_to_fetch_all(self):
        from sentinel.server.persistence import queries

        fake_con = mock.Mock()
        with mock.patch.object(queries.db, "connect", return_value=fake_con):
            with mock.patch.object(queries.db, "fetch_all", return_value=[]) as fetch_all:
                rows = queries.list_all_active_tech_links("postgres://example")
        fetch_all.assert_called_once()
        args = fetch_all.call_args.args
        self.assertEqual(len(args), 3)
        self.assertIs(args[0], fake_con)
        self.assertIn("from tech_links", args[1])
        self.assertEqual(args[2], ())
        self.assertEqual(rows, [])
