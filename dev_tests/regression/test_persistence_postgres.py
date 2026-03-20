import os
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


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

        client_id = queries.create_client(database_url, name="Test Client")
        project_id = queries.create_project(database_url, client_id=client_id, name="Test Project")

        clients = queries.list_clients(database_url)
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

