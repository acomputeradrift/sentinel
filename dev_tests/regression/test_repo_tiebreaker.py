import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class InMemoryRepositoryTieBreakerTest(unittest.TestCase):
    def test_latest_per_target_ties_break_by_test_result_id(self):
        from sentinel.server.services import repositories as repo_mod

        repo = repo_mod.InMemoryRepository()
        c = repo.create_client(name="Client A")
        p = repo.create_project(clientId=c.clientId, name="Project A")
        _link, tok = repo.create_tech_link(projectId=p.projectId, label="Onsite")

        old_utc_now = repo_mod.utc_now
        old_new_uuid = repo_mod.new_uuid
        try:
            repo_mod.utc_now = lambda: "2026-03-19T12:05:00+00:00"
            ids = iter(
                [
                    "ffffffff-ffff-ffff-ffff-ffffffffffff",
                    "00000000-0000-0000-0000-000000000000",
                ]
            )
            repo_mod.new_uuid = lambda: next(ids)

            # Append order is the opposite of expected "latest" under tie-breaking.
            # Both records share the exact timestamp; higher testResultId should win.
            repo.append_test_result(
                techToken=tok.techToken,
                target={"targetKey": "event:126:Trigger", "kind": "EVENT", "refs": {"eventId": 126}, "targetName": "Trigger"},
                outcome="PASS",
                failNote=None,
            )
            repo.append_test_result(
                techToken=tok.techToken,
                target={"targetKey": "event:126:Trigger", "kind": "EVENT", "refs": {"eventId": 126}, "targetName": "Trigger"},
                outcome="FAIL",
                failNote="forced tie-breaker",
            )
        finally:
            repo_mod.utc_now = old_utc_now
            repo_mod.new_uuid = old_new_uuid

        latest = repo.get_latest_results_for_project(projectId=p.projectId)
        self.assertEqual(latest["event:126:Trigger"].outcome, "PASS")

        status = repo.get_target_status(techToken=tok.techToken, targetKey="event:126:Trigger")
        self.assertEqual(status["currentOutcome"], "PASS")

