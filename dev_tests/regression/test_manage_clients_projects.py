import os
import tempfile
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


class ManageClientsProjectsTest(unittest.TestCase):
    def setUp(self):
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("SENTINEL_COMMISSIONING_API_KEY", None)

    def _app(self):
        TestClient = _require_fastapi()
        from sentinel.server.app.main import create_app
        from sentinel.server.services.repositories import InMemoryRepository

        repo = InMemoryRepository()
        app = create_app(repo=repo)
        return TestClient(app), repo

    def _client_and_project(self, client, *, client_name="Acme", project_name="Lobby"):
        created = client.post("/api/v1/commissioning/clients", json={"name": client_name})
        self.assertEqual(created.status_code, 200, created.text)
        project = client.post(
            f"/api/v1/commissioning/clients/{created.json()['clientId']}/projects",
            json={"name": project_name},
        )
        self.assertEqual(project.status_code, 200, project.text)
        return created.json(), project.json()

    def _error(self, response):
        body = response.json()
        return body["error"]["code"], body["error"]["message"]

    def test_rename_client_updates_listed_name(self):
        client, _repo = self._app()
        created, project = self._client_and_project(client)
        renamed = client.patch(
            f"/api/v1/commissioning/clients/{created['clientId']}",
            json={"name": "  Acme Homes  "},
        )
        self.assertEqual(renamed.status_code, 200, renamed.text)
        self.assertEqual(renamed.json()["name"], "Acme Homes")
        listed = client.get("/api/v1/commissioning/clients").json()
        self.assertEqual([row["name"] for row in listed], ["Acme Homes"])
        projects = client.get(
            f"/api/v1/commissioning/clients/{created['clientId']}/projects"
        ).json()
        self.assertEqual(projects[0]["projectId"], project["projectId"])
        self.assertEqual(projects[0]["name"], "Lobby")

    def test_rename_client_duplicate_name_is_conflict(self):
        client, _repo = self._app()
        self._client_and_project(client, client_name="Acme", project_name="One")
        other, _project = self._client_and_project(client, client_name="Other", project_name="Two")
        renamed = client.patch(
            f"/api/v1/commissioning/clients/{other['clientId']}",
            json={"name": "Acme"},
        )
        self.assertEqual(renamed.status_code, 409, renamed.text)
        code, message = self._error(renamed)
        self.assertEqual(code, "CLIENT_EXISTS")
        self.assertIn("already exists", message.lower())
        names = [row["name"] for row in client.get("/api/v1/commissioning/clients").json()]
        self.assertIn("Other", names)
        self.assertEqual(names.count("Acme"), 1)

    def test_rename_project_updates_listed_name(self):
        client, _repo = self._app()
        created, project = self._client_and_project(client, client_name="Acme", project_name="Lobby")
        renamed = client.patch(
            f"/api/v1/commissioning/projects/{project['projectId']}",
            json={"name": "  Great Room  "},
        )
        self.assertEqual(renamed.status_code, 200, renamed.text)
        self.assertEqual(renamed.json()["name"], "Great Room")
        projects = client.get(
            f"/api/v1/commissioning/clients/{created['clientId']}/projects"
        ).json()
        self.assertEqual(projects[0]["name"], "Great Room")
        clients = client.get("/api/v1/commissioning/clients").json()
        self.assertEqual(clients[0]["name"], "Acme")

    def test_delete_client_requires_exact_typed_name(self):
        client, repo = self._app()
        created = client.post("/api/v1/commissioning/clients", json={"name": "Acme"}).json()
        client_id = created["clientId"]
        mismatch = client.request(
            "DELETE",
            f"/api/v1/commissioning/clients/{client_id}",
            json={"confirmName": "acme"},
        )
        self.assertEqual(mismatch.status_code, 400, mismatch.text)
        code, _message = self._error(mismatch)
        self.assertEqual(code, "VALIDATION_ERROR")
        self.assertIn(client_id, {row["clientId"] for row in client.get("/api/v1/commissioning/clients").json()})
        self.assertIsNotNone(repo.get_client(clientId=client_id))

        deleted = client.request(
            "DELETE",
            f"/api/v1/commissioning/clients/{client_id}",
            json={"confirmName": "  Acme  "},
        )
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertTrue(deleted.json().get("deleted"))
        self.assertEqual(client.get("/api/v1/commissioning/clients").json(), [])
        self.assertIsNone(repo.get_client(clientId=client_id))

    def test_delete_project_requires_exact_typed_name(self):
        client, repo = self._app()
        created, project = self._client_and_project(client, client_name="Acme", project_name="Lobby")
        project_id = project["projectId"]
        mismatch = client.request(
            "DELETE",
            f"/api/v1/commissioning/projects/{project_id}",
            json={"confirmName": "lobby"},
        )
        self.assertEqual(mismatch.status_code, 400, mismatch.text)
        code, _message = self._error(mismatch)
        self.assertEqual(code, "VALIDATION_ERROR")
        still = client.get(f"/api/v1/commissioning/clients/{created['clientId']}/projects").json()
        self.assertEqual([row["projectId"] for row in still], [project_id])
        self.assertIsNotNone(repo.get_project(projectId=project_id))

        deleted = client.request(
            "DELETE",
            f"/api/v1/commissioning/projects/{project_id}",
            json={"confirmName": "  Lobby  "},
        )
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertTrue(deleted.json().get("deleted"))
        self.assertEqual(
            client.get(f"/api/v1/commissioning/clients/{created['clientId']}/projects").json(),
            [],
        )
        self.assertIsNone(repo.get_project(projectId=project_id))
        self.assertIsNotNone(repo.get_client(clientId=created["clientId"]))

    def test_delete_client_with_projects_is_refused(self):
        client, repo = self._app()
        created, project = self._client_and_project(client, client_name="Acme", project_name="Lobby")
        refused = client.request(
            "DELETE",
            f"/api/v1/commissioning/clients/{created['clientId']}",
            json={"confirmName": "Acme"},
        )
        self.assertEqual(refused.status_code, 409, refused.text)
        code, message = self._error(refused)
        self.assertEqual(code, "CLIENT_HAS_PROJECTS")
        self.assertIn("Delete the projects first", message)
        self.assertIsNotNone(repo.get_client(clientId=created["clientId"]))
        self.assertIsNotNone(repo.get_project(projectId=project["projectId"]))
        projects = client.get(
            f"/api/v1/commissioning/clients/{created['clientId']}/projects"
        ).json()
        self.assertEqual([row["name"] for row in projects], ["Lobby"])

    def test_other_user_client_and_project_stay(self):
        client, repo = self._app()
        other = repo.create_client(userId="aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb", name="Secret Co")
        job = repo.create_project(userId=other.userId, clientId=other.clientId, name="Secret Job")

        renamed_client = client.patch(
            f"/api/v1/commissioning/clients/{other.clientId}",
            json={"name": "Taken"},
        )
        self.assertEqual(renamed_client.status_code, 404, renamed_client.text)
        renamed_project = client.patch(
            f"/api/v1/commissioning/projects/{job.projectId}",
            json={"name": "Taken Job"},
        )
        self.assertEqual(renamed_project.status_code, 404, renamed_project.text)
        deleted_client = client.request(
            "DELETE",
            f"/api/v1/commissioning/clients/{other.clientId}",
            json={"confirmName": "Secret Co"},
        )
        self.assertEqual(deleted_client.status_code, 404, deleted_client.text)
        deleted_project = client.request(
            "DELETE",
            f"/api/v1/commissioning/projects/{job.projectId}",
            json={"confirmName": "Secret Job"},
        )
        self.assertEqual(deleted_project.status_code, 404, deleted_project.text)

        self.assertEqual(repo.get_client(clientId=other.clientId).name, "Secret Co")
        self.assertEqual(repo.get_project(projectId=job.projectId).name, "Secret Job")

    def test_delete_project_clears_children_disk_and_keeps_user_records(self):
        client, repo = self._app()
        created, project = self._client_and_project(client, client_name="Acme", project_name="Lobby")
        project_id = project["projectId"]
        kept_client, kept_project = self._client_and_project(
            client, client_name="Kept Client", project_name="Kept Job"
        )
        link = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"name": "Alex"},
        ).json()
        token = str(link["techUrl"]).rsplit("/testing/", 1)[-1]
        kept_link = client.post(
            f"/api/v1/commissioning/projects/{kept_project['projectId']}/tech-links",
            json={"name": "Sam"},
        ).json()
        kept_token = str(kept_link["techUrl"]).rsplit("/testing/", 1)[-1]
        repo.record_upload(
            projectId=project_id,
            uploadId="upload-1",
            originalFilename="job.apex",
            storagePath="uploads/job.apex",
        )
        repo.set_project_active_upload(projectId=project_id, uploadId="upload-1")
        repo.append_test_result(
            techToken=token,
            target={"targetKey": "btn:1:Lights", "targetKind": "BUTTON", "targetName": "Lights"},
            outcome="FAIL",
            failNote="dark",
        )
        repo.set_fail_tag(projectId=project_id, targetKey="btn:1:Lights", tag="wiring")
        repo.start_project_test_pass(
            projectId=project_id,
            recordedBy={"role": "PROGRAMMER"},
            confirmName="Lobby",
        )
        repo.set_layer_lock_state(
            projectId=project_id, scopeKey="room", layerKey="lights", visible=True, locked=False
        )
        repo.set_testing_type_disabled(projectId=project_id, disabledTypes=["button:Text"])
        repo.append_project_changelog(projectId=project_id, changelog={"status": "changed"})
        repo.put_idempotency_response(scope="testing", key="keep-me", response={"ok": True})

        from sentinel.server.services import pipeline

        with tempfile.TemporaryDirectory() as td:
            os.environ["SENTINEL_UPLOAD_ROOT"] = str(Path(td) / "uploads")
            os.environ["SENTINEL_GENERATED_ROOT"] = str(Path(td) / "generated")
            try:
                upload_dir = pipeline._project_upload_dir(projectId=project_id)
                upload_dir.mkdir(parents=True)
                (upload_dir / "job.apex").write_bytes(b"apex")
                generated_dir = pipeline._project_out_dir(projectId=project_id)
                generated_dir.mkdir(parents=True)
                (generated_dir / "home.html").write_text("<html></html>", encoding="utf-8")
                kept_upload = pipeline._project_upload_dir(projectId=kept_project["projectId"])
                kept_upload.mkdir(parents=True)
                (kept_upload / "kept.apex").write_bytes(b"kept")
                kept_generated = pipeline._project_out_dir(projectId=kept_project["projectId"])
                kept_generated.mkdir(parents=True)
                (kept_generated / "home.html").write_text("<html></html>", encoding="utf-8")

                mismatch = client.request(
                    "DELETE",
                    f"/api/v1/commissioning/projects/{project_id}",
                    json={"confirmName": "Not Lobby"},
                )
                self.assertEqual(mismatch.status_code, 400, mismatch.text)
                self.assertTrue((upload_dir / "job.apex").exists())
                self.assertTrue((generated_dir / "home.html").exists())
                self.assertIsNotNone(repo.get_project(projectId=project_id))

                deleted = client.request(
                    "DELETE",
                    f"/api/v1/commissioning/projects/{project_id}",
                    json={"confirmName": "Lobby"},
                )
                self.assertEqual(deleted.status_code, 200, deleted.text)
                self.assertFalse(upload_dir.exists())
                self.assertFalse(generated_dir.exists())
                self.assertTrue((kept_upload / "kept.apex").exists())
                self.assertTrue((kept_generated / "home.html").exists())
            finally:
                os.environ.pop("SENTINEL_UPLOAD_ROOT", None)
                os.environ.pop("SENTINEL_GENERATED_ROOT", None)

        self.assertIsNone(repo.get_project(projectId=project_id))
        self.assertEqual(repo.list_test_results_for_project(projectId=project_id), [])
        self.assertEqual(repo.get_fail_tags_for_project(projectId=project_id), {})
        self.assertEqual(repo.list_fail_tag_history_for_project(projectId=project_id), [])
        self.assertEqual(repo.list_layer_lock_states_for_project(projectId=project_id), [])
        self.assertEqual(repo.list_uploads_for_project(projectId=project_id), [])
        self.assertIsNone(repo.get_project_active_upload(projectId=project_id))
        self.assertEqual(repo.list_project_changelogs(projectId=project_id), [])
        self.assertEqual(repo.list_active_tech_links(projectId=project_id), [])
        self.assertNotIn(project_id, repo._testing_type_disabled_by_project)
        self.assertNotIn(project_id, repo._test_passes_by_project)
        self.assertFalse(any(key[0] == project_id for key in repo._first_outcome_by_project_target))
        with self.assertRaises(KeyError):
            repo.resolve_active_token(techToken=token)
        self.assertEqual(
            repo.resolve_active_token(techToken=kept_token).projectId, kept_project["projectId"]
        )
        technician_names = [tech.name for tech in repo.list_technicians(userId=repo.get_client(clientId=created["clientId"]).userId)]
        self.assertIn("Alex", technician_names)
        self.assertEqual(repo.get_idempotency_response(scope="testing", key="keep-me"), {"ok": True})
        self.assertEqual(repo.get_project(projectId=kept_project["projectId"]).name, "Kept Job")
        self.assertEqual(repo.get_client(clientId=kept_client["clientId"]).name, "Kept Client")

    def test_management_page_has_client_and_project_controls(self):
        TestClient = _require_fastapi()
        from sentinel.server.app.main import create_app

        http = TestClient(create_app())
        page = http.get("/management/")
        self.assertEqual(page.status_code, 200, page.text)
        self.assertIn('id="clientsProjectsCard"', page.text)
        self.assertIn('id="clientsProjectsList"', page.text)
        self.assertIn('id="allTechLinksByUser"', page.text)

        script = http.get("/management/management.js")
        self.assertEqual(script.status_code, 200, script.text)
        body = script.text
        self.assertIn("/commissioning/clients", body)
        self.assertIn("/commissioning/projects/", body)
        self.assertIn("PATCH", body)
        self.assertIn("DELETE", body)
        self.assertIn("confirmName", body)
        self.assertIn("Type the client name", body)
        self.assertIn("Type the project name", body)


