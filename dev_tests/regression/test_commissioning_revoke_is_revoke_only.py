import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class CommissioningRevokeIsRevokeOnlyTest(unittest.TestCase):
    def test_console_revokes_without_rotate(self):
        js = (ROOT / "src" / "sentinel" / "ui" / "commissioning" / "commissioning.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("/tech-links", js)
        self.assertIn("/revoke", js)
        self.assertNotIn("/rotate", js)
        self.assertNotIn(".catch(() =>", js)
        revoke_idx = js.find("/revoke")
        self.assertGreater(revoke_idx, 0)
        window = js[max(0, revoke_idx - 200) : revoke_idx + 500]
        self.assertNotIn("/rotate", window)
        self.assertNotIn("catch(() =>", window)

    def test_management_revoke_does_not_fall_back_to_rotate(self):
        js = (ROOT / "src" / "sentinel" / "ui" / "management" / "management.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("/revoke", js)
        self.assertNotIn(".catch(() =>", js)
        revoke_idx = js.find("/revoke")
        self.assertGreater(revoke_idx, 0)
        window = js[max(0, revoke_idx - 200) : revoke_idx + 500]
        self.assertNotIn("/rotate", window)
        self.assertNotIn("catch(() =>", window)
