import sys
import unittest
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.generation import render_core


def _minimal_list_host_page() -> dict:
    list_btn = {
        "buttonIdentity": {"buttonTagName": "DISPLAY - Room List", "text": "", "buttonType": None},
        "buttonUI": {
            "fontSize": 12,
            "orientations": {
                "portrait": {"visible": True, "coordinates": {"left": 10, "top": 20, "width": 200, "height": 62}},
                "landscape": {"visible": True, "coordinates": {"left": 110, "top": 120, "width": 220, "height": 70}},
            },
            "stack": {"layerOrder": 0, "buttonOrder": 1, "frameNumber": 0},
        },
        "testTargets": {
            "text": False,
            "macros": False,
            "macroSteps": False,
            "variables": {
                k: (k == "List")
                for k in ("Text", "Reversed", "Inactive", "Visible", "Value", "State", "Command", "Image", "List")
            },
            "graphics": {"bitmap": False, "icon": False},
            "pageLink": False,
        },
    }
    return {
        "pageName": "Controller",
        "pageId": 1,
        "rtiAddress": 99,
        "layers": [
            {
                "layerName": "Main",
                "layerOrder": 0,
                "sharedLayerId": 0,
                "buttonCategories": {
                    "screenLabels": [],
                    "screenButtons": [list_btn],
                    "hardButtons": [],
                    "uiItems": [],
                },
                "viewports": [],
            },
            {
                "layerName": "TopChrome",
                "layerOrder": 9,
                "sharedLayerId": 0,
                "buttonCategories": {
                    "screenLabels": [],
                    "screenButtons": [],
                    "hardButtons": [],
                    "uiItems": [],
                },
                "viewports": [],
            },
        ],
    }


def _minimal_source_list_host_page() -> dict:
    list_btn = {
        "buttonIdentity": {"buttonTagName": "DISPLAY - Source List", "text": "", "buttonType": None},
        "buttonUI": {
            "fontSize": 12,
            "orientations": {
                "portrait": {"visible": True, "coordinates": {"left": 40, "top": 30, "width": 220, "height": 70}},
                "landscape": {"visible": True, "coordinates": {"left": 140, "top": 130, "width": 260, "height": 90}},
            },
            "stack": {"layerOrder": 0, "buttonOrder": 7, "frameNumber": 0},
        },
        "testTargets": {
            "text": False,
            "macros": False,
            "macroSteps": False,
            "variables": {k: (k == "List") for k in ("Text", "Reversed", "Inactive", "Visible", "Value", "State", "Command", "Image", "List")},
            "graphics": {"bitmap": False, "icon": False},
            "pageLink": False,
        },
        "apexScopeSource": {
            "page": {"pageId": 1, "roomId": 1, "sourceDeviceId": 4, "rtiAddress": 99},
            "viewportLayer": {"layerId": 0, "sharedLayerId": 0, "roomId": None, "sourceId": None},
            "pageLayer": {"roomId": None, "sourceId": None},
            "button": {"buttonId": 16, "buttonTagId": 511},
            "bindings": {"macroIds": [], "variableIds": [], "macroStepIds": [], "pageLinkId": None},
        },
    }
    return {
        "pageName": "Controller",
        "pageId": 1,
        "rtiAddress": 99,
        "layers": [
            {
                "layerName": "Main",
                "layerOrder": 0,
                "sharedLayerId": 0,
                "buttonCategories": {"screenLabels": [], "screenButtons": [list_btn], "hardButtons": [], "uiItems": []},
                "viewports": [],
            }
        ],
    }


def _minimal_diag() -> dict:
    return {
        "deviceId": 1,
        "pages": [
            {"pageId": 1, "buttons": [], "viewports": []},
            {"pageId": 2, "buttons": [], "viewports": []},
        ],
        "rooms": [
            {
                "roomId": 1,
                "roomName": "Kitchen",
                "controllerRoomOrder": 0,
                "roomSelectTagsAll": [],
                "roomSelectRoomLabelTags": [{"buttonTagId": 1082, "buttonTagName": "Room: Kitchen", "macroId": 731}],
                "resolvedPageLink": {"targetPageId": 2, "targetPageName": "B", "resolutionPath": []},
            },
            {
                "roomId": 2,
                "roomName": "Bedroom",
                "controllerRoomOrder": 1,
                "roomSelectTagsAll": [],
                "roomSelectRoomLabelTags": [{"buttonTagId": 1083, "buttonTagName": "Room: Bedroom", "macroId": 732}],
                "resolvedPageLink": {"targetPageId": None, "targetPageName": None, "resolutionPath": []},
            },
        ],
        "sourceListRows": [
            {
                "roomId": 1,
                "roomName": "Kitchen",
                "sourceDeviceId": 4,
                "sourceName": "Player",
                "activityOrder": 0,
                "checked": 1,
                "resolvedPageLink": {"targetPageId": 2, "targetPageName": "B", "resolutionPath": "activityEvent"},
            },
            {
                "roomId": 1,
                "roomName": "Kitchen",
                "sourceDeviceId": 5,
                "sourceName": "Family",
                "activityOrder": 1,
                "checked": 0,
                "resolvedPageLink": {"targetPageId": None, "targetPageName": None, "resolutionPath": None},
            },
            {
                "roomId": 2,
                "roomName": "Bedroom",
                "sourceDeviceId": 6,
                "sourceName": "Bedroom TV",
                "activityOrder": 0,
                "checked": 1,
                "resolvedPageLink": {"targetPageId": None, "targetPageName": None, "resolutionPath": None},
            },
        ],
    }


