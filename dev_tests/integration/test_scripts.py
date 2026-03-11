import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXTRACT = ROOT / "src" / "sentinel" / "extraction" / "extract_project_data.py"
GENERATE = ROOT / "src" / "sentinel" / "generation" / "generate_html.py"


def create_test_apex(path: Path) -> None:
    con = sqlite3.connect(path)
    cur = con.cursor()

    cur.executescript(
        """
        create table Devices (DeviceId integer primary key, RoomId integer, DisplayOrder integer, ControlType integer, Name text, Manufacturer text, Type text, Model text, Comment text, HasCompositeController integer, SourceType integer, DisplayName text);
        create table RTIDeviceData (RTIAddress integer primary key, DeviceId integer, CloneRTIAddress integer, SupportedOrientations integer, ScreenPortraitWidth integer, ScreenPortraitHeight integer, ScreenLandscapeWidth integer, ScreenLandscapeHeight integer);
        create table RTIDevicePageData (PageId integer primary key, SourceDeviceId integer, PageNameId integer, RTIAddress integer, PageOrder integer);
        create table PageNames (PageNameId integer primary key, PageName text);
        create table Layers (LayerId integer primary key, PageId integer, SourceId integer, SharedLayerId integer, LayerOrder integer, IsVisible integer, VisibilityVariable text, IsLocked integer, ViewPortButtonId integer, RoomId integer);
        create table RTIDeviceButtonData (ButtonId integer primary key, SharedLayerId integer, ButtonOrder integer, ButtonTagId integer, FrameNumber integer, ButtonTop integer, ButtonLeft integer, ButtonHeight integer, ButtonWidth integer, Text text, TextSize integer, ButtonStyle integer, VisibleOrientations integer, ViewPortVerticalScroll integer);
        create table ButtonTagNames (ButtonTagId integer primary key, ButtonTagName text);
        create table Variables (VariableId integer primary key, RoomId integer, DeviceId integer, ButtonTagId integer, ButtonText text, ObjectData text, ReversedData text, InactiveData text, VisibleData text);
        create table ButtonTextTags (ButtonTextTagId integer primary key, ButtonId integer, ButtonTagId integer);
        create table Rooms (RoomId integer primary key, Name text, HomePageId integer, RoomOrder integer);
        create table Macros (MacroId integer primary key, SystemMacroId integer, RoomId integer, DeviceId integer, ButtonTagId integer, OutputType integer);
        create table MacroSteps (MacroStepId integer primary key, MacroId integer, StepIndex integer, Type integer, Level integer, InElseSection integer);
        create table PageLinks (PageLinkId integer primary key, DeviceId integer, ButtonTagId integer, LinkType integer, PageId integer);
        create table Events (EventId integer primary key, EventType integer, MacroId integer, Description text, Enabled integer, DriverId integer, DriverExtraString text);
        create table DriverData (DriverDeviceId integer primary key, DeviceId integer, Enabled integer, DriverId text, SystemFunctions text);
        """
    )

    cur.execute("insert into Devices values (1,0,1,5,'IST-5','','','','',0,0,'IST-5 (Global)')")
    cur.execute("insert into RTIDeviceData values (1,1,0,1,480,854,0,0)")
    cur.execute("insert into PageNames values (10,'Lights')")
    cur.execute("insert into Rooms values (0,'Global',0,0)")
    cur.execute("insert into RTIDevicePageData values (100,1,10,1,0)")
    cur.execute("insert into Layers values (200,100,1,300,0,1,'',0,null,0)")

    cur.execute("insert into ButtonTagNames values (114,'LIGHTS - Load 2 Level')")
    cur.execute("insert into ButtonTagNames values (129,'LIGHTS - Load 2 TOGGLE')")

    cur.execute("insert into RTIDeviceButtonData values (246,300,0,114,0,140,30,46,284,'',10,9,1,0)")
    cur.execute("insert into RTIDeviceButtonData values (247,300,1,129,0,140,334,46,76,'',10,7,1,0)")

    cur.execute("insert into Variables values (1,0,-1,114,'$%VARIABLE!x@DDL002%$','token@DDL002',null,null,null)")
    cur.execute("insert into Variables values (2,0,-1,129,null,'token@DDS002',null,null,null)")

    cur.execute("insert into Macros values (362,362,0,-1,129,0)")
    cur.execute("insert into MacroSteps values (1,362,0,1,0,0)")
    cur.execute("insert into Events values (1,1,362,'Sense Test',1,null,null)")
    cur.execute("insert into Events values (2,5,362,'Driver Test',1,99,'fallback')")
    cur.execute("insert into DriverData values (99,1,1,'Driver Name','SwitchCmd:Switch;DimmerCmd:SetLevel')")

    con.commit()
    con.close()


