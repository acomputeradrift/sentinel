import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.server.services import progress


class ScopeTargetKeyDerivationTest(unittest.TestCase):
    def test_derive_device_targets_uses_scope_keys_when_apex_scope_source_present(self):
        project_data = {
            "devices": [
                {
                    "userFacing": {
                        "displayName": "Device A",
                        "pages": [
                            {
                                "pageName": "Home",
                                "layers": [
                                    {
                                        "layerName": "Main",
                                        "layerOrder": 0,
                                        "buttonCategories": {
                                            "screenLabels": [],
                                            "screenButtons": [
                                                {
                                                    "buttonIdentity": {"buttonTagName": "TAG-1", "text": "", "buttonType": None},
                                                    "testTargets": {"text": False, "macros": True, "macroSteps": False, "variables": {}, "pageLink": False},
                                                    "apexScopeSource": {
                                                        "page": {"pageId": 513, "roomId": 23, "sourceDeviceId": 74, "rtiAddress": 2},
                                                        "layer": {"layerId": 300, "sharedLayerId": 700, "roomId": 23, "sourceId": 74},
                                                        "button": {"buttonId": 48551, "buttonTagId": 20},
                                                        "bindings": {"macroIds": [3122], "variableIds": [], "macroStepIds": [5921], "pageLinkId": None},
                                                    },
                                                },
                                                {
                                                    "buttonIdentity": {"buttonTagName": None, "text": "UI Item", "buttonType": None},
                                                    "testTargets": {"text": True, "macros": False, "macroSteps": False, "variables": {}, "pageLink": False},
                                                    "apexScopeSource": {
                                                        "page": {"pageId": 513, "roomId": 23, "sourceDeviceId": 74, "rtiAddress": 2},
                                                        "layer": {"layerId": 300, "sharedLayerId": 700, "roomId": 23, "sourceId": 74},
                                                        "button": {"buttonId": 48552, "buttonTagId": None},
                                                        "bindings": {"macroIds": [], "variableIds": [], "macroStepIds": [], "pageLinkId": None},
                                                    },
                                                },
                                            ],
                                            "hardButtons": [],
                                            "uiItems": [],
                                        },
                                        "viewports": [],
                                    }
                                ],
                            }
                        ],
                    },
                    "diagnostics": {
                        "deviceId": 81,
                        "pages": [
                            {
                                "pageId": 513,
                                "buttons": [
                                    {"buttonId": 48551, "buttonTagName": "TAG-1", "identifiers": {"text": ""}},
                                    {"buttonId": 48552, "buttonTagName": None, "identifiers": {"text": "UI Item"}},
                                ],
                                "viewports": [],
                            }
                        ],
                    },
                }
            ]
        }

        devices = progress._derive_device_targets(project_data)
        self.assertEqual(len(devices), 1)
        expected = set(devices[0]["expected"])
        self.assertIn("tt2:2:ROOM:23:74:20:macro:3122:Macro", expected)
        self.assertIn("tt_ui:2:SHARED:700:48552:Text", expected)


if __name__ == "__main__":
    unittest.main()
