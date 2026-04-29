import os
import unittest
from pathlib import Path
import sys
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.server.services.commissioning_user import COMMISSIONING_STUB_USER_ID


DATABASE_URL_ENV = "DATABASE_URL"


def _database_url() -> str | None:
    return os.environ.get(DATABASE_URL_ENV)


@unittest.skipIf(_database_url() is None, f"{DATABASE_URL_ENV} is not set")
class PostgresPersistenceMvpTest(unittest.TestCase):
    def test_apply_migrations(self):
        from sentinel.server.persistence import db

        db.apply_migrations(_database_url())

    def test_client_project_and_results_smoke(self):
        from sentinel.server.persistence import db, queries

        database_url = _database_url()
        assert database_url is not None

        db.apply_migrations(database_url)

        suffix = uuid4().hex
        client_id = queries.create_client(
            database_url, user_id=COMMISSIONING_STUB_USER_ID, name=f"Test Client {suffix}"
        )
        project_id = queries.create_project(database_url, client_id=client_id, name=f"Test Project {suffix}")

        clients = queries.list_clients_for_user(database_url, user_id=COMMISSIONING_STUB_USER_ID)
        self.assertTrue(any(c["clientId"] == client_id for c in clients))

        projects = queries.list_projects_for_client(database_url, client_id=client_id)
        self.assertTrue(any(p["projectId"] == project_id for p in projects))

        tech_link = queries.create_tech_link(database_url, project_id=project_id, label="Onsite Tech")
        token1 = queries.rotate_tech_link_token(database_url, tech_link_id=tech_link["techLinkId"])
        token2 = queries.rotate_tech_link_token(database_url, tech_link_id=tech_link["techLinkId"])

        self.assertNotEqual(token1["techToken"], token2["techToken"])

        resolved = queries.resolve_active_tech_token(database_url, tech_token=token2["techToken"])
        self.assertEqual(resolved["projectId"], project_id)
        self.assertEqual(resolved["techLinkId"], tech_link["techLinkId"])

        generation_run_id = queries.ensure_generation_run(database_url, project_id=project_id)
        queries.append_test_result(
            database_url,
            project_id=project_id,
            generation_run_id=generation_run_id,
            recorded_by_tech_link_id=tech_link["techLinkId"],
            target_key="event:126:Trigger",
            target_kind="EVENT",
            target_name="Trigger",
            refs={"eventId": 126},
            outcome="FAIL",
            fail_note="Did not trigger.",
        )
        queries.append_test_result(
            database_url,
            project_id=project_id,
            generation_run_id=generation_run_id,
            recorded_by_tech_link_id=tech_link["techLinkId"],
            target_key="event:126:Trigger",
            target_kind="EVENT",
            target_name="Trigger",
            refs={"eventId": 126},
            outcome="PASS",
            fail_note=None,
        )

        status = queries.get_target_status(database_url, project_id=project_id, target_key="event:126:Trigger")
        self.assertEqual(status["currentOutcome"], "PASS")

    def test_latest_target_statuses_and_failures(self):
        from sentinel.server.persistence import db, queries

        database_url = _database_url()
        assert database_url is not None

        db.apply_migrations(database_url)

        suffix = uuid4().hex
        client_id = queries.create_client(
            database_url, user_id=COMMISSIONING_STUB_USER_ID, name=f"Test Client {suffix}"
        )
        project_id = queries.create_project(database_url, client_id=client_id, name=f"Test Project {suffix}")

        tech_link = queries.create_tech_link(database_url, project_id=project_id, label="Onsite Tech")
        token = queries.rotate_tech_link_token(database_url, tech_link_id=tech_link["techLinkId"])
        resolved = queries.resolve_active_tech_token(database_url, tech_token=token["techToken"])
        self.assertEqual(resolved["projectId"], project_id)

        generation_run_id = queries.ensure_generation_run(database_url, project_id=project_id)

        # Target A ends PASS (FAIL then PASS).
        queries.append_test_result(
            database_url,
            project_id=project_id,
            generation_run_id=generation_run_id,
            recorded_by_tech_link_id=tech_link["techLinkId"],
            target_key="event:126:Trigger",
            target_kind="EVENT",
            target_name="Trigger",
            refs={"eventId": 126},
            outcome="FAIL",
            fail_note="Did not trigger.",
        )
        queries.append_test_result(
            database_url,
            project_id=project_id,
            generation_run_id=generation_run_id,
            recorded_by_tech_link_id=tech_link["techLinkId"],
            target_key="event:126:Trigger",
            target_kind="EVENT",
            target_name="Trigger",
            refs={"eventId": 126},
            outcome="PASS",
            fail_note=None,
        )

        # Target B ends FAIL.
        queries.append_test_result(
            database_url,
            project_id=project_id,
            generation_run_id=generation_run_id,
            recorded_by_tech_link_id=tech_link["techLinkId"],
            target_key="btn:81:513:48551:Macro",
            target_kind="BUTTON",
            target_name="Macro",
            refs={"deviceId": 81, "pageId": 513, "buttonId": 48551},
            outcome="FAIL",
            fail_note="Macro did not run.",
        )

        latest = queries.list_latest_target_statuses(database_url, project_id=project_id)
        self.assertEqual({r["targetKey"] for r in latest}, {"event:126:Trigger", "btn:81:513:48551:Macro"})

        by_key = {r["targetKey"]: r for r in latest}
        self.assertEqual(by_key["event:126:Trigger"]["currentOutcome"], "PASS")
        self.assertEqual(by_key["btn:81:513:48551:Macro"]["currentOutcome"], "FAIL")
        self.assertEqual(by_key["btn:81:513:48551:Macro"]["lastFailNote"], "Macro did not run.")
        self.assertEqual(by_key["btn:81:513:48551:Macro"]["recordedByTechLinkId"], tech_link["techLinkId"])
        self.assertEqual(by_key["btn:81:513:48551:Macro"]["recordedByTechLabel"], "Onsite Tech")

        failures = queries.list_latest_failed_targets(database_url, project_id=project_id)
        self.assertEqual([r["targetKey"] for r in failures], ["btn:81:513:48551:Macro"])

        # First outcome FAIL then PASS still counts as first-time fail; PASS-first does not.
        self.assertEqual(queries.count_first_time_fail_targets(database_url, project_id=project_id), 2)

    def test_active_upload_tracking_and_project_pointer(self):
        from sentinel.server.persistence import db, queries

        database_url = _database_url()
        assert database_url is not None
        db.apply_migrations(database_url)

        suffix = uuid4().hex
        client_id = queries.create_client(
            database_url, user_id=COMMISSIONING_STUB_USER_ID, name=f"Test Client {suffix}"
        )
        project_id = queries.create_project(database_url, client_id=client_id, name=f"Test Project {suffix}")

        upload_id = str(uuid4())
        queries.upsert_upload_record(
            database_url,
            project_id=project_id,
            upload_id=upload_id,
            original_filename="Project v1.apex",
            storage_path=f"/tmp/{upload_id}__Project v1.apex",
        )
        queries.set_project_active_upload(database_url, project_id=project_id, upload_id=upload_id)

        active = queries.get_project_active_upload(database_url, project_id=project_id)
        self.assertIsNotNone(active)
        assert active is not None
        self.assertEqual(active["uploadId"], upload_id)
        self.assertEqual(active["originalFilename"], "Project v1.apex")

    def test_rotate_rejects_mismatched_project(self):
        from sentinel.server.persistence import db, queries

        database_url = _database_url()
        assert database_url is not None
        db.apply_migrations(database_url)

        suffix = uuid4().hex
        client_id = queries.create_client(
            database_url, user_id=COMMISSIONING_STUB_USER_ID, name=f"Test Client {suffix}"
        )
        p1 = queries.create_project(database_url, client_id=client_id, name=f"Project A {suffix}")
        p2 = queries.create_project(database_url, client_id=client_id, name=f"Project B {suffix}")

        link = queries.create_tech_link(database_url, project_id=p1, label="Onsite Tech")
        with self.assertRaises(KeyError):
            queries.rotate_tech_link_token(database_url, tech_link_id=link["techLinkId"], project_id=p2)