def expected_render_coords_for_page(page: dict) -> tuple[list[str], list[str]]:
    button_styles = []
    viewport_styles = []
    for cat in ("screenLabels", "screenButtons", "hardButtons"):
        for b in page.get("buttonCategories", {}).get(cat, []):
            c = b["buttonUI"]["coordinates"]
            button_styles.append(
                f"left:{int(c['left'])}px;top:{int(c['top'])}px;width:{int(c['width'])}px;height:{int(c['height'])}px"
            )
    for vp in page.get("viewports", []):
        vc = vp["viewportUI"]["coordinates"]
        viewport_styles.append(
            f"left:{int(vc['left'])}px;top:{int(vc['top'])}px;width:{int(vc['width'])}px;height:{int(vc['height'])}px"
        )
        frames = sorted(vp.get("frames", []), key=lambda x: int(x.get("frameId", 0)))
        if not frames:
            continue
        frame0 = frames[0]
        for cat in ("screenLabels", "screenButtons", "hardButtons"):
            for b in frame0.get("buttonCategories", {}).get(cat, []):
                c = b["buttonUI"]["coordinates"]
                left = int(vc["left"]) + int(c["left"])
                top = int(vc["top"]) + int(c["top"])
                button_styles.append(
                    f"left:{left}px;top:{top}px;width:{int(c['width'])}px;height:{int(c['height'])}px"
                )
    return button_styles, viewport_styles


def expected_all_button_styles_for_page(page: dict) -> list[str]:
    def is_ui_only(b: dict) -> bool:
        i = b.get("buttonIdentity", {})
        t = b.get("testTargets", {})
        v = t.get("variables", {})
        has_vars = any(bool(v.get(k)) for k in ("Text", "Reversed", "Inactive", "Visible", "Value", "State", "Command"))
        return (
            not str(i.get("buttonTagName") or "").strip()
            and not str(i.get("text") or "").strip()
            and not bool(t.get("text"))
            and not bool(t.get("macro"))
            and not bool(t.get("pageLink"))
            and not has_vars
        )

    styles: list[str] = []
    for cat in ("screenLabels", "screenButtons", "hardButtons"):
        for b in page.get("buttonCategories", {}).get(cat, []):
            if is_ui_only(b):
                continue
            c = b["buttonUI"]["coordinates"]
            styles.append(
                f"left:{int(c['left'])}px;top:{int(c['top'])}px;width:{int(c['width'])}px;height:{int(c['height'])}px"
            )
    for vp in page.get("viewports", []):
        vc = vp["viewportUI"]["coordinates"]
        for frame in vp.get("frames", []):
            for cat in ("screenLabels", "screenButtons", "hardButtons"):
                for b in frame.get("buttonCategories", {}).get(cat, []):
                    if is_ui_only(b):
                        continue
                    c = b["buttonUI"]["coordinates"]
                    styles.append(
                        f"left:{int(vc['left']) + int(c['left'])}px;top:{int(vc['top']) + int(c['top'])}px;width:{int(c['width'])}px;height:{int(c['height'])}px"
                    )
    return styles


