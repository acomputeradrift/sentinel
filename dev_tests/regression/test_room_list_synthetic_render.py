import sys
import unittest
from pathlib import Path


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
                "landscape": {"visible": True, "coordinates": {"left": 10, "top": 20, "width": 200, "height": 62}},
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
                "roomSelectRoomLabelTags": ["Room:Kitchen"],
                "resolvedPageLink": {"targetPageId": 2, "targetPageName": "B", "resolutionPath": []},
            },
            {
                "roomId": 2,
                "roomName": "Bedroom",
                "controllerRoomOrder": 1,
                "roomSelectTagsAll": [],
                "roomSelectRoomLabelTags": [],
                "resolvedPageLink": {"targetPageId": None, "targetPageName": None, "resolutionPath": []},
            },
        ],
    }


class RoomListSyntheticRenderingTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
