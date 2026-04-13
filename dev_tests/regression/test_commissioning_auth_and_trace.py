import os
import unittest
from pathlib import Path
import sys
import tempfile


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


class CommissioningAuthMiddlewareTest(unittest.TestCase):
    def test_commissioning_requires_key_when_env_set(self):
        TestClient = _require_fastapi()
        from sentinel.server.app.main import create_app

        secret = "test-secret-key-123"
        os.environ["SENTINEL_COMMISSIONING_API_KEY"] = secret
        try:
            app = create_app()
            client = TestClient(app)
            r = client.post("/api/v1/commissioning/clients", json={"name": "A"})
            self.assertEqual(r.status_code, 401)
            self.assertEqual(r.json()["error"]["code"], "COMMISSIONING_AUTH_REQUIRED")
            self.assertIsNotNone(r.json()["error"].get("traceId"))

            ok = client.post(
                "/api/v1/commissioning/clients",
                json={"name": "B"},
                headers={"X-Sentinel-Commissioning-Key": secret},
            )
            self.assertEqual(ok.status_code, 200)
            self.assertIn("clientId", ok.json())
        finally:
            os.environ.pop("SENTINEL_COMMISSIONING_API_KEY", None)

    def test_trace_id_on_http_error_when_key_unset(self):
        TestClient = _require_fastapi()
        from sentinel.server.app.main import create_app

        os.environ.pop("SENTINEL_COMMISSIONING_API_KEY", None)
        app = create_app()
        client = TestClient(app)
        r = client.post("/api/v1/commissioning/clients", json={"name": ""})
        self.assertEqual(r.status_code, 400)
        self.assertIsNotNone(r.json().get("error", {}).get("traceId"))


if __name__ == "__main__":
    unittest.main()
