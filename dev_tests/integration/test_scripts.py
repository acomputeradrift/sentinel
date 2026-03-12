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


def sample_app_ui() -> dict:
    return {
        "appUiStructureVersion": "1.0.0",
        "layout": {
            "appCanvas": {"mode": "browser-viewport"},
            "appUIControls": {"top": 90, "bottom": 32, "left": 300, "right": 300},
            "rtiCanvas": {"deriveFromAppCanvas": True},
            "rtiDeviceCanvas": {
                "fitMode": "contain",
                "allowScaleAboveOne": True,
                "maxScale": 10,
                "minScale": 0.25,
                "centerWithinRtiCanvas": True,
            },
        },
        "uiHierarchy": {
            "appCanvas": ["appUIControls", "rtiCanvas"],
            "rtiCanvas": ["rtiDeviceCanvas"],
            "rtiDeviceUI": ["projectButtons", "projectViewports"],
            "appUIControls": ["header", "appNavigation", "viewportNavigation"],
            "rtiDeviceCanvas": ["rtiDeviceUI"],
        },
        "header": {"enabled": True, "titleTemplate": "{deviceName} - {pageName}", "placement": "top"},
        "appNavigation": {
            "enabled": True,
            "placement": "canvas-adjacent",
            "showPageControls": True,
            "pageLinks": {
                "enabled": True,
                "showLinkAffordanceOnHover": True,
                "iconPlacement": "right-center-inside-button",
                "iconStyle": "inline-svg",
                "iconSize": 16,
                "iconPaddingRight": 8,
                "hoverActivationArea": {"width": 28, "fullButtonHeight": True},
            },
        },
        "viewportNavigation": {
            "enabled": False,
            "placement": {"previous": "canvas-left-center", "next": "canvas-right-center", "frameIndicator": "canvas-bottom-center"},
            "indicatorStyle": "dots",
            "labels": {"previous": "Prev", "next": "Next"},
            "behavior": {"wrapFrames": False},
        },
        "testingPopup": {
            "enabled": True,
            "titleTemplate": "{category} Test - {identity}",
            "includeButtonTypeInTitle": True,
            "showIdentity": True,
            "variableLabelTemplate": "Variable - {variableType}",
            "targetGroupStyle": "single-group-per-target",
            "showOnlyTrueTargets": True,
            "failNoteRequiredOnFail": True,
        },
        "buttonPresentation": {"useProjectFontSize": True, "fallbackFontSize": 10, "preserveRtiCoordinates": True, "scaleRtiDerivedFontSizes": True},
        "viewportPresentation": {"showViewportContainer": True, "renderViewportButtonsByDefault": False, "initialFrameStrategy": "defaultFrameId"},
        "state": {"persistTestResults": True, "persistViewportFrameSelection": True},
    }


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
    cur.execute("insert into PageNames values (11,'Home')")
    cur.execute("insert into Rooms values (0,'Global',0,0)")
    cur.execute("insert into RTIDevicePageData values (100,1,10,1,0)")
    cur.execute("insert into RTIDevicePageData values (101,1,11,1,1)")
    cur.execute("insert into Layers values (200,100,1,300,0,1,'',0,null,0)")
    cur.execute("insert into Layers values (201,101,1,301,0,1,'',0,null,0)")

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
    cur.execute("insert into PageLinks values (1,1,129,0,101)")

    con.commit()
    con.close()