class RoomListSyntheticRenderingTest(unittest.TestCase):
    def _synthetic_attrs_by_room(self, html: str, room_id: str) -> str:
        for m in re.finditer(r"<div class='btn-wrap'([^>]*)>", html):
            attrs = m.group(1)
            if f"data-synthetic-room-id='{room_id}'" in attrs:
                return attrs
        self.fail(f"synthetic room row {room_id} not found")

    def test_slot_rects_splits_height_with_gaps(self):
        rects = render_core._room_list_row_slot_rects(0, 0, 100, 30, 2, 2)
        self.assertEqual(len(rects), 2)
        self.assertEqual(rects[0][3] + 2 + rects[1][3], 30)

    def test_page_payload_emits_synthetic_room_buttons(self):
        p2 = {
            "pageName": "B",
            "pageId": 2,
            "rtiAddress": 99,
            "layers": [],
        }
        device = {
            "userFacing": {
                "displayName": "DeviceA",
                "pages": [_minimal_list_host_page(), p2],
            },
            "diagnostics": _minimal_diag(),
        }
        project = {"devices": [device]}
        app_ui = render_core.load_json(ROOT / "src" / "sentinel" / "contracts" / "app_ui_structure.json")
        payload = render_core._page_payload(
            project,
            app_ui,
            "sample",
            0,
            0,
            "portrait",
            resolved_targets=None,
        )
        html = payload["page_button_rows"]
        self.assertIn("data-synthetic-room-list='1'", html)
        self.assertIn("Kitchen", html)
        self.assertIn("Bedroom", html)
        self.assertIn("page-link-hit", html)

    def test_synthetic_rows_use_orientation_specific_coordinates(self):
        p2 = {"pageName": "B", "pageId": 2, "rtiAddress": 99, "layers": []}
        device = {"userFacing": {"displayName": "DeviceA", "pages": [_minimal_list_host_page(), p2]}, "diagnostics": _minimal_diag()}
        project = {"devices": [device]}
        app_ui = render_core.load_json(ROOT / "src" / "sentinel" / "contracts" / "app_ui_structure.json")
        payload = render_core._page_payload(project, app_ui, "sample", 0, 0, "portrait", resolved_targets=None)
        html = payload["page_button_rows"]
        attrs = self._synthetic_attrs_by_room(html, "1")
        self.assertIn("data-p-left='10'", attrs)
        self.assertIn("data-l-left='110'", attrs)

    def test_synthetic_rows_use_host_layer_z_index(self):
        p2 = {"pageName": "B", "pageId": 2, "rtiAddress": 99, "layers": []}
        device = {"userFacing": {"displayName": "DeviceA", "pages": [_minimal_list_host_page(), p2]}, "diagnostics": _minimal_diag()}
        project = {"devices": [device]}
        app_ui = render_core.load_json(ROOT / "src" / "sentinel" / "contracts" / "app_ui_structure.json")
        payload = render_core._page_payload(project, app_ui, "sample", 0, 0, "portrait", resolved_targets=None)
        html = payload["page_button_rows"]
        m = re.search(r"<div class='btn-wrap' style='z-index:(\d+);'[^>]*data-synthetic-room-id='1'", html)
        self.assertIsNotNone(m)
        self.assertEqual(int(m.group(1)), 100)

    def test_synthetic_rows_carry_room_specific_scope_identity(self):
        p2 = {"pageName": "B", "pageId": 2, "rtiAddress": 99, "layers": []}
        device = {"userFacing": {"displayName": "DeviceA", "pages": [_minimal_list_host_page(), p2]}, "diagnostics": _minimal_diag()}
        project = {"devices": [device]}
        app_ui = render_core.load_json(ROOT / "src" / "sentinel" / "contracts" / "app_ui_structure.json")
        payload = render_core._page_payload(project, app_ui, "sample", 0, 0, "portrait", resolved_targets=None)
        html = payload["page_button_rows"]
        self.assertIn('"roomId": 1', html)
        self.assertIn('"roomId": 2', html)
        self.assertIn('"buttonTagId": 1082', html)
        self.assertIn('"buttonTagId": 1083', html)
        self.assertIn("data-synthetic-room-tag-id='1082'", html)
        self.assertIn("data-synthetic-room-tag-id='1083'", html)

    def test_page_payload_emits_scoped_synthetic_source_rows(self):
        p2 = {"pageName": "B", "pageId": 2, "rtiAddress": 99, "layers": []}
        device = {
            "userFacing": {"displayName": "DeviceA", "pages": [_minimal_source_list_host_page(), p2]},
            "diagnostics": _minimal_diag(),
        }
        project = {"devices": [device]}
        app_ui = render_core.load_json(ROOT / "src" / "sentinel" / "contracts" / "app_ui_structure.json")
        payload = render_core._page_payload(project, app_ui, "sample", 0, 0, "portrait", resolved_targets=None)
        html = payload["page_button_rows"]
        self.assertIn("data-synthetic-source-list='1'", html)
        self.assertIn("data-synthetic-source-room-id='1'", html)
        self.assertIn("data-synthetic-source-device-id='4'", html)
        self.assertIn("data-synthetic-source-device-id='5'", html)
        self.assertNotIn("data-synthetic-source-device-id='6'", html)
        self.assertIn('"sourceDeviceId": 4', html)
        self.assertIn('"sourceDeviceId": 5', html)


if __name__ == "__main__":
    unittest.main()
