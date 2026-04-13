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


class PostResultIdempotencyTest(unittest.TestCase):
    def test_duplicate_idempotency_key_returns_same_test_result_id(self):
        TestClient = _require_fastapi()
        from sentinel.server.app.main import create_app

        app = create_app()
        client = TestClient(app)

        c = client.post("/api/v1/commissioning/clients", json={"name": "Idem Client"}).json()
        p = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "P"}).json()
        link = client.post(f"/api/v1/commissioning/projects/{p['projectId']}/tech-links", json={"label": "T"}).json()
        token = str(link["techUrl"]).split("/testing/")[1]

        payload = {
            "target": {"targetKey": "event:1:X", "kind": "EVENT", "refs": {"eventId": 1}, "targetName": "X"},
            "outcome": "PASS",
            "failNote": None,
        }
        headers = {"Idempotency-Key": "idem-1"}
        a = client.post(f"/api/v1/testing/{token}/results", json=payload, headers=headers).json()
        b = client.post(f"/api/v1/testing/{token}/results", json=payload, headers=headers).json()
        self.assertEqual(a["testResultId"], b["testResultId"])

        c2 = client.post(f"/api/v1/testing/{token}/results", json=payload, headers={"Idempotency-Key": "idem-2"}).json()
        self.assertNotEqual(a["testResultId"], c2["testResultId"])


if __name__ == "__main__":
    unittest.main()