class ManageClientsProjectsSqlTest(unittest.TestCase):
    def test_rename_client_sql_maps_unique_violation(self):
        from sentinel.server.persistence import queries

        fake_con = mock.Mock()
        cursor = mock.Mock()
        cursor.execute.side_effect = Exception(
            'duplicate key value violates unique constraint "clients_user_id_name_uq"'
        )
        fake_con.cursor.return_value = cursor

        def fetch_one(_con, sql, _params):
            self.assertIn("from clients", sql)
            self.assertIn("user_id=%s", sql)
            return {"name": "Other"}

        with mock.patch.object(queries.db, "connect", return_value=fake_con):
            with mock.patch.object(queries.db, "fetch_one", side_effect=fetch_one):
                with self.assertRaises(queries.DuplicateClientNameError):
                    queries.rename_client(
                        "postgres://example",
                        user_id="user-1",
                        client_id="client-1",
                        name="Acme",
                    )
        fake_con.rollback.assert_called()
        fake_con.commit.assert_not_called()

    def test_delete_client_sql_refuses_when_projects_exist(self):
        from sentinel.server.persistence import queries

        fake_con = mock.Mock()
        cursor = mock.Mock()
        fake_con.cursor.return_value = cursor

        def fetch_one(_con, sql, _params):
            if "from clients" in sql:
                self.assertIn("user_id=%s", sql)
                return {"name": "Acme"}
            if "from projects" in sql:
                return {"projectId": "project-1"}
            raise AssertionError(sql)

        with mock.patch.object(queries.db, "connect", return_value=fake_con):
            with mock.patch.object(queries.db, "fetch_one", side_effect=fetch_one):
                with self.assertRaises(KeyError) as raised:
                    queries.delete_client(
                        "postgres://example",
                        user_id="user-1",
                        client_id="client-1",
                        confirm_name="Acme",
                    )
        self.assertEqual(raised.exception.args[0], "CLIENT_HAS_PROJECTS")
        cursor.execute.assert_not_called()
        fake_con.commit.assert_not_called()

    def test_delete_client_sql_mismatch_deletes_nothing(self):
        from sentinel.server.persistence import queries

        fake_con = mock.Mock()
        cursor = mock.Mock()
        fake_con.cursor.return_value = cursor

        def fetch_one(_con, sql, _params):
            self.assertIn("from clients", sql)
            return {"name": "Acme"}

        with mock.patch.object(queries.db, "connect", return_value=fake_con):
            with mock.patch.object(queries.db, "fetch_one", side_effect=fetch_one):
                with self.assertRaises(KeyError) as raised:
                    queries.delete_client(
                        "postgres://example",
                        user_id="user-1",
                        client_id="client-1",
                        confirm_name="Nope",
                    )
        self.assertEqual(raised.exception.args[0], "CONFIRM_NAME_MISMATCH")
        cursor.execute.assert_not_called()
        fake_con.commit.assert_not_called()

    def test_delete_project_sql_clears_children_before_project_row(self):
        from sentinel.server.persistence import queries

        fake_con = mock.Mock()
        cursor = mock.Mock()
        fake_con.cursor.return_value = cursor

        def fetch_one(_con, sql, params):
            self.assertIn("from projects", sql)
            self.assertIn("clients", sql)
            self.assertEqual(params[0], "project-1")
            return {"name": "Lobby", "userId": "user-1"}

        with mock.patch.object(queries.db, "connect", return_value=fake_con):
            with mock.patch.object(queries.db, "fetch_one", side_effect=fetch_one):
                queries.delete_project(
                    "postgres://example",
                    user_id="user-1",
                    project_id="project-1",
                    confirm_name="  Lobby  ",
                )
        sqls = [str(call.args[0]) for call in cursor.execute.call_args_list]
        joined = "\n".join(sqls)
        fragments = [
            "active_upload_id=null",
            "recorded_by_tech_link_id=null",
            "delete from tech_link_tokens",
            "delete from tech_links",
            "delete from target_first_test_outcomes",
            "delete from test_results",
            "delete from generation_runs",
            "delete from fail_tag_history",
            "delete from project_test_passes",
            "delete from fail_tags",
            "delete from layer_lock_states",
            "delete from project_testing_type_settings",
            "delete from uploads",
            "delete from projects",
        ]
        positions = [joined.find(fragment) for fragment in fragments]
        self.assertTrue(all(pos >= 0 for pos in positions), joined)
        self.assertEqual(positions, sorted(positions), joined)
        self.assertNotIn("idempotency_keys", joined)
        self.assertNotIn("technicians", joined)
        fake_con.commit.assert_called_once()

    def test_delete_project_sql_mismatch_deletes_nothing(self):
        from sentinel.server.persistence import queries

        fake_con = mock.Mock()
        cursor = mock.Mock()
        fake_con.cursor.return_value = cursor

        with mock.patch.object(queries.db, "connect", return_value=fake_con):
            with mock.patch.object(queries.db, "fetch_one", return_value={"name": "Lobby", "userId": "user-1"}):
                with self.assertRaises(KeyError) as raised:
                    queries.delete_project(
                        "postgres://example",
                        user_id="user-1",
                        project_id="project-1",
                        confirm_name="lobby",
                    )
        self.assertEqual(raised.exception.args[0], "CONFIRM_NAME_MISMATCH")
        cursor.execute.assert_not_called()
        fake_con.commit.assert_not_called()

    def test_delete_project_sql_other_user_deletes_nothing(self):
        from sentinel.server.persistence import queries

        fake_con = mock.Mock()
        cursor = mock.Mock()
        fake_con.cursor.return_value = cursor

        with mock.patch.object(queries.db, "connect", return_value=fake_con):
            with mock.patch.object(
                queries.db, "fetch_one", return_value={"name": "Secret Job", "userId": "other-user"}
            ):
                with self.assertRaises(KeyError) as raised:
                    queries.delete_project(
                        "postgres://example",
                        user_id="user-1",
                        project_id="project-1",
                        confirm_name="Secret Job",
                    )
        self.assertEqual(raised.exception.args[0], "PROJECT_NOT_FOUND")
        cursor.execute.assert_not_called()
        fake_con.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
