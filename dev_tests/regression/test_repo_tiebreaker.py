import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class InMemoryRepositoryTieBreakerTest(unittest.TestCase):
    def test_latest_per_target_ties_break_by_test_result_id(self):
        """When recordedAtUtc ties, higher test_result_id wins (Postgres: order by recorded_at desc, id desc)."""
        from sentinel.server.services import repositories as repo_mod

        repo = repo_mod.InMemoryRepository()
        c = repo.create_client(name="Client A")
        p = repo.create_project(clientId=c.clientId, name="Project A")
        _link, tok = repo.create_tech_link(projectId=p.projectId, label="Onsite")

        old_utc_now = repo_mod.utc_now
        try:
            repo_mod.utc_now = lambda: "2026-03-19T12:05:00+00:00"

            # Same timestamp: FAIL first (id 1), PASS second (id 2) — latest must be PASS.
            repo.append_test_result(
                techToken=tok.techToken,
                target={"targetKey": "event:126:Trigger", "kind": "EVENT", "refs": {"eventId": 126}, "targetName": "Trigger"},
                outcome="FAIL",
                failNote="forced tie-breaker",
            )
            repo.append_test_result(
                techToken=tok.techToken,
                target={"targetKey": "event:126:Trigger", "kind": "EVENT", "refs": {"eventId": 126}, "targetName": "Trigger"},
                outcome="PASS",
                failNote=None,
            )
        finally:
            repo_mod.utc_now = old_utc_now

        latest = repo.get_latest_results_for_project(projectId=p.projectId)
        self.assertEqual(latest["event:126:Trigger"].outcome, "PASS")

        status = repo.get_target_status(techToken=tok.techToken, targetKey="event:126:Trigger")
        self.assertEqual(status["currentOutcome"], "PASS")