class ScriptContractsTest(unittest.TestCase):
    def test_extract_creates_project_data_json(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            apex = td_path / "sample.apex"
            schema = td_path / "project_structure.json"
            schema.write_text("{}", encoding="utf-8")
            create_test_apex(apex)

            run = subprocess.run(
                [sys.executable, str(EXTRACT), "--apex", str(apex), "--project-structure", str(schema), "--out-dir", str(td_path)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(run.returncode, 0, msg=run.stderr + run.stdout)

            data = json.loads((td_path / "sample_project_data.json").read_text(encoding="utf-8"))
            slider = data["devices"][0]["userFacing"]["pages"][0]["buttonCategories"]["screenButtons"][0]
            toggle = data["devices"][0]["userFacing"]["pages"][0]["buttonCategories"]["screenButtons"][1]
            self.assertTrue(slider["testTargets"]["variables"]["Value"])
            self.assertFalse(slider["testTargets"]["variables"]["State"])
            self.assertTrue(slider["testTargets"]["variables"]["Command"])
            self.assertEqual(slider["testTargets"]["pageLink"], {"enabled": False, "targetPageId": None})
            self.assertEqual(toggle["testTargets"]["pageLink"], {"enabled": True, "targetPageId": 101})

    def test_generate_writes_html(self):
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
                                                    "pageLink": {"enabled": False, "targetPageId": None},
                                                },
                                            }
                                        ],
                                        "hardButtons": [],
                                    },
                                    "viewports": [],
                                }
                            ],
                        },
                        "diagnostics": {"deviceId": 1, "pages": [{"pageId": 100, "pageName": "Lights"}]},
                    }
                ]
            }
            project_path = td_path / "sample_project_data.json"
            ui_path = td_path / "app_ui_structure.json"
            project_path.write_text(json.dumps(project_data), encoding="utf-8")
            ui_path.write_text(json.dumps(sample_app_ui()), encoding="utf-8")

            run = subprocess.run([sys.executable, str(GENERATE), "--project-data", str(project_path), "--app-ui", str(ui_path), "--out-dir", str(td_path)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, msg=run.stderr + run.stdout)

            html = (td_path / "sample_project_data__page-0-lights.html").read_text(encoding="utf-8")
            self.assertIn("IST-5 (Global) - Lights", html)
            self.assertIn("Variable - Value", html)
            self.assertIn(">Btn</button>", html)
            self.assertIn("const APP_UI_CONTROLS=", html)
            self.assertIn("const RTI_DEVICE_LAYOUT=", html)
            self.assertIn("const widthScale=rtiCanvasWidth/SOURCE_DEVICE_SIZE.width;", html)
            self.assertIn("const heightScale=rtiCanvasHeight/SOURCE_DEVICE_SIZE.height;", html)
            self.assertIn("let scale=Math.min(widthScale,heightScale);", html)
            self.assertIn("id='rtiCanvas'", html)
            self.assertIn("id='rtiDeviceCanvas'", html)
            self.assertIn("leftControls.style.width", html)
            self.assertIn("rightControls.style.width", html)

    def test_generate_writes_all_pages_when_page_index_not_given(self):
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
                                {"pageName": "Home", "buttonCategories": {"screenLabels": [], "screenButtons": [], "hardButtons": []}, "viewports": []},
                                {"pageName": "Lights", "buttonCategories": {"screenLabels": [], "screenButtons": [], "hardButtons": []}, "viewports": []},
                            ],
                        },
                        "diagnostics": {"deviceId": 1, "pages": [{"pageId": 101, "pageName": "Home"}, {"pageId": 100, "pageName": "Lights"}]},
                    }
                ]
            }
            project_path = td_path / "sample_project_data.json"
            ui_path = td_path / "app_ui_structure.json"
            project_path.write_text(json.dumps(project_data), encoding="utf-8")
            ui_path.write_text(json.dumps(sample_app_ui()), encoding="utf-8")

            run = subprocess.run([sys.executable, str(GENERATE), "--project-data", str(project_path), "--app-ui", str(ui_path), "--out-dir", str(td_path)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, msg=run.stderr + run.stdout)
            self.assertTrue((td_path / "sample_project_data__page-0-home.html").exists())
            self.assertTrue((td_path / "sample_project_data__page-1-lights.html").exists())

    def test_generate_defaults_output_to_project_data_directory(self):
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
                                {"pageName": "Home", "buttonCategories": {"screenLabels": [], "screenButtons": [], "hardButtons": []}, "viewports": []}
                            ],
                        },
                        "diagnostics": {"deviceId": 1, "pages": [{"pageId": 101, "pageName": "Home"}]},
                    }
                ]
            }
            project_path = td_path / "sample_project_data.json"
            ui_path = td_path / "app_ui_structure.json"
            project_path.write_text(json.dumps(project_data), encoding="utf-8")
            ui_path.write_text(json.dumps(sample_app_ui()), encoding="utf-8")

            run = subprocess.run([sys.executable, str(GENERATE), "--project-data", str(project_path), "--app-ui", str(ui_path)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, msg=run.stderr + run.stdout)
            self.assertTrue((td_path / "sample_project_data__page-0-home.html").exists())

    def test_generate_includes_page_link_overlay_and_target(self):
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
                                    "pageName": "Home",
                                    "buttonCategories": {
                                        "screenLabels": [],
                                        "screenButtons": [
                                            {
                                                "buttonIdentity": {"buttonTagName": "GO - Lights", "text": "Lights", "buttonType": None},
                                                "buttonUI": {"fontSize": 10, "coordinates": {"top": 20, "left": 20, "height": 40, "width": 120}},
                                                "testTargets": {
                                                    "text": True,
                                                    "macro": False,
                                                    "variables": {"Text": False, "Reversed": False, "Inactive": False, "Visible": False, "Value": False, "State": False, "Command": False},
                                                    "pageLink": {"enabled": True, "targetPageId": 200},
                                                },
                                            }
                                        ],
                                        "hardButtons": [],
                                    },
                                    "viewports": [],
                                },
                                {
                                    "pageName": "Lights",
                                    "buttonCategories": {"screenLabels": [], "screenButtons": [], "hardButtons": []},
                                    "viewports": [],
                                },
                            ],
                        },
                        "diagnostics": {"deviceId": 1, "pages": [{"pageId": 100, "pageName": "Home"}, {"pageId": 200, "pageName": "Lights"}]},
                    }
                ]
            }
            project_path = td_path / "sample_project_data.json"
            ui_path = td_path / "app_ui_structure.json"
            project_path.write_text(json.dumps(project_data), encoding="utf-8")
            ui_path.write_text(json.dumps(sample_app_ui()), encoding="utf-8")

            run = subprocess.run([sys.executable, str(GENERATE), "--project-data", str(project_path), "--app-ui", str(ui_path), "--out-dir", str(td_path), "--page-index", "0"], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, msg=run.stderr + run.stdout)
            html = (td_path / "sample_project_data__page-0-home.html").read_text(encoding="utf-8")
            self.assertIn("page-link-hit", html)
            self.assertIn("sample_project_data__page-1-lights.html", html)
            self.assertIn("PageLink", html)
            self.assertIn("test-btn", html)

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
                                                                    "pageLink": {"enabled": False, "targetPageId": None},
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
                        "diagnostics": {"deviceId": 1, "pages": [{"pageId": 100, "pageName": "Lights"}]},
                    }
                ]
            }
            project_path = td_path / "sample_project_data.json"
            ui_path = td_path / "app_ui_structure.json"
            project_path.write_text(json.dumps(project_data), encoding="utf-8")
            ui_path.write_text(json.dumps(sample_app_ui()), encoding="utf-8")

            run = subprocess.run([sys.executable, str(GENERATE), "--project-data", str(project_path), "--app-ui", str(ui_path), "--out-dir", str(td_path)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, msg=run.stderr + run.stdout)

            html = (td_path / "sample_project_data__page-0-lights.html").read_text(encoding="utf-8")
            self.assertIn("LIGHTS - Load 2 TOGGLE", html)
            self.assertIn("data-left='354'", html)
            self.assertIn("data-top='200'", html)


if __name__ == "__main__":
    unittest.main()
