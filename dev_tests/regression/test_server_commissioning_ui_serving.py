import sys
import unittest
from pathlib import Path


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


class CommissioningUiServingTest(unittest.TestCase):
    def test_commissioning_ui_is_served(self):
        TestClient = _require_fastapi()

        from sentinel.server.app.main import create_app

        app = create_app()
        client = TestClient(app)

        r = client.get("/commissioning/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/html", r.headers.get("content-type", ""))
        self.assertIn("Sentinel Console", r.text)

        js = client.get("/commissioning/commissioning.js")
        self.assertEqual(js.status_code, 200)
        self.assertIn("javascript", js.headers.get("content-type", ""))
