import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


from sentinel.extraction import extractor_core


class ExtractorContractEnforcementTest(unittest.TestCase):
    def test_validate_contract_shape_accepts_matching_payload(self):
        contract = {
            "events": {"system": [{"userFacing": {"eventType": ""}}]},
            "devices": [{"userFacing": {"displayName": ""}}],
        }
        payload = {
            "events": {"system": [{"userFacing": {"eventType": "Sense"}}]},
            "devices": [{"userFacing": {"displayName": "iPhone"}}],
        }

        extractor_core.validate_contract_shape(contract=contract, payload=payload)

    def test_validate_contract_shape_raises_when_required_key_missing(self):
        contract = {
            "events": {"system": [{"userFacing": {"eventType": ""}}]},
            "devices": [{"userFacing": {"displayName": ""}}],
        }
        payload = {
            "events": {"system": [{"userFacing": {}}]},
            "devices": [{"userFacing": {"displayName": "iPhone"}}],
        }

        with self.assertRaises(ValueError):
            extractor_core.validate_contract_shape(contract=contract, payload=payload)


if __name__ == "__main__":
    unittest.main()
