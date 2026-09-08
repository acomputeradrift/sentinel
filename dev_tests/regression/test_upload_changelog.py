import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _coords(*, top=0, left=0, height=40, width=80):
    return {"top": top, "left": left, "height": height, "width": width}


def _test_targets(**overrides):
    payload = {
        "text": False,
        "macros": True,
        "macroSteps": False,
        "variables": {},
        "graphics": {"bitmap": False, "icon": False, "rtspVideo": False},
        "pageLink": False,
    }
    payload.update(overrides)
    return payload


def _button(
    *,
    button_id,
    tag,
    text="",
    page_id=110,
    device_id=57,
    test_targets=None,
    portrait=None,
    landscape=None,
    layer_order=0,
    button_order=0,
    macro_ids=None,
    variable_ids=None,
    page_link_id=None,
    target_page_id=None,
):
    ident_text = text or tag
    resolved = None
    if target_page_id is not None:
        resolved = {"targetPageId": target_page_id, "targetPageName": "Dest"}
    return {
        "buttonIdentity": {"buttonTagName": tag, "text": ident_text, "buttonType": "regular"},
        "buttonUI": {
            "fontSize": 12,
            "orientations": {
                "portrait": {"visible": True, "coordinates": portrait or _coords(left=15)},
                "landscape": {"visible": True, "coordinates": landscape or _coords(left=100)},
            },
            "stack": {"layerOrder": layer_order, "buttonOrder": button_order, "frameNumber": 0},
        },
        "testTargets": test_targets if test_targets is not None else _test_targets(),
        "resolvedPageLink": resolved,
        "apexScopeSource": {
            "page": {"pageId": page_id, "deviceId": device_id},
            "button": {"buttonId": button_id, "buttonTagId": 1},
            "bindings": {
                "macroIds": list(macro_ids or [12]),
                "variableIds": list(variable_ids or []),
                "macroStepIds": [],
                "pageLinkId": page_link_id,
            },
        },
    }


def _project(
    *,
    buttons,
    device_id=57,
    device_name="RTiPanel (Simple)",
    page_id=110,
    page_name="Cameras (Overview) v2",
    viewport_layers=None,
    viewport_button_id=11483,
    viewport_tag="VIEWPORT - Cameras",
    place_buttons="page",
):
    host = _button(button_id=viewport_button_id, tag=viewport_tag, page_id=page_id, device_id=device_id)
    vp_layers_spec = list(viewport_layers or [])
    if place_buttons == "viewport" and not vp_layers_spec:
        vp_layers_spec = [(0, "Feeds")]
    page_buttons = [] if place_buttons == "viewport" else list(buttons)
    frame_buttons = list(buttons) if place_buttons == "viewport" else []
    frame_payload = []
    if frame_buttons:
        frame_payload = [
            {
                "frameId": 0,
                "buttonCategories": {
                    "screenLabels": [],
                    "screenButtons": frame_buttons,
                    "hardButtons": [],
                    "emptyTag": [],
                    "uiItems": [],
                },
            }
        ]
    viewport = {
        "viewportIdentity": {"viewportButtonId": viewport_button_id},
        "viewportUI": {"navigationMode": "page", "orientations": host["buttonUI"]["orientations"]},
        "layers": [
            {
                "layerName": name,
                "layerOrder": order,
                "frames": frame_payload if index == 0 else [],
            }
            for index, (order, name) in enumerate(vp_layers_spec)
        ],
    }
    return {
        "source": {"extractedAtUtc": "2026-01-01T00:00:00Z", "file": "ignored.apex"},
        "devices": [
            {
                "userFacing": {
                    "displayName": device_name,
                    "pages": [
                        {
                            "pageName": page_name,
                            "layers": [
                                {
                                    "layerName": "Page",
                                    "layerOrder": 0,
                                    "buttonCategories": {
                                        "screenLabels": [],
                                        "screenButtons": [host, *page_buttons],
                                        "hardButtons": [],
                                        "emptyTag": [],
                                        "uiItems": [],
                                    },
                                    "viewports": [viewport] if vp_layers_spec else [],
                                }
                            ],
                        }
                    ],
                },
                "diagnostics": {
                    "deviceId": device_id,
                    "displayName": device_name,
                    "pages": [{"pageId": page_id, "pageName": page_name}],
                },
            }
        ],
        "events": {"system": [], "driver": []},
    }


