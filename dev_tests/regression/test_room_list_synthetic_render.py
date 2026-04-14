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

    def test_slot_rects_uses_apex_row_height_when_it_fits(self):
        rects = render_core._room_list_row_slot_rects(0, 0, 100, 100, 3, 2, row_height_px=20)
        self.assertEqual(len(rects), 3)
        self.assertTrue(all(r[3] == 20 for r in rects))
        self.assertEqual(rects[0][1], 0)
        self.assertEqual(rects[1][1], 22)
        self.assertEqual(rects[2][1], 44)

    def test_slot_rects_keeps_rti_height_when_it_overflows_host_box(self):
        """RTI row height must not collapse back to divide-by-n when the stack is taller than the host."""
        thin = render_core._room_list_row_slot_rects(0, 0, 100, 30, 3, 2, row_height_px=None)
        self.assertTrue(all(r[3] < 20 for r in thin))
        fixed = render_core._room_list_row_slot_rects(0, 0, 100, 30, 3, 2, row_height_px=20)
        self.assertEqual(len(fixed), 3)
        self.assertTrue(all(r[3] == 20 for r in fixed))

    def test_list_row_height_px_triples_apex_list_item_height(self):
        btn = {"buttonUI": {"listItemHeightPx": 10}}
        self.assertEqual(render_core._list_row_height_px_from_host(btn), 30)

    def test_sorted_diag_source_rows_filters_unchecked_and_respects_scope(self):
        diag = _minimal_diag()
        scoped = render_core._sorted_diag_source_rows(diag, 1)
        self.assertEqual([int(r["sourceDeviceId"]) for r in scoped], [4])
        unscoped = render_core._sorted_diag_source_rows(diag, None)
        self.assertEqual(sorted(int(r["sourceDeviceId"]) for r in unscoped), [4, 6])
        self.assertEqual(render_core._sorted_diag_source_rows(diag, 0), unscoped)

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
        synthetic_z = int(m.group(1))
        native = re.search(r"<div class='btn-wrap' style='z-index:(\d+);'[^>]*data-button-tag='DISPLAY - Room List'", html)
        self.assertIsNotNone(native)
        self.assertGreater(synthetic_z, int(native.group(1)))

    def test_synthetic_room_rows_share_one_z_index(self):
        """All rows in a synthetic room list use the same composite z (no per-row ladder)."""
        p2 = {"pageName": "B", "pageId": 2, "rtiAddress": 99, "layers": []}
        device = {"userFacing": {"displayName": "DeviceA", "pages": [_minimal_list_host_page(), p2]}, "diagnostics": _minimal_diag()}
        project = {"devices": [device]}
        app_ui = render_core.load_json(ROOT / "src" / "sentinel" / "contracts" / "app_ui_structure.json")
        payload = render_core._page_payload(project, app_ui, "sample", 0, 0, "portrait", resolved_targets=None)
        html = payload["page_button_rows"]
        zs = [int(m.group(1)) for m in re.finditer(r"<div class='btn-wrap' style='z-index:(\d+);'[^>]*data-synthetic-room-list='1'", html)]
        self.assertGreaterEqual(len(zs), 2)
        self.assertEqual(len(set(zs)), 1)

    def test_synthetic_rows_do_not_escape_host_layer_ordering(self):
        page = _minimal_list_host_page()
        page["layers"][1]["buttonCategories"]["screenButtons"] = [
            {
                "buttonIdentity": {"buttonTagName": "Top Action", "text": "Top", "buttonType": None},
                "buttonUI": {
                    "fontSize": 12,
                    "orientations": {
                        "portrait": {"visible": True, "coordinates": {"left": 8, "top": 8, "width": 88, "height": 28}},
                        "landscape": {"visible": True, "coordinates": {"left": 8, "top": 8, "width": 88, "height": 28}},
                    },
                    # stack.layerOrder is intentionally wrong to verify owner layer order wins.
                    "stack": {"layerOrder": 0, "buttonOrder": 1, "frameNumber": 0},
                },
                "testTargets": {
                    "text": True,
                    "macros": False,
                    "macroSteps": False,
                    "variables": {k: False for k in ("Text", "Reversed", "Inactive", "Visible", "Value", "State", "Command", "Image", "List")},
                    "graphics": {"bitmap": False, "icon": False},
                    "pageLink": False,
                },
            }
        ]
        p2 = {"pageName": "B", "pageId": 2, "rtiAddress": 99, "layers": []}
        device = {"userFacing": {"displayName": "DeviceA", "pages": [page, p2]}, "diagnostics": _minimal_diag()}
        project = {"devices": [device]}
        app_ui = render_core.load_json(ROOT / "src" / "sentinel" / "contracts" / "app_ui_structure.json")
        payload = render_core._page_payload(project, app_ui, "sample", 0, 0, "portrait", resolved_targets=None)
        html = payload["page_button_rows"]
        synthetic = re.search(r"<div class='btn-wrap' style='z-index:(\d+);'[^>]*data-synthetic-room-id='1'", html)
        top_native = re.search(r"<div class='btn-wrap' style='z-index:(\d+);'[^>]*data-button-tag='Top Action'", html)
        self.assertIsNotNone(synthetic)
        self.assertIsNotNone(top_native)
        self.assertLess(int(synthetic.group(1)), int(top_native.group(1)))

    def test_higher_layer_always_beats_lower_layer_even_with_large_button_order(self):
        page = _minimal_list_host_page()
        page["layers"][0]["buttonCategories"]["screenButtons"].append(
            {
                "buttonIdentity": {"buttonTagName": "Lower Huge", "text": "Lower Huge", "buttonType": None},
                "buttonUI": {
                    "fontSize": 12,
                    "orientations": {
                        "portrait": {"visible": True, "coordinates": {"left": 30, "top": 30, "width": 120, "height": 30}},
                        "landscape": {"visible": True, "coordinates": {"left": 30, "top": 30, "width": 120, "height": 30}},
                    },
                    "stack": {"layerOrder": 0, "buttonOrder": 50_000, "frameNumber": 0},
                },
                "testTargets": {
                    "text": True,
                    "macros": False,
                    "macroSteps": False,
                    "variables": {k: False for k in ("Text", "Reversed", "Inactive", "Visible", "Value", "State", "Command", "Image", "List")},
                    "graphics": {"bitmap": False, "icon": False},
                    "pageLink": False,
                },
            }
        )
        page["layers"][1]["buttonCategories"]["screenButtons"].append(
            {
                "buttonIdentity": {"buttonTagName": "Upper Small", "text": "Upper Small", "buttonType": None},
                "buttonUI": {
                    "fontSize": 12,
                    "orientations": {
                        "portrait": {"visible": True, "coordinates": {"left": 40, "top": 40, "width": 120, "height": 30}},
                        "landscape": {"visible": True, "coordinates": {"left": 40, "top": 40, "width": 120, "height": 30}},
                    },
                    "stack": {"layerOrder": 9, "buttonOrder": 1, "frameNumber": 0},
                },
                "testTargets": {
                    "text": True,
                    "macros": False,
                    "macroSteps": False,
                    "variables": {k: False for k in ("Text", "Reversed", "Inactive", "Visible", "Value", "State", "Command", "Image", "List")},
                    "graphics": {"bitmap": False, "icon": False},
                    "pageLink": False,
                },
            }
        )
        p2 = {"pageName": "B", "pageId": 2, "rtiAddress": 99, "layers": []}
        device = {"userFacing": {"displayName": "DeviceA", "pages": [page, p2]}, "diagnostics": _minimal_diag()}
        project = {"devices": [device]}
        app_ui = render_core.load_json(ROOT / "src" / "sentinel" / "contracts" / "app_ui_structure.json")
        payload = render_core._page_payload(project, app_ui, "sample", 0, 0, "portrait", resolved_targets=None)
        html = payload["page_button_rows"]
        lower = re.search(r"<div class='btn-wrap' style='z-index:(\d+);'[^>]*data-button-tag='Lower Huge'", html)
        upper = re.search(r"<div class='btn-wrap' style='z-index:(\d+);'[^>]*data-button-tag='Upper Small'", html)
        self.assertIsNotNone(lower)
        self.assertIsNotNone(upper)
        self.assertLess(int(lower.group(1)), int(upper.group(1)))

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
        # Room 1 scope: checked activities only (Player 4); Family 5 is unchecked in fixture.
        self.assertIn("data-synthetic-source-device-id='4'", html)
        self.assertNotIn("data-synthetic-source-device-id='5'", html)
        self.assertNotIn("data-synthetic-source-device-id='6'", html)
        self.assertIn('"sourceDeviceId": 4', html)

    def test_page_payload_global_source_list_emits_all_checked_rooms(self):
        """No apex scope (or room 0): emit every checked source row; client filters by selected room."""
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
        }
        global_page = {
            "pageName": "Camera Overview",
            "pageId": 3,
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
        p2 = {"pageName": "B", "pageId": 2, "rtiAddress": 99, "layers": []}
        device = {"userFacing": {"displayName": "DeviceA", "pages": [global_page, p2]}, "diagnostics": _minimal_diag()}
        project = {"devices": [device]}
        app_ui = render_core.load_json(ROOT / "src" / "sentinel" / "contracts" / "app_ui_structure.json")
        payload = render_core._page_payload(project, app_ui, "sample", 0, 0, "portrait", resolved_targets=None)
        html = payload["page_button_rows"]
        self.assertIn("data-synthetic-source-list='1'", html)
        self.assertIn("data-synthetic-source-room-id='1'", html)
        self.assertIn("data-synthetic-source-room-id='2'", html)
        self.assertIn("data-synthetic-source-device-id='4'", html)
        self.assertNotIn("data-synthetic-source-device-id='5'", html)
        self.assertIn("data-synthetic-source-device-id='6'", html)

    def test_page_payload_includes_selected_room_runtime_indicator(self):
        p2 = {"pageName": "B", "pageId": 2, "rtiAddress": 99, "layers": []}
        device = {
            "userFacing": {"displayName": "DeviceA", "pages": [_minimal_source_list_host_page(), p2]},
            "diagnostics": _minimal_diag(),
        }
        project = {"devices": [device]}
        app_ui = render_core.load_json(ROOT / "src" / "sentinel" / "contracts" / "app_ui_structure.json")
        html = render_core.render_single_device_html(project, app_ui, "sample", device_index=0, resolved_targets=None)
        self.assertIn("id='selectedRoomIndicator'", html)
        self.assertIn("Selected Room:", html)
        self.assertIn("function setSelectedRoom(", html)
        self.assertIn("function applySelectedRoomToSourceRows(", html)


if __name__ == "__main__":
    unittest.main()