class ScriptContractsTest(unittest.TestCase):
    def test_extract_creates_project_data_json(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            apex = td_path / "sample.apex"
            schema = td_path / "project_structure.json"
            schema.write_text("{}", encoding="utf-8")
            create_test_apex(apex)

            cmd = [
                sys.executable,
                str(EXTRACT),
                "--apex",
                str(apex),
                "--project-structure",
                str(schema),
                "--out-dir",
                str(td_path),
            ]
            run = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, msg=run.stderr + run.stdout)

            out_file = td_path / "sample_project_data.json"
            self.assertTrue(out_file.exists())
            data = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(data["devices"][0]["userFacing"]["pages"]), 1)

            slider = data["devices"][0]["userFacing"]["pages"][0]["buttonCategories"]["screenButtons"][0]
            self.assertTrue(slider["testTargets"]["variables"]["Value"])
            self.assertFalse(slider["testTargets"]["variables"]["State"])
            self.assertTrue(slider["testTargets"]["variables"]["Command"])

    def test_generate_creates_html(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            project_data = {
                "devices": [
                    {
                        "userFacing": {
                            "displayName": "IST-5 (Global)",
                            "deviceUI": {
                                "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                                "landscape": {"supported": False, "resolution": {"width": 854, "height": 480}},
                            },
                            "pages": [
                                {
                                    "pageName": "Lights",
                                    "buttonCategories": {
                                        "screenLabels": [],
                                        "screenButtons": [
                                            {
                                                "buttonIdentity": {"buttonTagName": "X", "text": "Btn", "buttonType": "Slider"},
                                                "buttonUI": {"fontSize": 10, "coordinates": {"top": 10, "left": 10, "height": 40, "width": 100}},
                                                "testTargets": {
                                                    "text": True,
                                                    "macro": False,
                                                    "variables": {"Text": False, "Reversed": False, "Inactive": False, "Visible": False, "Value": True, "State": False, "Command": True},
                                                    "pageLink": False,
                                                },
                                            }
                                        ],
                                        "hardButtons": [],
                                    },
                                    "viewports": [],
                                }
                            ],
                        },
                        "diagnostics": {"deviceId": 1, "pages": []},
                    }
                ]
            }
            app_ui = {
                "header": {"enabled": True, "titleTemplate": "{deviceName} - {pageName}"},
                "buttonPresentation": {"fallbackFontSize": 10},
                "testingPopup": {"enabled": True, "titleTemplate": "{category} Test - {identity}", "includeButtonTypeInTitle": True, "variableLabelTemplate": "Variable - {variableType}"},
                "viewportNavigation": {"enabled": False},
            }
            project_path = td_path / "sample_project_data.json"
            ui_path = td_path / "app_ui_structure.json"
            project_path.write_text(json.dumps(project_data), encoding="utf-8")
            ui_path.write_text(json.dumps(app_ui), encoding="utf-8")

            cmd = [
                sys.executable,
                str(GENERATE),
                "--project-data",
                str(project_path),
                "--app-ui",
                str(ui_path),
                "--out-dir",
                str(td_path),
            ]
            run = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, msg=run.stderr + run.stdout)

            html_file = td_path / "sample_project_data__page-0-lights.html"
            self.assertTrue(html_file.exists())
            html = html_file.read_text(encoding="utf-8")
            self.assertIn("IST-5 (Global) - Lights", html)
            self.assertIn("Variable - Value", html)
            self.assertIn(">Btn</button>", html)

    def test_generate_renders_viewport_default_frame_buttons(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            project_data = {
                "devices": [
                    {
                        "userFacing": {
                            "displayName": "IST-5 (Global)",
                            "deviceUI": {
                                "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                                "landscape": {"supported": False, "resolution": {"width": 854, "height": 480}},
                            },
                            "pages": [
                                {
                                    "pageName": "Lights",
                                    "buttonCategories": {"screenLabels": [], "screenButtons": [], "hardButtons": []},
                                    "viewports": [
                                        {
                                            "viewportIdentity": {"viewportButtonId": 2},
                                            "viewportUI": {"coordinates": {"top": 60, "left": 20, "height": 694, "width": 440}},
                                            "frames": [
                                                {
                                                    "frameId": 0,
                                                    "buttonCategories": {
                                                        "screenLabels": [],
                                                        "screenButtons": [
                                                            {
                                                                "buttonIdentity": {"buttonTagName": "LIGHTS - Load 2 TOGGLE", "text": "", "buttonType": "Toggle"},
                                                                "buttonUI": {"fontSize": 10, "coordinates": {"top": 140, "left": 334, "height": 46, "width": 76}},
                                                                "testTargets": {
                                                                    "text": False,
                                                                    "macro": True,
                                                                    "variables": {"Text": False, "Reversed": False, "Inactive": False, "Visible": False, "Value": False, "State": True, "Command": False},
                                                                    "pageLink": False,
                                                                },
                                                            }
                                                        ],
                                                        "hardButtons": [],
                                                    },
                                                }
                                            ],
                                        }
                                    ],
                                }
                            ],
                        },
                        "diagnostics": {"deviceId": 1, "pages": []},
                    }
                ]
            }
            app_ui = {
                "header": {"enabled": True, "titleTemplate": "{deviceName} - {pageName}"},
                "buttonPresentation": {"fallbackFontSize": 10},
                "testingPopup": {"enabled": True, "titleTemplate": "{category} Test - {identity}", "includeButtonTypeInTitle": True, "variableLabelTemplate": "Variable - {variableType}"},
                "viewportNavigation": {"enabled": False},
            }
            project_path = td_path / "sample_project_data.json"
            ui_path = td_path / "app_ui_structure.json"
            project_path.write_text(json.dumps(project_data), encoding="utf-8")
            ui_path.write_text(json.dumps(app_ui), encoding="utf-8")

            cmd = [sys.executable, str(GENERATE), "--project-data", str(project_path), "--app-ui", str(ui_path), "--out-dir", str(td_path)]
            run = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, msg=run.stderr + run.stdout)

            html = (td_path / "sample_project_data__page-0-lights.html").read_text(encoding="utf-8")
            self.assertIn("LIGHTS - Load 2 TOGGLE", html)
            self.assertIn("left:354px;top:200px", html)

    def test_generate_renders_all_json_driven_ui_elements_at_coordinates(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            page = {
                "pageName": "Lights",
                "buttonCategories": {
                    "screenLabels": [
                        {
                            "buttonIdentity": {"buttonTagName": None, "text": "Lights", "buttonType": None},
                            "buttonUI": {"fontSize": 16, "coordinates": {"top": 0, "left": 0, "height": 60, "width": 480}},
                            "testTargets": {"text": True, "macro": False, "variables": {"Text": False, "Reversed": False, "Inactive": False, "Visible": False, "Value": False, "State": False, "Command": False}, "pageLink": False},
                        }
                    ],
                    "screenButtons": [
                        {
                            "buttonIdentity": {"buttonTagName": "NAV - Home", "text": "", "buttonType": None},
                            "buttonUI": {"fontSize": 10, "coordinates": {"top": 754, "left": 20, "height": 100, "width": 440}},
                            "testTargets": {"text": False, "macro": False, "variables": {"Text": False, "Reversed": False, "Inactive": False, "Visible": False, "Value": False, "State": False, "Command": False}, "pageLink": True},
                        }
                    ],
                    "hardButtons": [],
                },
                "viewports": [
                    {
                        "viewportIdentity": {"viewportButtonId": 105},
                        "viewportUI": {"coordinates": {"top": 60, "left": 20, "height": 694, "width": 440}},
                        "frames": [
                            {
                                "frameId": 0,
                                "buttonCategories": {
                                    "screenLabels": [],
                                    "screenButtons": [
                                        {
                                            "buttonIdentity": {"buttonTagName": "LIGHTS - Load 2 TOGGLE", "text": "", "buttonType": "Toggle"},
                                            "buttonUI": {"fontSize": 10, "coordinates": {"top": 140, "left": 334, "height": 46, "width": 76}},
                                            "testTargets": {"text": False, "macro": True, "variables": {"Text": False, "Reversed": False, "Inactive": False, "Visible": False, "Value": False, "State": True, "Command": False}, "pageLink": False},
                                        }
                                    ],
                                    "hardButtons": [],
                                },
                            }
                        ],
                    }
                ],
            }
            project_data = {
                "devices": [
                    {
                        "userFacing": {
                            "displayName": "IST-5 (Global)",
                            "deviceUI": {
                                "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                                "landscape": {"supported": False, "resolution": {"width": 854, "height": 480}},
                            },
                            "pages": [page],
                        },
                        "diagnostics": {"deviceId": 1, "pages": []},
                    }
                ]
            }
            app_ui = {
                "header": {"enabled": True, "titleTemplate": "{deviceName} - {pageName}"},
                "buttonPresentation": {"fallbackFontSize": 10},
                "testingPopup": {"enabled": True, "titleTemplate": "{category} Test - {identity}", "includeButtonTypeInTitle": True, "variableLabelTemplate": "Variable - {variableType}"},
                "viewportNavigation": {"enabled": False},
            }
            project_path = td_path / "sample_project_data.json"
            ui_path = td_path / "app_ui_structure.json"
            project_path.write_text(json.dumps(project_data), encoding="utf-8")
            ui_path.write_text(json.dumps(app_ui), encoding="utf-8")

            run = subprocess.run([sys.executable, str(GENERATE), "--project-data", str(project_path), "--app-ui", str(ui_path), "--out-dir", str(td_path)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, msg=run.stderr + run.stdout)
            html = (td_path / "sample_project_data__page-0-lights.html").read_text(encoding="utf-8")

            expected_buttons, expected_viewports = expected_render_coords_for_page(page)
            for style in expected_buttons:
                self.assertIn(style, html)
            for style in expected_viewports:
                self.assertIn(style, html)

            self.assertEqual(html.count("class='btn"), len(expected_buttons))
            self.assertEqual(html.count("class='vp-box'"), len(expected_viewports))

    def test_real_carlos_lights_all_buttons_exact_coordinates(self):
        root = ROOT
        project_path = root / "archives" / "generated-samples" / "Carlos OBryans v6.3.1 (tag cleanup)_project_data.json"
        html_path = root / "archives" / "generated-samples" / "Carlos OBryans v6.3.1 (tag cleanup)_project_data__page-2-lights.html"
        if not project_path.exists() or not html_path.exists():
            self.skipTest("Real Carlos generated files not present")

        data = json.loads(project_path.read_text(encoding="utf-8"))
        page = data["devices"][0]["userFacing"]["pages"][2]
        html = html_path.read_text(encoding="utf-8")

        expected_styles = expected_all_button_styles_for_page(page)
        for style in expected_styles:
            self.assertIn(style, html)


if __name__ == "__main__":
    unittest.main()