def _resolved(*, keys, device_id=57, device_name="RTiPanel (Simple)"):
    return {
        "format": "sentinel-resolved-targets-v1",
        "events": {"system": [], "driver": []},
        "devices": [{"deviceId": device_id, "displayName": device_name, "expected": list(keys)}],
    }


class UploadChangelogBuilderTest(unittest.TestCase):
    def test_added_and_removed_target_keys_are_testable(self):
        from sentinel.server.services import upload_changelog

        old_btn = _button(button_id=10, tag="NAV - Go to CAMERA 1")
        new_btn = _button(button_id=10, tag="NAV - Go to CAMERA 1")
        old = _project(buttons=[old_btn])
        new = _project(buttons=[new_btn])
        doc = upload_changelog.build_changelog(
            old_project_data=old,
            new_project_data=new,
            old_resolved=_resolved(keys=["tt2:57:110:10:Macro"]),
            new_resolved=_resolved(keys=["tt2:57:110:11:Macro"]),
            previous_filename="old.apex",
            current_filename="new.apex",
        )
        self.assertEqual(doc["status"], "ok")
        self.assertTrue(any("added" in line.lower() for line in doc["testable"]))
        self.assertTrue(any("removed" in line.lower() for line in doc["testable"]))
        self.assertEqual(doc["layoutOnly"], [])

    def test_test_target_flag_and_binding_changes_are_testable(self):
        from sentinel.server.services import upload_changelog

        old_btn = _button(button_id=20, tag="Lights", test_targets=_test_targets(macros=True), macro_ids=[12])
        new_btn = _button(button_id=20, tag="Lights", test_targets=_test_targets(macros=False), macro_ids=[99])
        doc = upload_changelog.build_changelog(
            old_project_data=_project(buttons=[old_btn]),
            new_project_data=_project(buttons=[new_btn]),
            old_resolved=_resolved(keys=[]),
            new_resolved=_resolved(keys=[]),
            previous_filename="v1.apex",
            current_filename="v2.apex",
        )
        joined = " ".join(doc["testable"]).lower()
        self.assertEqual(doc["status"], "ok")
        self.assertIn(
            "rTiPanel (Simple) / Cameras (Overview) v2 / Page / Screen Button / Lights".lower(),
            joined,
        )
        self.assertTrue("test target" in joined or "binding" in joined)
        self.assertEqual(doc["layoutOnly"], [])

    def test_coordinate_and_layer_order_changes_are_layout_only(self):
        from sentinel.server.services import upload_changelog

        old_btn = _button(
            button_id=11514,
            tag="NAV - Go to CAMERA 1",
            portrait=_coords(left=15),
            landscape=_coords(left=100),
        )
        new_btn = _button(
            button_id=11514,
            tag="NAV - Go to CAMERA 1",
            portrait=_coords(left=14),
            landscape=_coords(left=100),
        )
        old = _project(
            buttons=[old_btn],
            viewport_layers=[(1, "Loading"), (2, "Feeds"), (3, "Select")],
        )
        new = _project(
            buttons=[new_btn],
            viewport_layers=[(0, "Loading"), (1, "Feeds"), (2, "Select")],
        )
        doc = upload_changelog.build_changelog(
            old_project_data=old,
            new_project_data=new,
            old_resolved=_resolved(keys=["tt2:57:110:11514:Macro"]),
            new_resolved=_resolved(keys=["tt2:57:110:11514:Macro"]),
            previous_filename="1790 High Rd (Simple v28).apex",
            current_filename="1790 High Rd (Simple v29).apex",
        )
        self.assertEqual(doc["status"], "ok")
        self.assertEqual(doc["testable"], [])
        self.assertEqual(
            doc["heading"],
            "Change Log (1790 High Rd (Simple v28).apex -> 1790 High Rd (Simple v29).apex)",
        )
        self.assertIn(
            "RTiPanel (Simple) / Cameras (Overview) v2 / Page / Screen Button / NAV - Go to CAMERA 1: moved 1 px (portrait left 15 → 14)",
            doc["layoutOnly"],
        )
        self.assertIn(
            "RTiPanel (Simple) / Cameras (Overview) v2 / Page / VIEWPORT - Cameras: layer order 1, 2, 3 → 0, 1, 2 (Loading, Feeds, Select). Relative stack unchanged.",
            doc["layoutOnly"],
        )

    def test_viewport_frame_button_includes_viewport_in_path(self):
        from sentinel.server.services import upload_changelog

        old_btn = _button(
            button_id=99,
            tag="POWER OFF - All TOGGLE",
            portrait=_coords(left=1062),
            landscape=_coords(left=100),
        )
        new_btn = _button(
            button_id=99,
            tag="POWER OFF - All TOGGLE",
            portrait=_coords(left=1022),
            landscape=_coords(left=100),
        )
        doc = upload_changelog.build_changelog(
            old_project_data=_project(buttons=[old_btn], place_buttons="viewport"),
            new_project_data=_project(buttons=[new_btn], place_buttons="viewport"),
            old_resolved=_resolved(keys=[]),
            new_resolved=_resolved(keys=[]),
            previous_filename="v1.apex",
            current_filename="v2.apex",
        )
        self.assertEqual(doc["status"], "ok")
        self.assertEqual(
            doc["layoutOnly"],
            [
                "RTiPanel (Simple) / Cameras (Overview) v2 / Feeds / Frame 1 / Screen Button / POWER OFF - All TOGGLE: moved 40 px (portrait left 1062 → 1022)"
            ],
        )

    def test_first_file_and_no_changes(self):
        from sentinel.server.services import upload_changelog

        btn = _button(button_id=1, tag="Home")
        project = _project(buttons=[btn])
        resolved = _resolved(keys=["tt2:57:110:1:Macro"])
        first = upload_changelog.build_changelog(
            old_project_data=None,
            new_project_data=project,
            old_resolved=None,
            new_resolved=resolved,
            previous_filename="",
            current_filename="first.apex",
        )
        self.assertEqual(first["status"], "first_file")
        self.assertIn("previous file", first["emptyMessage"].lower())
        self.assertEqual(first["testable"], [])
        self.assertEqual(first["layoutOnly"], [])

        same = upload_changelog.build_changelog(
            old_project_data=project,
            new_project_data=project,
            old_resolved=resolved,
            new_resolved=resolved,
            previous_filename="same.apex",
            current_filename="same.apex",
        )
        self.assertEqual(same["status"], "no_changes")
        self.assertIn("no changes", same["emptyMessage"].lower())

    def test_display_heading_prefixes_upload_timestamp(self):
        from sentinel.server.services import upload_changelog

        heading = upload_changelog.display_heading(
            previous_filename="1790 High Rd (Simple v28).apex",
            current_filename="1790 High Rd (Simple v29).apex",
            uploaded_at_utc="2026-09-08T16:20:00Z",
        )
        self.assertEqual(
            heading,
            "2026-09-08 16:20:00Z Change Log (1790 High Rd (Simple v28).apex -> 1790 High Rd (Simple v29).apex)",
        )

    def test_builder_exception_is_fail_soft(self):
        from sentinel.server.services import upload_changelog

        with mock.patch.object(upload_changelog, "build_changelog", side_effect=RuntimeError("boom")):
            doc = upload_changelog.safe_build_changelog(
                old_project_data={},
                new_project_data={},
                old_resolved={},
                new_resolved={},
                previous_filename="a.apex",
                current_filename="b.apex",
            )
        self.assertEqual(doc["status"], "error")
        self.assertTrue(doc["emptyMessage"])

    def test_stage_writer_survives_builder_exception(self):
        from sentinel.server.services import upload_changelog

        with tempfile.TemporaryDirectory() as td:
            old_dir = Path(td) / "old"
            stage_dir = Path(td) / "stage"
            old_dir.mkdir()
            stage_dir.mkdir()
            (old_dir / "x_project_data.json").write_text("{}", encoding="utf-8")
            (stage_dir / "x_project_data.json").write_text("{}", encoding="utf-8")
            with mock.patch.object(upload_changelog, "build_changelog", side_effect=ValueError("nope")):
                doc = upload_changelog.write_stage_changelog(
                    old_dir=old_dir,
                    stage_dir=stage_dir,
                    previous_filename="old.apex",
                    current_filename="new.apex",
                )
            self.assertEqual(doc["status"], "error")
            written = json.loads((stage_dir / "upload_changelog.json").read_text(encoding="utf-8"))
            self.assertEqual(written["status"], "error")


