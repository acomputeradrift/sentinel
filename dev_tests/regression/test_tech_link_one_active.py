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


class TechLinkOneActivePerNameTest(unittest.TestCase):
    def _app_client(self):
        TestClient = _require_fastapi()
        from sentinel.server.app.main import create_app
        from sentinel.server.services.repositories import InMemoryRepository

        app = create_app(repo=InMemoryRepository())
        return TestClient(app)

    def _job(self, client, *, client_name="One Active Client", project_name="One Active Job"):
        c = client.post("/api/v1/commissioning/clients", json={"name": client_name}).json()
        p = client.post(
            f"/api/v1/commissioning/clients/{c['clientId']}/projects",
            json={"name": project_name},
        ).json()
        return c, p

    def test_create_same_name_twice_reuses_active_link_and_url(self):
        client = self._app_client()
        _c, p = self._job(client)
        project_id = p["projectId"]

        first = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"name": "Alex"},
        )
        self.assertEqual(first.status_code, 200, first.text)
        first_body = first.json()
        first_url = str(first_body.get("techUrl") or "")
        self.assertTrue(first_url.startswith("/testing/"), first_url)

        second = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"name": "alex"},
        )
        self.assertEqual(second.status_code, 200, second.text)
        second_body = second.json()
        self.assertEqual(second_body["techLinkId"], first_body["techLinkId"])
        self.assertEqual(second_body["technicianId"], first_body["technicianId"])
        self.assertEqual(str(second_body.get("techUrl") or ""), first_url)

        listed = client.get(f"/api/v1/commissioning/projects/{project_id}/tech-links").json()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["techLinkId"], first_body["techLinkId"])
        self.assertEqual(str(listed[0].get("techUrl") or ""), first_url)

        token = first_url.split("/testing/")[1]
        still_open = client.get(f"/testing/{token}")
        self.assertEqual(still_open.status_code, 200, still_open.text)

    def test_create_same_technician_id_reuses_without_rotate(self):
        client = self._app_client()
        _c, p = self._job(client, client_name="Reuse Id Client", project_name="Reuse Id Job")
        project_id = p["projectId"]

        tech = client.post("/api/v1/commissioning/technicians", json={"name": "Morgan"}).json()
        first = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"technicianId": tech["technicianId"]},
        ).json()
        second = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"technicianId": tech["technicianId"]},
        ).json()
        self.assertEqual(second["techLinkId"], first["techLinkId"])
        self.assertEqual(second["techUrl"], first["techUrl"])

        listed = client.get(f"/api/v1/commissioning/projects/{project_id}/tech-links").json()
        self.assertEqual(len(listed), 1)

    def test_different_names_still_get_separate_active_links(self):
        client = self._app_client()
        _c, p = self._job(client, client_name="Two Names Client", project_name="Two Names Job")
        project_id = p["projectId"]

        alex = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"name": "Alex"},
        ).json()
        morgan = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"name": "Morgan"},
        ).json()
        self.assertNotEqual(alex["techLinkId"], morgan["techLinkId"])
        self.assertNotEqual(alex["techUrl"], morgan["techUrl"])

        listed = client.get(f"/api/v1/commissioning/projects/{project_id}/tech-links").json()
        self.assertEqual(len(listed), 2)

    def test_reuse_after_revoke_issues_a_new_active_link(self):
        client = self._app_client()
        _c, p = self._job(client, client_name="After Revoke Client", project_name="After Revoke Job")
        project_id = p["projectId"]

        first = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"name": "Riley"},
        ).json()
        old_url = first["techUrl"]
        client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links/{first['techLinkId']}/revoke"
        )

        again = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"name": "Riley"},
        ).json()
        self.assertTrue(str(again.get("techUrl") or "").startswith("/testing/"))
        self.assertNotEqual(again["techUrl"], old_url)

        listed = client.get(f"/api/v1/commissioning/projects/{project_id}/tech-links").json()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["techUrl"], again["techUrl"])

    def test_reuse_then_revoke_one_name_leaves_other_name_active(self):
        client = self._app_client()
        _c, p = self._job(client, client_name="Revoke Isolate Client", project_name="Revoke Isolate Job")
        project_id = p["projectId"]

        alex = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"name": "Alex"},
        ).json()
        morgan = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"name": "Morgan"},
        ).json()
        again = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"name": "alex"},
        ).json()
        self.assertEqual(again["techLinkId"], alex["techLinkId"])

        revoked = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links/{alex['techLinkId']}/revoke"
        )
        self.assertEqual(revoked.status_code, 200, revoked.text)

        listed = client.get(f"/api/v1/commissioning/projects/{project_id}/tech-links").json()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["techLinkId"], morgan["techLinkId"])
        self.assertEqual(listed[0]["techUrl"], morgan["techUrl"])

        alex_token = str(alex["techUrl"]).split("/testing/")[1]
        morgan_token = str(morgan["techUrl"]).split("/testing/")[1]
        self.assertEqual(client.get(f"/testing/{alex_token}").status_code, 410)
        self.assertEqual(client.get(f"/testing/{morgan_token}").status_code, 200)


