import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMMISSIONING_JS = ROOT / "src" / "sentinel" / "ui" / "commissioning" / "commissioning.js"
COMMISSION_TAB_JS = ROOT / "src" / "sentinel" / "ui" / "commissioning" / "commission_tab.js"


class UploadTimeLabelStoreTest(unittest.TestCase):
    def test_generation_phase_applies_active_upload_only_when_present(self):
        text = COMMISSION_TAB_JS.read_text(encoding="utf-8")
        self.assertIn('t === "generation_phase"', text)
        self.assertIn("payload?.activeUpload", text)
        phase_idx = text.find('t === "generation_phase"')
        self.assertGreater(phase_idx, 0)
        chunk = text[phase_idx : phase_idx + 450]
        self.assertIn("project.activeUpload", chunk)
        self.assertIn("return state", chunk)

    def test_apply_active_upload_keeps_newer_uploaded_at(self):
        text = COMMISSIONING_JS.read_text(encoding="utf-8")
        self.assertIn("function applyActiveUpload(", text)
        self.assertIn("_uploadedAtMs", text)
        self.assertIn("prevMs > incomingMs", text)

    def test_load_file_success_dispatches_active_upload_into_store(self):
        text = COMMISSIONING_JS.read_text(encoding="utf-8")
        self.assertIn("uploadedAtUtc", text)
        self.assertIn('type: "generation"', text)
        self.assertIn("store.dispatch", text)


if __name__ == "__main__":
    unittest.main()