class UploadChangelogPersistTest(unittest.TestCase):
    def test_inmemory_active_upload_changelog_round_trips_on_snapshot(self):
        from sentinel.server.api.commissioning_snapshots import active_upload_payload
        from sentinel.server.services.commissioning_user import COMMISSIONING_STUB_USER_ID
        from sentinel.server.services.repositories import InMemoryRepository

        repo = InMemoryRepository()
        client = repo.create_client(userId=COMMISSIONING_STUB_USER_ID, name="Changelog Client")
        project = repo.create_project(
            userId=COMMISSIONING_STUB_USER_ID, clientId=client.clientId, name="Changelog Job"
        )
        upload = repo.record_upload(
            projectId=project.projectId,
            uploadId="up-1",
            originalFilename="v29.apex",
            storagePath="/tmp/v29.apex",
        )
        repo.set_project_active_upload(projectId=project.projectId, uploadId=upload.uploadId)
        changelog = {
            "status": "ok",
            "heading": "Change Log (v28.apex -> v29.apex)",
            "previousFilename": "v28.apex",
            "currentFilename": "v29.apex",
            "emptyMessage": None,
            "testable": [],
            "layoutOnly": ["RTiPanel (Simple) / Cameras (Overview) v2 / NAV - Go to CAMERA 1: moved 1 px"],
            "testableOmitted": 0,
            "layoutOnlyOmitted": 0,
        }
        repo.set_upload_changelog(uploadId=upload.uploadId, changelog=changelog)
        payload = active_upload_payload(repo=repo, projectId=project.projectId)
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["changelog"]["heading"], changelog["heading"])
        self.assertEqual(payload["changelog"]["layoutOnly"], changelog["layoutOnly"])
        self.assertEqual(payload["changelogHistory"], [])

    def test_changelog_history_survives_upload_prune(self):
        from sentinel.server.api.commissioning_snapshots import active_upload_payload
        from sentinel.server.services.commissioning_user import COMMISSIONING_STUB_USER_ID
        from sentinel.server.services.repositories import InMemoryRepository

        repo = InMemoryRepository()
        client = repo.create_client(userId=COMMISSIONING_STUB_USER_ID, name="History Client")
        project = repo.create_project(
            userId=COMMISSIONING_STUB_USER_ID, clientId=client.clientId, name="History Job"
        )
        first = repo.record_upload(
            projectId=project.projectId,
            uploadId="up-old",
            originalFilename="v28.apex",
            storagePath="/tmp/v28.apex",
        )
        repo.set_project_active_upload(projectId=project.projectId, uploadId=first.uploadId)
        older = {
            "status": "ok",
            "heading": "2026-09-07 11:00:00Z Change Log (v27.apex -> v28.apex)",
            "previousFilename": "v27.apex",
            "currentFilename": "v28.apex",
            "uploadedAtUtc": "2026-09-07T11:00:00Z",
            "testable": [],
            "layoutOnly": ["old line"],
        }
        newer = {
            "status": "ok",
            "heading": "2026-09-08 16:20:00Z Change Log (v28.apex -> v29.apex)",
            "previousFilename": "v28.apex",
            "currentFilename": "v29.apex",
            "uploadedAtUtc": "2026-09-08T16:20:00Z",
            "testable": [],
            "layoutOnly": ["new line"],
        }
        repo.append_project_changelog(projectId=project.projectId, changelog=older)
        second = repo.record_upload(
            projectId=project.projectId,
            uploadId="up-new",
            originalFilename="v29.apex",
            storagePath="/tmp/v29.apex",
        )
        repo.set_upload_changelog(uploadId=second.uploadId, changelog=newer)
        repo.append_project_changelog(projectId=project.projectId, changelog=newer)
        repo.set_project_active_upload(projectId=project.projectId, uploadId=second.uploadId)
        repo.prune_project_upload_retention(
            projectId=project.projectId,
            activeUploadId=second.uploadId,
            activeStoragePath=second.storagePath,
        )
        self.assertEqual(len(repo.list_uploads_for_project(projectId=project.projectId)), 1)
        history = repo.list_project_changelogs(projectId=project.projectId)
        self.assertEqual([item["currentFilename"] for item in history], ["v29.apex", "v28.apex"])
        payload = active_upload_payload(repo=repo, projectId=project.projectId)
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(len(payload["changelogHistory"]), 2)
        self.assertEqual(payload["changelogHistory"][0]["heading"], newer["heading"])

    def test_persist_helper_seeds_existing_upload_changelog_into_history(self):
        from sentinel.server.api import commissioning as commissioning_api
        from sentinel.server.services.commissioning_user import COMMISSIONING_STUB_USER_ID
        from sentinel.server.services.repositories import InMemoryRepository

        repo = InMemoryRepository()
        client = repo.create_client(userId=COMMISSIONING_STUB_USER_ID, name="Seed Client")
        project = repo.create_project(
            userId=COMMISSIONING_STUB_USER_ID, clientId=client.clientId, name="Seed Job"
        )
        old = repo.record_upload(
            projectId=project.projectId,
            uploadId="up-old",
            originalFilename="v28.apex",
            storagePath="/tmp/v28.apex",
        )
        repo.set_project_active_upload(projectId=project.projectId, uploadId=old.uploadId)
        repo.set_upload_changelog(
            uploadId=old.uploadId,
            changelog={
                "status": "ok",
                "heading": "Change Log (v27.apex -> v28.apex)",
                "previousFilename": "v27.apex",
                "currentFilename": "v28.apex",
                "testable": [],
                "layoutOnly": ["seeded"],
            },
        )
        new = repo.record_upload(
            projectId=project.projectId,
            uploadId="up-new",
            originalFilename="v29.apex",
            storagePath="/tmp/v29.apex",
        )
        commissioning_api._persist_generation_changelog(
            repo,
            projectId=project.projectId,
            uploadId=new.uploadId,
            generation={
                "changelog": {
                    "status": "ok",
                    "previousFilename": "v28.apex",
                    "currentFilename": "v29.apex",
                    "testable": [],
                    "layoutOnly": ["fresh"],
                }
            },
        )
        history = repo.list_project_changelogs(projectId=project.projectId)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["currentFilename"], "v29.apex")
        self.assertEqual(history[1]["currentFilename"], "v28.apex")
        self.assertIn("Change Log (v27.apex -> v28.apex)", history[1]["heading"])


if __name__ == "__main__":
    unittest.main()