class TechLinkReuseNullTechnicianIdTest(unittest.TestCase):
    def _repo_job(self, *, client_name="Null Tech Id Client", project_name="Null Tech Id Job"):
        from sentinel.server.services.commissioning_user import COMMISSIONING_STUB_USER_ID
        from sentinel.server.services.repositories import InMemoryRepository

        repo = InMemoryRepository()
        client = repo.create_client(userId=COMMISSIONING_STUB_USER_ID, name=client_name)
        project = repo.create_project(
            userId=COMMISSIONING_STUB_USER_ID, clientId=client.clientId, name=project_name
        )
        return repo, project

    def _plant_null_technician_link(self, repo, *, project_id, label):
        from sentinel.server.services.repositories import TechLink, new_uuid, utc_now

        link = TechLink(
            techLinkId=new_uuid(),
            projectId=project_id,
            label=label,
            createdAtUtc=utc_now(),
            technicianId=None,
        )
        with repo._lock:
            repo._tech_links[link.techLinkId] = link
            token = repo._issue_token_locked(projectId=project_id, techLinkId=link.techLinkId)
        return link, token

    def test_create_same_name_twice_reuses_active_link_and_token(self):
        repo, project = self._repo_job(client_name="Repo Reuse Client", project_name="Repo Reuse Job")
        first, first_token = repo.create_tech_link(projectId=project.projectId, label="Alex")
        second, second_token = repo.create_tech_link(projectId=project.projectId, label="alex")
        self.assertEqual(second.techLinkId, first.techLinkId)
        self.assertEqual(second_token.techToken, first_token.techToken)
        active = repo.list_active_tech_links(projectId=project.projectId)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].techLinkId, first.techLinkId)

    def test_reuse_then_revoke_one_name_leaves_other_name_active(self):
        repo, project = self._repo_job(
            client_name="Repo Revoke Isolate Client", project_name="Repo Revoke Isolate Job"
        )
        alex, alex_token = repo.create_tech_link(projectId=project.projectId, label="Alex")
        morgan, morgan_token = repo.create_tech_link(projectId=project.projectId, label="Morgan")
        again, again_token = repo.create_tech_link(projectId=project.projectId, label="alex")
        self.assertEqual(again.techLinkId, alex.techLinkId)
        self.assertEqual(again_token.techToken, alex_token.techToken)
        repo.revoke_tech_link(projectId=project.projectId, techLinkId=alex.techLinkId)
        active = repo.list_active_tech_links(projectId=project.projectId)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].techLinkId, morgan.techLinkId)
        self.assertEqual(repo.resolve_active_token(techToken=morgan_token.techToken).techLinkId, morgan.techLinkId)
        with self.assertRaises(KeyError):
            repo.resolve_active_token(techToken=alex_token.techToken)

    def test_create_reuses_active_null_technician_id_link_by_name(self):
        repo, project = self._repo_job()
        planted, token = self._plant_null_technician_link(
            repo, project_id=project.projectId, label="Sung"
        )
        reused, reused_token = repo.create_tech_link(projectId=project.projectId, label="sung")
        self.assertEqual(reused.techLinkId, planted.techLinkId)
        self.assertEqual(reused_token.techToken, token.techToken)
        active = repo.list_active_tech_links(projectId=project.projectId)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].techLinkId, planted.techLinkId)

    def test_revoke_one_planted_same_name_duplicate_leaves_the_other(self):
        repo, project = self._repo_job(client_name="Dup Sung Client", project_name="Dup Sung Job")
        first, _first_token = self._plant_null_technician_link(
            repo, project_id=project.projectId, label="Sung"
        )
        second, second_token = self._plant_null_technician_link(
            repo, project_id=project.projectId, label="Sung"
        )
        repo.revoke_tech_link(projectId=project.projectId, techLinkId=first.techLinkId)
        active = repo.list_active_tech_links(projectId=project.projectId)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].techLinkId, second.techLinkId)
        resolved = repo.resolve_active_token(techToken=second_token.techToken)
        self.assertEqual(resolved.techLinkId, second.techLinkId)


if __name__ == "__main__":
    unittest.main()
