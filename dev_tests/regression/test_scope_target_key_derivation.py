import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.server.services import progress


class ScopeTargetKeyDerivationTest(unittest.TestCase):
    def test_scoped_uiitem_key_uses_category_when_label_missing(self):
        button = {
            "buttonCategory": "UI Item",
            "apexScopeSource": {
                "page": {"pageId": 513, "roomId": 23, "sourceDeviceId": 74, "rtiAddress": 2},
                "viewportLayer": {"layerId": 300, "sharedLayerId": 700, "roomId": 23, "sourceId": 74},
                "pageLayer": {"roomId": None, "sourceId": None},
                "button": {"buttonId": 48552, "buttonTagId": None},
                "bindings": {"macroIds": [], "variableIds": [], "macroStepIds": [], "pageLinkId": None},
            },
        }

        scoped = progress._scoped_target_key_from_button(button=button, label="")
        self.assertEqual(scoped, "tt_ui:2:SHARED:700:48552:UI Item")

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
        self.assertIn("tt2:2:ROOM:23:74:20:macro:3122:System Macro", expected)
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
        self.assertIn("tt2:2:ROOM:2:88:20:macro:3122:System Macro", expected)
        self.assertNotIn("tt2:2:ROOM:23:74:20:macro:3122:System Macro", expected)

    def test_macrostep_scope_key_falls_back_to_macro_id_when_macrostep_ids_absent(self):
        button = {
            "apexScopeSource": {
                "page": {"pageId": 513, "roomId": 23, "sourceDeviceId": 74, "rtiAddress": 2},
                "viewportLayer": {"layerId": 300, "sharedLayerId": 700, "roomId": 23, "sourceId": 74},
                "pageLayer": {"roomId": None, "sourceId": None},
                "button": {"buttonId": 48551, "buttonTagId": 20},
                "bindings": {"macroIds": [3122], "variableIds": [], "macroStepIds": [], "pageLinkId": None},
            },
        }

        scoped = progress._scoped_target_key_from_button(button=button, label="Macro Step")
        self.assertEqual(scoped, "tt2:2:ROOM:23:74:20:mstepmacro:3122:Macro Step")

    def test_direct_page_link_uses_device_tag_scope_not_layer_source(self):
        base_scope = {
            "page": {"pageId": 11, "deviceId": 6, "roomId": 1, "sourceDeviceId": 10, "rtiAddress": 1},
            "viewportLayer": {"layerId": 80, "sharedLayerId": 39, "roomId": None, "sourceId": 10},
            "pageLayer": {"roomId": None, "sourceId": None},
            "button": {"buttonId": 349, "buttonTagId": 1},
            "bindings": {"macroIds": [], "variableIds": [], "macroStepIds": [], "pageLinkId": 9},
        }
        cable_tv = {
            "resolvedPageLink": {
                "targetPageId": 2,
                "targetPageName": "Home",
                "resolutionPath": "directPageLink",
            },
            "apexScopeSource": dict(base_scope),
        }
        home_page = {
            "resolvedPageLink": dict(cable_tv["resolvedPageLink"]),
            "apexScopeSource": {
                **base_scope,
                "page": {**base_scope["page"], "pageId": 2, "sourceDeviceId": 7},
                "viewportLayer": {**base_scope["viewportLayer"], "layerId": 3, "sourceId": 7},
            },
        }
        key_a = progress._scoped_target_key_from_button(button=cable_tv, label="Page Link")
        key_b = progress._scoped_target_key_from_button(button=home_page, label="Page Link")
        self.assertEqual(key_a, "tt2_pagelink:6:1:Page Link")
        self.assertEqual(key_b, key_a)

    def test_macrostep_page_link_keeps_tt2_scope(self):
        button = {
            "resolvedPageLink": {
                "targetPageId": 521,
                "targetPageName": "AppleTV 1",
                "resolutionPath": "macroStep",
            },
            "apexScopeSource": {
                "page": {"pageId": 518, "deviceId": 81, "roomId": 6, "sourceDeviceId": 74, "rtiAddress": 2},
                "viewportLayer": {"layerId": 300, "sharedLayerId": 700, "roomId": 6, "sourceId": 74},
                "pageLayer": {"roomId": None, "sourceId": None},
                "button": {"buttonId": 50245, "buttonTagId": 20},
                "bindings": {"macroIds": [5940], "variableIds": [], "macroStepIds": [], "pageLinkId": None},
            },
        }
        scoped = progress._scoped_target_key_from_button(button=button, label="Page Link")
        self.assertEqual(scoped, "tt2:2:ROOM:6:74:20:none:Page Link")


if __name__ == "__main__":
    unittest.main()
