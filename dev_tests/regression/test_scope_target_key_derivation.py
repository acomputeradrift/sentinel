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
                                                        "viewportLayer": {"layerId": 300, "sharedLayerId": 700, "roomId": 23, "sourceId": 74},
                                                        "pageLayer": {"roomId": None, "sourceId": None},
                                                        "button": {"buttonId": 48551, "buttonTagId": 20},
                                                        "bindings": {"macroIds": [3122], "variableIds": [], "macroStepIds": [5921], "pageLinkId": None},
                                                    },
                                                },
                                                {
                                                    "buttonIdentity": {"buttonTagName": None, "text": "UI Item", "buttonType": None},
                                                    "testTargets": {"text": True, "macros": False, "macroSteps": False, "variables": {}, "pageLink": False},
                                                    "apexScopeSource": {
                                                        "page": {"pageId": 513, "roomId": 23, "sourceDeviceId": 74, "rtiAddress": 2},
                                                        "viewportLayer": {"layerId": 300, "sharedLayerId": 700, "roomId": 23, "sourceId": 74},
                                                        "pageLayer": {"roomId": None, "sourceId": None},
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

    def test_viewport_target_uses_viewport_then_page_layer_then_page_scope(self):
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
                                            "screenButtons": [],
                                            "hardButtons": [],
                                            "uiItems": [],
                                        },
                                        "viewports": [
                                            {
                                                "viewportIdentity": {"viewportButtonId": 9001},
                                                "layers": [
                                                    {
                                                        "layerName": "Viewport Child",
                                                        "layerOrder": 0,
                                                        "frames": [
                                                            {
                                                                "frameId": 0,
                                                                "buttonCategories": {
                                                                    "screenLabels": [],
                                                                    "screenButtons": [
                                                                        {
                                                                            "buttonIdentity": {
                                                                                "buttonTagName": "VP-TAG",
                                                                                "text": "",
                                                                                "buttonType": None,
                                                                            },
                                                                            "testTargets": {
                                                                                "text": False,
                                                                                "macros": True,
                                                                                "macroSteps": False,
                                                                                "variables": {},
                                                                                "pageLink": False,
                                                                            },
                                                                            "apexScopeSource": {
                                                                                "page": {
                                                                                    "pageId": 513,
                                                                                    "roomId": 23,
                                                                                    "sourceDeviceId": 74,
                                                                                    "rtiAddress": 2,
                                                                                },
                                                                                "viewportLayer": {
                                                                                    "layerId": 300,
                                                                                    "sharedLayerId": 700,
                                                                                    "roomId": None,
                                                                                    "sourceId": None,
                                                                                },
                                                                                "pageLayer": {
                                                                                    "roomId": 2,
                                                                                    "sourceId": 88,
                                                                                },
                                                                                "button": {"buttonId": 48551, "buttonTagId": 20},
                                                                                "bindings": {
                                                                                    "macroIds": [3122],
                                                                                    "variableIds": [],
                                                                                    "macroStepIds": [],
                                                                                    "pageLinkId": None,
                                                                                },
                                                                            },
                                                                        }
                                                                    ],
                                                                    "hardButtons": [],
                                                                    "uiItems": [],
                                                                },
                                                            }
                                                        ],
                                                    }
                                                ],
                                            }
                                        ],
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
                                "buttons": [],
                                "viewports": [
                                    {
                                        "viewportButtonId": 9001,
                                        "frames": [
                                            {
                                                "frameId": 0,
                                                "buttons": [
                                                    {
                                                        "buttonId": 48551,
                                                        "buttonTagName": "VP-TAG",
                                                        "identifiers": {"text": ""},
                                                    }
                                                ],
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    },
                }
            ]
        }

        devices = progress._derive_device_targets(project_data)
        self.assertEqual(len(devices), 1)
        expected = set(devices[0]["expected"])
        # viewportLayer room/source are null, so fallback must use pageLayer (2/88), not page (23/74)
        self.assertIn("tt2:2:ROOM:2:88:20:macro:3122:Macro", expected)
        self.assertNotIn("tt2:2:ROOM:23:74:20:macro:3122:Macro", expected)


if __name__ == "__main__":
    unittest.main()
